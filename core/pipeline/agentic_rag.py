"""
core/pipeline/agentic_rag.py
Agentic RAG pipeline for Local Study RAG Agent.
Handles Query Routing, Corrective RAG (CRAG) with Self-Reflection/Query Rewriting,
and Code Interpreter (Python Sandbox Tool) execution.
"""
import httpx
import json
import re
from typing import Generator, Callable
from utils.config import get_config
from core.retrieval.hybrid_retriever import hybrid_search, search as retrieval_search
from modules.code_sandbox import run_python

# ── SYSTEM PROMPTS ────────────────────────────────────────────────────────────

SYSTEM_CODE_AGENT_PROMPT = """Bạn là trợ lý học tập chuyên lập trình và toán học.
Nhiệm vụ của bạn là giải quyết câu hỏi/yêu cầu của người dùng bằng cách viết một chương trình Python hoàn chỉnh để giải bài toán, thực hiện phép tính phức tạp hoặc mô phỏng giải thuật.

QUY TẮC VIẾT CODE:
1. Viết mã Python hoàn chỉnh, tự chạy được, và in kết quả/lời giải chi tiết ra màn hình (stdout) sử dụng print().
2. Luôn đặt mã Python trong khối mã ```python ... ```
3. CẤM sử dụng các thư viện bị chặn: os, sys, subprocess, socket, shutil, hoặc các hàm gọi hệ điều hành.
4. Giữ code đơn giản, tập trung vào giải thuật hoặc tính toán chính xác.

Hệ thống sẽ tự động trích xuất và thực thi code của bạn, sau đó đưa kết quả chạy code để bạn hoàn thiện câu trả lời cuối cùng."""


SYSTEM_CODE_SYNTHESIZER_PROMPT = """Bạn là trợ lý học tập chuyên nghiệp.
Nhiệm vụ của bạn là viết câu trả lời hoàn thiện và dễ hiểu cho người học dựa trên câu hỏi ban đầu, đoạn mã Python đã thực thi, và kết quả đầu ra thực tế từ chương trình.

Dưới đây là thông tin thực thi:
- Mã Python đã chạy:
```python
{code}
```
- Kết quả đầu ra (Stdout):
```
{stdout}
```
- Lỗi phát sinh (nếu có):
```
{stderr}
```

Hãy giải thích chi tiết các bước tính toán, phân tích giải thuật một cách dễ hiểu và đưa ra kết quả cuối cùng chính xác dựa trên kết quả chạy code trên. Trả lời bằng tiếng Việt."""

# ── LLM UTILITIES ─────────────────────────────────────────────────────────────

def _call_llm(system: str, user: str, stream: bool = False, json_mode: bool = False) -> str | Generator[str, None, None]:
    cfg = get_config()["llm"]
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "options": {"temperature": 0.1 if json_mode else cfg["temperature"]},
        "stream": stream
    }
    if json_mode:
        payload["format"] = "json"

    url = f"{cfg['base_url']}/api/chat"
    timeout = cfg["timeout"]

    if stream:
        return _stream_llm(url, payload, timeout)
    else:
        return _blocking_llm(url, payload, timeout)


def _blocking_llm(url: str, payload: dict, timeout: int) -> str:
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()["message"]["content"]


def _stream_llm(url: str, payload: dict, timeout: int) -> Generator[str, None, None]:
    with httpx.Client(timeout=timeout) as client:
        with client.stream("POST", url, json=payload) as resp:
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


# ── AGENTIC STAGES ────────────────────────────────────────────────────────────

