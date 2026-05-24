"""
core/pipeline/answer_generator.py
LLM answer generation via Ollama local API.
Strict RAG mode: only answers from provided context, always cites sources.
Uses structured JSON output + multi-pass parser for accurate metadata extraction.
"""
import httpx
import json
import re
from typing import Generator, TypedDict
from utils.config import get_config


# ── Types ─────────────────────────────────────────────────────────────────────

class SourceMeta(TypedDict):
    index:     int
    doc_name:  str
    page_num:  str | int
    file_path: str


class StructuredAnswer(TypedDict):
    answer:   str               # answer text with inline [N] citations
    sources:  list[SourceMeta]  # parsed & enriched source metadata
    raw:      str               # raw LLM output (for debugging)
    grounded: bool              # True nếu LLM tuân thủ format


# ── Config ────────────────────────────────────────────────────────────────────

def _get_llm_cfg() -> dict:
    return get_config()["llm"]


def _build_prompt(system: str, user: str) -> list[dict]:
    return [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ]


# ── Core LLM call ─────────────────────────────────────────────────────────────

def generate(
    system_prompt: str,
    user_prompt: str,
    stream: bool = False,
) -> str | Generator[str, None, None]:
    cfg = _get_llm_cfg()
    temperature = cfg.get("rag_temperature", 0)
    payload = {
        "model":    cfg["model"],
        "messages": _build_prompt(system_prompt, user_prompt),
        "options":  {"temperature": temperature},
        "stream":   stream,
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
                        data  = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue


# ── System prompt (JSON-structured output) ────────────────────────────────────

_SYSTEM_PROMPT = """\
Bạn là trợ lý học tập. Nhiệm vụ của bạn là trả lời câu hỏi CHỈ dựa trên TÀI LIỆU THAM KHẢO được cung cấp.

QUY TẮC NGHIÊM NGẶT:
1. CHỈ sử dụng thông tin trong các đoạn [1], [2], [3]... được cung cấp. TUYỆT ĐỐI không dùng kiến thức bên ngoài.
2. Nếu tài liệu không có thông tin để trả lời: trường "answer" = "Không tìm thấy thông tin trong tài liệu đã cung cấp.", "sources" = [].
3. Mỗi câu/ý trong "answer" PHẢI có số trích dẫn [N] ngay cuối câu đó.
4. Chỉ đưa vào "sources" những index [N] đã thực sự xuất hiện trong "answer". KHÔNG khai báo source không dùng đến.
5. Mọi index trong "sources" PHẢI xuất hiện ít nhất một lần trong "answer", và ngược lại.
6. Không suy đoán, không bịa đặt, không mở rộng ngoài nội dung tài liệu.
7. Trả lời bằng cùng ngôn ngữ với câu hỏi.

ĐẦU RA BẮT BUỘC là JSON hợp lệ, không có text nào ngoài JSON:
{
  "answer": "<nội dung trả lời, mỗi câu có [N]>",
  "sources": [
    {"index": 1, "doc_name": "<tên file>", "page_num": <số trang>},
    {"index": 2, "doc_name": "<tên file>", "page_num": <số trang>}
  ]
}

--- VÍ DỤ ĐÚNG (few-shot) ---
Tài liệu:
[1] (Tài liệu: CTDL.pdf, Trang 12)\\nStack là cấu trúc dữ liệu LIFO.
[2] (Tài liệu: CTDL.pdf, Trang 15)\\nStack hỗ trợ hai thao tác chính: push và pop.

Câu hỏi: Stack là gì?
Đầu ra ĐÚNG:
{"answer": "Stack là cấu trúc dữ liệu theo nguyên tắc LIFO (Last In First Out) [1]. Stack hỗ trợ hai thao tác chính là push và pop [2].", "sources": [{"index": 1, "doc_name": "CTDL.pdf", "page_num": 12}, {"index": 2, "doc_name": "CTDL.pdf", "page_num": 15}]}

--- VÍ DỤ SAI ---
{"answer": "Stack là cấu trúc dữ liệu LIFO. Nó hỗ trợ push và pop [2].", "sources": [{"index": 1, "doc_name": "CTDL.pdf", "page_num": 12}, {"index": 2, "doc_name": "CTDL.pdf", "page_num": 15}]}
^^ SAI vì câu đầu không có [1] nhưng index 1 vẫn khai báo trong sources.

LƯU Ý JSON:
- Nếu answer có code, dùng \\n để xuống dòng bên trong chuỗi JSON.
- TUYỆT ĐỐI không đưa newline thật vào giữa dấu ngoặc kép của JSON string.\
"""


# ── Output parser ─────────────────────────────────────────────────────────────

def _extract_json_block(raw: str) -> str:
    """Extract first JSON object from raw LLM output (handles markdown fences)."""
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fenced:
        return fenced.group(1).strip()
    start = raw.find("{")
    end   = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start:end + 1].strip()
    return raw.strip()


