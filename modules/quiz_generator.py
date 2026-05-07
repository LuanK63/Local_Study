"""
modules/quiz_generator.py — M6
Generate Multiple Choice Questions (MCQ) from topic/document.
Returns structured JSON quiz sessions.
"""
import json
import re
from core.retrieval.hybrid_retriever import hybrid_search
from core.pipeline.answer_generator import generate, generate_with_context
from utils.db_schema import get_connection
from datetime import datetime


SYSTEM = (
    "Bạn là giáo viên tạo đề kiểm tra. Hãy tạo câu hỏi trắc nghiệm (MCQ) theo định dạng JSON sau:\n"
    '[\n'
    '  {\n'
    '    "question": "Câu hỏi...",\n'
    '    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],\n'
    '    "correct": "A",\n'
    '    "explanation": "Giải thích tại sao đáp án đúng..."\n'
    '  }\n'
    ']\n'
    "Chỉ trả về JSON, không thêm text khác. "
    "Câu hỏi phải tập trung vào: độ phức tạp, cách hoạt động, khi nào dùng."
)


def generate_quiz(
    topic: str,
    subject_id: str,
    num_questions: int = 5,
    difficulty: str = "medium",
) -> list[dict]:
    """
    Generate quiz questions for a topic.
    Returns list of {question, options, correct, explanation}.
    """
    # Get context from documents
    chunks = hybrid_search(topic, subject_id, top_k=4)
    context_parts = [c["text"] for c in chunks]
    context = "\n\n".join(context_parts)

    user = (
        f"Chủ đề: {topic}\n"
        f"Độ khó: {difficulty}\n"
        f"Số câu: {num_questions}\n\n"
        f"Tài liệu tham khảo:\n{context}\n\n"
        f"Tạo {num_questions} câu hỏi MCQ."
    )

    raw = generate(SYSTEM, user, stream=False)
    questions = _parse_json(raw)
    return questions


def _parse_json(raw: str) -> list[dict]:
    """Extract JSON array from LLM output."""
    # Find JSON array
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return []


def save_quiz_result(
    question: str,
    options: list,
    correct: str,
    user_answer: str,
    explanation: str,
    topic_id: str,
    subject_id: str,
):
    is_correct = 1 if user_answer.upper() == correct.upper() else 0
    conn = get_connection()
    conn.execute(
        "INSERT INTO quiz_sessions "
        "(timestamp, subject_id, topic_id, question, options, correct_answer, "
        "user_answer, is_correct, explanation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.now().isoformat(), subject_id, topic_id,
            question, json.dumps(options), correct,
            user_answer, is_correct, explanation
        )
    )
    conn.commit()
    conn.close()
    return is_correct
