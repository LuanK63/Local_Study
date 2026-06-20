import sys
import os
import sqlite3

# Add project root to path
sys.path.append(os.getcwd())

# Reconfigure stdout/stderr for UTF-8 on Windows
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from core.pipeline.agentic_rag import AgentState, generate_agentic_response
from utils.benchmark_loader import load_benchmark_questions
from utils.subject_loader import get_subject
from core.retrieval.hybrid_retriever import warm_up_bm25
from utils.config import get_config
from utils.db_schema import get_db_path

def count_sqlite_rows(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM benchmark_runs")
    count = cur.fetchone()[0]
    conn.close()
    return count

def count_csv_rows(csv_path):
    import csv
    if not os.path.exists(csv_path):
        return 0
    try:
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            return sum(1 for _ in reader)
    except Exception:
        return 0

def main():
    print("==================================================")
    print("STARTING RUNTIME LOGGER INTEGRATION VALIDATION")
    print("==================================================")

    db_path = get_db_path()
    csv_path = "data/experiments/benchmark_log.csv"

    # 1. Count rows before
    sqlite_before = count_sqlite_rows(db_path)
    csv_before = count_csv_rows(csv_path)

    print(f"Before: SQLite rows = {sqlite_before}, CSV rows = {csv_before}")

    # 2. Warm up BM25
    print("Warming up BM25...")
    try:
        warm_up_bm25(["dsa"])
    except Exception as e:
        print(f"Warning warming up BM25: {e}")

    # 3. Load 5 questions
    questions = load_benchmark_questions()
    test_questions = questions[:5]

    # Force rag_mode to rag_grader in config
    cfg = get_config()
    if "rag" not in cfg:
        cfg["rag"] = {}
    old_rag_mode = cfg["rag"].get("mode", "pure_rag")
    cfg["rag"]["mode"] = "rag_grader"

    subject_cfg = get_subject("dsa")

    # 4. Run pipeline
    for idx, q in enumerate(test_questions, 1):
        q_id = q["id"]
        query_text = q["question"]

        state = AgentState(
            query=query_text,
            rag_mode="rag_grader",
            chunking_strategy=cfg.get("retrieval", {}).get("chunking_strategy", "fixed"),
            question_id=q_id
        )

        # Execute response generator (do NOT call log_benchmark_run here!)
        generator = generate_agentic_response(
            query=query_text,
            subject_id="dsa",
            subject_cfg=subject_cfg,
            state=state
        )

        # Consume the generator fully
        for _ in generator:
            pass

        print(f"Run {idx} logged")

    # Restore old rag_mode
    cfg["rag"]["mode"] = old_rag_mode

    # 5. Count rows after
    sqlite_after = count_sqlite_rows(db_path)
    csv_after = count_csv_rows(csv_path)

    sqlite_added = sqlite_after - sqlite_before
    csv_added = csv_after - csv_before

    print(f"\nSQLite rows added: {sqlite_added}")
    print(f"CSV rows added: {csv_added}")

    # Verification checks
    assert sqlite_added == 5, f"Expected 5 SQLite rows added, got {sqlite_added}"
    assert csv_added == 5, f"Expected 5 CSV rows added, got {csv_added}"
    print("\nValidation PASSED!")

if __name__ == "__main__":
    main()
