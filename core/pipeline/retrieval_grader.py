import httpx
import json
from utils.config import get_config

SYSTEM_GRADER_PROMPT = """Bạn là một kiểm định viên hệ thống RAG độc lập và khách quan.
Nhiệm vụ của bạn là đánh giá mức độ liên quan của các tài liệu/ngữ cảnh được truy xuất đối với câu hỏi của người dùng.
Hãy đưa ra điểm số từ 0 đến 5 dựa trên tiêu chí sau:
- 0: Không liên quan gì tới câu hỏi.
- 1: Rất ít liên quan, không thể trích xuất thông tin hữu ích nào.
- 2: Liên quan yếu, chỉ chứa các từ khóa tương đồng bề nổi.
- 3: Khá liên quan, có thể trả lời được một phần nhỏ của câu hỏi.
- 4: Liên quan tốt, chứa hầu hết các thông tin để trả lời câu hỏi.
- 5: Rất liên quan, chứa thông tin hoàn hảo để trả lời chính xác câu hỏi.

Bạn BẮT BUỘC phải trả về kết quả dưới định dạng JSON duy nhất, có cấu trúc như sau:
{
  "score": <số nguyên từ 0 đến 5>,
  "explanation": "<giải thích ngắn gọn lý do cho điểm số bằng tiếng Việt>"
}
Không thêm bất kỳ văn bản nào khác ngoài JSON này."""

def grade_documents(query: str, chunks: list[dict]) -> dict:
    """
    Grades the relevance of retrieved chunks for a given query using the configured LLM.
    Returns:
        {"score": int, "explanation": str}
    """
    if not chunks:
        return {"score": 0, "explanation": "no_chunks_provided"}
        
    # Concatenate chunk texts
    context_parts = []
    for idx, c in enumerate(chunks, 1):
        doc = c.get("doc_name") or c.get("document") or "unknown"
        page = c.get("page_num") or c.get("page") or "unknown"
        text = c.get("text") or ""
        context_parts.append(f"[Chunk {idx}] Tài liệu: {doc} (Trang: {page})\nNội dung: {text}")
    context_text = "\n\n".join(context_parts)
    
    cfg = get_config()["llm"]
    # Use judge_model if configured, otherwise fallback to standard LLM
    judge_cfg = get_config().get("judge_model", {})
    model_name = judge_cfg.get("model_name") or cfg["model"]
    temperature = judge_cfg.get("temperature", 0.0)
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_GRADER_PROMPT},
            {"role": "user", "content": f"Câu hỏi: {query}\nNgữ cảnh:\n{context_text}"}
        ],
        "options": {"temperature": temperature},
        "stream": False,
        "format": "json"
    }
    
    url = f"{cfg['base_url']}/api/chat"
    timeout = cfg.get("timeout", 60)
    
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            response_text = resp.json()["message"]["content"]
            
        data = json.loads(response_text)
        score = data.get("score")
        explanation = data.get("explanation", "parse_error")
        
        # Ensure score is an integer between 0 and 5
        try:
            score = int(score)
            if score not in (0, 1, 2, 3, 4, 5):
                score = 0
        except Exception:
            score = 0
            
        return {"score": score, "explanation": explanation}
    except Exception as e:
        print(f"[WARN] Grader parsing or call failed: {e}")
        return {"score": 0, "explanation": "parse_error"}
