"""
modules/weakness_detector.py
Analyze quiz/practice history to find weak topics and suggest review using AI.
"""
from typing import List
from utils.db_schema import get_connection
from utils.subject_loader import get_topic
from core.pipeline.answer_generator import generate


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
    """Generate a personalized review plan based on detected weaknesses using LLM."""
    if not weak_topics:
        return " Không phát hiện điểm yếu rõ ràng. Hãy tiếp tục luyện tập!"

    # We can fetch human-readable names to make the LLM prompt more informative
    topic_lines = []
    for t in weak_topics[:5]:
        topic_id = t["topic_id"]
        topic_info = get_topic(subject_id, topic_id)
        topic_name = topic_info["name"] if topic_info else topic_id
        topic_lines.append(
            f"- {topic_name} ({topic_id}): {t['wrong']}/{t['attempts']} sai ({t['wrong_rate']*100:.0f}%)"
        )
    topic_list = "\n".join(topic_lines)

    system = (
        "Bạn là cố vấn học tập. Dựa vào thống kê điểm yếu của học sinh, "
        "hãy đề xuất kế hoạch ôn tập cụ thể, ưu tiên các chủ đề yếu nhất. "
        "Gợi ý cả phương pháp ôn tập phù hợp. Dùng Markdown."
    )
    user = f"Điểm yếu của học sinh (môn {subject_id}):\n{topic_list}\n\nĐề xuất kế hoạch ôn tập."
    
    try:
        plan = generate(system, user, stream=False)
        if isinstance(plan, str):
            return plan
        return "Không thể khởi tạo kế hoạch ôn tập lúc này."
    except Exception as e:
        return f"Lỗi lập kế hoạch ôn tập: {e}"
