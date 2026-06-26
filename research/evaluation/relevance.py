"""
research/evaluation/relevance.py — phiên bản có embedding cache
"""
import httpx
import numpy as np
from rapidfuzz import fuzz
from functools import lru_cache
from utils.config import get_config


@lru_cache(maxsize=1024)
def _get_embedding_cached(text: str) -> tuple[float, ...] | None:
    """
    Cache embedding theo text — tránh gọi Ollama lặp lại
    cho cùng một reference context hoặc chunk.
    lru_cache yêu cầu return type hashable → dùng tuple.
    """
    try:
        cfg = get_config()
        base_url = cfg["llm"]["base_url"]
        
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{base_url}/api/embeddings",
                json={
                    "model": "nomic-embed-text",
                    "prompt": text
                }
            )
            resp.raise_for_status()
            emb = resp.json()["embedding"]
            return tuple(emb)  # hashable cho lru_cache
    except Exception as e:
        print(f"[WARN] Embedding failed: {e}")
        return None


def _cosine_similarity(vec_a: tuple, vec_b: tuple) -> float:
    a = np.array(vec_a)
    b = np.array(vec_b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def evaluate_relevance(
    reference_contexts: list[str],
    chunk_text: str,
    cosine_threshold: float = 0.65,
    fuzzy_threshold: float = 75.0,
) -> bool:
    chunk_lower = chunk_text.lower().strip()
    chunk_emb = _get_embedding_cached(chunk_text)  # cache chunk embedding

    for ref in reference_contexts:
        ref_lower = ref.lower().strip()

        # Lớp 1 — Exact match
        if ref_lower in chunk_lower:
            return True

        # Lớp 2 — Embedding similarity (có cache)
        ref_emb = _get_embedding_cached(ref)

        if ref_emb is not None and chunk_emb is not None:
            sim = _cosine_similarity(ref_emb, chunk_emb)
            if sim >= cosine_threshold:
                return True
        else:
            # Lớp 3 — Fuzzy fallback
            score = fuzz.partial_ratio(ref_lower, chunk_lower)
            if score >= fuzzy_threshold:
                return True

    return False