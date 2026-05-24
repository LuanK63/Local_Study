"""
core/document_processor/embedder.py
Generate embeddings via Ollama's local embedding API.
Uses nomic-embed-text — multilingual, runs fully offline.
Supports large documents with progress callbacks.
"""
import httpx
from typing import Callable
from utils.config import get_config
from core.document_processor.chunker import Chunk


def _get_ollama_url() -> str:
    return get_config()["embedding"]["base_url"]


def _get_model() -> str:
    return get_config()["embedding"]["model"]


def embed_text(text: str) -> list[float]:
    """Embed a single text string. Returns vector."""
    url_modern = f"{_get_ollama_url()}/api/embed"
    url_legacy = f"{_get_ollama_url()}/api/embeddings"
    
    # Try modern API first
    try:
        response = httpx.post(
            url_modern,
            json={"model": _get_model(), "input": text},
            timeout=60,
        )
        if response.status_code == 200:
            return response.json()["embeddings"][0]
    except Exception:
        pass
        
    # Fallback to legacy API
    response = httpx.post(
        url_legacy,
        json={"model": _get_model(), "prompt": text},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def embed_chunks(
    chunks: list[Chunk],
    batch_size: int = 32,
    progress_cb: Callable[[int, int], None] | None = None,
) -> list[list[float]]:
    """
    Embed a list of chunks in batches.
    Tries modern batch /api/embed first. If it fails with 400/404, falls back to legacy one-by-one /api/embeddings.
    """
    url_modern = f"{_get_ollama_url()}/api/embed"
    url_legacy = f"{_get_ollama_url()}/api/embeddings"
    model = _get_model()
    total = len(chunks)
    vectors = []

    # Try modern batch embedding first to see if it's supported
    use_modern = True
    if total > 0:
        try:
            test_batch = chunks[:1]
            test_texts = [c.text for c in test_batch]
            r = httpx.post(
                url_modern,
                json={"model": model, "input": test_texts},
                timeout=10,
            )
            if r.status_code != 200:
                use_modern = False
        except Exception:
            use_modern = False
    else:
        use_modern = False

    if use_modern:
        # Standard modern batching
        for i in range(0, total, batch_size):
            batch = chunks[i: i + batch_size]
            texts = [c.text for c in batch]
            response = httpx.post(
                url_modern,
                json={"model": model, "input": texts},
                timeout=300,   # 5 min timeout for large batches
            )
            response.raise_for_status()
            vectors.extend(response.json()["embeddings"])
            if progress_cb:
                progress_cb(min(i + batch_size, total), total)
    else:
        # Legacy one-by-one embedding
        for i, chunk in enumerate(chunks):
            response = httpx.post(
                url_legacy,
                json={"model": model, "prompt": chunk.text},
                timeout=60,
            )
            response.raise_for_status()
            vectors.append(response.json()["embedding"])
            if progress_cb:
                progress_cb(i + 1, total)

    return vectors
