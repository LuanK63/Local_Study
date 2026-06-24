"""
analytics/thesis_tables.py
Phase 19 — Sinh Markdown Tables cho Khóa Luận.

TABLE 1: Chunking Benchmark      (Answer Accuracy, Tokens, Latency)
TABLE 2: Retrieval Analysis      (Hit@5, Recall@5, MRR, Median Grader)
TABLE 3: Agent Improvement       (Rewrite Rate, Recall Gain, Similarity Gain)

Output: Markdown tables, copy trực tiếp vào khóa luận.
Không sinh kết luận khoa học tự động.
"""
from analytics.research_statistics import (
    compute_retrieval_statistics,
    compute_generation_statistics,
    compute_agent_statistics,
)


def _md_row(cells: list) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def _md_separator(n_cols: int) -> str:
    return "| " + " | ".join(["---"] * n_cols) + " |"


# ── TABLE 1: Chunking Benchmark ───────────────────────────────────────────────

def generate_table1_chunking_benchmark() -> str:
    """
    TABLE 1 — Chunking Benchmark
    Columns: Chunking | Answer Accuracy | Total Tokens | Latency (ms)

    Nguồn: generation_statistics (pure_rag) vì có token + latency.
    Accuracy lấy từ evaluation_results (nếu có).
    """
    gen = compute_generation_statistics()

    # One row per chunking (hiện chỉ có 1 strategy per rag_mode trong dataset nhỏ)
    # Lấy toàn bộ theo chunking từ DB trực tiếp
    import sqlite3
    from utils.db_schema import get_db_path

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()
    cur.execute(
        """
        SELECT
            br.chunking_strategy,
            AVG(COALESCE(er.answer_accuracy, 0))  AS avg_accuracy,
            AVG(br.total_tokens)                   AS avg_tokens,
            AVG(br.total_time_ms)                  AS avg_latency_ms
        FROM benchmark_runs br
        LEFT JOIN evaluation_results er ON er.run_id = br.id
        WHERE br.rag_mode = 'pure_rag'
        GROUP BY br.chunking_strategy
        ORDER BY br.chunking_strategy
        """
    )
    rows = cur.fetchall()
    conn.close()

    lines = []
    lines.append("### Bảng 1: Chunking Benchmark (pure_rag)\n")
    headers = ["Chunking Strategy", "Answer Accuracy (Mean)", "Total Tokens (Mean)", "Latency ms (Mean)"]
    lines.append(_md_row(headers))
    lines.append(_md_separator(len(headers)))

    for row in rows:
        strategy = row["chunking_strategy"] or "N/A"
        acc      = f"{row['avg_accuracy']:.2f}"   if row["avg_accuracy"]  is not None else "N/A"
        tokens   = f"{row['avg_tokens']:.0f}"     if row["avg_tokens"]    is not None else "N/A"
        latency  = f"{row['avg_latency_ms']:.1f}" if row["avg_latency_ms"] is not None else "N/A"
        lines.append(_md_row([strategy, acc, tokens, latency]))

    if not rows:
        lines.append(_md_row(["(no data)", "-", "-", "-"]))

    lines.append(f"\n> Nguồn: `benchmark_runs` rag_mode=pure_rag, n={gen['n_runs']} runs")
    return "\n".join(lines)


# ── TABLE 2: Retrieval Analysis ───────────────────────────────────────────────

def generate_table2_retrieval_analysis() -> str:
    """
    TABLE 2 — Retrieval Analysis
    Columns: Chunking | Hit@5 | Recall@5 | MRR | Median Grader Score
    """
    stats = compute_retrieval_statistics()

    lines = []
    lines.append("### Bảng 2: Retrieval Analysis (rag_grader)\n")
    headers = ["Chunking Strategy", "Hit@5 (Mean)", "Recall@5 (Mean)", "MRR", "Grader Score (Median)", "n"]
    lines.append(_md_row(headers))
    lines.append(_md_separator(len(headers)))

    if not stats:
        lines.append(_md_row(["(no data)", "-", "-", "-", "-", "-"]))
    else:
        for strategy, m in sorted(stats.items()):
            lines.append(_md_row([
                strategy,
                f"{m['hit_at_5_mean']:.4f}",
                f"{m['recall_at_5_mean']:.4f}",
                f"{m['mrr']:.4f}",
                f"{m['grader_score_median']:.1f}",
                m["n"],
            ]))

    lines.append("\n> Nguồn: `benchmark_runs` rag_mode=rag_grader")
    lines.append("> *Grader Score là dữ liệu Ordinal → báo cáo Median thay vì Mean.*")
    return "\n".join(lines)


# ── TABLE 3: Agent Improvement ────────────────────────────────────────────────

def generate_table3_agent_improvement() -> str:
    """
    TABLE 3 — Agent Improvement
    Columns: Metric | Value
    """
    stats = compute_agent_statistics()

    lines = []
    lines.append("### Bảng 3: Agent Improvement (agentic_light)\n")

    if stats.get("n_runs", 0) == 0:
        lines.append("*Chưa có dữ liệu rag_mode=agentic_light trong database.*")
        lines.append(f"\n> Ghi chú: {stats.get('note', '')}")
        return "\n".join(lines)

    headers = ["Chỉ số", "Giá trị"]
    lines.append(_md_row(headers))
    lines.append(_md_separator(len(headers)))

    metrics = [
        ("n_runs",                          "Số lượng runs"),
        ("rewrite_activation_rate",         "Rewrite Activation Rate"),
        ("rewrite_count",                   "Rewrite Count"),
        ("grader_improvement_mean",         "Grader Score Improvement (Mean)"),
        ("grader_improvement_median",       "Grader Score Improvement (Median)"),
        ("grader_improvement_iqr",          "Grader Score Improvement (IQR)"),
        ("recall_at_5_improvement_mean",    "Recall@5 Improvement (Mean)"),
        ("recall_at_5_improvement_median",  "Recall@5 Improvement (Median)"),
        ("similarity_improvement_mean",     "Similarity Improvement (Mean)"),
        ("similarity_improvement_median",   "Similarity Improvement (Median)"),
        ("attempts_1_count",                "Attempts=1 Count"),
        ("attempts_2_count",                "Attempts=2 Count"),
        ("attempts_1_pct",                  "Attempts=1 (%)"),
        ("attempts_2_pct",                  "Attempts=2 (%)"),
    ]

    for key, label in metrics:
        val = stats.get(key, "N/A")
        if isinstance(val, float):
            val = f"{val:.4f}"
        lines.append(_md_row([label, val]))

    lines.append(f"\n> Nguồn: `benchmark_runs` rag_mode=agentic_light, n={stats['n_runs']} runs")
    lines.append("> *Grader Score là dữ liệu Ordinal → báo cáo Median + IQR.*")
    return "\n".join(lines)


# ── Generate All ──────────────────────────────────────────────────────────────

def generate_all_tables() -> str:
    """
    Sinh toàn bộ 3 bảng Markdown.

    Returns
    -------
    str: Markdown string, có thể copy trực tiếp vào khóa luận.
    """
    parts = [
        "# Bảng Thống Kê Thực Nghiệm — Khóa Luận\n",
        generate_table1_chunking_benchmark(),
        "\n---\n",
        generate_table2_retrieval_analysis(),
        "\n---\n",
        generate_table3_agent_improvement(),
    ]
    return "\n\n".join(parts)


if __name__ == "__main__":
    import sys, io, os
    if sys.platform.startswith("win"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    print(generate_all_tables())
