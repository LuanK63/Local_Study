import argparse
import sys
import os

# Reconfigure stdout/stderr to use UTF-8 on Windows to avoid UnicodeEncodeErrors
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import yaml
import json
import time
import sqlite3
import pandas as pd
from pathlib import Path

from core.document_processor.pdf_reader import read_pdf
from core.document_processor.chunking.factory import get_chunker
from core.retrieval.hybrid_retriever import search
from core.pipeline.answer_generator import generate_with_context
from utils.db_schema import get_db_path

# ==============================================================================
# Helper functions for Database
# ==============================================================================
def get_or_create_run_id(config: dict, chunking: str, chunk_size: int, matrix_cfg: dict) -> int:
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()
    
    # Kiem tra xem run da ton tai chua bang cach match config attributes
    dataset_name = config["dataset"]["name"]
    dataset_version = config["dataset"]["version"]
    dataset_path = config["dataset"]["path"]
    embedding_model = config["models"]["embedding_model"]
    reranker_model = config["models"]["reranker_model"]
    retrieval_mode = matrix_cfg["retrieval_mode"]
    
    cur.execute("""
        SELECT id FROM benchmark_runs 
        WHERE dataset_name=? AND dataset_version=? AND chunking_strategy=? 
          AND chunk_size=? AND retrieval_mode=? AND embedding_model=? AND reranker_model=?
    """, (dataset_name, dataset_version, chunking, chunk_size, retrieval_mode, embedding_model, reranker_model))
    row = cur.fetchone()
    if row:
        run_id = row[0]
    else:
        # Tinh toan question_count tu file json
        question_count = 0
        if os.path.exists(dataset_path):
            with open(dataset_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                question_count = len(data.get("questions", []))
                
        cur.execute("""
            INSERT INTO benchmark_runs (
                timestamp, config_json, dataset_name, dataset_version, dataset_path,
                question_count, chunking_strategy, chunk_size, index_version,
                retrieval_mode, embedding_model, reranker_model, latency_avg
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            json.dumps(config), dataset_name, dataset_version, dataset_path,
            question_count, chunking, chunk_size, "v1", retrieval_mode,
            embedding_model, reranker_model, 0.0
        ))
        run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return run_id

def is_question_evaluated(run_id: int, question_id: str) -> bool:
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()
    cur.execute("SELECT id FROM benchmark_scores WHERE run_id=? AND question_id=?", (run_id, question_id))
    row = cur.fetchone()
    conn.close()
    return row is not None

def save_score(run_id: int, question_id: str, faithfulness: float, answer_relevancy: float, context_precision: float, context_recall: float, total_latency_ms: float):
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO benchmark_scores (
            run_id, question_id, faithfulness, answer_relevancy, 
            context_precision, context_recall, total_latency_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (run_id, question_id, faithfulness, answer_relevancy, context_precision, context_recall, total_latency_ms))
    
    # Tinh lai latency_avg
    cur.execute("SELECT AVG(total_latency_ms) FROM benchmark_scores WHERE run_id=?", (run_id,))
    avg = cur.fetchone()[0] or 0.0
    cur.execute("UPDATE benchmark_runs SET latency_avg=? WHERE id=?", (avg, run_id))
    
    conn.commit()
    conn.close()

# ==============================================================================
# Pipeline Execution
# ==============================================================================
def run_rebuild_index(config: dict):
    print("=== STARTING REBUILD INDEX ===")
    docs_dir = Path("subjects/dsa/documents")
    if not docs_dir.exists():
        print(f"[ERROR] Thu muc khong ton tai: {docs_dir}")
        return
        
    print(f"-> Reading PDFs tu {docs_dir}")
    pages = []
    for f in docs_dir.iterdir():
        if f.suffix.lower() == ".pdf":
            pages.extend(read_pdf(str(f)))
    print(f"-> Da tai {len(pages)} pages.")

    matrix = config["matrix"]
    static_params = config["static_params"]
    import chromadb
    chroma_client = chromadb.PersistentClient(path="data/chroma_db")

    for chunking in matrix["chunking"]:
        for size in matrix["chunk_sizes"]:
            collection_name = f"{chunking}_{size}"
            print(f"\n[REBUILD] Dang build collection: {collection_name}")
            
            # Xoa collection neu co (CHỈ XÓA collection này, không xóa cả thư mục)
            try:
                chroma_client.delete_collection(name=collection_name)
                print(f"  -> Deleted old collection {collection_name}")
            except Exception:
                pass
                
            col = chroma_client.create_collection(name=collection_name)
            
            overlap = int(size * static_params.get("overlap_ratio", 0.1))
            parent_size = static_params.get("parent_size", 1200)
            chunker = get_chunker(strategy_name=chunking, chunk_size=size, chunk_overlap=overlap, parent_size=parent_size)
            
            chunks = chunker.chunk(pages)
            print(f"  -> Generated {len(chunks)} chunks.")
            
            if chunks:
                from utils.config import get_config
                from langchain_ollama import OllamaEmbeddings
                sys_cfg = get_config()
                embeddings_wrapper = OllamaEmbeddings(
                    model=config["models"]["embedding_model"],
                    base_url=sys_cfg["embedding"]["base_url"]
                )
                
                texts = [c.text for c in chunks]
                ids = [c.chunk_id for c in chunks]
                metadatas = [c.metadata for c in chunks]
                
                print("  -> Dang tao embeddings va luu vao ChromaDB... (Co the mat nhieu thoi gian)")
                # Batch processing
                batch_size = 100
                for i in range(0, len(chunks), batch_size):
                    end = min(i + batch_size, len(chunks))
                    embeds = embeddings_wrapper.embed_documents(texts[i:end])
                    col.add(ids=ids[i:end], embeddings=embeds, documents=texts[i:end], metadatas=metadatas[i:end])
                    print(f"     + Saved batch {i}-{end}")
                print(f"  -> Xong collection {collection_name}")

def run_benchmark(config: dict, resume: bool):
    print("\n=== STARTING BENCHMARK ===")
    dataset_path = config["dataset"]["path"]
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
        
    questions = dataset.get("questions", [])
    matrix = config["matrix"]
    static_params = config["static_params"]
    
    # De don gian, su dung Fake Evaluator (do qwen2.5:14b ton tai nguyen. Phai tich hop Ragas sau).
    # Trong code thuc te, day la noi call ragas_eval.py
    
    for chunking in matrix["chunking"]:
        for size in matrix["chunk_sizes"]:
            collection_name = f"{chunking}_{size}"
            print(f"\n--- Running Benchmark for: {collection_name} ---")
            
            run_id = get_or_create_run_id(config, chunking, size, static_params)
            
            for q_item in questions:
                q_id = q_item["id"]
                if resume and is_question_evaluated(run_id, q_id):
                    print(f"  [SKIP] Question {q_id} da duoc evaluate.")
                    continue
                    
                print(f"  [RUN] Question {q_id}...")
                start_time = time.time()
                
                # 1 & 2. Hybrid Retrieve & MiniLM Rerank (duoc xu ly ben trong search())
                # Truy truyen mode=retrieval_mode (mac dinh 'hybrid'), va lay top_k_rerank
                final_chunks, _ = search(
                    query=q_item["question"], 
                    subject_id=collection_name, 
                    top_k=static_params["top_k_rerank"],
                    mode=static_params["retrieval_mode"]
                )

                
                # 3. Generate Answer
                answer = generate_with_context(q_item["question"], final_chunks, stream=False)
                
                # 4. Evaluate (Mocked for now. Integrate Ragas proper later)
                total_latency_ms = (time.time() - start_time) * 1000
                save_score(run_id, q_id, 0.9, 0.9, 0.8, 0.8, total_latency_ms)
                
    export_results()

def export_results():
    print("\n=== EXPORTING RESULTS ===")
    conn = sqlite3.connect(get_db_path())
    
    query = """
        SELECT r.chunking_strategy, r.chunk_size, 
               AVG(s.faithfulness) as avg_faithfulness,
               AVG(s.context_recall) as avg_recall,
               AVG(s.answer_relevancy) as avg_relevancy,
               AVG(s.context_precision) as avg_precision,
               AVG(s.total_latency_ms) as avg_latency
        FROM benchmark_runs r
        JOIN benchmark_scores s ON r.id = s.run_id
        GROUP BY r.chunking_strategy, r.chunk_size
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    os.makedirs("outputs", exist_ok=True)
    df.to_csv("outputs/benchmark_results.csv", index=False)
    df.to_excel("outputs/benchmark_results.xlsx", index=False)
    
    # Generate benchmark_summary.json
    summary = {}
    if not df.empty:
        best_f = df.loc[df['avg_faithfulness'].idxmax()]
        summary["best_by_faithfulness"] = {"chunker": best_f["chunking_strategy"], "chunk_size": int(best_f["chunk_size"]), "score": float(best_f["avg_faithfulness"])}
        
        best_r = df.loc[df['avg_recall'].idxmax()]
        summary["best_by_context_recall"] = {"chunker": best_r["chunking_strategy"], "chunk_size": int(best_r["chunk_size"]), "score": float(best_r["avg_recall"])}
        
        # calculate overall best as sum of metrics
        df['overall'] = df['avg_faithfulness'] + df['avg_recall'] + df['avg_relevancy'] + df['avg_precision']
        best_o = df.loc[df['overall'].idxmax()]
        summary["overall_best"] = {"chunker": best_o["chunking_strategy"], "chunk_size": int(best_o["chunk_size"]), "avg_score": float(best_o["overall"]/4)}
        
    with open("outputs/benchmark_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4)
        
    print("-> Exports saved to outputs/ thư mục.")

# ==============================================================================
# CLI Entrypoint
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DSA Tutor RAG Benchmark Framework")
    parser.add_argument("--config", type=str, required=True, help="Path to YAML config")
    parser.add_argument("--rebuild-index", action="store_true", help="Rebuild vector indexes before running")
    parser.add_argument("--resume", action="store_true", help="Resume from last crashed question")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if args.rebuild_index:
        run_rebuild_index(config)
        
    run_benchmark(config, resume=args.resume)
