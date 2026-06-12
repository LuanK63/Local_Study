"""
core/pipeline/answer_generator.py
LLM answer generation via Ollama local API.
Strict RAG mode: only answers from provided context, always cites sources.
"""
import httpx
import json
from typing import Generator
from utils.config import get_config


def _get_llm_cfg() -> dict:
    return get_config()["llm"]


def _build_prompt(system: str, user: str) -> list[dict]:
    return [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ]


def generate(
    system_prompt: str,
    user_prompt: str,
    stream: bool = False,
) -> str | Generator[str, None, None]:
    cfg = _get_llm_cfg()
    payload = {
        "model":   cfg["model"],
        "messages": _build_prompt(system_prompt, user_prompt),
        "options": {"temperature": cfg["temperature"]},
        "stream":  stream,
    }
    url = f"{cfg['base_url']}/api/chat"
    if stream:
        return _stream(url, payload, cfg["timeout"])
    else:
        return _blocking(url, payload, cfg["timeout"])


def _blocking(url: str, payload: dict, timeout: int) -> str:
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, json={**payload, "stream": False})
        resp.raise_for_status()
        return resp.json()["message"]["content"]


def _stream(url: str, payload: dict, timeout: int) -> Generator[str, None, None]:
    with httpx.Client(timeout=timeout) as client:
        with client.stream("POST", url, json={**payload, "stream": True}) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue


_SYSTEM_PROMPT = """\
Bạn là trợ lý học tập. Nhiệm vụ của bạn là trả lời câu hỏi CHỈ dựa trên tài liệu được cung cấp bên dưới.

QUY TẮC NGHIÊM NGẶT:
1. CHỈ sử dụng thông tin có trong các đoạn tài liệu được đánh số [1], [2], [3]...
2. Không được sử dụng kiến thức bên ngoài tài liệu.
3. Nếu không tìm thấy thông tin: trả lời đúng một câu "Không tìm thấy thông tin trong tài liệu đã cung cấp."
4. Mỗi ý/câu phải kèm số trích dẫn [N] ngay sau, ví dụ: "Binary Search Tree lưu trữ theo thứ tự [1]."
5. Không tạo ra nguồn, không suy đoán, không mở rộng ngoài tài liệu.
6. Trả lời ngắn gọn, rõ ràng, sát nội dung gốc.
7. Trả lời bằng cùng ngôn ngữ với câu hỏi của người dùng.

ĐỊNH DẠNG BẮT BUỘC:
**Câu trả lời:**
<nội dung trả lời, mỗi ý có [N]>

**Nguồn:**
[1] <tên file> — Trang <số trang>
[2] <tên file> — Trang <số trang>
...\
"""


def generate_with_context(
    query: str,
    context_chunks: list[dict],
    system_hint: str = "",
    stream: bool = False,
) -> str | Generator[str, None, None]:
    """
    Generate answer grounded strictly in retrieved context chunks.
    context_chunks: [{text, doc_name, page_num, file_path}]
    Citations [1]..[N] map to chunk order.
    """
    if not context_chunks:
        no_ctx = (
            "Không tìm thấy thông tin trong tài liệu đã cung cấp.\n\n"
            "**Nguồn:** (không có đoạn nào được tìm thấy)"
        )
        if stream:
            return iter([no_ctx])
        return no_ctx

    # Build numbered context
    context_parts = []
    source_lines = []
    for i, chunk in enumerate(context_chunks, 1):
        doc = chunk.get("doc_name", "unknown")
        page = chunk.get("page_num", "?")
        text = chunk.get("text", "").strip()
        context_parts.append(f"[{i}] (Tài liệu: {doc}, Trang {page})\n{text}")
        source_lines.append(f"[{i}] {doc} — Trang {page}")

    context_str = "\n\n---\n\n".join(context_parts)
    sources_hint = "\n".join(source_lines)

    system = _SYSTEM_PROMPT + (f"\n\nGợi ý môn học: {system_hint}" if system_hint else "")

    user = (
        f"TÀI LIỆU THAM KHẢO:\n\n{context_str}\n\n"
        f"---\n"
        f"Danh sách nguồn để điền vào mục **Nguồn:**:\n{sources_hint}\n\n"
        f"---\n"
        f"CÂU HỎI: {query}"
    )

    return generate(system, user, stream=stream)
