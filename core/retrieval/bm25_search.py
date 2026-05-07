"""
core/retrieval/bm25_search.py
BM25 keyword search using rank_bm25.
Index is built in-memory per subject from all indexed chunks.
"""
from rank_bm25 import BM25Okapi
import re

# In-memory BM25 index per subject_id
_indexes: dict[str, tuple[BM25Okapi, list[dict]]] = {}


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenizer (works for EN + VI)."""
    return re.findall(r'\w+', text.lower())


def build_bm25_index(chunks: list[dict], subject_id: str):
    """
    Build BM25 index from list of chunk dicts.
    chunks: [{text, file_path, page_num, doc_name}]
    """
    corpus = [_tokenize(c["text"]) for c in chunks]
    _indexes[subject_id] = (BM25Okapi(corpus), chunks)


def bm25_search(query: str, subject_id: str, top_k: int = 5) -> list[dict]:
    """
    Search BM25 index. Returns top_k hits with score.
    Returns [] if index not built yet.
    """
    if subject_id not in _indexes:
        return []

    bm25, chunks = _indexes[subject_id]
    tokens = _tokenize(query)
    scores = bm25.get_scores(tokens)

    ranked = sorted(
        enumerate(scores), key=lambda x: x[1], reverse=True
    )[:top_k]

    results = []
    for idx, score in ranked:
        if score > 0:
            c = chunks[idx]
            results.append({
                "text":      c["text"],
                "score":     float(score),
                "file_path": c["file_path"],
                "page_num":  c["page_num"],
                "doc_name":  c["doc_name"],
            })
    return results


def has_index(subject_id: str) -> bool:
    return subject_id in _indexes
