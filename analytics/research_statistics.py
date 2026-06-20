"""
analytics/research_statistics.py
Phase 19 — Statistical Analysis Layer.

Chỉ đọc SQLite, không ghi dữ liệu.
Không tính t-test, ANOVA, Pearson Correlation.
Không tự động sinh kết luận khoa học.
Chỉ sinh số liệu.

Scientific constraints (Grader Score là dữ liệu Ordinal):
  Báo cáo Mean, Median, IQR — không báo cáo SD như metric chính.
"""
import sqlite3
import statistics
from utils.db_schema import get_db_path


# ── Internal helpers ─────────────────────────────────────────────────────────

def _fetchall(sql: str, params: tuple = ()) -> list[dict]:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _safe_mean(values: list) -> float:
    vals = [v for v in values if v is not None]
    return statistics.mean(vals) if vals else 0.0


def _safe_median(values: list) -> float:
    vals = [v for v in values if v is not None]
    return statistics.median(vals) if vals else 0.0


def _iqr(values: list) -> float:
    """Interquartile Range = Q3 - Q1."""
    vals = sorted(v for v in values if v is not None)
    n = len(vals)
    if n < 2:
        return 0.0
    q1 = statistics.median(vals[: n // 2])
    q3 = statistics.median(vals[(n + 1) // 2 :])
    return round(q3 - q1, 4)


def _mrr(first_ranks: list) -> float:
    """Mean Reciprocal Rank — first_relevant_rank_l1 (999 = not found → 0)."""
    vals = [v for v in first_ranks if v is not None]
    if not vals:
        return 0.0
    return round(statistics.mean(1.0 / v if v < 999 else 0.0 for v in vals), 4)


# ── 1. Retrieval Statistics ───────────────────────────────────────────────────

def compute_retrieval_statistics() -> dict:
    """
    Thống kê retrieval cho từng chunking_strategy.
    Chỉ dùng rag_mode = 'rag_grader'.

    Returns
    -------
    dict: {chunking_strategy → {metric: value}}
    """
    rows = _fetchall(
        """
        SELECT
            chunking_strategy,
            hit_at_1_l1, hit_at_3_l1, hit_at_5_l1,
            recall_at_1_l1, recall_at_3_l1, recall_at_5_l1,
            first_relevant_rank_l1,
            grader_score_l1,
            best_similarity_l1,
            retrieval_success_grader_l1
        FROM benchmark_runs
        WHERE rag_mode = 'rag_grader'
        """
    )

    # Group by chunking_strategy
    groups: dict[str, list[dict]] = {}
    for r in rows:
        key = r["chunking_strategy"]
        groups.setdefault(key, []).append(r)

    result = {}
    for strategy, items in groups.items():
        def col(k):
            return [r[k] for r in items]

        grader_scores = col("grader_score_l1")
        result[strategy] = {
            "n":                        len(items),
            "hit_at_1_mean":            round(_safe_mean(col("hit_at_1_l1")), 4),
            "hit_at_3_mean":            round(_safe_mean(col("hit_at_3_l1")), 4),
            "hit_at_5_mean":            round(_safe_mean(col("hit_at_5_l1")), 4),
            "recall_at_1_mean":         round(_safe_mean(col("recall_at_1_l1")), 4),
            "recall_at_3_mean":         round(_safe_mean(col("recall_at_3_l1")), 4),
            "recall_at_5_mean":         round(_safe_mean(col("recall_at_5_l1")), 4),
            "mrr":                      _mrr(col("first_relevant_rank_l1")),
            "grader_score_mean":        round(_safe_mean(grader_scores), 4),
            "grader_score_median":      _safe_median(grader_scores),
            "grader_score_iqr":         _iqr(grader_scores),
            "retrieval_success_rate":   round(_safe_mean(col("retrieval_success_grader_l1")), 4),
            "best_similarity_l1_mean":  round(_safe_mean(col("best_similarity_l1")), 4),
        }

    return result


# ── 2. Generation Statistics ──────────────────────────────────────────────────

def compute_generation_statistics() -> dict:
    """
    Thống kê generation: join benchmark_runs ← evaluation_results.
    Chỉ dùng rag_mode = 'pure_rag'.

    Khi chưa có đủ evaluation_results, các accuracy metrics sẽ là 0.

    Returns
    -------
    dict: {metric: value}
    """
    # Runs với evaluation
    eval_rows = _fetchall(
        """
        SELECT
            br.chunking_strategy,
            br.retrieval_time_ms,
            br.generation_time_ms,
            br.total_time_ms,
            br.prompt_tokens,
            br.completion_tokens,
            br.total_tokens,
            br.context_char_count,
            br.final_answer_length,
            er.answer_accuracy,
            er.citation_accuracy
        FROM benchmark_runs br
        LEFT JOIN evaluation_results er ON er.run_id = br.id
        WHERE br.rag_mode = 'pure_rag'
        """
    )

    # All pure_rag runs (for latency/token even without eval)
    all_rows = _fetchall(
        """
        SELECT
            retrieval_time_ms, generation_time_ms, total_time_ms,
            prompt_tokens, completion_tokens, total_tokens,
            context_char_count, final_answer_length
        FROM benchmark_runs
        WHERE rag_mode = 'pure_rag'
        """
    )

    def col(rows, k):
        return [r[k] for r in rows if r[k] is not None]

    # Accuracy only from evaluated rows
    acc_vals  = [r["answer_accuracy"]  for r in eval_rows if r["answer_accuracy"]  is not None]
    cite_vals = [r["citation_accuracy"] for r in eval_rows if r["citation_accuracy"] is not None]

    return {
        "n_runs":                       len(all_rows),
        "n_evaluated":                  len(acc_vals),
        # Accuracy (Ordinal → Mean + Median)
        "answer_accuracy_mean":         round(_safe_mean(acc_vals), 4),
        "answer_accuracy_median":       _safe_median(acc_vals),
        "citation_accuracy_mean":       round(_safe_mean(cite_vals), 4),
        # Latency (ms)
        "retrieval_time_ms_mean":       round(_safe_mean(col(all_rows, "retrieval_time_ms")), 2),
        "generation_time_ms_mean":      round(_safe_mean(col(all_rows, "generation_time_ms")), 2),
        "total_time_ms_mean":           round(_safe_mean(col(all_rows, "total_time_ms")), 2),
        # Tokens
        "prompt_tokens_mean":           round(_safe_mean(col(all_rows, "prompt_tokens")), 2),
        "completion_tokens_mean":       round(_safe_mean(col(all_rows, "completion_tokens")), 2),
        "total_tokens_mean":            round(_safe_mean(col(all_rows, "total_tokens")), 2),
        # Context
        "context_char_count_mean":      round(_safe_mean(col(all_rows, "context_char_count")), 2),
        "final_answer_length_mean":     round(_safe_mean(col(all_rows, "final_answer_length")), 2),
    }


# ── 3. Agent Improvement Statistics ──────────────────────────────────────────

def compute_agent_statistics() -> dict:
    """
    Thống kê cải thiện của agentic_light so với L1 baseline.
    Chỉ dùng rag_mode = 'agentic_light'.

    Returns
    -------
    dict: {metric: value}
    """
    rows = _fetchall(
        """
        SELECT
            attempts,
            rewrite_activated,
            grader_score_l1, grader_score_l2,
            recall_at_5_l1,  recall_at_5_l2,
            best_similarity_l1, best_similarity_l2
        FROM benchmark_runs
        WHERE rag_mode = 'agentic_light'
        """
    )

    if not rows:
        return {
            "n_runs": 0,
            "note": "Chua co du lieu rag_mode=agentic_light trong DB",
        }

    def col(k):
        return [r[k] for r in rows if r[k] is not None]

    rewrite_vals  = col("rewrite_activated")
    attempts_vals = col("attempts")

    grader_l1 = col("grader_score_l1")
    grader_l2 = col("grader_score_l2")
    grader_improvements = [
        b - a
        for a, b in zip(grader_l1, grader_l2)
        if a is not None and b is not None
    ]

    recall_l1 = col("recall_at_5_l1")
    recall_l2 = col("recall_at_5_l2")
    recall_improvements = [
        b - a
        for a, b in zip(recall_l1, recall_l2)
        if a is not None and b is not None
    ]

    sim_l1 = col("best_similarity_l1")
    sim_l2 = col("best_similarity_l2")
    sim_improvements = [
        b - a
        for a, b in zip(sim_l1, sim_l2)
        if a is not None and b is not None
    ]

    attempts_1 = sum(1 for v in attempts_vals if v == 1)
    attempts_2 = sum(1 for v in attempts_vals if v == 2)

    return {
        "n_runs":                        len(rows),
        # Rewrite
        "rewrite_activation_rate":       round(_safe_mean(rewrite_vals), 4),
        "rewrite_count":                 sum(1 for v in rewrite_vals if v == 1),
        # Grader improvement (Ordinal → report Mean + Median)
        "grader_improvement_mean":       round(_safe_mean(grader_improvements), 4),
        "grader_improvement_median":     _safe_median(grader_improvements),
        "grader_improvement_iqr":        _iqr(grader_improvements),
        # Recall@5 improvement
        "recall_at_5_improvement_mean":  round(_safe_mean(recall_improvements), 4),
        "recall_at_5_improvement_median": _safe_median(recall_improvements),
        # Similarity improvement
        "similarity_improvement_mean":   round(_safe_mean(sim_improvements), 4),
        "similarity_improvement_median": _safe_median(sim_improvements),
        # Attempt distribution
        "attempts_1_count":              attempts_1,
        "attempts_2_count":              attempts_2,
        "attempts_1_pct":                round(attempts_1 / len(rows) * 100, 1) if rows else 0.0,
        "attempts_2_pct":                round(attempts_2 / len(rows) * 100, 1) if rows else 0.0,
    }
