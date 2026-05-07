"""
modules/code_explainer.py — M3
Explains code line-by-line: logic flow, time complexity, edge cases.
"""
from core.pipeline.answer_generator import generate
from utils.db_schema import get_connection
from datetime import datetime


SYSTEM = (
    "Bạn là chuyên gia phân tích code. Với đoạn code được cung cấp, hãy:\n"
    "1. Giải thích từng phần/hàm chính\n"
    "2. Mô tả logic flow (input → xử lý → output)\n"
    "3. Phân tích Time Complexity và Space Complexity (Big-O)\n"
    "4. Chỉ ra các edge case và lỗi tiềm năng nếu có\n"
    "Trả lời bằng tiếng Việt, dùng Markdown."
)


def explain_code(code: str, language: str = "cpp", subject_id: str = "dsa") -> str:
    user = f"```{language}\n{code}\n```\n\nHãy giải thích đoạn code trên."
    answer = generate(SYSTEM, user, stream=False)
    _save(code, answer, language, subject_id)
    return answer


def explain_code_stream(code: str, language: str = "cpp"):
    """Returns a generator for streaming explanation."""
    user = f"```{language}\n{code}\n```\n\nHãy giải thích đoạn code trên."
    return generate(SYSTEM, user, stream=True)


def _save(code: str, answer: str, language: str, subject_id: str):
    import json
    conn = get_connection()
    conn.execute(
        "INSERT INTO conversations (timestamp, subject_id, module, query, answer, sources) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), subject_id, "code_explainer",
         f"[{language}] {code[:100]}...", answer, json.dumps([]))
    )
    conn.commit()
    conn.close()
