"""
analytics/export_statistics.py
Phase 19 — Xuất thống kê ra CSV.

Xuất 3 file:
  data/experiments/retrieval_statistics.csv
  data/experiments/generation_statistics.csv
  data/experiments/agent_statistics.csv

Không ghi vào benchmark_runs hay evaluation_results.
"""
import csv
import os

from analytics.research_statistics import (
    compute_retrieval_statistics,
    compute_generation_statistics,
    compute_agent_statistics,
)

_DATA_DIR = os.path.join("data", "experiments")


def _write_csv(path: str, rows: list[dict]) -> int:
    """Ghi danh sách dict ra CSV. Trả về số dòng (không kể header)."""
    if not rows:
        print(f"[ExportStats] No data for {path}")
        return 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    headers = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[ExportStats] {len(rows)} rows → {path}")
    return len(rows)


# ── Retrieval ─────────────────────────────────────────────────────────────────

def export_retrieval_statistics(
    output_path: str = os.path.join(_DATA_DIR, "retrieval_statistics.csv"),
) -> int:
    """
    Xuất thống kê retrieval (rag_mode=rag_grader) theo chunking_strategy.
    """
    stats = compute_retrieval_statistics()
    rows = []
    for strategy, metrics in stats.items():
        row = {"chunking_strategy": strategy, **metrics}
        rows.append(row)
    return _write_csv(output_path, rows)


# ── Generation ────────────────────────────────────────────────────────────────

def export_generation_statistics(
    output_path: str = os.path.join(_DATA_DIR, "generation_statistics.csv"),
) -> int:
    """
    Xuất thống kê generation (rag_mode=pure_rag) join evaluation_results.
    """
    stats = compute_generation_statistics()
    # Single-row format: metric → value
    rows = [{"metric": k, "value": v} for k, v in stats.items()]
    return _write_csv(output_path, rows)


# ── Agent ─────────────────────────────────────────────────────────────────────

def export_agent_statistics(
    output_path: str = os.path.join(_DATA_DIR, "agent_statistics.csv"),
) -> int:
    """
    Xuất thống kê agent improvement (rag_mode=agentic_light).
    """
    stats = compute_agent_statistics()
    rows = [{"metric": k, "value": v} for k, v in stats.items()]
    return _write_csv(output_path, rows)


# ── Export All ────────────────────────────────────────────────────────────────

def export_all_statistics() -> dict:
    """
    Xuất tất cả 3 file thống kê.

    Returns
    -------
    dict: {filename: n_rows}
    """
    return {
        "retrieval_statistics.csv": export_retrieval_statistics(),
        "generation_statistics.csv": export_generation_statistics(),
        "agent_statistics.csv":      export_agent_statistics(),
    }


if __name__ == "__main__":
    import sys, io
    if sys.platform.startswith("win"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    result = export_all_statistics()
    for f, n in result.items():
        print(f"  {f}: {n} rows")
