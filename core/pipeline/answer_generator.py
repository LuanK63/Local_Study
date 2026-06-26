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
    temperature: float = None,
) -> str | Generator:
    """
    Legacy wrapper — returns only text (str) for non-stream, or token Generator for stream.
    Use generate_with_token_metadata() when token metrics are needed.
    """
    cfg = _get_llm_cfg()
    payload = {
        "model":   cfg["model"],
        "messages": _build_prompt(system_prompt, user_prompt),
        "options": {"temperature": temperature if temperature is not None else cfg["temperature"]},
        "stream":  stream,
    }
    url = f"{cfg['base_url']}/api/chat"
    if stream:
        return _stream(url, payload, cfg["timeout"])
    else:
        text, _meta = _blocking(url, payload, cfg["timeout"])
        return text


def _blocking(url: str, payload: dict, timeout: int) -> tuple[str, dict]:
    """
    Returns (text, token_meta) where token_meta has keys:
        prompt_eval_count  (= prompt_tokens)
        eval_count         (= completion_tokens)
    Both default to 0 if Ollama does not return them.
    """
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, json={**payload, "stream": False})
        resp.raise_for_status()
        body = resp.json()
        text = body.get("message", {}).get("content", "")
        token_meta = {
            "prompt_eval_count": body.get("prompt_eval_count", 0) or 0,
            "eval_count":        body.get("eval_count", 0) or 0,
        }
        return text, token_meta


def _stream(url: str, payload: dict, timeout: int) -> Generator[str | dict, None, None]:
    """
    Yields text tokens, then at the end yields a single sentinel dict:
        {"__token_meta__": True, "prompt_eval_count": N, "eval_count": M}
    so callers can capture Ollama usage metadata.
    """
    token_meta = {"prompt_eval_count": 0, "eval_count": 0}
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
                            # Capture token metadata from the final "done" chunk
                            token_meta["prompt_eval_count"] = data.get("prompt_eval_count", 0) or 0
                            token_meta["eval_count"]        = data.get("eval_count", 0) or 0
                            break
                    except json.JSONDecodeError:
                        continue
    # Yield sentinel so callers can extract token metadata
    yield {"__token_meta__": True, **token_meta}


# ── System Prompt ──────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
Bạn là trợ lý học tập. Trả lời câu hỏi CHỈ dựa trên nội dung tài liệu được cung cấp bên dưới.

QUY TẮC NGHIÊM NGẶT:
1. CHỈ dùng thông tin TRÍCH DẪN TRỰC TIẾP từ các đoạn [1], [2], [3]...
2. KHÔNG dùng kiến thức bên ngoài — dù bạn biết câu trả lời, KHÔNG được viết thêm.
3. Nếu tài liệu không chứa đủ thông tin để trả lời câu hỏi, bạn BẮT BUỘC phải viết đúng một câu: "Không tìm thấy thông tin trong tài liệu đã cung cấp."
4. Tuyệt đối không tự suy luận, không phỏng đoán, không thêm thắt thông tin.
5. Mỗi câu/ý trong câu trả lời phải có số trích dẫn [N] ngay sau.
6. NGHIÊM CẤM:
   - Viết code, giả mã, ví dụ nếu KHÔNG có sẵn trong tài liệu.
   - Dịch code từ ngôn ngữ này sang ngôn ngữ khác (Pascal → C, C → Python...).
   - Tổng hợp tạo nội dung mới không có trong bất kỳ đoạn nào.
   - Mở rộng, giải thích thêm ngoài những gì tài liệu viết.
7. Nếu tài liệu có code, chỉ COPY NGUYÊN VẸN, không sửa đổi.
8. Trả lời bằng cùng ngôn ngữ với câu hỏi.

ĐỊNH DẠNG BẮT BUỘC:
**Câu trả lời:**
<nội dung trả lời, chỉ từ tài liệu, mỗi ý có [N]>\
"""


def _build_sources_block(source_lines: list[str]) -> str:
    """Tạo block Nguồn cứng từ danh sách source lines — luôn chính xác, không phụ thuộc LLM."""
    return "\n\n---\n**Nguồn:**\n" + "\n".join(source_lines)


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

    Phần **Nguồn:** được append deterministically SAU khi LLM stream xong,
    đảm bảo luôn hiển thị đúng tài liệu và số trang bất kể model có follow format hay không.
    """
    if not context_chunks:
        no_ctx = (
            "Không tìm thấy thông tin trong tài liệu đã cung cấp.\n\n"
            "---\n**Nguồn:** (không có đoạn nào được tìm thấy)"
        )
        if stream:
            return iter([no_ctx])
        return no_ctx

    # Build numbered context + source list
    context_parts = []
    source_lines  = []
    seen_sources: set[str] = set()

    for i, chunk in enumerate(context_chunks, 1):
        doc  = chunk.get("doc_name", "unknown")
        page = chunk.get("page_num", "?")
        text = chunk.get("text", "").strip()
        context_parts.append(f"[{i}] (Tài liệu: {doc}, Trang {page})\n{text}")

        # Deduplicate: cùng file + page chỉ hiện một lần trong Nguồn
        src_key = f"{doc}:{page}"
        if src_key not in seen_sources:
            seen_sources.add(src_key)
            if not source_lines:
                source_lines.append(f"{doc} — Trang {page}")

    context_str   = "\n\n---\n\n".join(context_parts)
    sources_block = _build_sources_block(source_lines)

    # ── [RAG DEBUG] LOGGING CONTEXT GỬI LLM ──────────────────────────────────
    print("\n" + "="*80)
    print(f"[RAG DEBUG] 4. Context sent to LLM ({len(context_chunks)} chunks):")
    safe_context = context_str.encode('ascii', 'ignore').decode('ascii')
    print(safe_context)
    print("="*80 + "\n")

    system = _SYSTEM_PROMPT + (f"\n\nGợi ý môn học: {system_hint}" if system_hint else "")

    user = (
        f"TÀI LIỆU THAM KHẢO:\n\n{context_str}\n\n"
        f"---\n"
        f"CÂU HỎI: {query}\n\n"
        f"LƯU Ý QUAN TRỌNG: Hãy kiểm tra kỹ xem tài liệu tham khảo có chứa thông tin để trả lời câu hỏi hay không. "
        f"Nếu không có thông tin chính xác hoặc không đủ dữ liệu để trả lời, bạn bắt buộc phải trả lời đúng một câu: "
        f"\"Không tìm thấy thông tin trong tài liệu đã cung cấp.\". Tuyệt đối không tự suy luận hoặc sử dụng kiến thức bên ngoài."
    )

    if stream:
        def _stream_with_sources() -> Generator[str, None, None]:
            llm_text = ""
            # Ép buộc temperature=0.0 cho RAG để tránh ảo tưởng
            for token in generate(system, user, stream=True, temperature=0.0):
                llm_text += token
                yield token
            
            # Chỉ hiển thị nguồn nếu câu trả lời không phải là "Không tìm thấy thông tin..."
            is_no_info = "không tìm thấy thông tin" in llm_text.lower()
            if not is_no_info and "**Nguồn:**" not in llm_text:
                yield sources_block

        return _stream_with_sources()
    else:
        # Ép buộc temperature=0.0 cho RAG để tránh ảo tưởng
        result = generate(system, user, stream=False, temperature=0.0)
        is_no_info = "không tìm thấy thông tin" in result.lower()
        if not is_no_info and "**Nguồn:**" not in result:
            result += sources_block
        return result


