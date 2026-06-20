"""
utils/ollama_check.py
Utilities to verify Ollama service connectivity and model availability.
"""
import urllib.request
import json
import sys
import io
from utils.config import get_config

def check_ollama_status():
    """
    Check if the Ollama service is running and if the configured judge model is available.
    If Ollama is not running, prints instructions and exits.
    If the model is not found, prints instructions and exits.
    """
    # Configure stdout/stderr to use UTF-8 on Windows to prevent UnicodeEncodeError
    if sys.platform.startswith('win'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except AttributeError:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    cfg = get_config()
    judge_cfg = cfg.get("judge_model", {})
    judge_model = judge_cfg.get("model_name", "qwen2.5:14b")
    base_url = cfg.get("llm", {}).get("base_url", "http://localhost:11434")

    # 1. Check connection to Ollama server endpoint /api/tags
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
    except Exception:
        print("\nKhông kết nối được tới Ollama.")
        print("Vui lòng chạy:")
        print("ollama serve\n")
        sys.exit(1)

    # 2. Check model existence
    installed_models = [m["name"] for m in data.get("models", [])]
    normalized_target = judge_model.lower()
    
    found = False
    for model in installed_models:
        m_name = model.lower()
        if m_name == normalized_target:
            found = True
            break
        # Also match if names are parts of each other
        if normalized_target in m_name or m_name in normalized_target:
            found = True
            break
            
    if not found:
        print(f"\nKhông tìm thấy model {judge_model} trong Ollama.")
        print("Vui lòng chạy:")
        print(f"ollama pull {judge_model}\n")
        sys.exit(1)
