"""
modules/code_generator.py — M4
Generates complete code with explanation from natural language description.
"""
from core.pipeline.answer_generator import generate
from utils.db_schema import get_connection
from datetime import datetime


SYSTEM = (
    "Bạn là lập trình viên chuyên nghiệp. Khi được yêu cầu viết code, hãy:\n"
    "1. Viết code đầy đủ, có comment giải thích\n"
    "2. Đảm bảo code biên dịch được và chạy đúng\n"
    "3. Sau code, giải thích ngắn gọn ý tưởng thuật toán\n"
    "4. Nêu Time Complexity và Space Complexity\n"
    "Ưu tiên C/C++ trừ khi được yêu cầu ngôn ngữ khác. Dùng Markdown."
)


def generate_code(description: str, language: str = "cpp", subject_id: str = "dsa") -> str:
    user = f"Yêu cầu: {description}\nNgôn ngữ: {language}"
    answer = generate(SYSTEM, user, stream=False)
    _save(description, answer, language, subject_id)
    return answer


def generate_code_stream(description: str, language: str = "cpp"):
    user = f"Yêu cầu: {description}\nNgôn ngữ: {language}"
    return generate(SYSTEM, user, stream=True)


def _save(description: str, answer: str, language: str, subject_id: str):
    import json
    conn = get_connection()
    conn.execute(
        "INSERT INTO conversations (timestamp, subject_id, module, query, answer, sources) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), subject_id, "code_generator",
         f"[{language}] {description}", answer, json.dumps([]))
    )
    conn.commit()
    conn.close()
