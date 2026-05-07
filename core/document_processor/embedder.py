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
    url = f"{_get_ollama_url()}/api/embed"
    response = httpx.post(
        url,
        json={"model": _get_model(), "input": text},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["embeddings"][0]


def embed_chunks(
    chunks: list[Chunk],
    batch_size: int = 32,
    progress_cb: Callable[[int, int], None] | None = None,
) -> list[list[float]]:
    """
    Embed a list of chunks in batches. Returns list of vectors.
    batch_size=32 balances memory and speed for large books.
    progress_cb(done, total) called after each batch.
    """
    vectors = []
    url = f"{_get_ollama_url()}/api/embed"
    model = _get_model()
    total = len(chunks)

    for i in range(0, total, batch_size):
        batch = chunks[i: i + batch_size]
        texts = [c.text for c in batch]
        response = httpx.post(
            url,
            json={"model": model, "input": texts},
            timeout=300,   # 5 min timeout for large batches
        )
        response.raise_for_status()
        vectors.extend(response.json()["embeddings"])
        if progress_cb:
            progress_cb(min(i + batch_size, total), total)

    return vectors
