"""
core/pipeline/answer_generator.py
LLM answer generation via Ollama local API.
Strict RAG mode: only answers from provided context, always cites sources.
"""
import httpx
import json
import re
from typing import Generator
from utils.config import get_config
from utils.language_utils import detect_response_language


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


# ── System Prompts ─────────────────────────────────────────────────────────────
_SYSTEM_PROMPT_VI = """\
Bạn là trợ lý học tập. Trả lời câu hỏi CHỈ dựa trên nội dung tài liệu được cung cấp.

QUY TẮC NGHIÊM NGẶT:
1. CHỈ dùng thông tin TRÍCH DẪN TRỰC TIẾP từ các đoạn [1], [2], [3]...
2. KHÔNG dùng kiến thức bên ngoài.
3. Nếu tài liệu không đủ để trả lời, viết đúng một câu: "Không tìm thấy thông tin trong tài liệu đã cung cấp."
4. KHÔNG tự suy luận, không bịa thêm.
5. Trích dẫn: đặt [1], [2]... MỘT LẦN ở cuối mỗi ý/bullet (KHÔNG lặp trên từng câu; KHÔNG viết [N]; KHÔNG viết số 1/2 đứng riêng).
6. NGHIÊM CẤM đưa code, pseudocode, ví dụ lập trình (C/C++/Python/Pascal...) — kể cả tài liệu có code, chỉ tóm tắt bằng lời.
7. Trả lời bằng tiếng Việt nếu câu hỏi là tiếng Việt; tiếng Anh nếu câu hỏi là tiếng Anh.

ĐỊNH DẠNG:
**Câu trả lời:**
<bullet hoặc đoạn ngắn, mỗi ý kết thúc bằng [N]>\
"""

_SYSTEM_PROMPT_EN = """\
You are a study assistant. Answer ONLY from the provided document excerpts.

STRICT RULES:
1. Use ONLY information from chunks [1], [2], [3]...
2. Do NOT use outside knowledge.
3. If documents lack enough information, reply exactly: "No relevant information was found in the provided documents."
4. Do NOT infer or invent content.
5. Citations: put [1], [2]... ONCE at the end of each bullet/point (NOT on every sentence; NOT [N]; NOT bare numbers like 1 or 2).
6. NEVER include code, pseudocode, or programming examples (C/C++/Python/...) — even if the source has code, summarize in prose only.
7. Write the ENTIRE answer in English when the question is in English.

FORMAT:
**Answer:**
<short bullets or paragraphs, each point ending with [N]>\
"""

_NO_INFO = {
    "vi": "Không tìm thấy thông tin trong tài liệu đã cung cấp.",
    "en": "No relevant information was found in the provided documents.",
}


def _system_prompt(lang: str, hint: str = "") -> str:
    base = _SYSTEM_PROMPT_EN if lang == "en" else _SYSTEM_PROMPT_VI
    if hint:
        suffix = f"\n\nSubject hint: {hint}" if lang == "en" else f"\n\nGợi ý môn học: {hint}"
        return base + suffix
    return base


def _build_sources_block(source_lines: list[str]) -> str:
    """Tạo block Nguồn cứng từ danh sách source lines — luôn chính xác, không phụ thuộc LLM."""
    return "\n\n---\n**Nguồn:**\n" + "\n".join(source_lines)


def _build_numbered_context(context_chunks: list[dict]) -> tuple[str, list[str]]:
    """Đánh số chunk [1]..[N]; mỗi chunk một dòng nguồn (index khớp [N] trong câu trả lời)."""
    context_parts: list[str] = []
    chunk_sources: list[str] = []

    for i, chunk in enumerate(context_chunks, 1):
        doc = chunk.get("doc_name", "unknown")
        page = chunk.get("page_num", "?")
        text = chunk.get("text", "").strip()
        context_parts.append(f"[{i}] (Tài liệu: {doc}, Trang {page})\n{text}")
        chunk_sources.append(f"[{i}] {doc} — Trang {page}")

    context_str = "\n\n---\n\n".join(context_parts)
    return context_str, chunk_sources


def _split_answer_and_sources(text: str) -> tuple[str, str]:
    source_split = re.split(r"\n---\n", text, maxsplit=1)
    body = source_split[0]
    tail = f"\n---\n{source_split[1]}" if len(source_split) > 1 else ""
    return body, tail


def _strip_trailing_separators(text: str) -> str:
    """Xóa --- thừa do LLM hoặc stream chèn trước block Nguồn."""
    body = text.rstrip()
    while True:
        cleaned = re.sub(r"(?:\n)?---\s*$", "", body).rstrip()
        if cleaned == body:
            return body
        body = cleaned


