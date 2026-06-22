import os
import sys
import time
import json
import sqlite3
import argparse

# Add project root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import get_config
from core.retrieval.hybrid_retriever import delete_document, ingest_document, warm_up_bm25
from core.evaluation.ragas_eval import evaluate_pipeline

def reset_subject_index(subject_id: str):
    import sqlite3
    print(f"[Comparison] Resetting index for subject '{subject_id}'...")
    # 1. Clear SQLite parent chunks for this subject
    conn = sqlite3.connect("data/study_agent.db")
    conn.execute("DELETE FROM parent_chunks WHERE subject_id = ?", (subject_id,))
    conn.commit()
    conn.close()
    
    # 2. Delete ChromaDB collection
    from core.retrieval.vector_search import _get_client, _get_collection
    client = _get_client()
    try:
        client.delete_collection(subject_id)
    except Exception:
        pass
    
    # Re-create empty collection
    _get_collection(subject_id)
    
    # 3. Clear BM25 cache and L1 cache
    from core.retrieval.hybrid_retriever import _chunks_cache, _parent_cache
    _chunks_cache.pop(subject_id, None)
    _parent_cache.pop(subject_id, None)

def run_experiment(strategy_name: str, chunk_size: int, chunk_overlap: int, parent_size: int = 1200, max_pages: int = 120, max_questions: int = None, questions_path: str = "data/evaluation/questions.json") -> int:
    subject_id = "dsa"
    file_path = "subjects/dsa/documents/Giai thuat va Lap Trinh - cau truc du lieu va giai thuat by Lê Minh Hoàng (z-lib.org).pdf"
    
    print(f"\n======================================================================")
    print(f"RUNNING COMPARISON EXPERIMENT: {strategy_name.upper()}")
    print(f"Params: Size={chunk_size}, Overlap={chunk_overlap}, ParentSize={parent_size}, MaxPages={max_pages}")
    print(f"======================================================================")
    
    # 1. Update config dynamically in memory
    cfg = get_config()
    cfg["retrieval"]["chunking_strategy"] = strategy_name
    
    if strategy_name == "fixed":
        cfg["retrieval"]["fixed_chunk_size"] = chunk_size
        cfg["retrieval"]["fixed_chunk_overlap"] = chunk_overlap
    elif strategy_name == "recursive":
        cfg["retrieval"]["recursive_chunk_size"] = chunk_size
        cfg["retrieval"]["recursive_chunk_overlap"] = chunk_overlap
    elif strategy_name == "semantic":
        # Semantic chunker has a dynamic threshold factor from config
        pass
    elif strategy_name == "parent_child":
        cfg["retrieval"]["parent_chunk_size"] = parent_size
        cfg["retrieval"]["child_chunk_size"] = chunk_size
        cfg["retrieval"]["child_chunk_overlap"] = chunk_overlap
        
    # Also update general aliases for backward compatibility
    cfg["retrieval"]["chunk_size"] = chunk_size
    cfg["retrieval"]["chunk_overlap"] = chunk_overlap

    # 2. Reset database and index
    reset_subject_index(subject_id)
    
    # 3. Ingest documents and measure time
    print(f"[Comparison] Ingesting document (max_pages={max_pages})...")
    start_time = time.time()
    total_indexed = ingest_document(file_path, subject_id, max_pages=max_pages)
    ingestion_time = time.time() - start_time
    print(f"[Comparison] Ingested {total_indexed} child chunks in {ingestion_time:.2f}s")
    
    # 4. Get the run_id that was logged inside ingest_document
    db_path = cfg["database"]["path"]
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM experiment_runs WHERE subject_id = ? AND chunking_strategy = ? ORDER BY id DESC LIMIT 1",
        (subject_id, strategy_name)
    )
    row = cur.fetchone()
    if row:
        run_id = row[0]
    else:
        # Fallback if log_ingestion failed
        cur.execute("SELECT MAX(id) FROM experiment_runs")
        run_id = cur.fetchone()[0]
    conn.close()
    
    print(f"[Comparison] Associated run_id: {run_id}")
    
    # 5. Warm up BM25 index
    warm_up_bm25([subject_id])
    
    # 6. Load evaluation questions
    with open(questions_path, "r", encoding="utf-8") as f:
        test_dataset = json.load(f)
        
    if max_questions is not None:
        test_dataset = test_dataset[:max_questions]
        
    # 7. Run evaluation
    print(f"[Comparison] Running evaluation on {len(test_dataset)} questions...")
    results = evaluate_pipeline(test_dataset, subject_id, run_id=run_id)
    
    # 8. Export run results to CSV
    from utils.experiment_logger import export_run_to_csv
    export_run_to_csv(run_id)
    
    print(f"[Comparison] Completed experiment for {strategy_name}. Run ID: {run_id}")
    return run_id

if __name__ == "__main__":
    # Reconfigure stdout to use UTF-8
    if sys.platform.startswith('win'):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        
    parser = argparse.ArgumentParser(description="Run a single chunking strategy comparison experiment.")
    parser.add_argument("--strategy", type=str, required=True, choices=["fixed", "recursive", "semantic", "parent_child"])
    parser.add_argument("--size", type=int, default=300)
    parser.add_argument("--overlap", type=int, default=30)
    parser.add_argument("--parent-size", type=int, default=1200)
    parser.add_argument("--max-pages", type=int, default=120)
    parser.add_argument("--max-questions", type=int, default=None, help="Limit number of questions to evaluate")
    parser.add_argument("--questions", type=str, default="data/evaluation/questions.json", help="Path to evaluation questions JSON file")
    
    args = parser.parse_args()
    
    run_experiment(
        strategy_name=args.strategy,
        chunk_size=args.size,
        chunk_overlap=args.overlap,
        parent_size=args.parent_size,
        max_pages=args.max_pages,
        max_questions=args.max_questions,
        questions_path=args.questions
    )
