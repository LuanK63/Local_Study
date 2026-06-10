"""
core/retrieval/hyde.py
Hypothetical Document Embeddings (HyDE) logic for query transformation.
Generates hypothetical documents using the local Ollama LLM.
"""
import httpx
import json
import re
from utils.config import get_config

# Prompts for HyDE generation
_HYDE_PROMPT = """Bạn là một chuyên gia khoa học máy tính và giảng viên CNTT chuyên sâu.
Hãy viết một câu trả lời giả định ngắn gọn (từ 2 đến 4 câu, khoảng 80-150 từ) để giải thích trực tiếp câu hỏi dưới đây.
Đoạn văn này sẽ được dùng để làm tài liệu đối sánh ngữ nghĩa trong cơ sở dữ liệu (vector database search).

YÊU CẦU:
1. Viết dưới dạng câu KHẲNG ĐỊNH hoặc định nghĩa chuyên môn, KHÔNG viết dưới dạng hỏi đáp hay dẫn nhập (ví dụ: không bắt đầu bằng "Theo tôi...", "Câu trả lời là...").
2. Sử dụng thuật ngữ kỹ thuật chính xác, kết hợp cả tiếng Anh và tiếng Việt tương đương nếu cần.
3. Tập trung giải thích bản chất lý thuyết, cơ chế hoạt động hoặc định nghĩa của khái niệm được hỏi.
4. Trả lời bằng cùng ngôn ngữ với câu hỏi gốc.

Câu hỏi: {query}

Câu trả lời giả định:"""

def generate_hypothetical_document(query: str) -> str:
    """
    Generate a hypothetical document (answer) for the query using the local LLM via Ollama.
    Returns the original query if generation fails or is disabled.
    """
    cfg = get_config()
    ret_cfg = cfg.get("retrieval", {})
    hyde_cfg = ret_cfg.get("hyde", {})
    
    # Check if enabled in config
    if not hyde_cfg.get("enabled", True):
        print("[HyDE] HyDE is disabled in configuration.")
        return query
        
    llm_cfg = cfg.get("llm", {})
    model = hyde_cfg.get("model", llm_cfg.get("model"))
    temperature = hyde_cfg.get("temperature", 0.3)
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": _HYDE_PROMPT.format(query=query)}
        ],
        "options": {"temperature": temperature},
        "stream": False
    }
    
    url = f"{llm_cfg.get('base_url', 'http://localhost:11434')}/api/chat"
    timeout = llm_cfg.get("timeout", 120)
    
    try:
        print(f"[HyDE] Generating hypothetical document using model '{model}'...")
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            content = resp.json()["message"]["content"].strip()
            
            # Clean up potential markdown formatting wrapping the output
            if content.startswith("```"):
                content = re.sub(r"^```[a-zA-Z]*\n", "", content)
                content = re.sub(r"\n```$", "", content)
            
            cleaned_content = content.strip()
            print(f"[HyDE] Successfully generated hypothetical document:\n\"\"\"\n{cleaned_content}\n\"\"\"")
            return cleaned_content
    except Exception as e:
        print(f"[HyDE][WARN] Hypothetical document generation failed: {e}. Falling back to original query.")
        return query
