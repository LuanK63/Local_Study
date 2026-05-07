"""
utils/config.py
Load and cache global_config.yaml.
"""
import yaml
from functools import lru_cache
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "global_config.yaml"

@lru_cache(maxsize=1)
def get_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
