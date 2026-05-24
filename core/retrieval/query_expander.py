"""
core/retrieval/query_expander.py
Hai kỹ thuật cải thiện retrieval recall:

1. Multi-query expansion  — tạo N biến thể câu hỏi để search song song
2. HyDE (Hypothetical Document Embeddings) — tạo câu TRẢ LỜI giả,
   embed câu trả lời đó để search thay vì embed câu hỏi.

Tại sao HyDE hiệu quả hơn?
  Query: "stack là gì?"        → embedding của CÂU HỎI (dạng hỏi)
  Doc:   "Stack là danh sách..." → embedding của CÂU KHẲNG ĐỊNH
  → Similarity thấp dù nội dung liên quan

  HyDE: sinh ra "Stack là cấu trúc dữ liệu..." → embed → gần với doc hơn nhiều
"""
import re
import httpx
from utils.config import get_config


# ── System prompts ────────────────────────────────────────────────────────────

_EXPAND_SYSTEM = """\
Bạn là trợ lý tìm kiếm tài liệu học tập. Nhiệm vụ: tạo ra các cách diễn đạt khác nhau \
của câu hỏi để tìm kiếm tài liệu hiệu quả hơn.

QUY TẮC:
- Mỗi biến thể giữ nguyên ý nghĩa gốc nhưng dùng từ ngữ / góc độ khác.
- Chỉ trả về danh sách câu hỏi, mỗi câu một dòng, không đánh số, không giải thích.
- Viết bằng cùng ngôn ngữ với câu hỏi gốc.
- Có thể thêm thuật ngữ kỹ thuật liên quan để tăng khả năng tìm kiếm.\
"""

_HYDE_SYSTEM = """\
Bạn là chuyên gia về khoa học máy tính. Hãy viết một đoạn văn ngắn (2-4 câu) trả lời \
câu hỏi sau như thể bạn đang viết cho giáo trình đại học.

QUY TẮC:
- Viết dưới dạng định nghĩa/khẳng định, KHÔNG viết dưới dạng hỏi đáp.
- Dùng thuật ngữ kỹ thuật chính xác.
- Ngắn gọn, súc tích, không giải thích dài dòng.
- Viết bằng cùng ngôn ngữ với câu hỏi gốc.\
"""


# ── Internal LLM call ─────────────────────────────────────────────────────────

def _call_llm(system: str, user: str, timeout: int = 20) -> str | None:
    """Gọi Ollama với system + user prompt, trả về text hoặc None nếu lỗi."""
    cfg     = get_config()["llm"]
    payload = {
        "model":    cfg["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "options": {"temperature": 0},
        "stream":  False,
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(f"{cfg['base_url']}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()
    except Exception:
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def expand_query(query: str, n_variants: int | None = None) -> list[str]:
    """
    Tạo n_variants biến thể câu hỏi bằng LLM.
    Trả về [query_gốc, variant_1, variant_2, ...].

    Nếu query_expansion = false trong config hoặc LLM lỗi,
    trả về [query_gốc] để không làm hỏng pipeline chính.
    """
    cfg     = get_config()
    ret_cfg = cfg.get("retrieval", {})

    if not ret_cfg.get("query_expansion", True):
        return [query]

    n = n_variants if n_variants is not None else ret_cfg.get("query_variants", 2)

    raw = _call_llm(
        system=_EXPAND_SYSTEM,
        user=(
            f"Tạo ra đúng {n} cách diễn đạt khác cho câu hỏi sau:\n"
            f'"{query}"\n\n'
            f"Chỉ trả về {n} câu, mỗi câu một dòng, không đánh số:"
        ),
    )
    if not raw:
        return [query]

    variants: list[str] = []
    for line in raw.splitlines():
        line = re.sub(r'^[\d\.\-\*\s]+', '', line).strip()
        if line and line.lower() != query.lower():
            variants.append(line)

    return [query] + variants[:n]


def generate_hyde(query: str) -> str | None:
    """
    Sinh câu trả lời giả (Hypothetical Document) từ query để dùng cho HyDE search.
    Trả về string câu trả lời giả, hoặc None nếu tắt HyDE hoặc LLM lỗi.
    """
    cfg     = get_config()
    ret_cfg = cfg.get("retrieval", {})

    if not ret_cfg.get("hyde", True):
        return None

    return _call_llm(
        system=_HYDE_SYSTEM,
        user=f"Hãy viết câu trả lời giả cho câu hỏi: \"{query}\"",
    )
