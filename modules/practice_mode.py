"""
modules/practice_mode.py — M7
Interactive practice: AI asks → user answers → AI grades + explains.
Supports text answers and code submission.
"""
import json
from core.retrieval.hybrid_retriever import hybrid_search
from core.pipeline.answer_generator import generate
from utils.db_schema import get_connection
from datetime import datetime


ASK_SYSTEM = (
    "Bạn là giáo viên dạy DSA. Hãy ra một bài tập thực hành về chủ đề được yêu cầu.\n"
    "Bài tập phải:\n"
    "- Rõ ràng, có input/output mẫu nếu là bài code\n"
    "- Phù hợp độ khó được chỉ định\n"
    "- Có thể là: giải thích khái niệm, viết code, phân tích complexity\n"
    "Chỉ ra đề bài, không giải trước."
)

GRADE_SYSTEM = (
    "Bạn là giáo viên chấm bài. Với bài làm của học sinh, hãy:\n"
    "1. Đánh giá điểm từ 0-10\n"
    "2. Nhận xét: điểm đúng, điểm sai, điểm cần cải thiện\n"
    "3. Đưa ra đáp án/giải pháp tốt hơn nếu cần\n"
    "Trả lời bằng tiếng Việt, dùng Markdown."
)


def generate_question(
    topic: str,
    subject_id: str,
    difficulty: str = "medium",
    question_type: str = "code",  # 'code' | 'text'
) -> str:
    """Generate a practice question for the given topic."""
    chunks = hybrid_search(topic, subject_id, top_k=3)
    context = "\n\n".join(c["text"] for c in chunks)

    user = (
        f"Chủ đề: {topic}\n"
        f"Loại bài: {'Viết code C/C++' if question_type == 'code' else 'Giải thích/phân tích'}\n"
        f"Độ khó: {difficulty}\n\n"
        f"Tài liệu:\n{context}\n\n"
        f"Ra đề bài thực hành."
    )
    return generate(ASK_SYSTEM, user, stream=False)


def grade_answer(
    question: str,
    user_answer: str,
    topic: str,
    subject_id: str,
    question_type: str = "code",
) -> tuple[float, str]:
    """
    Grade user's answer. Returns (score 0-10, feedback string).
    """
    user = (
        f"Đề bài:\n{question}\n\n"
        f"Bài làm của học sinh:\n{user_answer}\n\n"
        f"Hãy chấm bài và cho điểm."
    )
    feedback = generate(GRADE_SYSTEM, user, stream=False)

    # Extract score (simple heuristic: look for digit/10 pattern)
    import re
    score_match = re.search(r'(\d+(?:\.\d+)?)\s*/\s*10', feedback)
    score = float(score_match.group(1)) if score_match else 5.0

    _save(question, user_answer, score, feedback, topic, question_type, subject_id)
    return score, feedback


def _save(question, answer, score, feedback, topic_id, q_type, subject_id):
    conn = get_connection()
    conn.execute(
        "INSERT INTO practice_sessions "
        "(timestamp, subject_id, topic_id, type, question, user_answer, score, feedback) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), subject_id, topic_id,
         q_type, question, answer, score, feedback)
    )
    conn.commit()
    conn.close()
