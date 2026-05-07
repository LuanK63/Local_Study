"""
modules/weakness_detector.py — M8
Analyze quiz/practice history to find weak topics and suggest review.
"""
import json
from collections import defaultdict
from utils.db_schema import get_connection
from core.pipeline.answer_generator import generate


def get_weak_topics(subject_id: str, min_attempts: int = 2) -> list[dict]:
    """
    Analyze quiz history for a subject.
    Returns list of {topic_id, attempts, wrong_count, wrong_rate} sorted by weak first.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT topic_id, is_correct FROM quiz_sessions WHERE subject_id = ?",
        (subject_id,)
    ).fetchall()
    conn.close()

    stats: dict[str, dict] = defaultdict(lambda: {"attempts": 0, "wrong": 0})
    for row in rows:
        tid = row["topic_id"] or "unknown"
        stats[tid]["attempts"] += 1
        if not row["is_correct"]:
            stats[tid]["wrong"] += 1

    # Practice sessions
    conn = get_connection()
    prows = conn.execute(
        "SELECT topic_id, score FROM practice_sessions WHERE subject_id = ?",
        (subject_id,)
    ).fetchall()
    conn.close()
    for row in prows:
        tid = row["topic_id"] or "unknown"
        stats[tid]["attempts"] += 1
        if (row["score"] or 10) < 6.0:
            stats[tid]["wrong"] += 1

    weak = []
    for tid, s in stats.items():
        if s["attempts"] >= min_attempts:
            rate = s["wrong"] / s["attempts"]
            weak.append({
                "topic_id":   tid,
                "attempts":   s["attempts"],
                "wrong":      s["wrong"],
                "wrong_rate": round(rate, 2),
            })

    return sorted(weak, key=lambda x: x["wrong_rate"], reverse=True)


def generate_review_plan(weak_topics: list[dict], subject_id: str) -> str:
    """Generate a personalized review plan based on detected weaknesses."""
    if not weak_topics:
        return "✅ Không phát hiện điểm yếu rõ ràng. Hãy tiếp tục luyện tập!"

    topic_list = "\n".join(
        f"- {t['topic_id']}: {t['wrong']}/{t['attempts']} sai ({t['wrong_rate']*100:.0f}%)"
        for t in weak_topics[:5]
    )
    system = (
        "Bạn là cố vấn học tập. Dựa vào thống kê điểm yếu của học sinh, "
        "hãy đề xuất kế hoạch ôn tập cụ thể, ưu tiên các chủ đề yếu nhất. "
        "Gợi ý cả phương pháp ôn tập phù hợp. Dùng Markdown."
    )
    user = f"Điểm yếu của học sinh (môn {subject_id}):\n{topic_list}\n\nĐề xuất kế hoạch ôn tập."
    return generate(system, user, stream=False)
