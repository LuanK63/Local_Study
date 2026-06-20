"""
scratch/test_qwen_judge.py
Quick connection test script for Qwen 14B Ragas LLM Judge.
"""
import sys
import os

# Add project root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ollama_check import check_ollama_status
from langchain_ollama import ChatOllama
from utils.config import get_config

def main():
    print("[TEST] Running Ollama service and model checks...")
    check_ollama_status()
    print("[TEST] Checks passed successfully!")

    cfg = get_config()
    judge_cfg = cfg.get("judge_model", {})
    judge_model = judge_cfg.get("model_name", "qwen2.5:14b")
    temperature = judge_cfg.get("temperature", 0)
    timeout = judge_cfg.get("timeout", 600)
    base_url = cfg.get("llm", {}).get("base_url", "http://localhost:11434")

    print(f"[TEST] Initializing ChatOllama with model={judge_model}, base_url={base_url}...")
    llm = ChatOllama(
        model=judge_model,
        temperature=temperature,
        base_url=base_url,
        timeout=timeout
    )
    
    print("[TEST] Invoking simple prompt 'Hi, are you ready to act as a judge?'...")
    try:
        response = llm.invoke("Hi, are you ready to act as a judge?")
        print("[TEST] Response received:")
        print(response.content)
        print("[TEST] SUCCESS!")
    except Exception as e:
        print(f"[TEST] FAILED: {e}")

if __name__ == "__main__":
    main()
