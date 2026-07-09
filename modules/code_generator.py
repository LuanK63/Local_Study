"""
modules/code_generator.py — M4
Generates complete code with explanation from natural language description.
"""
from core.pipeline.answer_generator import generate
from utils.db_schema import get_connection
from datetime import datetime


SYSTEM = (
    "Bạn là lập trình viên chuyên nghiệp. Khi được yêu cầu viết code, hãy trả lời bằng Markdown gọn, dễ đọc:\n\n"
    "## [Tên thuật toán / bài toán]\n"
    "```[ngôn ngữ]\n"
    "[code đầy đủ, biên dịch được, comment ngắn gọn]\n"
    "```\n\n"
    "## Giải thích\n"
    "- 3–5 gạch đầu dòng ngắn về ý tưởng và các bước chính\n\n"
    "Quy tắc:\n"
    "- Code phải chạy được, có hàm main / ví dụ sử dụng khi phù hợp\n"
    "- Không phân tích độ phức tạp Big-O\n"
    "- Không lặp lại toàn bộ code trong phần giải thích\n"
    "- Dùng đúng ngôn ngữ được yêu cầu"
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