def _validate_citations(answer: str, sources: list[dict]) -> tuple[bool, set[int], set[int]]:
    """
    Bidirectional citation check.
    Returns (grounded, orphan_citations, orphan_sources).
    """
    cited          = set(int(m) for m in re.findall(r"\[(\d+)\]", answer))
    source_indices = set(int(s.get("index", -1)) for s in sources)
    orphan_citations = cited - source_indices   # cited but not declared
    orphan_sources   = source_indices - cited   # declared but never cited
    grounded = (not orphan_citations) and (not orphan_sources)
    return grounded, orphan_citations, orphan_sources


def _repair_json(text: str) -> str:
    """
    Fix common LLM JSON issue: literal newlines/tabs inside string values.
    Processes char-by-char, tracking JSON string context.
    """
    result    = []
    in_string = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '\\' and in_string:
            result.append(ch)
            if i + 1 < len(text):
                result.append(text[i + 1])
                i += 2
            else:
                i += 1
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
        elif in_string and ch == '\n':
            result.append('\\n')
        elif in_string and ch == '\r':
            pass
        elif in_string and ch == '\t':
            result.append('\\t')
        else:
            result.append(ch)
        i += 1
    return ''.join(result)


def _extract_answer_sources_fallback(raw: str) -> tuple[str, list[dict]] | None:
    """
    Last-resort regex extraction when JSON parse fails.
    Handles any field ordering in sources objects.
    """
    answer_m = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', raw, re.DOTALL)
    if not answer_m:
        return None
    answer_text = answer_m.group(1).replace('\\n', '\n').replace('\\t', '\t')

    sources: list[dict] = []
    # Match source objects regardless of key order
    for obj_m in re.finditer(r'\{([^}]*"index"[^}]*)\}', raw):
        obj_str = obj_m.group(0)
        idx_m  = re.search(r'"index"\s*:\s*(\d+)',   obj_str)
        doc_m  = re.search(r'"doc_name"\s*:\s*"([^"]+)"', obj_str)
        page_m = re.search(r'"page_num"\s*:\s*(\d+)', obj_str)
        if idx_m and doc_m and page_m:
            sources.append({
                "index":    int(idx_m.group(1)),
                "doc_name": doc_m.group(1),
                "page_num": int(page_m.group(1)),
            })
    return answer_text, sources


def _build_structured(
    answer: str,
    raw_sources: list[dict],
    chunk_map: dict,
    raw: str,
    from_repair: bool = False,
) -> StructuredAnswer:
    """Build StructuredAnswer from parsed fields. Enriches sources with file_path."""
    if not answer:
        answer = "Không tìm thấy thông tin trong tài liệu đã cung cấp."

    enriched: list[SourceMeta] = []
    for s in raw_sources:
        idx   = int(s.get("index", -1))
        chunk = chunk_map.get(idx, {})
        enriched.append(SourceMeta(
            index    = idx,
            doc_name = s.get("doc_name") or chunk.get("doc_name", "unknown"),
            page_num = s.get("page_num") or chunk.get("page_num", "?"),
            file_path= chunk.get("file_path", ""),
        ))

    grounded, _, orphan_srcs = _validate_citations(answer, enriched)
    if orphan_srcs:
        enriched = [s for s in enriched if s["index"] not in orphan_srcs]
        grounded, _, _ = _validate_citations(answer, enriched)

    return StructuredAnswer(
        answer   = answer,
        sources  = enriched,
        raw      = raw,
        grounded = grounded and not from_repair,
    )


