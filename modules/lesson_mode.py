"""
modules/lesson_mode.py — Lesson Mode Backend
RAG-based lesson generation (8-12 interactive questions) and database persistence.
"""
import json
import re
from datetime import datetime

SYSTEM_PROMPT = (
    "Bạn là giáo viên tạo bài học (Lesson Mode). Hãy tạo một danh sách gồm 8-12 câu hỏi ngắn (micro-learning) "
    "xoay quanh chủ đề được yêu cầu dưới dạng JSON array.\n"
    "Các câu hỏi chỉ được dựa trên tài liệu tham khảo (Context) được cung cấp, không tự suy diễn.\n"
    "Phân bổ hợp lý các câu hỏi theo 6 loại sau:\n"
    "1. multiple_choice: options là danh sách 4 lựa chọn, correct là nhãn đáp án đúng ('A', 'B', 'C' hoặc 'D').\n"
    "2. true_false: correct là 'Đúng' hoặc 'Sai'.\n"
    "3. fill_blank: câu hỏi chứa vị trí điền khuyết biểu diễn bằng '________', correct là đáp án điền đúng.\n"
    "4. matching: left_items (3 mục bên trái), right_items (3 mục bên phải), correct_pairs là dictionary tương ứng giữa left và right.\n"
    "5. ordering: items là danh sách các bước cần sắp xếp, correct_order là danh sách index số nguyên biểu thị thứ tự đúng (ví dụ: [0, 1, 2]).\n"
    "6. output_prediction: câu hỏi kèm code ngắn (code tối đa 5 dòng), language là ngôn ngữ lập trình, correct là kết quả stdout chính xác.\n\n"
    "Yêu cầu phân bố độ khó hợp lý ('easy', 'medium', 'hard') cho các câu hỏi.\n"
    "Chỉ trả về JSON array, không thêm văn bản giải thích ngoài khối JSON."
)


def generate_lesson(
    topic: str,
    subject_id: str,
    difficulty: str = "medium",
) -> list[dict]:
    """Generate a lesson session (8-12 questions) for a topic using RAG."""
    from core.retrieval.hybrid_retriever import hybrid_search
    from core.pipeline.answer_generator import generate
    import random

    try:
        chunks = hybrid_search(topic, subject_id, top_k=6)
        if chunks:
            random.shuffle(chunks)
            selected_chunks = chunks[:4]
        else:
            selected_chunks = []

        context = "\n\n".join(c["text"] for c in selected_chunks)

        user_prompt = (
            f"Chủ đề: {topic}\n"
            f"Độ khó chung đề xuất: {difficulty}\n\n"
            f"Tài liệu tham khảo (Context):\n{context}\n\n"
            f"Hãy tạo danh sách câu hỏi học tập ngắn (8-12 câu)."
        )

        raw_response = generate(SYSTEM_PROMPT, user_prompt, stream=False, temperature=0.7)
        questions = _parse_json(raw_response)
        if not questions:
            raise ValueError("Không thể tách hoặc phân tích được mảng JSON câu hỏi từ phản hồi của LLM.")
        return questions
    except Exception as e:
        print(f"[ERROR] generate_lesson failed: {e}")
        raise e


def _parse_json(raw: str) -> list[dict]:
    """Extract and validate JSON array from LLM response."""
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group())
        if isinstance(data, list):
            return data
        return []
    except json.JSONDecodeError:
        return []


def save_lesson_session(
    subject_id: str,
    topic_id: str,
    score: float,
    total_questions: int,
    correct_answers: int,
    duration: int,
) -> int:
    """Save summary of a lesson session and return its auto-increment ID."""
    from utils.db_schema import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO lesson_sessions "
        "(timestamp, subject_id, topic_id, score, total_questions, correct_answers, duration) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.now().isoformat(),
            subject_id,
            topic_id,
            score,
            total_questions,
            correct_answers,
            duration
        )
    )
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return session_id


def save_lesson_answer(
    session_id: int,
    question_index: int,
    question_type: str,
    topic_id: str,
    difficulty: str,
    user_answer: str,
    correct_answer: str,
    is_correct: int,
    time_spent: int,
):
    """Save detailed answers for each question within a lesson session."""
    from utils.db_schema import get_connection
    conn = get_connection()
    conn.execute(
        "INSERT INTO lesson_answers "
        "(lesson_session_id, question_index, question_type, topic_id, difficulty, user_answer, correct_answer, is_correct, time_spent) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            session_id,
            question_index,
            question_type,
            topic_id,
            difficulty,
            user_answer,
            correct_answer,
            is_correct,
            time_spent
        )
    )
    conn.commit()
    conn.close()


def get_topics_progress(subject_id: str) -> dict[str, dict]:
    """Query progress stats (highest score, sessions count) for each topic under the subject.

    Returns: dict mapping topic_id -> {'max_score': float, 'attempts': int, 'status': str}
    """
    from utils.db_schema import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT topic_id, MAX(score), COUNT(*) FROM lesson_sessions "
            "WHERE subject_id = ? "
            "GROUP BY topic_id",
            (subject_id,)
        )
        rows = cursor.fetchall()
    except Exception as e:
        print(f"[ERROR] get_topics_progress failed: {e}")
        rows = []
    finally:
        conn.close()

    progress = {}
    for topic_id, max_score, attempts in rows:
        status = "completed" if max_score >= 7.0 else "needs_review"
        progress[topic_id] = {
            "max_score": round(max_score, 1),
            "attempts": attempts,
            "status": status
        }
    return progress