def route_query(query: str) -> str:
    """Route user query to RAG, CODE or CHAT."""
    system_prompt = """Bạn là bộ phân loại câu hỏi thông minh. Hãy phân tích câu hỏi của người học và đưa ra phân loại chính xác dưới định dạng JSON:
{
  "route": "RAG" | "CODE" | "CHAT"
}

QUY TẮC PHÂN LOẠI CHẶT CHẼ:
1. "RAG": Câu hỏi lý thuyết, khái niệm chuyên ngành, định nghĩa có trong tài liệu môn học (Ví dụ: "BST là gì", "so sánh AVL và Red-Black tree", "các phép quay cây AVL").
2. "CODE": Câu hỏi yêu cầu viết code, sửa lỗi code, thuật toán lập trình, tính toán toán học/số học phức tạp (Ví dụ: "viết hàm quicksort bằng Python", "tính 453 * 123 + 999", "chạy thử thuật toán Dijkstra", "tính Fibonacci thứ 10").
3. "CHAT": Trò chuyện bình thường, chào hỏi xã giao, cảm ơn (Ví dụ: "chào bạn", "bạn khỏe không", "cảm ơn trợ lý").

CHỈ trả về đúng định dạng JSON như trên, không giải thích gì thêm."""

    user_prompt = f"Câu hỏi của người dùng: {query}"
    
    try:
        response_str = _call_llm(system_prompt, user_prompt, stream=False, json_mode=True)
        data = json.loads(response_str)
        route = data.get("route", "RAG").upper()
        if route in ("RAG", "CODE", "CHAT"):
            return route
    except Exception as e:
        print(f"[WARN] route_query fallback to RAG due to: {e}")
    
    return "RAG"


def evaluate_chunks(query: str, chunks: list[dict]) -> list[dict]:
    """
    Filter chunks using RRF fused score threshold — fast, deterministic, no extra LLM call.
    Keeps chunks whose boosted fused score is above the dynamic threshold computed from raw RRF scores.
    Falls back to all chunks if none meet the threshold.
    """
    if not chunks:
        return []

    # Compute threshold based on raw (un-boosted) fused scores to avoid inflation
    raw_scores = [c.get("fused_raw", c.get("fused", 0.0)) for c in chunks]
    max_raw_score = max(raw_scores) if raw_scores else 0.0

    # Threshold: keep chunks that are at least 40% of the best chunk's raw score
    # This allows weaker-but-still-related paragraphs through
    THRESHOLD_RATIO = 0.40
    threshold = max_raw_score * THRESHOLD_RATIO

    # Filter using the boosted fused score, but against the raw-based threshold
    filtered = [c for c in chunks if c.get("fused", 0.0) >= threshold]
    print(f"[CRAG] Score filter: max_raw={max_raw_score:.4f}, threshold={threshold:.4f}, kept {len(filtered)}/{len(chunks)} chunks")

    # Safety: never return empty — if all filtered out, return all
    return filtered if filtered else chunks



def rewrite_query(query: str) -> str:
    """Rewrite query to be more effective for keyword/vector search."""
    system_prompt = """Bạn là chuyên gia tối ưu hóa tìm kiếm tài liệu học tập.
Câu hỏi ban đầu của người dùng không tìm thấy tài liệu phù hợp. 
Nhiệm vụ của bạn là viết lại câu hỏi đó thành một câu truy vấn tìm kiếm mới bằng Tiếng Việt ngắn gọn, tập trung hoàn toàn vào các từ khóa chuyên môn cốt lõi để giúp bộ tìm kiếm hoạt động hiệu quả hơn.

CHỈ trả về đúng câu truy vấn mới bằng tiếng Việt, không giải thích gì thêm, không đặt trong dấu ngoặc kép."""
    
    user_prompt = f"Câu hỏi ban đầu: {query}"
    try:
        rewritten = _call_llm(system_prompt, user_prompt, stream=False, json_mode=False)
        return rewritten.strip()
    except Exception:
        return query


def extract_python_code(text: str) -> str:
    """Extract Python code from markdown blocks."""
    pattern = r"```python(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


# ── MAIN PIPELINE ENTRYPOINT ──────────────────────────────────────────────────