def parse_structured_answer(
    raw: str,
    context_chunks: list[dict],
) -> StructuredAnswer:
    """
    Parse LLM JSON output into StructuredAnswer.
    Strategy:
      Pass 1 — direct json.loads()
      Pass 2 — _repair_json() then json.loads()
      Pass 3 — regex field extraction
      Fallback — return raw text stripped of JSON artifacts
    """
    chunk_map = {i + 1: c for i, c in enumerate(context_chunks)}
    json_str  = _extract_json_block(raw)

    # Pass 1
    data: dict | None = None
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # Pass 2 — repair newlines in strings
    if data is None:
        try:
            data = json.loads(_repair_json(json_str))
        except json.JSONDecodeError:
            pass

    # Pass 3 — regex fallback
    if data is None:
        fallback = _extract_answer_sources_fallback(raw)
        if fallback:
            answer_text, raw_sources = fallback
            return _build_structured(answer_text, raw_sources, chunk_map, raw, from_repair=True)
        clean = re.sub(r'[{}"]', '', raw).strip()
        return StructuredAnswer(answer=clean, sources=[], raw=raw, grounded=False)

    answer_text = str(data.get("answer", "")).strip()
    raw_sources = data.get("sources", [])
    answer_text = answer_text.replace('\\n', '\n').replace('\\t', '\t')
    return _build_structured(answer_text, raw_sources, chunk_map, raw)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_with_context(
    query: str,
    context_chunks: list[dict],
    system_hint: str = "",
    stream: bool = False,
    structured: bool = False,
) -> str | Generator[str, None, None] | StructuredAnswer:
    """
    Generate answer grounded strictly in retrieved context chunks.

    Args:
        query:          User question
        context_chunks: [{text, doc_name, page_num, file_path}]
        system_hint:    Extra subject-specific instruction
        stream:         If True, return token generator (structured must be False)
        structured:     If True, return StructuredAnswer dict (stream must be False)

    Citations [1]..[N] map to chunk order.
    """
    if not context_chunks:
        empty = StructuredAnswer(
            answer   = "Không tìm thấy thông tin trong tài liệu đã cung cấp.",
            sources  = [],
            raw      = "",
            grounded = True,
        )
        if structured:
            return empty
        msg = empty["answer"]
        return iter([msg]) if stream else msg

    # Build numbered context
    context_parts: list[str] = []
    for i, chunk in enumerate(context_chunks, 1):
        doc  = chunk.get("doc_name", "unknown")
        page = chunk.get("page_num", "?")
        text = chunk.get("text", "").strip()
        context_parts.append(f"[{i}] (Tài liệu: {doc}, Trang {page})\n{text}")

    context_str = "\n\n---\n\n".join(context_parts)
    system = _SYSTEM_PROMPT + (f"\n\nGợi ý môn học: {system_hint}" if system_hint else "")
    user   = f"TÀI LIỆU THAM KHẢO:\n\n{context_str}\n\n---\n\nCÂU HỎI: {query}"

    if stream:
        return generate(system, user, stream=True)

    raw = generate(system, user, stream=False)

    if structured:
        return parse_structured_answer(raw, context_chunks)

    return raw


def format_structured_answer(result: StructuredAnswer) -> str:
    """Format StructuredAnswer back to human-readable markdown string."""
    lines = [result["answer"]]
    if result["sources"]:
        lines += ["", "**Nguồn:**"]
        for s in result["sources"]:
            lines.append(f"[{s['index']}] {s['doc_name']} — Trang {s['page_num']}")
    return "\n".join(lines)
