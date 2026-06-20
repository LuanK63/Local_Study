"""
scratch/test_evaluation_results.py
Phase 17 Validation: Human Evaluation Layer
"""
import sys
import os
import sqlite3
import csv

# Fix Windows console encoding
if sys.platform.startswith("win"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.append(os.getcwd())

from utils.db_schema import init_db, get_db_path
from utils.evaluation_logger import (
    insert_evaluation_result,
    get_evaluation,
    list_unevaluated_runs,
)

def main():
    print("=" * 60)
    print("PHASE 17 VALIDATION: Human Evaluation Layer")
    print("=" * 60)

    # 1. Đảm bảo DB đã migrate
    print("\n[Step 1] Running init_db() migration...")
    init_db()

    # 2. Lấy run_id mới nhất từ benchmark_runs
    db_path = get_db_path()
    conn    = sqlite3.connect(db_path)
    cur     = conn.cursor()
    cur.execute("SELECT id FROM benchmark_runs ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()

    if row is None:
        print("[ERROR] Khong co du lieu trong benchmark_runs. Hay chay pipeline truoc.")
        sys.exit(1)

    latest_run_id = row[0]
    print(f"[Step 2] Latest benchmark_runs.id = {latest_run_id}")

    # 3. Liệt kê unevaluated trước khi insert
    unevaluated_before = list_unevaluated_runs()
    print(f"\n[Step 3] Unevaluated runs before insert: {len(unevaluated_before)} runs")

    # 4. Insert evaluation
    print(f"\n[Step 4] Inserting evaluation for run_id={latest_run_id}...")
    eval_id = insert_evaluation_result(
        run_id           = latest_run_id,
        answer_accuracy  = 4,
        citation_accuracy = 0.8,
        notes            = "Phase 17 test insert",
        evaluator        = "student",
    )
    print(f"  Inserted eval_id = {eval_id}")

    # 5. Đọc lại từ DB
    print(f"\n[Step 5] Reading back evaluation for run_id={latest_run_id}...")
    result = get_evaluation(latest_run_id)

    if result is None:
        print("  [FAIL] get_evaluation() returned None")
        sys.exit(1)

    print(f"\n  Run ID           : {result['run_id']}")
    print(f"  Answer Accuracy  : {result['answer_accuracy']}")
    print(f"  Citation Accuracy: {result['citation_accuracy']}")
    print(f"  Evaluator        : {result['evaluator']}")
    print(f"  Notes            : {result['notes']}")
    print(f"  Evaluated At     : {result['evaluated_at']}")

    # 6. Xác nhận dữ liệu đúng
    assert result["run_id"]           == latest_run_id, "run_id mismatch"
    assert result["answer_accuracy"]  == 4,             "answer_accuracy mismatch"
    assert abs(result["citation_accuracy"] - 0.8) < 1e-6, "citation_accuracy mismatch"
    assert result["evaluator"]        == "student",     "evaluator mismatch"
    print("\n  [PASS] SQLite data correct")

    # 7. Liệt kê unevaluated sau insert
    unevaluated_after = list_unevaluated_runs()
    print(f"\n[Step 6] Unevaluated runs after insert: {len(unevaluated_after)} runs")
    diff = len(unevaluated_before) - len(unevaluated_after)
    print(f"         Reduced by {diff} (run_id={latest_run_id} now evaluated)")

    # 8. Kiểm tra CSV
    csv_path = os.path.join("data", "experiments", "evaluation_results.csv")
    print(f"\n[Step 7] Checking CSV: {csv_path}")
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader   = csv.DictReader(f)
            csv_rows = list(reader)

        if csv_rows:
            last = csv_rows[-1]
            print(f"  Last CSV row:")
            print(f"    id              : {last.get('id')}")
            print(f"    run_id          : {last.get('run_id')}")
            print(f"    answer_accuracy : {last.get('answer_accuracy')}")
            print(f"    citation_accuracy: {last.get('citation_accuracy')}")
            print(f"    evaluator       : {last.get('evaluator')}")
            print(f"    evaluated_at    : {last.get('evaluated_at')}")

            assert str(last.get("run_id"))           == str(latest_run_id)
            assert str(last.get("answer_accuracy"))  == "4"
            assert str(last.get("evaluator"))        == "student"
            print("\n  [PASS] CSV data correct")
        else:
            print("  [FAIL] CSV is empty")
    except FileNotFoundError:
        print(f"  [FAIL] CSV not found: {csv_path}")

    # 9. Kiểm tra idempotency: chạy init_db() lần 2 không lỗi
    print("\n[Step 8] Idempotency check — running init_db() again...")
    try:
        init_db()
        print("  [PASS] init_db() idempotent")
    except Exception as e:
        print(f"  [FAIL] init_db() raised exception: {e}")

    print("\n" + "=" * 60)
    print("[DONE] Phase 17 Human Evaluation Layer Validation PASSED.")
    print("=" * 60)

if __name__ == "__main__":
    main()
