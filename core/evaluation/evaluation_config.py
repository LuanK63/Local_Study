"""
core/evaluation/evaluation_config.py
Configuration for Ragas evaluation using local Ollama model.
"""
from utils.config import get_config

# Load evaluation configuration from global_config.yaml
_cfg = get_config()
_judge_cfg = _cfg.get("judge_model", {})

JUDGE_PROVIDER = _judge_cfg.get("provider", "ollama")
JUDGE_MODEL = _judge_cfg.get("model_name", "qwen2.5:14b")
TEMPERATURE = _judge_cfg.get("temperature", 0)
NUM_CTX = _judge_cfg.get("num_ctx", 4096)
TIMEOUT = _judge_cfg.get("timeout", 600)

