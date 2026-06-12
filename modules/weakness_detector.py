"""Weakness detection helpers for the study agent."""
from typing import List

from utils.db_schema import get_connection
from utils.subject_loader import get_topic


def get_weak_topics(subject_id: str) -> List[dict]:
    """Return weak topics for a subject based on quiz and practice history."""
    conn = get_connection()
    cur = conn.cursor()

    weak_data = {}

    cur.execute(
        """
        SELECT topic_id,
               COUNT(*) AS attempts,
               SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) AS wrong
        FROM quiz_sessions
        WHERE subject_id = ?
          AND topic_id IS NOT NULL
        GROUP BY topic_id
        """,
        (subject_id,)
    )
    for row in cur.fetchall():
        topic_id = row[0]
        weak_data[topic_id] = {
            "topic_id": topic_id,
            "attempts": int(row[1]),
            "wrong": int(row[2] or 0),
        }

    cur.execute(
        """
        SELECT topic_id,
               COUNT(*) AS attempts,
               SUM(CASE
                       WHEN score IS NULL THEN 1
                       WHEN score < 0.7 THEN 1
                       ELSE 0
                   END) AS wrong
        FROM practice_sessions
        WHERE subject_id = ?
          AND topic_id IS NOT NULL
        GROUP BY topic_id
        """,
        (subject_id,)
    )
    for row in cur.fetchall():
        topic_id = row[0]
        practice_attempts = int(row[1])
        practice_wrong = int(row[2] or 0)
        if topic_id in weak_data:
            weak_data[topic_id]["attempts"] += practice_attempts
            weak_data[topic_id]["wrong"] += practice_wrong
        else:
            weak_data[topic_id] = {
                "topic_id": topic_id,
                "attempts": practice_attempts,
                "wrong": practice_wrong,
            }

    # Compute wrong rate and sort by severity.
    results = []
    for data in weak_data.values():
        attempts = data["attempts"]
        if attempts == 0:
            continue
        wrong = data["wrong"]
        data["wrong_rate"] = wrong / attempts
        results.append(data)

    results.sort(key=lambda item: (-item["wrong_rate"], -item["wrong"], item["topic_id"]))
    return results


def generate_review_plan(weak_topics: List[dict], subject_id: str) -> str:
    """Generate a simple review plan from weak topics."""
    if not weak_topics:
        return "Không có đủ dữ liệu để tạo kế hoạch ôn tập. Hãy làm thêm bài Quiz hoặc Practice trước nhé."

    lines = [
        "Kế hoạch ôn tập cá nhân hóa:"
    ]

    for index, topic_data in enumerate(weak_topics, start=1):
        topic_id = topic_data["topic_id"]
        topic_info = get_topic(subject_id, topic_id)
        topic_name = topic_info["name"] if topic_info else topic_id

        wrong_rate = topic_data["wrong_rate"]
        difficulty = "Rất yếu" if wrong_rate >= 0.6 else "Cần cải thiện" if wrong_rate >= 0.3 else "Nhẹ"

        lines.append(
            f"{index}. {topic_name} ({topic_id}) - {topic_data['wrong']} sai / {topic_data['attempts']} thử ({wrong_rate*100:.0f}%). {difficulty}."
        )
        lines.append(
            "   - Học lại lý thuyết chính, xem ví dụ mẫu và làm thêm ít nhất 3 bài tập liên quan."
        )
        lines.append(
            "   - Nếu là bài code, viết lại giải pháp và kiểm tra từng bước."
        )

    lines.append("")
    lines.append("Gợi ý chung:")
    lines.append("- Bắt đầu với chủ đề có tỷ lệ sai cao nhất.")
    lines.append("- Ghi chú lại lỗi, xác định nguyên nhân và ôn lại các khái niệm liên quan.")
    lines.append("- Tận dụng Flashcards hoặc ghi chú nhanh để ôn lại sau mỗi buổi học.")

    return "\n".join(lines)