def generate_agentic_response(
    query: str,
    subject_id: str,
    subject_cfg,
    status_cb: Callable[[str], None] = None,
    chunks_cb: Callable[[list[dict]], None] = None,
    search_mode: str | None = None,   # None = đọc từ global_config
) -> Generator[str, None, None]:
    """
    Main entry point for Agentic RAG.
    search_mode: "hybrid" | "semantic" | "bm25" | None (auto from config)
    Yields string tokens suitable for StreamWorker.
    """
    # Clear chunks in UI on start
    if chunks_cb:
        chunks_cb([])

    # Bypass query classification, routing directly to RAG mode
    route = "RAG"
    print(f"[DEBUG AGENT] Query classification bypassed. Routing directly to RAG.")

    if route == "CHAT":
        if status_cb:
            status_cb("💬 Đang trò chuyện...")
        system_prompt = "Bạn là trợ lý học tập thân thiện. Hãy trò chuyện bình thường và giúp đỡ người học bằng tiếng Việt ngắn gọn, dễ thương."
        for token in _call_llm(system_prompt, query, stream=True):
            yield token
        return

    elif route == "CODE":
        if status_cb:
            status_cb("💻 Đang viết mã Python lập luận...")
        
        code_prompt = f"Hãy viết chương trình Python để giải quyết câu hỏi: {query}"
        try:
            code_response = _call_llm(SYSTEM_CODE_AGENT_PROMPT, code_prompt, stream=False)
            code = extract_python_code(code_response)
        except Exception as e:
            yield f"Lỗi sinh code: {e}"
            return

        if not code:
            if status_cb:
                status_cb("✍️ Đang trả lời trực tiếp...")
            system_prompt = "Bạn là trợ lý học tập chuyên lập trình và toán. Hãy trả lời câu hỏi sau bằng tiếng Việt."
            for token in _call_llm(system_prompt, query, stream=True):
                yield token
            return

        if status_cb:
            status_cb("🧪 Đang thực thi mã Python trong Sandbox...")
            
        result = run_python(code)
        
        if status_cb:
            status_cb("✍️ Đang tổng hợp câu trả lời...")
            
        synth_prompt = SYSTEM_CODE_SYNTHESIZER_PROMPT.format(
            code=code,
            stdout=result.stdout if result.stdout else "(Không có output)",
            stderr=result.stderr if result.stderr else "(Không có lỗi)"
        )
        user_prompt = f"Hãy tạo câu trả lời cuối cùng dựa trên kết quả chạy code cho câu hỏi: {query}"
        
        for token in _call_llm(synth_prompt, user_prompt, stream=True):
            yield token
        return

    else:  # route == "RAG"
        if status_cb:
            status_cb("🔍 Đang tìm kiếm tài liệu...")

        # 1. Search (dispatcher theo mode)
        top_k = subject_cfg.prompt_hints.get("top_k", 5) if hasattr(subject_cfg, "prompt_hints") else 5
        try:
            chunks, mode_used = retrieval_search(query, subject_id, top_k=top_k, mode=search_mode)
        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            print(f"[ERROR] search failed: {err_msg}")
            yield f"❌ Lỗi tìm kiếm tài liệu: {e}\n\nVui lòng kiểm tra kết nối Ollama (chạy `ollama serve`) và thử lại."
            return

        if not chunks:
            print(f"[DEBUG AGENT] search({mode_used}) returned 0 chunks for query='{query}' subject='{subject_id}'")
            yield "❌ Không tìm thấy tài liệu liên quan trong môn học này. Hãy đảm bảo bạn đã nạp tài liệu vào hệ thống."
            return

        # 2. Filter by RRF score (fast, deterministic — no LLM call needed)
        relevant_chunks = evaluate_chunks(query, chunks)  # never returns empty

        # 3. Save relevant chunks to UI
        print(f"[DEBUG AGENT] Sending {len(relevant_chunks)} chunks to generator")
        if chunks_cb:
            chunks_cb(relevant_chunks)

        # 4. Generate response
        if status_cb:
            status_cb("✍️ Đang sinh câu trả lời...")

        from core.pipeline.answer_generator import generate_with_context
        hint = subject_cfg.prompt_hints.get("explain", "") if hasattr(subject_cfg, "prompt_hints") else ""

        try:
            ans_gen = generate_with_context(query, relevant_chunks, system_hint=hint, stream=True)
            if isinstance(ans_gen, Generator):
                for token in ans_gen:
                    yield token
            else:
                yield ans_gen
        except Exception as e:
            import traceback
            print(f"[ERROR] generate_with_context failed: {traceback.format_exc()}")
            yield f"❌ Lỗi sinh câu trả lời: {e}"

