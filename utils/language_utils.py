"""Lightweight language detection for RAG response routing."""
import re

_VI_DIACRITICS = re.compile(
    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]",
    re.IGNORECASE,
)

_VI_MARKERS = re.compile(
    r"\b("
    r"là gì|la gi|là ai|la ai|như thế nào|nhu the nao|tại sao|tai sao|"
    r"vì sao|vi sao|khác nhau|khac nhau|so sánh|so sanh|giải thích|giai thich|"
    r"định nghĩa|dinh nghia|cho biết|cho biet|hãy|hay|không|khong|"
    r"trong|của|cua|các|cac|này|nay|đó|do|với|voi|và|va|hay|hoặc|hoac|"
    r"thuật toán|thuat toan|giải thuật|giai thuat|môn học|mon hoc|tài liệu|tai lieu"
    r")\b",
    re.IGNORECASE,
)


def is_vietnamese(text: str) -> bool:
    if not text or not text.strip():
        return False
    if _VI_DIACRITICS.search(text):
        return True
    return bool(_VI_MARKERS.search(text))


def detect_language(text: str) -> str:
    return "vi" if is_vietnamese(text) else "en"


def detect_response_language(query: str, context_chunks: list[dict] | None = None) -> str:
    """Prefer the question language; fall back to document language when ambiguous."""
    if is_vietnamese(query):
        return "vi"
    if context_chunks:
        sample = " ".join((c.get("text") or "")[:300] for c in context_chunks[:3])
        if sample.strip() and is_vietnamese(sample):
            return "vi"
    return "en"
