import os
import sys
import time
from pathlib import Path

# Khắc phục lỗi UnicodeEncodeError trên terminal Windows
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from utils.config import get_config
from core.retrieval.hybrid_retriever import ingest_subject_documents, _get_db_conn
from research.utils.yaml_loader import load_benchmark_matrix, load_chunking_config

def main():
    print("=== TIẾN TRÌNH NẠP TÀI LIỆU (INGESTION ONLY) FOR BENCHMARK ===")
    
    # 1. Đường dẫn thư mục tài liệu gốc
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(base_dir, "subjects", "dsa", "documents")
    
    if not os.path.exists(docs_dir):
        print(f"[ERROR] Không tìm thấy thư mục tài liệu tại: {docs_dir}")
        return

    # 2. Tải ma trận 7 cấu hình
    try:
        matrix = load_benchmark_matrix()
    except Exception as e:
        print(f"Lỗi tải benchmark matrix: {e}")
        return

    print(f"Đã nhận diện {len(matrix)} cấu hình cần nạp dữ liệu.")
    
    # 3. Lặp qua từng cấu hình và nạp dữ liệu
    for exp_name in matrix:
        print("\n" + "="*80)
        print(f"CẤU HÌNH: {exp_name.upper()}")
        print("="*80)

        chunk_cfg = load_chunking_config(exp_name)
        
        # Thiết lập cấu hình tạm thời cho Ingest
        global_cfg = get_config()
        ret_cfg = global_cfg["retrieval"]
        strategy = chunk_cfg["strategy"]
        ret_cfg["chunking_strategy"] = strategy
        
        # Dọn dẹp cấu hình cũ
        for key in [
            "chunk_size", "chunk_overlap", "length_unit",
            "sentence_count", "overlap_sentences",
            "paragraphs_per_chunk", "overlap_paragraphs",
            "parent_chunk_size", "child_chunk_size", "child_chunk_overlap",
            "semantic_threshold_factor" ]:
            ret_cfg.pop(key, None)

        # Áp dụng cấu hình mới
        for key, value in chunk_cfg.items():
            ret_cfg[key] = value
            
        # Đồng bộ alias
        if strategy == "parent_child":
            ret_cfg["chunk_size"] = ret_cfg["child_chunk_size"]
            ret_cfg["chunk_overlap"] = ret_cfg["child_chunk_overlap"]
        elif strategy == "token":
            ret_cfg["chunk_size"] = ret_cfg["chunk_size"]
            ret_cfg["chunk_overlap"] = ret_cfg["chunk_overlap"]
        elif strategy in ("fixed", "recursive"):
            ret_cfg[f"{strategy}_chunk_size"] = ret_cfg["chunk_size"]
            ret_cfg[f"{strategy}_chunk_overlap"] = ret_cfg["chunk_overlap"]

        subject_id = f"dsa_{exp_name}" # Kiểm tra xem cấu hình này đã được nạp dữ liệu chưa
        db_conn = _get_db_conn()
        already_ingested = False
        try:
            row = db_conn.execute(
                "SELECT COUNT(*) as cnt FROM parent_chunks WHERE subject_id = ?",
                (subject_id,)
            ).fetchone()
            already_ingested = row["cnt"] > 0 if row else False
        except Exception as e:
            print(f"[WARN] Lỗi kiểm tra cache: {e}")
        finally:
            db_conn.close()

        if already_ingested:
            print(f"[{exp_name}] [CACHE HIT] Dữ liệu đã có sẵn trong database. Bỏ qua.")
            continue
            
        # Thực hiện Ingestion thực tế
        print(f"[{exp_name}] Bắt đầu nạp 3 tài liệu vào '{subject_id}'...")
        start_time = time.time()
        try:
            total_chunks = ingest_subject_documents(subject_id, docs_dir)
            duration = time.time() - start_time
            print(f"[{exp_name}] [OK] Hoàn thành. Tổng số: {total_chunks} chunks. Thời gian: {duration:.2f}s")
        except Exception as e:
            print(f"[{exp_name}] [ERROR] Nạp tài liệu thất bại: {e}")

    print("\n" + "="*80)
    print("HOÀN THÀNH TIẾN TRÌNH NẠP DỮ LIỆU.")
    print("="*80)

if __name__ == "__main__":
    main()
