"""
tools/export_evaluation_report.py
Phase 18 — Xuất CSV báo cáo đánh giá thủ công.

Xuất: data/experiments/evaluation_report.csv
Bao gồm:
    run_id, question_id, chunking_strategy, rag_mode,
    answer_accuracy, citation_accuracy

Không xuất toàn bộ benchmark fields.
Không thay đổi benchmark_log.csv hay evaluation_results.csv.
"""
import csv
import os
import sqlite3
from utils.db_schema import get_db_path


_REPORT_PATH = os.path.join("data", "experiments", "evaluation_report.csv")

_REPORT_HEADERS = [
    "run_id",
    "question_id",
    "chunking_strategy",
    "rag_mode",
    "answer_accuracy",
    "citation_accuracy",
    "evaluator",
    "notes",
    "evaluated_at",
]


def export_evaluation_report(output_path: str = _REPORT_PATH) -> int:
    """
    Xuất toàn bộ kết quả đánh giá đã ghi vào CSV.

    Nối benchmark_runs (lấy question_id, chunking_strategy, rag_mode)
    với evaluation_results (lấy điểm đánh giá).

    Parameters
    ----------
    output_path : đường dẫn file CSV đầu ra

    Returns
    -------
    int: số dòng được xuất (không kể header)
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    cur.execute(
        """
        SELECT
            er.run_id,
            br.question_id,
            br.chunking_strategy,
            br.rag_mode,
            er.answer_accuracy,
            er.citation_accuracy,
            er.evaluator,
            er.notes,
            er.evaluated_at
        FROM evaluation_results er
        INNER JOIN benchmark_runs br ON br.id = er.run_id
        ORDER BY er.run_id ASC
        """
    )
    rows = cur.fetchall()
    conn.close()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_REPORT_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in _REPORT_HEADERS})

    print(f"[ExportReport] Exported {len(rows)} rows → {output_path}")
    return len(rows)


if __name__ == "__main__":
    import sys
    import io
    if sys.platform.startswith("win"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    n = export_evaluation_report()
    print(f"Done. {n} rows exported to {_REPORT_PATH}")