def remove_code_from_answer(text: str) -> str:
    """Gỡ khối code và dòng ví dụ lập trình — chat RAG chỉ trả lời lý thuyết."""
    text = re.sub(r"```[^\n]*\n.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    code_line = re.compile(
        r"^(#include|#define|using namespace|int main|std::|cout|cin|return 0|"
        r"def |class |public:|private:|queue<|stack<|\}\s*$|\{\s*$)",
        re.IGNORECASE,
    )
    cleaned: list[str] = []
    skip_block = False
    for line in text.split("\n"):
        stripped = line.strip()
        if re.match(r"(?i)^(?:ví dụ|example).*(?:code|lập trình|c\+\+|python)", stripped):
            skip_block = True
            continue
        if re.match(r"(?i)^(?:stack|queue)\s*:\s*$", stripped):
            skip_block = True
            continue
        if skip_block:
            if not stripped:
                skip_block = False
            continue
        if code_line.match(stripped):
            continue
        cleaned.append(line)

    text = "\n".join(cleaned)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_citation_placeholders(text: str) -> str:
    """[N] / [n] từ prompt → [1]; gỡ số rác sau citation."""
    text = re.sub(r"\[N\]", "[1]", text, flags=re.IGNORECASE)
    text = re.sub(r"\[(\d+)\]\.\s+\d+\s*$", r"[\1].", text, flags=re.MULTILINE)
    text = re.sub(r"\[(\d+)\]\s+\d+\s*$", r"[\1]", text, flags=re.MULTILINE)
    return text


def normalize_trailing_bare_refs(text: str) -> str:
    """'... câu. 3' hoặc '... : 1' ở cuối dòng → '... [3]'."""
    lines: list[str] = []
    for line in text.split("\n"):
        if re.search(r"\[\d+\]", line):
            lines.append(line)
            continue
        if re.match(r"^Nguồn tham khảo", line.strip(), re.IGNORECASE):
            lines.append(line)
            continue
        if re.match(r"^\*\*", line.strip()):
            lines.append(line)
            continue
        line = re.sub(r"([.!?…:])\s+(\d+)\s*$", r"\1 [\2]", line)
        line = re.sub(r"(?<!\[)\s+(\d+)\.\s*$", r" [\1].", line)
        line = re.sub(r"(?<!\[)\s+(\d+)\s*$", r" [\1]", line)
        lines.append(line)
    return "\n".join(lines)


def normalize_bare_citations(text: str) -> str:
    """Chuyển trích dẫn lỏng '... 1.' / '... 2.' thành '... [1].'"""
    lines: list[str] = []
    for line in text.split("\n"):
        if re.search(r"\[\d+\]", line):
            lines.append(line)
            continue
        line = re.sub(r"(?<!\[)\s+(\d+)\.\s*$", r" [\1].", line)
        lines.append(line)
    return "\n".join(lines)


def normalize_answer_body(body: str) -> str:
    body = _strip_trailing_separators(body)
    body = remove_code_from_answer(body)
    body = normalize_citation_placeholders(body)
    body = normalize_trailing_bare_refs(body)
    body = normalize_bare_citations(body)

    if not re.search(r"\[\d+\]", body):
        body = body.rstrip()
        if body and not body.endswith("[1]"):
            body += " [1]"

    return body.strip()


def extract_cited_indices(text: str) -> list[int]:
    return sorted({int(n) for n in re.findall(r"\[(\d+)\]", text)})


def _filter_chunk_sources(chunk_sources: list[str], cited_indices: list[int]) -> list[str]:
    """Chỉ giữ nguồn của các [N] thực sự xuất hiện trong câu trả lời."""
    if not cited_indices:
        cited_indices = [1]
    lines: list[str] = []
    seen: set[int] = set()
    for idx in cited_indices:
        if idx in seen or idx < 1 or idx > len(chunk_sources):
            continue
        seen.add(idx)
        lines.append(chunk_sources[idx - 1])
    return lines


def prepare_answer_citations(text: str) -> str:
    """Chuẩn hóa trích dẫn trong phần thân (bỏ --- thừa, không giữ tail cũ)."""
    if not text or _is_no_info_answer(text):
        return text

    m = _find_sources_marker(text)
    raw_body = text[: m.start()] if m else text
    body, _ = _split_answer_and_sources(raw_body)
    return normalize_answer_body(body)


def build_sources_block_for_answer(answer_text: str, chunk_sources: list[str]) -> str:
    """Chỉ liệt kê nguồn khớp [N] trong câu trả lời (mặc định [1] nếu thiếu)."""
    body, _ = _split_answer_and_sources(answer_text)
    cited = extract_cited_indices(body)
    source_lines = _filter_chunk_sources(chunk_sources, cited)
    return _build_sources_block(source_lines)


