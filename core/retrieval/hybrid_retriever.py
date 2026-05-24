"""
core/retrieval/hybrid_retriever.py
Combines BM25 + Vector search using Reciprocal Rank Fusion (RRF).
Also handles document ingestion pipeline (read → chunk → index).
"""
from pathlib import Path
from utils.config import get_config
from core.document_processor.pdf_reader import read_pdf
from core.document_processor.docx_reader import read_docx
from core.document_processor.chunker import chunk_pages, Chunk
from core.retrieval.vector_search import (
    index_chunks, vector_search, collection_count, delete_chunks_by_doc
)
from core.retrieval.bm25_search import (
    build_bm25_index, bm25_search, has_index
)

# BM25 chunks cache per subject
_chunks_cache: dict[str, list[dict]] = {}


# ── Ingestion ─────────────────────────────────────────────────────────────────
def ingest_document(
    file_path: str | Path,
    subject_id: str,
    progress_cb=None,
) -> int:
    """
    Full pipeline: read → chunk → embed → store in ChromaDB + BM25.
    progress_cb(stage, done, total) where stage is one of:
      'read'  — reading PDF pages
      'embed' — generating embeddings
      'store' — saving to ChromaDB
    Returns number of chunks indexed.
    """
    cfg = get_config()["retrieval"]
    path = Path(file_path)
    ext = path.suffix.lower()

    def _read_progress(done, total):
        if progress_cb:
            progress_cb("read", done, total)

    def _index_progress(stage, done, total):
        if progress_cb:
            progress_cb(stage, done, total)

    # Read
    if ext == ".pdf":
        pages = read_pdf(path, progress_cb=_read_progress)
    elif ext in (".docx", ".doc"):
        pages = read_docx(path)
        if progress_cb:
            progress_cb("read", len(pages), len(pages))
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    # Chunk
    chunks: list[Chunk] = chunk_pages(
        pages,
        chunk_size=cfg["chunk_size"],
        chunk_overlap=cfg["chunk_overlap"],
    )
    if not chunks:
        return 0

    # Index in ChromaDB (vector + embed)
    index_chunks(chunks, subject_id, progress_cb=_index_progress)

    # Build / update BM25 index
    chunk_dicts = [
        {"text": c.text, "file_path": c.file_path,
         "page_num": c.page_num, "doc_name": c.doc_name}
        for c in chunks
    ]
    existing = _chunks_cache.get(subject_id, [])
    updated = existing + chunk_dicts
    _chunks_cache[subject_id] = updated
    build_bm25_index(updated, subject_id)

    return len(chunks)


# ── Deletion ──────────────────────────────────────────────────────────────────
def delete_document(file_path: str | Path, subject_id: str) -> int:
    """
    Remove all chunks belonging to a specific file from ChromaDB and BM25.
    Returns number of chunks removed.
    """
    path = Path(file_path)
    doc_name = path.name

    # 1. Remove from ChromaDB
    removed = delete_chunks_by_doc(doc_name, subject_id)

    # 2. Rebuild BM25 without this doc's chunks
    existing = _chunks_cache.get(subject_id, [])
    updated = [c for c in existing if c.get("doc_name") != doc_name]
    _chunks_cache[subject_id] = updated
    if updated:
        build_bm25_index(updated, subject_id)
    else:
        # Clear the BM25 index if empty
        from core.retrieval.bm25_search import _indexes
        _indexes.pop(subject_id, None)

    return removed


def ingest_subject_documents(subject_id: str, documents_dir: str | Path) -> int:
    """Ingest all PDF/DOCX files from a subject's documents directory."""
    total = 0
    doc_dir = Path(documents_dir)
    if not doc_dir.exists():
        return 0
    for f in doc_dir.iterdir():
        if f.suffix.lower() in (".pdf", ".docx", ".doc"):
            total += ingest_document(f, subject_id)
    return total


# ── RRF Fusion ────────────────────────────────────────────────────────────────
def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank + 1)


def _chunk_key(hit: dict) -> str:
    """Stable dedup key for a chunk."""
    return f"{hit['file_path']}:{hit['page_num']}:{hit['text'][:40]}"


def hybrid_search(query: str, subject_id: str, top_k: int = 5) -> list[dict]:
    """
    Multi-query + HyDE hybrid search:
      1. HyDE: sinh câu trả lời giả → embed → vector search (tìm trang 4!)
      2. Multi-query: expand query → BM25 + vector mỗi variant
      3. Merge tất cả với RRF → top_k tốt nhất

    Tại sao cần cả 2?
      - HyDE: tìm chunk định nghĩa chính xác (cao về semantic)
      - Multi-query: tìm chunk liên quan gián tiếp (cao về keyword)
    """
    from core.retrieval.query_expander import expand_query, generate_hyde
    from core.document_processor.embedder import embed_text

    cfg     = get_config()["retrieval"]
    bm25_w  = cfg["bm25_weight"]
    vec_w   = cfg["vector_weight"]
    fetch_k = top_k * cfg.get("retrieval_multiplier", 2)

    scores: dict[str, dict] = {}

    # ── Step 1: HyDE vector search ───────────────────────────────────────────
    # Tạo câu trả lời giả → embed → vector search với embedding đó
    if cfg.get("hyde", True):
        hyde_text = generate_hyde(query)
        if hyde_text:
            try:
                hyde_vec = embed_text(hyde_text)   # embed hypothetical answer
                from core.retrieval.vector_search import _get_collection
                col = _get_collection(subject_id)
                results = col.query(
                    query_embeddings=[hyde_vec],
                    n_results=min(fetch_k, col.count() or 1),
                    include=["documents", "metadatas", "distances"],
                )
                for rank, (doc, meta, dist) in enumerate(zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                )):
                    hit = {
                        "text":      doc,
                        "file_path": meta.get("file_path", ""),
                        "page_num":  meta.get("page_num", ""),
                        "doc_name":  meta.get("doc_name", ""),
                        "score":     1.0 - dist,
                    }
                    key = _chunk_key(hit)
                    if key not in scores:
                        scores[key] = {**hit, "fused": 0.0}
                    scores[key]["fused"] += vec_w * _rrf_score(rank)
            except Exception:
                # Fallback silently if HyDE fails
                pass

    # ── Step 2 & 3: Multi-query search + RRF accumulation ───────────────────
    queries = expand_query(query)   # [original, var1, var2, ...]

    for q in queries:
        vec_results  = vector_search(q, subject_id, top_k=fetch_k)
        bm25_results = bm25_search(q, subject_id, top_k=fetch_k)

        for rank, hit in enumerate(vec_results):
            key = _chunk_key(hit)
            if key not in scores:
                scores[key] = {**hit, "fused": 0.0}
            scores[key]["fused"] += vec_w * _rrf_score(rank)

        for rank, hit in enumerate(bm25_results):
            key = _chunk_key(hit)
            if key not in scores:
                scores[key] = {**hit, "fused": 0.0}
            scores[key]["fused"] += bm25_w * _rrf_score(rank)

    # ── Step 4: Sort & return top_k ─────────────────────────────────────────
    ranked = sorted(scores.values(), key=lambda x: x["fused"], reverse=True)
    return ranked[:top_k]
