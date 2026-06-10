"""
core/retrieval/bm25_search.py
BM25 keyword search using rank_bm25.
Index is built in-memory per subject from all indexed chunks.
"""
from rank_bm25 import BM25Okapi
import re
from core.retrieval.query_expander import expand_query

# In-memory BM25 index per subject_id
_indexes: dict[str, tuple[BM25Okapi, list[dict]]] = {}


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenizer (works for EN + VI)."""
    return re.findall(r'\w+', text.lower())


def _get_pickle_path(subject_id: str) -> str:
    from utils.config import get_config
    import os
    cfg = get_config()
    db_path = cfg["database"]["path"]
    data_dir = os.path.dirname(db_path)
    bm25_dir = os.path.join(data_dir, "bm25_indices")
    os.makedirs(bm25_dir, exist_ok=True)
    return os.path.join(bm25_dir, f"bm25_{subject_id}.pkl")


def save_bm25_index(subject_id: str):
    """Serialize and save BM25 index to pickle file."""
    import pickle
    if subject_id in _indexes:
        pickle_path = _get_pickle_path(subject_id)
        try:
            with open(pickle_path, "wb") as f:
                pickle.dump(_indexes[subject_id], f)
            print(f"[BM25] Saved index cache to pickle for '{subject_id}'")
        except Exception as e:
            print(f"[WARN] Failed to save BM25 pickle: {e}")


def load_bm25_index(subject_id: str) -> bool:
    """Load BM25 index from pickle file if it exists."""
    import pickle
    import os
    pickle_path = _get_pickle_path(subject_id)
    if os.path.exists(pickle_path):
        try:
            with open(pickle_path, "rb") as f:
                data = pickle.load(f)
            # Validate loaded tuple structure
            if isinstance(data, tuple) and len(data) == 2 and isinstance(data[0], BM25Okapi):
                _indexes[subject_id] = data
                return True
        except Exception as e:
            print(f"[WARN] Failed to load BM25 pickle for '{subject_id}': {e}")
    return False


def delete_bm25_index(subject_id: str):
    """Delete BM25 index cache and pickle file."""
    import os
    _indexes.pop(subject_id, None)
    pickle_path = _get_pickle_path(subject_id)
    if os.path.exists(pickle_path):
        try:
            os.remove(pickle_path)
            print(f"[BM25] Deleted index pickle file for '{subject_id}'")
        except Exception as e:
            print(f"[WARN] Failed to delete BM25 pickle: {e}")


def build_bm25_index(chunks: list[dict], subject_id: str):
    """
    Build BM25 index from list of chunk dicts.
    chunks: [{text, file_path, page_num, doc_name}]
    """
    corpus = [_tokenize(c["text"]) for c in chunks]
    _indexes[subject_id] = (BM25Okapi(corpus), chunks)
    save_bm25_index(subject_id)



def bm25_search(query: str, subject_id: str, top_k: int = 5) -> list[dict]:
    """
    Search BM25 index. Returns top_k hits with score.
    Tự động expand query (EN → VI synonyms) để match thuật ngữ tiếng Việt trong tài liệu.
    Returns [] if index not built yet.
    """
    if subject_id not in _indexes:
        return []

    bm25, chunks = _indexes[subject_id]

    # Expand query: thêm thuật ngữ tiếng Việt tương đương
    # "stack là gì" → "stack ngăn xếp là gì" → BM25 match cả trang định nghĩa lẫn trang code
    expanded_query = expand_query(query)
    if expanded_query != query:
        print(f"[BM25] Query expanded: '{query}' → '{expanded_query}'")

    tokens = _tokenize(expanded_query)
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
                "parent_id": c.get("parent_id", ""),   # có thể rỗng với flat chunks cũ
            })
    return results



def has_index(subject_id: str) -> bool:
    return subject_id in _indexes