def _build_strict_user_prompt(query: str, context_str: str, lang: str) -> str:
    if lang == "en":
        return (
            f"REFERENCE EXCERPTS:\n\n{context_str}\n\n"
            f"---\n"
            f"QUESTION: {query}\n\n"
            f"Answer in English using ONLY the excerpts above. "
            f"Do NOT include any code or programming examples. "
            f"Put [1], [2]... once at the end of each bullet (real chunk numbers only). "
            f"If insufficient information, reply exactly: "
            f"\"{_NO_INFO['en']}\"."
        )
    return (
        f"TÀI LIỆU THAM KHẢO:\n\n{context_str}\n\n"
        f"---\n"
        f"CÂU HỎI: {query}\n\n"
        f"Trả lời bằng tiếng Việt, CHỈ dựa trên tài liệu trên. "
        f"KHÔNG đưa code hay ví dụ lập trình vào câu trả lời. "
        f"Đặt [1], [2]... một lần ở cuối mỗi ý (số chunk thực, không viết [N]). "
        f"Nếu không đủ thông tin, trả lời đúng một câu: \"{_NO_INFO['vi']}\"."
    )


def _find_sources_marker(text: str) -> re.Match[str] | None:
    """Tìm vị trí bắt đầu block nguồn (markdown hoặc plain UI)."""
    patterns = [
        r"\*\*Nguồn[^*]*:\*\*",
        r"\*\*Sources?[^*]*:\*\*",
        r"(?:^|\n)Nguồn tham khảo\s*(?:\n|$)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m
    return None


def rebuild_sources_in_answer(text: str) -> str:
    """Chuẩn hóa citation và chỉ giữ nguồn [N] được trích dẫn trong thân."""
    if not text or _is_no_info_answer(text):
        return text

    m = _find_sources_marker(text)
    if not m:
        return prepare_answer_citations(text)

    body = prepare_answer_citations(text[: m.start()].rstrip())
    cited = extract_cited_indices(body) or [1]

    source_map: dict[int, str] = {}
    tail = text[m.end() :]
    for line in tail.split("\n"):
        line = line.strip()
        if not line or line == "---":
            continue
        m_line = re.match(r"^\[(\d+)\]\s*(.+)", line)
        if not m_line:
            m_line = re.match(r"^(\d+)\s+(.+)", line)
        if not m_line:
            m_line = re.match(r"^(\d+)([A-Za-zÀ-ỹ\u00C0-\u1EF9].+)", line)
        if m_line:
            idx = int(m_line.group(1))
            label = m_line.group(2).strip()
            source_map[idx] = f"[{idx}] {label}"

    filtered = [source_map[i] for i in cited if i in source_map]
    if not filtered and source_map:
        first = min(source_map)
        filtered = [source_map[first]]

    return body + _build_sources_block(filtered)


def ensure_inline_citations(text: str) -> str:
    """Alias giữ tương thích UI."""
    return rebuild_sources_in_answer(text)


def _is_no_info_answer(text: str) -> bool:
    low = text.lower()
    return "không tìm thấy thông tin" in low or "no relevant information" in low


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
    context_str, chunk_sources = _build_numbered_context(context_chunks)
    lang = detect_response_language(query, context_chunks)

    print("\n" + "="*80)
    print(f"[RAG DEBUG] 4. Context sent to LLM ({len(context_chunks)} chunks, lang={lang}):")
    safe_context = context_str.encode('ascii', 'ignore').decode('ascii')
    print(safe_context)
    print("="*80 + "\n")

    system = _system_prompt(lang, system_hint)
    user = _build_strict_user_prompt(query, context_str, lang)

    if stream:
        def _stream_with_sources() -> Generator[str, None, None]:
            llm_text = ""
            for token in generate(system, user, stream=True, temperature=0.0):
                llm_text += token
                yield token

            if not _is_no_info_answer(llm_text) and "**Nguồn:**" not in llm_text:
                prepared = prepare_answer_citations(llm_text)
                if prepared != llm_text:
                    yield prepared[len(llm_text):]
                    llm_text = prepared
                yield build_sources_block_for_answer(llm_text, chunk_sources)

        return _stream_with_sources()
    else:
        result = generate(system, user, stream=False, temperature=0.0)
        if not _is_no_info_answer(result) and "**Nguồn:**" not in result:
            result = prepare_answer_citations(result)
            result += build_sources_block_for_answer(result, chunk_sources)
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

    context_str, chunk_sources = _build_numbered_context(context_chunks)
    lang = detect_response_language(query, context_chunks)

    system = _system_prompt(lang, system_hint)
    user = _build_strict_user_prompt(query, context_str, lang)

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
        if not _is_no_info_answer(llm_text) and "**Nguồn:**" not in llm_text:
            prepared = prepare_answer_citations(llm_text)
            if prepared != llm_text:
                yield prepared[len(llm_text):]
                llm_text = prepared
            yield build_sources_block_for_answer(llm_text, chunk_sources)

    return _stream_with_meta(), token_meta_holder

