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
class AgentState:
    def __init__(self, query: str, rag_mode: str, chunking_strategy: str, question_id: int):
        # Metadata
        self.question_id = question_id
        self.query = query
        self.rewritten_query = ""
        self.rag_mode = rag_mode
        self.chunking_strategy = chunking_strategy
        self.chunking_version = "v1"   # Version của chunking để tránh benchmark cũ bị mất ý nghĩa khi tinh chỉnh tham số
        self.attempts = 1
        self.experiment_seed = 42
        self.dataset_version = "ds_v1"
        self.prompt_template_version = "prompt_v1"
        self.chunk_size = None         # Thiết lập động từ cấu hình tương ứng với chiến lược chunking (INTEGER)
        self.chunk_overlap = None      # Thiết lập động từ cấu hình tương ứng với chiến lược chunking (INTEGER)
        
        # Metadata môi trường thực thi (Phục vụ tái lập nghiên cứu)
        try:
            from utils.system_info import collect_system_metadata
            sys_meta = collect_system_metadata()
            self.git_commit_hash = sys_meta.get("git_commit_hash", "")
            self.machine_name = sys_meta.get("machine_name", "")
            self.gpu_name = sys_meta.get("gpu_name", "")
            self.ram_gb = sys_meta.get("ram_gb", 0)
            self.ollama_version = sys_meta.get("ollama_version", "")
            self.os_version = sys_meta.get("os_version", "")
        except Exception as e:
            print(f"[WARN] Failed to collect system metadata: {e}")
            self.git_commit_hash = ""
            self.machine_name = ""
            self.gpu_name = ""
            self.ram_gb = 0
            self.ollama_version = ""
            self.os_version = ""
        
        # Danh sách chunk lưu trong runtime phục vụ debug (Không ghi text thô vào SQLite)
        self.retrieved_chunks_l1 = []
        self.retrieved_chunks_l2 = []
        self.final_chunks = []
        
        # Thống kê số lượng chunk phân tách theo Lượt 1 và Lượt 2
        self.raw_retrieved_count_l1 = 0
        self.raw_retrieved_count_l2 = 0
        self.filtered_chunk_count_l1 = 0
        self.filtered_chunk_count_l2 = 0
        self.context_chunk_count = 0  
        self.context_char_count = 0
        
        # Cấu trúc JSON chi tiết lưu vào SQLite phục vụ debug/tái lập (mỗi đối tượng lưu đầy đủ: rank, similarity, document, page, chunk_id)
        self.retrieved_chunks_json_l1 = "[]"
        self.retrieved_chunks_json_l2 = "[]"
        self.final_chunks_json = "[]"
        
        # Chỉ số vị trí trích xuất đúng đầu tiên (phục vụ MRR)
        self.first_relevant_rank_l1 = 999
        self.first_relevant_rank_l2 = 999
        
        # Chỉ số Hit@k và Recall@k lưu trực tiếp (k = 1, 3, 5)
        self.hit_at_1_l1 = 0
        self.hit_at_3_l1 = 0
        self.hit_at_5_l1 = 0
        self.recall_at_1_l1 = 0.0
        self.recall_at_3_l1 = 0.0
        self.recall_at_5_l1 = 0.0
        
        self.hit_at_1_l2 = 0
        self.hit_at_3_l2 = 0
        self.hit_at_5_l2 = 0
        self.recall_at_1_l2 = 0.0
        self.recall_at_3_l2 = 0.0
        self.recall_at_5_l2 = 0.0
        
        # Điểm tương đồng cosine tốt nhất của Lượt 1 và Lượt 2
        self.best_similarity_l1 = 0.0
        self.best_similarity_l2 = 0.0
        
        # Kết quả đánh giá
        self.grader_score_l1 = 0
        self.grader_score_l2 = 0
        self.grader_explanation_l1 = "" # Chỉ giữ ở runtime phục vụ in log debug, không ghi vào SQLite
        self.grader_explanation_l2 = "" # Chỉ giữ ở runtime phục vụ in log debug, không ghi vào SQLite
        self.retrieval_success_grader_l1 = 0  # 1 nếu grader_score_l1 >= 3, ngược lại 0
        self.retrieval_success_grader_l2 = 0  # 1 nếu grader_score_l2 >= 3, ngược lại 0
        
        self.rewrite_activated = 0     # 0: No, 1: Yes
        self.final_answer = ""         # Lưu văn bản câu trả lời để chấm điểm accuracy thủ công
        
        # Chỉ số Tokens (Ollama metadata)
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        
        # Latency Metrics (ms)
        self.retrieval_time_ms = 0.0
        self.grading_time_ms = 0.0
        self.rewrite_time_ms = 0.0
        self.generation_time_ms = 0.0
        self.total_time_ms = 0.0
        
        self.final_answer_length = 0