def generate_with_token_metadata(
    query: str,
    context_chunks: list[dict],
    system_hint: str = "",
) -> tuple[Generator, dict]:
    """
    Sinh câu trả lời có thu thập Token Metadata từ Ollama.

    Pipeline chính dùng hàm này thay vì generate_with_context() để nhận token info.

    Returns:
        (stream_gen, token_meta_holder)
        - stream_gen: Generator yield từng text token (không bao gồm sentinel)
        - token_meta_holder: dict {"prompt_eval_count": 0, "eval_count": 0}
          Được cập nhật IN-PLACE khi stream kết thúc.

    Mapping Ollama → AgentState:
        prompt_eval_count  →  state.prompt_tokens
        eval_count         →  state.completion_tokens
    """
    if not context_chunks:
        no_ctx = (
            "Không tìm thấy thông tin trong tài liệu đã cung cấp.\n\n"
            "---\n**Nguồn:** (không có đoạn nào được tìm thấy)"
        )
        token_meta_holder = {"prompt_eval_count": 0, "eval_count": 0}

        def _empty_gen():
            yield no_ctx

        return _empty_gen(), token_meta_holder

    # Build context
    context_parts = []
    source_lines  = []
    seen_sources: set[str] = set()

    for i, chunk in enumerate(context_chunks, 1):
        doc  = chunk.get("doc_name", "unknown")
        page = chunk.get("page_num", "?")
        text = chunk.get("text", "").strip()
        context_parts.append(f"[{i}] (Tài liệu: {doc}, Trang {page})\n{text}")

        src_key = f"{doc}:{page}"
        if src_key not in seen_sources:
            seen_sources.add(src_key)
            if len(source_lines) == 0:
                source_lines.append(f"{doc} — Trang {page}")

    context_str   = "\n\n---\n\n".join(context_parts)
    sources_block = _build_sources_block(source_lines)

    system = _SYSTEM_PROMPT + (f"\n\nGợi ý môn học: {system_hint}" if system_hint else "")
    user = (
        f"TÀI LIỆU THAM KHẢO:\n\n{context_str}\n\n"
        f"---\n"
        f"CÂU HỎI: {query}\n\n"
        f"LƯU Ý: Hãy dựa vào tài liệu tham khảo để trả lời. "
        f"Nếu tài liệu không có thông tin trực tiếp, hãy cố gắng tận dụng các thông tin liên quan nhất để giải thích. "
        f"Chỉ trả lời \"Không tìm thấy thông tin trong tài liệu đã cung cấp.\" nếu hoàn toàn không có bất kỳ thông tin nào liên quan. "
        f"Bạn có thể kết hợp kiến thức của mình để giải thích rõ hơn, nhưng phải dựa trên nền tảng của tài liệu."
    )

    cfg = _get_llm_cfg()
    payload = {
        "model":    cfg["model"],
        "messages": _build_prompt(system, user),
        "options":  {"temperature": 0.0},
        "stream":   True,
    }
    url = f"{cfg['base_url']}/api/chat"

    # Shared mutable holder — updated in-place by generator
    token_meta_holder = {"prompt_eval_count": 0, "eval_count": 0}

    def _stream_with_meta() -> Generator[str, None, None]:
        llm_text = ""
        for item in _stream(url, payload, cfg["timeout"]):
            if isinstance(item, dict) and item.get("__token_meta__"):
                # Sentinel: capture and update holder in-place
                token_meta_holder["prompt_eval_count"] = item.get("prompt_eval_count", 0)
                token_meta_holder["eval_count"]        = item.get("eval_count", 0)
            else:
                llm_text += item
                yield item

        # Append sources block deterministically
        is_no_info = "không tìm thấy thông tin" in llm_text.lower()
        if not is_no_info and "**Nguồn:**" not in llm_text:
            yield sources_block

    return _stream_with_meta(), token_meta_holder

