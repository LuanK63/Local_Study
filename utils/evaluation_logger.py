"""
utils/evaluation_logger.py
Human Evaluation Layer — Phase 17.

Ghi kết quả chấm điểm thủ công vào:
  - SQLite: bảng evaluation_results
  - CSV:    data/experiments/evaluation_results.csv

Tách biệt hoàn toàn khỏi runtime benchmark pipeline.
Không sửa benchmark_runs, retrieval, generator, grader.
"""
import csv
import os
import sqlite3
from datetime import datetime, timezone

from utils.db_schema import get_db_path, init_db


# ── Path CSV ────────────────────────────────────────────────────────────────
def _get_csv_path() -> str:
    return os.path.join("data", "experiments", "evaluation_results.csv")


_CSV_HEADERS = [
    "id",
    "run_id",
    "evaluator",
    "answer_accuracy",
    "citation_accuracy",
    "notes",
    "evaluated_at",
]


def _ensure_csv(csv_path: str) -> None:
    """Tạo file CSV với header nếu chưa tồn tại."""
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    if not os.path.exists(csv_path):
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_CSV_HEADERS)
            writer.writeheader()


def _append_csv(csv_path: str, row: dict) -> None:
    """Append một dòng mới vào CSV."""
    _ensure_csv(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_HEADERS)
        writer.writerow({k: row.get(k, "") for k in _CSV_HEADERS})


# ── Core Functions ───────────────────────────────────────────────────────────

def insert_evaluation_result(
    run_id: int,
    answer_accuracy: int,
    citation_accuracy: float,
    notes: str = "",
    evaluator: str = "student",
) -> int:
    """
    Ghi một kết quả đánh giá thủ công vào evaluation_results.

    Parameters
    ----------
    run_id           : ID của benchmark_run cần đánh giá
    answer_accuracy  : Điểm trả lời (0–5 hoặc theo thang tự định nghĩa)
    citation_accuracy: Tỷ lệ trích dẫn đúng (0.0 – 1.0)
    notes            : Ghi chú tự do
    evaluator        : Người/công cụ đánh giá (mặc định 'student')

    Returns
    -------
    int: ID dòng vừa insert vào evaluation_results
    """
    # Đảm bảo DB và bảng đã tồn tại
    init_db()

    evaluated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = sqlite3.connect(get_db_path())
    cur  = conn.cursor()

    cur.execute(
        """
        INSERT INTO evaluation_results
            (run_id, evaluator, answer_accuracy, citation_accuracy, notes, evaluated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (run_id, evaluator, answer_accuracy, citation_accuracy, notes or "", evaluated_at),
    )
    eval_id = cur.lastrowid
    conn.commit()
    conn.close()

    # Export CSV
    csv_path = _get_csv_path()
    _append_csv(csv_path, {
        "id":               eval_id,
        "run_id":           run_id,
        "evaluator":        evaluator,
        "answer_accuracy":  answer_accuracy,
        "citation_accuracy": citation_accuracy,
        "notes":            notes or "",
        "evaluated_at":     evaluated_at,
    })

    print(f"[EvaluationLogger] Inserted eval id={eval_id} for run_id={run_id} → {csv_path}")
    return eval_id


def get_evaluation(run_id: int) -> dict | None:
    """
    Đọc kết quả đánh giá của một run_id.
    Trả về dict hoặc None nếu chưa được đánh giá.
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    cur.execute(
        """
        SELECT id, run_id, evaluator, answer_accuracy, citation_accuracy, notes, evaluated_at
        FROM evaluation_results
        WHERE run_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (run_id,),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        return None
    return dict(row)


def list_unevaluated_runs() -> list[dict]:
    """
    Trả về danh sách các benchmark_runs chưa có bản ghi trong evaluation_results.
    Mỗi phần tử là dict: {id, timestamp, question_id, query, rag_mode}
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    cur.execute(
        """
        SELECT br.id, br.timestamp, br.question_id, br.query, br.rag_mode
        FROM benchmark_runs br
        LEFT JOIN evaluation_results er ON er.run_id = br.id
        WHERE er.id IS NULL
        ORDER BY br.id ASC
        """
    )
    rows = cur.fetchall()
    conn.close()

    return [dict(row) for row in rows]