def _compute_retrieval_metrics(chunks: list[dict], gt_docs: list[str], gt_pages: list[int]):
    """
    Computes Hit@k, Recall@k, and first_relevant_rank for k = 1, 3, 5.
    Returns:
        hit_at_1, hit_at_3, hit_at_5,
        recall_at_1, recall_at_3, recall_at_5,
        first_relevant_rank
    """
    import os
    if not gt_docs:
        return 0, 0, 0, 0.0, 0.0, 0.0, 999

    # Normalize gt docs and create target pairs
    gt_docs_norm = [os.path.splitext(d.lower())[0] for d in gt_docs]
    gt_pairs = set()
    
    # If gt_pages exists and is of same length, zip. Otherwise, cross product.
    if gt_pages and len(gt_docs) == len(gt_pages):
        for d, p in zip(gt_docs_norm, gt_pages):
            gt_pairs.add((d, p))
    else:
        for d in gt_docs_norm:
            if gt_pages:
                for p in gt_pages:
                    gt_pairs.add((d, p))
            else:
                gt_pairs.add((d, None))

    first_relevant_rank = 999
    
    # Calculate values at k = 1, 3, 5
    metrics = {}
    for k in (1, 3, 5):
        sub_chunks = chunks[:k]
        found_pairs = set()
        for idx, c in enumerate(sub_chunks, 1):
            c_doc = os.path.splitext(c.get("doc_name", "").lower())[0]
            try:
                c_page = int(c.get("page_num"))
            except (ValueError, TypeError):
                c_page = None
                
            is_match = False
            if (c_doc, c_page) in gt_pairs or (c_doc, None) in gt_pairs:
                is_match = True
            
            if is_match:
                found_pairs.add((c_doc, c_page) if c_page is not None else (c_doc, None))
                if first_relevant_rank == 999 or idx < first_relevant_rank:
                    first_relevant_rank = idx
                    
        hit = 1 if len(found_pairs) > 0 else 0
        recall = len(found_pairs) / len(gt_pairs) if len(gt_pairs) > 0 else 0.0
        metrics[f"hit_at_{k}"] = hit
        metrics[f"recall_at_{k}"] = recall

    # Adjust first_relevant_rank if it wasn't found in top 5, but might be in overall chunks
    if first_relevant_rank == 999:
        for idx, c in enumerate(chunks, 1):
            c_doc = os.path.splitext(c.get("doc_name", "").lower())[0]
            try:
                c_page = int(c.get("page_num"))
            except (ValueError, TypeError):
                c_page = None
            if (c_doc, c_page) in gt_pairs or (c_doc, None) in gt_pairs:
                first_relevant_rank = idx
                break

    return (
        metrics["hit_at_1"], metrics["hit_at_3"], metrics["hit_at_5"],
        metrics["recall_at_1"], metrics["recall_at_3"], metrics["recall_at_5"],
        first_relevant_rank
    )


def _populate_retrieval_metrics(state, chunks: list[dict], level: int, gt_docs: list[str] = None, gt_pages: list[int] = None):
    """
    Populates retrieval metrics into AgentState for Lượt 1 or Lượt 2.
    level: 1 or 2
    """
    import json
    if not state:
        return
        
    # Ghi nhận raw count
    if level == 1:
        state.raw_retrieved_count_l1 = len(chunks)
    else:
        state.raw_retrieved_count_l2 = len(chunks)
        
    # Ghi nhận JSON danh sách các chunks được truy xuất
    chunks_json = []
    for rank, c in enumerate(chunks, 1):
        chunks_json.append({
            "rank": rank,
            "similarity": c.get("score", 0.0),
            "document": c.get("doc_name", "unknown"),
            "page": c.get("page_num", 0),
            "chunk_id": c.get("id", "")
        })
    chunks_json_str = json.dumps(chunks_json, ensure_ascii=False)
    if level == 1:
        state.retrieved_chunks_json_l1 = chunks_json_str
    else:
        state.retrieved_chunks_json_l2 = chunks_json_str
        
    # Ghi nhận cosine similarity tốt nhất
    best_sim = max([c.get("score", 0.0) for c in chunks]) if chunks else 0.0
    if level == 1:
        state.best_similarity_l1 = best_sim
    else:
        state.best_similarity_l2 = best_sim
        
    # Tính toán Retrieval Metrics
    if gt_docs:
        hit_1, hit_3, hit_5, recall_1, recall_3, recall_5, mrr = _compute_retrieval_metrics(chunks, gt_docs, gt_pages)
        if level == 1:
            state.hit_at_1_l1 = hit_1
            state.hit_at_3_l1 = hit_3
            state.hit_at_5_l1 = hit_5
            state.recall_at_1_l1 = recall_1
            state.recall_at_3_l1 = recall_3
            state.recall_at_5_l1 = recall_5
            state.first_relevant_rank_l1 = mrr
        else:
            state.hit_at_1_l2 = hit_1
            state.hit_at_3_l2 = hit_3
            state.hit_at_5_l2 = hit_5
            state.recall_at_1_l2 = recall_1
            state.recall_at_3_l2 = recall_3
            state.recall_at_5_l2 = recall_5
            state.first_relevant_rank_l2 = mrr
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
    state: AgentState | None = None,
    gt_docs: list[str] | None = None,
    gt_pages: list[int] | None = None,
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
            import time
            start_retrieval = time.time()
            chunks, mode_used = retrieval_search(query, subject_id, top_k=top_k, mode=search_mode)
            retrieval_duration = (time.time() - start_retrieval) * 1000
            if state:
                state.retrieval_time_ms = retrieval_duration
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

        # 2. Populate Retrieval Metrics
        if state:
            _populate_retrieval_metrics(state, chunks, level=1, gt_docs=gt_docs, gt_pages=gt_pages)

        # 2. Đọc cấu hình chế độ RAG và kiểm soát CRAG
        rag_cfg = get_config().get("rag", {})
        rag_mode = rag_cfg.get("mode", "pure_rag")
        
        if rag_mode == "pure_rag":
            use_crag = False  # Khóa cứng vô hiệu hóa CRAG trong chế độ pure_rag
        else:
            use_crag = rag_cfg.get("enable_crag", True)

        # 3. Lọc CRAG Filter (chỉ khi được kích hoạt)
        if use_crag:
            relevant_chunks = evaluate_chunks(query, chunks)
        else:
            relevant_chunks = chunks  # Chế độ pure_rag sử dụng trực tiếp các chunks thô truy xuất được

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

