"""
research/evaluation/relevance.py — phiên bản có embedding cache
"""
import re
import httpx
import numpy as np
from rapidfuzz import fuzz
from functools import lru_cache
from utils.config import get_config

# Ngưỡng containment cho dataset v5
V5_CONTAINMENT_THRESHOLD = 0.5


def _normalize_for_containment(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def compute_ref_containment(reference: str, chunk_text: str) -> float:
    """
    Tỷ lệ containment (token recall): phần trăm token của reference xuất hiện trong chunk.
    Substring đủ → 1.0. Không dùng embedding/cosine.
    """
    ref_norm = _normalize_for_containment(reference)
    chunk_norm = _normalize_for_containment(chunk_text)
    if not ref_norm:
        return 0.0
    if ref_norm in chunk_norm:
        return 1.0

    ref_tokens = re.findall(r"\w+", ref_norm)
    if not ref_tokens:
        return 0.0

    hit = sum(1 for token in ref_tokens if token in chunk_norm)
    return hit / len(ref_tokens)


def best_ref_containment(reference_contexts: list[str], chunk_text: str) -> float:
    if not reference_contexts:
        return 0.0
    return max(compute_ref_containment(ref, chunk_text) for ref in reference_contexts)


def evaluate_containment(
    reference_contexts: list[str],
    chunk_text: str,
    threshold: float = V5_CONTAINMENT_THRESHOLD,
) -> bool:
    return best_ref_containment(reference_contexts, chunk_text) >= threshold


def uses_containment_eval(dataset_version: str) -> bool:
    return "dpr_containment" in dataset_version


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