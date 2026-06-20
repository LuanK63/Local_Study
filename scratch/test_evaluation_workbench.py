"""
scratch/test_evaluation_workbench.py
Phase 18 Validation: Manual Evaluation Assistant Tool

Tests:
  A. load_pending_runs()
  B. get_next_unevaluated_run()
  C. save_evaluation() — bao gồm validate đúng và sai
  D. evaluation_progress()
  E. export_evaluation_report()
"""
import sys
import os
import csv

# Fix Windows console encoding
if sys.platform.startswith("win"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.append(os.getcwd())

from tools.evaluation_workbench import (
    load_pending_runs,
    get_next_unevaluated_run,
    save_evaluation,
    evaluation_progress,
)
from tools.export_evaluation_report import export_evaluation_report


def sep(title=""):
    print(f"\n{'='*60}")
    if title:
        print(f"  {title}")


def main():
    print("=" * 60)
    print("PHASE 18 VALIDATION: Manual Evaluation Assistant Tool")
    print("=" * 60)

    # ── A. load_pending_runs() ────────────────────────────────────────────────
    sep("A. load_pending_runs()")
    pending = load_pending_runs()
    print(f"  Pending runs (chua cham): {len(pending)}")

    required_keys = {"run_id", "question_id", "query", "final_answer",
                     "ground_truth_answer", "chunking_strategy", "rag_mode"}
    if pending:
        sample = pending[0]
        missing = required_keys - set(sample.keys())
        if missing:
            print(f"  [FAIL] Thieu keys: {missing}")
        else:
            print(f"  [PASS] Keys dung")
            print(f"  Sample run_id={sample['run_id']} | qid={sample['question_id']} | mode={sample['rag_mode']}")
            print(f"  Query   : {sample['query'][:60]}...")
            print(f"  GT ans  : {str(sample['ground_truth_answer'])[:60]}...")
    else:
        print("  [INFO] Khong con run nao chua cham — tat ca da duoc danh gia")

    # ── B. get_next_unevaluated_run() ─────────────────────────────────────────
    sep("B. get_next_unevaluated_run()")
    next_run = get_next_unevaluated_run()
    if next_run:
        print(f"  Next run_id   : {next_run['run_id']}")
        print(f"  question_id   : {next_run['question_id']}")
        print(f"  rag_mode      : {next_run['rag_mode']}")
        print(f"  query         : {next_run['query'][:60]}...")
        print(f"  [PASS] get_next_unevaluated_run() hoat dong")
    else:
        print("  [INFO] Khong con run chua cham")

    # ── C. save_evaluation() ─────────────────────────────────────────────────
    sep("C. save_evaluation()")

    # C1. Validation sai — answer_accuracy out of range
    print("  C1. Test ValueError: answer_accuracy=6 (invalid)...")
    try:
        save_evaluation(run_id=9999, answer_accuracy=6, citation_accuracy=0.5)
        print("  [FAIL] Khong raise ValueError cho answer_accuracy=6")
    except ValueError as e:
        print(f"  [PASS] ValueError: {e}")

    # C2. Validation sai — citation_accuracy > 1.0
    print("  C2. Test ValueError: citation_accuracy=1.5 (invalid)...")
    try:
        save_evaluation(run_id=9999, answer_accuracy=3, citation_accuracy=1.5)
        print("  [FAIL] Khong raise ValueError cho citation_accuracy=1.5")
    except ValueError as e:
        print(f"  [PASS] ValueError: {e}")

    # C3. Insert hop le vao run chua cham
    if next_run:
        target_run_id = next_run["run_id"]
        print(f"  C3. Inserting valid evaluation for run_id={target_run_id}...")
        try:
            eval_id = save_evaluation(
                run_id            = target_run_id,
                answer_accuracy   = 3,
                citation_accuracy = 0.75,
                notes             = "Phase 18 workbench test",
                evaluator         = "student",
            )
            print(f"  [PASS] Inserted eval_id={eval_id} for run_id={target_run_id}")
        except Exception as e:
            print(f"  [FAIL] save_evaluation raised: {e}")
    else:
        print("  C3. [SKIP] Khong con run nao de insert")

    # ── D. evaluation_progress() ─────────────────────────────────────────────
    sep("D. evaluation_progress()")
    progress = evaluation_progress()
    total     = progress["total_runs"]
    evaluated = progress["evaluated_runs"]
    remaining = progress["remaining_runs"]

    print(f"  Total    : {total}")
    print(f"  Evaluated: {evaluated}")
    print(f"  Remaining: {remaining}")

    if total == evaluated + remaining:
        print(f"  [PASS] total = evaluated + remaining ({evaluated} + {remaining} = {total})")
    else:
        print(f"  [FAIL] Phep tinh khong khop")

    # ── E. export_evaluation_report() ────────────────────────────────────────
    sep("E. export_evaluation_report()")
    report_path = os.path.join("data", "experiments", "evaluation_report.csv")
    try:
        n_rows = export_evaluation_report(report_path)
        print(f"  Exported {n_rows} rows -> {report_path}")

        if n_rows > 0:
            with open(report_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                all_rows = list(reader)

            print(f"\n  Header: {reader.fieldnames}")
            print(f"\n  Last row:")
            last = all_rows[-1]
            for k, v in last.items():
                print(f"    {k:<22}: {v}")
            print(f"\n  [PASS] evaluation_report.csv created with {n_rows} rows")
        else:
            print("  [INFO] 0 rows — chua co evaluation nao de export")
    except Exception as e:
        import traceback
        print(f"  [FAIL] export_evaluation_report: {traceback.format_exc()}")

    # ── Tong ket ─────────────────────────────────────────────────────────────
    sep()
    print("[DONE] Phase 18 Manual Evaluation Assistant Validation complete.")
    print(f"  Remaining unevaluated runs: {evaluation_progress()['remaining_runs']}")


if __name__ == "__main__":
    main()
