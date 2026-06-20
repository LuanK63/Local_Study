"""
scratch/test_statistics.py
Phase 19 Validation: Statistical Analysis & Research Report Engine

Tests:
  1. Doc benchmark_runs
  2. Doc evaluation_results
  3. Tinh toan thong ke (Retrieval, Generation, Agent)
  4. Xuat CSV
  5. In Markdown tables
"""
import sys
import os
import sqlite3

# Fix Windows console encoding
if sys.platform.startswith("win"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.append(os.getcwd())

from utils.db_schema import get_db_path
from analytics.research_statistics import (
    compute_retrieval_statistics,
    compute_generation_statistics,
    compute_agent_statistics,
)
from analytics.export_statistics import export_all_statistics
from analytics.thesis_tables import generate_all_tables


def sep(title=""):
    print(f"\n{'='*60}")
    if title:
        print(f"  {title}")
    print()


def main():
    print("=" * 60)
    print("PHASE 19 VALIDATION: Statistical Analysis Engine")
    print("=" * 60)

    db_path = get_db_path()
    conn    = sqlite3.connect(db_path)
    cur     = conn.cursor()

    # ── Step 1: Doc benchmark_runs ──────────────────────────────────────────
    sep("Step 1: benchmark_runs")
    cur.execute("SELECT COUNT(*) FROM benchmark_runs")
    total_runs = cur.fetchone()[0]
    cur.execute("SELECT rag_mode, COUNT(*) FROM benchmark_runs GROUP BY rag_mode")
    mode_dist  = cur.fetchall()
    cur.execute("SELECT chunking_strategy, COUNT(*) FROM benchmark_runs GROUP BY chunking_strategy")
    strat_dist = cur.fetchall()
    print(f"  Total runs        : {total_runs}")
    print(f"  rag_mode          : {dict(mode_dist)}")
    print(f"  chunking_strategy : {dict(strat_dist)}")

    # ── Step 2: Doc evaluation_results ─────────────────────────────────────
    sep("Step 2: evaluation_results")
    cur.execute("SELECT COUNT(*) FROM evaluation_results")
    eval_count = cur.fetchone()[0]
    cur.execute("SELECT AVG(answer_accuracy), AVG(citation_accuracy) FROM evaluation_results")
    avg_acc, avg_cit = cur.fetchone()
    print(f"  Evaluation count  : {eval_count}")
    print(f"  Avg answer_acc    : {avg_acc}")
    print(f"  Avg citation_acc  : {avg_cit}")
    conn.close()

    # ── Step 3A: Retrieval Statistics ──────────────────────────────────────
    sep("Step 3A: Retrieval Statistics")
    ret_stats = compute_retrieval_statistics()
    if ret_stats:
        for strategy, m in ret_stats.items():
            print(f"  chunking_strategy : {strategy}")
            print(f"  n                 : {m['n']}")
            print(f"  Hit@1 Mean        : {m['hit_at_1_mean']}")
            print(f"  Hit@3 Mean        : {m['hit_at_3_mean']}")
            print(f"  Hit@5 Mean        : {m['hit_at_5_mean']}")
            print(f"  Recall@1 Mean     : {m['recall_at_1_mean']}")
            print(f"  Recall@3 Mean     : {m['recall_at_3_mean']}")
            print(f"  Recall@5 Mean     : {m['recall_at_5_mean']}")
            print(f"  MRR               : {m['mrr']}")
            print(f"  Grader Mean       : {m['grader_score_mean']}")
            print(f"  Grader Median     : {m['grader_score_median']}")
            print(f"  Grader IQR        : {m['grader_score_iqr']}")
            print(f"  Success Rate      : {m['retrieval_success_rate']}")
            print(f"  Best Sim L1 Mean  : {m['best_similarity_l1_mean']}")
        print("  [PASS] Retrieval statistics computed")
    else:
        print("  [WARN] No rag_grader data in DB yet")

    # ── Step 3B: Generation Statistics ─────────────────────────────────────
    sep("Step 3B: Generation Statistics")
    gen_stats = compute_generation_statistics()
    for k, v in gen_stats.items():
        print(f"  {k:<35}: {v}")
    print("  [PASS] Generation statistics computed")

    # ── Step 3C: Agent Statistics ───────────────────────────────────────────
    sep("Step 3C: Agent Statistics")
    agent_stats = compute_agent_statistics()
    if agent_stats.get("n_runs", 0) == 0:
        print(f"  [WARN] {agent_stats.get('note', 'No agentic_light data')}")
    else:
        for k, v in agent_stats.items():
            print(f"  {k:<40}: {v}")
    print("  [PASS] Agent statistics computed")

    # ── Step 4: Export CSV ──────────────────────────────────────────────────
    sep("Step 4: Export CSV")
    export_result = export_all_statistics()
    all_ok = True
    for fname, n_rows in export_result.items():
        status = "PASS" if n_rows >= 0 else "FAIL"
        print(f"  [{status}] {fname}: {n_rows} rows")
        if n_rows < 0:
            all_ok = False
    if all_ok:
        print("\n  [PASS] All CSVs exported successfully")

    # ── Step 5: Markdown Tables ─────────────────────────────────────────────
    sep("Step 5: Markdown Tables")
    try:
        md = generate_all_tables()
        line_count = md.count("\n")
        print(f"  Markdown generated: {line_count} lines")
        print()
        print(md)
        print("  [PASS] Markdown tables generated")
    except Exception as e:
        import traceback
        print(f"  [FAIL] {traceback.format_exc()}")

    sep()
    print("[DONE] Phase 19 Statistical Analysis Validation complete.")


if __name__ == "__main__":
    main()
