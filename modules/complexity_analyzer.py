"""
modules/complexity_analyzer.py — M5
Analyze Big-O time and space complexity from code or algorithm description.
"""
from core.pipeline.answer_generator import generate


SYSTEM = (
    "Bạn là chuyên gia phân tích thuật toán. Hãy phân tích complexity của code/thuật toán được đưa ra:\n\n"
    "**Time Complexity:** [Big-O notation + giải thích]\n"
    "**Space Complexity:** [Big-O notation + giải thích]\n"
    "**Phân tích chi tiết:**\n"
    "- Vòng lặp/đệ quy nào chiếm nhiều thời gian nhất?\n"
    "- Best case / Average case / Worst case\n"
    "- So sánh với các thuật toán tương tự nếu có\n\n"
    "Dùng Markdown. Ngắn gọn nhưng chính xác."
)


def analyze_complexity(code_or_description: str, is_code: bool = True) -> str:
    """
    Analyze complexity of code snippet or algorithm description.
    Returns markdown-formatted analysis.
    """
    if is_code:
        user = f"Phân tích complexity của code sau:\n\n```\n{code_or_description}\n```"
    else:
        user = f"Phân tích complexity của thuật toán: {code_or_description}"

    return generate(SYSTEM, user, stream=False)


def analyze_complexity_stream(code_or_description: str, is_code: bool = True):
    if is_code:
        user = f"Phân tích complexity của code sau:\n\n```\n{code_or_description}\n```"
    else:
        user = f"Phân tích complexity của thuật toán: {code_or_description}"
    return generate(SYSTEM, user, stream=True)
