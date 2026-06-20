"""
tools/evaluation_workbench.py
Phase 18 — Manual Evaluation Assistant Tool.

Cung cấp các hàm hỗ trợ chấm điểm thủ công hàng loạt:
  - load_pending_runs()        : Danh sách run chưa được chấm
  - get_next_unevaluated_run() : Run ID nhỏ nhất chưa chấm
  - save_evaluation()          : Validate + ghi kết quả
  - evaluation_progress()      : Thống kê tiến độ chấm

Không sửa pipeline RAG, retrieval, grader, orchestrator,
benchmark_runs, evaluation_results schema.
"""
import sqlite3
from utils.db_schema import get_db_path
from utils.evaluation_logger import insert_evaluation_result
from utils.benchmark_loader import load_benchmark_questions


# ── Internal helper ──────────────────────────────────────────────────────────

def _get_ground_truth_map() -> dict:
    """Trả về {question_id (str/int) → ground_truth_answer}."""
    questions = load_benchmark_questions()
    return {str(q["id"]): q.get("ground_truth_answer", "") for q in questions}


# ── 1. load_pending_runs ──────────────────────────────────────────────────────

def load_pending_runs() -> list[dict]:
    """
    Lấy toàn bộ benchmark_runs chưa được chấm điểm.

    Dùng LEFT JOIN evaluation_results để tìm các run chưa có bản ghi.

    Returns
    -------
    list[dict] với các key:
        run_id, question_id, query, final_answer,
        ground_truth_answer, chunking_strategy, rag_mode
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            br.id            AS run_id,
            br.question_id,
            br.query,
            br.final_answer,
            br.chunking_strategy,
            br.rag_mode
        FROM benchmark_runs br
        LEFT JOIN evaluation_results er ON er.run_id = br.id
        WHERE er.id IS NULL
        ORDER BY br.id ASC
        """
    )
    rows = cur.fetchall()
    conn.close()

    gt_map = _get_ground_truth_map()

    return [
        {
            "run_id":               row["run_id"],
            "question_id":          row["question_id"],
            "query":                row["query"],
            "final_answer":         row["final_answer"],
            "ground_truth_answer":  gt_map.get(str(row["question_id"]), ""),
            "chunking_strategy":    row["chunking_strategy"],
            "rag_mode":             row["rag_mode"],
        }
        for row in rows
    ]


# ── 2. get_next_unevaluated_run ───────────────────────────────────────────────

def get_next_unevaluated_run() -> dict | None:
    """
    Trả về run có ID nhỏ nhất chưa được chấm điểm.

    Hỗ trợ workflow tuần tự:
        Đọc câu hỏi → đọc ground truth → đọc final answer
        → chấm điểm → lưu → chuyển câu tiếp theo

    Returns
    -------
    dict hoặc None nếu tất cả đã được chấm.
    """
    pending = load_pending_runs()
    if not pending:
        return None
    return pending[0]


# ── 3. save_evaluation ────────────────────────────────────────────────────────

def save_evaluation(
    run_id: int,
    answer_accuracy: int,
    citation_accuracy: float,
    notes: str = "",
    evaluator: str = "student",
) -> int:
    """
    Validate rồi ghi kết quả đánh giá thủ công.

    Validation
    ----------
    answer_accuracy  : phải thuộc [0..5]  → ValueError nếu sai
    citation_accuracy: phải thuộc [0.0..1.0] → ValueError nếu sai

    Returns
    -------
    int: eval_id vừa insert
    """
    # Validate
    if not isinstance(answer_accuracy, int) or not (0 <= answer_accuracy <= 5):
        raise ValueError(
            f"answer_accuracy phải là int trong [0..5], nhận: {answer_accuracy!r}"
        )
    if not (0.0 <= float(citation_accuracy) <= 1.0):
        raise ValueError(
            f"citation_accuracy phải trong [0.0..1.0], nhận: {citation_accuracy!r}"
        )

    return insert_evaluation_result(
        run_id            = run_id,
        answer_accuracy   = answer_accuracy,
        citation_accuracy = float(citation_accuracy),
        notes             = notes,
        evaluator         = evaluator,
    )


# ── 4. evaluation_progress ────────────────────────────────────────────────────

def evaluation_progress() -> dict:
    """
    Trả về thống kê tiến độ chấm điểm.

    Returns
    -------
    {
        "total_runs":     int,
        "evaluated_runs": int,
        "remaining_runs": int,
    }
    """
    conn = sqlite3.connect(get_db_path())
    cur  = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM benchmark_runs")
    total = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(DISTINCT er.run_id)
        FROM evaluation_results er
        INNER JOIN benchmark_runs br ON br.id = er.run_id
        """
    )
    evaluated = cur.fetchone()[0]
    conn.close()

    return {
        "total_runs":     total,
        "evaluated_runs": evaluated,
        "remaining_runs": total - evaluated,
    }
