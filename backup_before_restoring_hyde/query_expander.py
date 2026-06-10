"""
core/retrieval/query_expander.py
Multi-query expansion: dùng LLM tạo thêm N biến thể câu hỏi
để tăng recall khi retrieval.

Ví dụ:
  Input:  "Stack là gì?"
  Output: ["Stack là gì?",
           "Cấu trúc dữ liệu Stack hoạt động như thế nào?",
           "Định nghĩa và đặc điểm của Stack LIFO"]
"""
import re
import httpx
from utils.config import get_config


# ── System prompt ─────────────────────────────────────────────────────────────

_EXPAND_SYSTEM = """\
Bạn là trợ lý tìm kiếm tài liệu học tập. Nhiệm vụ: tạo ra các cách diễn đạt khác nhau \
của câu hỏi để tìm kiếm tài liệu hiệu quả hơn.

QUY TẮC:
- Mỗi biến thể giữ nguyên ý nghĩa gốc nhưng dùng từ ngữ / góc độ khác.
- Chỉ trả về danh sách câu hỏi, mỗi câu một dòng, không đánh số, không giải thích.
- Viết bằng cùng ngôn ngữ với câu hỏi gốc.
- Có thể thêm thuật ngữ kỹ thuật liên quan để tăng khả năng tìm kiếm.\
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
