"""
research/benchmark_runner.py
============================
Benchmark Runner độc lập.
Thực thi các thí nghiệm dựa trên cấu hình ma trận (YAML) và tập dữ liệu (JSON).
Hỗ trợ Smoke Test.
"""

import argparse
import time
import json
import os
import sys
from pathlib import Path

if sys.platform.startswith("win"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import get_config
from core.retrieval.hybrid_retriever import ingest_subject_documents
from core.pipeline.retrieval_pipeline import RetrievalPipeline
from research.utils.yaml_loader import load_benchmark_matrix, load_chunking_config
from research.utils.dataset_loader import load_active_dataset
from research.database.init_benchmark_db import get_benchmark_connection, init_benchmark_db
from research.evaluation.relevance import (
    V5_CONTAINMENT_THRESHOLD,
    best_ref_containment,
    evaluate_relevance,
    uses_containment_eval,
)
from research.evaluation.metrics import calculate_metrics


def _resolve_retrieval_version(dataset_version: str) -> str:
    if uses_containment_eval(dataset_version):
        return "v1-containment"
    return "v1"


def run_experiment(exp_name: str, exp_id: int, questions: list, dataset_version: str):
    """Thực thi một experiment (với một chunking strategy cố định)."""
    print(f"\n[{exp_name}] Bắt đầu thực thi (ID={exp_id}). Số câu hỏi: {len(questions)}")
    
    # 1. Nạp cấu hình chunking
    chunk_cfg = load_chunking_config(exp_name)
    
    # 2. Cập nhật cấu hình bộ nhớ để Ingestion dùng đúng
    global_cfg = get_config()
    ret_cfg = global_cfg["retrieval"]
    strategy = chunk_cfg["strategy"]
    ret_cfg["chunking_strategy"] = strategy
    
    # Xóa các tham số cũ để tránh rò rỉ cấu hình giữa các experiment
    for key in ["chunk_size", "chunk_overlap", "length_unit", "sentence_count", "overlap_sentences"]:
        ret_cfg.pop(key, None)

    # Ghi toàn bộ các key trong chunk_cfg vào ret_cfg để chunker load được
    for key, value in chunk_cfg.items():
        ret_cfg[key] = value
        
    # Dự phòng cho backward compatibility
    if "chunk_size" in chunk_cfg:
        size = chunk_cfg["chunk_size"]
        ret_cfg["chunk_size"] = size
        ret_cfg[f"{strategy}_chunk_size"] = size
    if "chunk_overlap" in chunk_cfg:
        overlap = chunk_cfg["chunk_overlap"]
        ret_cfg["chunk_overlap"] = overlap
        ret_cfg[f"{strategy}_chunk_overlap"] = overlap

    # 3. Tiến hành Re-Ingest tài liệu với cấu hình mới
    subject_id = f"dsa_{exp_name}"
    print(f"[{exp_name}] Chuẩn bị nạp tài liệu cho môn học '{subject_id}' với chiến lược {strategy}...")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(base_dir, "subjects", "dsa", "documents")
    
    # Kiểm tra xem cấu hình này đã được nạp tài liệu (ingest) trước đó chưa
    from core.retrieval.hybrid_retriever import _get_db_conn
    db_conn = _get_db_conn()
    already_ingested = False
    try:
        row = db_conn.execute(
            "SELECT COUNT(*) as cnt FROM parent_chunks WHERE subject_id = ?",
            (subject_id,)
        ).fetchone()
        already_ingested = row["cnt"] > 0 if row else False
    except Exception as e:
        print(f"[WARN] Lỗi kiểm tra cache ingestion: {e}")
    finally:
        db_conn.close()

    if already_ingested:
        print(f"[{exp_name}] [CACHE HIT] Cấu hình này đã được nạp tài liệu trước đó. Bỏ qua bước build index.")
        ingest_duration = 0.0
        
        # Lấy total_chunks từ cơ sở dữ liệu
        db_conn = _get_db_conn()
        try:
            row = db_conn.execute(
                "SELECT COUNT(*) as cnt FROM parent_chunks WHERE subject_id = ?",
                (subject_id,)
            ).fetchone()
            total_chunks = row["cnt"] if row else 0
        except Exception:
            total_chunks = 0
        finally:
            db_conn.close()
    else:
        start_ingest = time.time()
        # Ingestion sẽ xóa sạch data cũ và nạp mới
        total_chunks = ingest_subject_documents(subject_id, docs_dir)
        ingest_duration = time.time() - start_ingest
        print(f"[{exp_name}] Hoàn thành nạp tài liệu. Nạp được {total_chunks} chunks. Mất {ingest_duration:.2f}s")

    # 3.1. Tính toán thống kê chunk từ database
    db_conn = _get_db_conn()
    try:
        rows = db_conn.execute(
            "SELECT parent_text FROM parent_chunks WHERE subject_id = ?",
            (subject_id,)
        ).fetchall()
        parent_texts = [r["parent_text"] for r in rows]
    except Exception as e:
        print(f"[WARN] Lỗi khi lấy thống kê chunk từ database: {e}")
        parent_texts = []
    finally:
        db_conn.close()

    if parent_texts:
        sizes = [len(txt) for txt in parent_texts]
        avg_size = sum(sizes) / len(sizes)
        median_size = sorted(sizes)[len(sizes) // 2]
        min_size = min(sizes)
        max_size = max(sizes)
    else:
        avg_size, median_size, min_size, max_size = 0, 0, 0, 0

    print(f"[{exp_name}] Thống kê Chunk:")
    print(f"  - Tổng số chunk: {total_chunks}")
    print(f"  - Kích thước trung bình: {avg_size:.1f} ký tự")
    print(f"  - Kích thước trung vị: {median_size} ký tự")
    print(f"  - Kích thước Min/Max: {min_size}/{max_size} ký tự")

    # Lưu thống kê chunk vào bảng chunk_statistics
    db_conn = get_benchmark_connection()
    try:
        db_conn.execute("""
            INSERT OR REPLACE INTO chunk_statistics (
                experiment_id, total_chunks, avg_chunk_size, median_chunk_size, min_chunk_size, max_chunk_size, ingestion_time_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (exp_id, total_chunks, avg_size, median_size, min_size, max_size, ingest_duration))
        db_conn.commit()
    except Exception as e:
        print(f"[WARN] Lỗi khi lưu thống kê chunk vào database: {e}")
    finally:
        db_conn.close()
    
    # 4. Chạy các câu hỏi Benchmark
    containment_eval = uses_containment_eval(dataset_version)
    if containment_eval:
        print(
            f"[{exp_name}] Chế độ chấm: containment-only "
            f"(token recall >= {V5_CONTAINMENT_THRESHOLD}, không cosine)"
        )

    pipeline = RetrievalPipeline(
        subject_id=subject_id,
        top_k=5,
        use_crag=False,
    )
    
    conn = get_benchmark_connection()
    total_q = len(questions)
    
    sum_precision = 0.0
    sum_recall = 0.0
    sum_f1 = 0.0
    sum_hitrate = 0.0
    sum_mrr = 0.0
    sum_latency = 0.0
    
    for i, q in enumerate(questions, 1):
        question_id = q.get("id", f"Q{i}")
        query = q["question"]
        ref_contexts = q["reference_contexts"]
        
        # Gọi RetrievalPipeline
        result = pipeline.run(query)
        final_chunks = result["final_chunks"]
        latency = result["retrieval_latency"]
        
        # Đánh giá relevance
        relevant_flags = []
        containment_scores = []
        for chunk in final_chunks:
            chunk_text = chunk.get("text", "")
            coverage = best_ref_containment(ref_contexts, chunk_text)
            containment_scores.append(coverage)
            if containment_eval:
                is_rel = coverage >= V5_CONTAINMENT_THRESHOLD
            else:
                is_rel = evaluate_relevance(ref_contexts, chunk_text)
            relevant_flags.append(is_rel)

        ref_coverage = max(containment_scores) if containment_scores else 0.0
        full_hit = 1.0 if ref_coverage >= V5_CONTAINMENT_THRESHOLD else 0.0
            
        # Tính toán metric
        metrics = calculate_metrics(relevant_flags, k=5)
        
        # Ghi vào db table question_results
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO question_results (
                experiment_id, question_id, hit_rate, mrr, retrieval_latency,
                ref_coverage, full_hit
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            exp_id, question_id, metrics["hit_rate_at_k"], metrics["mrr"], latency,
            ref_coverage, full_hit,
        ))
        conn.commit()
        
        # Cộng dồn
        sum_precision += metrics["precision_at_k"]
        sum_recall += metrics["recall_at_k"]
        sum_f1 += metrics["f1_at_k"]
        sum_hitrate += metrics["hit_rate_at_k"]
        sum_mrr += metrics["mrr"]
        sum_latency += latency
        
        print(f"  [{i}/{total_q}] {question_id} - MRR: {metrics['mrr']:.2f} - Latency: {latency:.1f}ms")
        
    # Tính trung bình (Mean)
    mean_precision = sum_precision / total_q
    mean_recall = sum_recall / total_q
    mean_f1 = sum_f1 / total_q
    mean_hitrate = sum_hitrate / total_q
    mean_mrr = sum_mrr / total_q
    mean_latency = sum_latency / total_q
    
    # Ghi vào benchmark_results
    cur.execute("""
        INSERT INTO benchmark_results (
            experiment_id, total_questions, precision_at_5, recall_at_5, f1_at_5, hit_rate_at_5, mrr, retrieval_latency
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (exp_id, total_q, mean_precision, mean_recall, mean_f1, mean_hitrate, mean_mrr, mean_latency))
    
    # Cập nhật status
    cur.execute("UPDATE experiments SET status = 'completed' WHERE experiment_id = ?", (exp_id,))
    conn.commit()
    conn.close()
    
    print(f"[{exp_name}] Hoàn thành. MRR: {mean_mrr:.4f}, HitRate: {mean_hitrate:.4f}, Latency: {mean_latency:.1f}ms\n")

def print_summary_table():
    """Truy vấn kết quả và in ra bảng markdown cập nhật từ benchmark_logs.db."""
    import sys
    conn = get_benchmark_connection()
    cur = conn.cursor()
    
    # Query all experiments and their results/stats
    cur.execute("""
        SELECT 
            e.experiment_id,
            e.config_name,
            e.status,
            s.total_chunks,
            s.ingestion_time_seconds,
            r.hit_rate_at_5,
            r.mrr,
            r.retrieval_latency
        FROM experiments e
        LEFT JOIN chunk_statistics s ON e.experiment_id = s.experiment_id
        LEFT JOIN benchmark_results r ON e.experiment_id = r.experiment_id
        ORDER BY e.experiment_id ASC
    """)
    rows = cur.fetchall()
    conn.close()
    
    print("\n" + "="*40 + " BẢNG KẾT QUẢ CHI TIẾT CẬP NHẬT TỪ BENCHMARK_LOGS.DB " + "="*40)
    print(f"| {'ID':<3} | {'Cấu hình':<25} | {'Trạng thái':<10} | {'Số chunks':<9} | {'Build (s)':<9} | {'HR@5':<6} | {'MRR':<6} | {'Latency (ms)':<12} |")
    print(f"|{'-'*5}|{'-'*27}|{'-'*12}|{'-'*11}|{'-'*11}|{'-'*8}|{'-'*8}|{'-'*14}|")
    for r in rows:
        eid = r["experiment_id"]
        cfg_name = r["config_name"]
        status = r["status"]
        
        total_chunks = r["total_chunks"] if r["total_chunks"] is not None else "-"
        ingest_time = f"{r['ingestion_time_seconds']:.1f}" if r["ingestion_time_seconds"] is not None else "-"
        hr = f"{r['hit_rate_at_5']:.4f}" if r["hit_rate_at_5"] is not None else "-"
        mrr = f"{r['mrr']:.4f}" if r["mrr"] is not None else "-"
        latency = f"{r['retrieval_latency']:.1f}" if r["retrieval_latency"] is not None else "-"
        
        print(f"| {eid:<3} | {cfg_name:<25} | {status:<10} | {total_chunks:<9} | {ingest_time:<9} | {hr:<6} | {mrr:<6} | {latency:<12} |")
    print("="*134 + "\n")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="Benchmark Runner")
    parser.add_argument("--smoke-test", action="store_true", help="Chạy Smoke Test với 5 câu và max 2 cấu hình.")
    args = parser.parse_args()

    print("=== Khởi tạo Benchmark Runner ===")
    init_benchmark_db()
    
    try:
        matrix = load_benchmark_matrix()
    except Exception as e:
        print(f"Lỗi tải benchmark matrix: {e}")
        return

    try:
        questions, ds_version = load_active_dataset()
    except Exception as e:
        print(f"Lỗi tải dataset: {e}")
        return
        
    print(f"Đã nạp Benchmark Matrix gồm {len(matrix)} cấu hình.")
    print(f"Đã nạp Dataset {ds_version} gồm {len(questions)} câu hỏi.")
    if uses_containment_eval(ds_version):
        print(
            f"Dataset v5 → chấm containment-only (token recall >= {V5_CONTAINMENT_THRESHOLD}), "
            "retrieval_version=v1-containment"
        )

    if args.smoke_test:
        print("\n>>> CHẾ ĐỘ SMOKE TEST <<<")
        matrix = matrix[:10]      # Max 10 config
        questions = questions[:2] # Max 2 câu
        print(f"Giới hạn: {len(matrix)} cấu hình, {len(questions)} câu hỏi.")
        
    # Đồng bộ với Database (experiments table)
    conn = get_benchmark_connection()
    cur = conn.cursor()
    
    retrieval_version = _resolve_retrieval_version(ds_version)
    
    experiments_to_run = []
    
    for exp_name in matrix:
        chunk_cfg = load_chunking_config(exp_name)
        cfg_json = json.dumps(chunk_cfg)
        
        # Check if exists
        cur.execute("""
            SELECT experiment_id, status FROM experiments 
            WHERE config_name = ? AND dataset_version = ? AND retrieval_version = ?
        """, (exp_name, ds_version, retrieval_version))
        row = cur.fetchone()
        
        if row:
            exp_id = row["experiment_id"]
            status = row["status"]
            if status == "completed":
                print(f"[SKIP] {exp_name} đã completed.")
            elif status in ("pending", "failed"):
                cur.execute("UPDATE experiments SET status = 'pending' WHERE experiment_id = ?", (exp_id,))
                conn.commit()
                experiments_to_run.append((exp_name, exp_id))
            elif status == "running":
                # Kịch bản crash giữa chừng, coi như failed và cho phép resume
                cur.execute("UPDATE experiments SET status = 'pending' WHERE experiment_id = ?", (exp_id,))
                conn.commit()
                experiments_to_run.append((exp_name, exp_id))
        else:
            cur.execute("""
                INSERT INTO experiments (config_name, chunking_config, dataset_version, retrieval_version, status)
                VALUES (?, ?, ?, ?, 'pending')
            """, (exp_name, cfg_json, ds_version, retrieval_version))
            exp_id = cur.lastrowid
            conn.commit()
            experiments_to_run.append((exp_name, exp_id))
            
    conn.close()
    
    # In bảng trạng thái/kết quả hiện tại trước khi chạy
    try:
        print_summary_table()
    except Exception as e:
        print(f"[WARN] Không thể in bảng kết quả ban đầu: {e}")
    
    if not experiments_to_run:
        print("Tất cả các cấu hình đã được hoàn thành. Không có task nào cần chạy.")
        return
        
    for exp_name, exp_id in experiments_to_run:
        # Update running status
        conn = get_benchmark_connection()
        conn.execute("UPDATE experiments SET status = 'running' WHERE experiment_id = ?", (exp_id,))
        conn.commit()
        conn.close()
        
        try:
            run_experiment(exp_name, exp_id, questions, ds_version)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[{exp_name}] LỖI NGHIÊM TRỌNG: {e}")
            conn = get_benchmark_connection()
            conn.execute("UPDATE experiments SET status = 'failed' WHERE experiment_id = ?", (exp_id,))
            conn.commit()
            conn.close()
            
        # In bảng kết quả chi tiết cập nhật sau mỗi cấu hình
        try:
            print_summary_table()
        except Exception as table_err:
            print(f"[WARN] Lỗi in bảng kết quả sau cấu hình: {table_err}")
            
if __name__ == "__main__":
    main()
