"""
core/retrieval/vector_search.py
ChromaDB vector search. Each subject has its own isolated collection.
"""
import sys
import types

# ── Bypass ChromaDB native import checks on Windows ─────────────────────────-
# ChromaDB may attempt to import onnxruntime / tokenizers / transformers / torch.
# For our client-only vector delete/search operations we don't need those modules.
class _DummyModule(types.ModuleType):
    def __getattr__(self, name):
        return _DummyModule(name)
    def __call__(self, *args, **kwargs):
        return self
    def __iter__(self):
        return iter([])

for _mod in ("onnxruntime", "tokenizers", "transformers", "torch"):
    if _mod not in sys.modules:
        sys.modules[_mod] = _DummyModule(_mod)
# ──────────────────────────────────────────────────────────────────────────────

import chromadb
from pathlib import Path
from typing import Optional
from utils.config import get_config
from core.document_processor.chunker import Chunk
from core.document_processor.embedder import embed_text, embed_chunks

_client: Optional[chromadb.PersistentClient] = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        db_path = get_config()["chromadb"]["path"]
        Path(db_path).mkdir(parents=True, exist_ok=True)
        from chromadb.config import Settings
        _client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False)
        )
    return _client


def _get_collection(subject_id: str):
    return _get_client().get_or_create_collection(
        name=subject_id,
        metadata={"hnsw:space": "cosine"},
        embedding_function=None
    )


# ── Index ────────────────────────────────────────────────────────────────────────────────
def index_chunks(
    chunks: list[Chunk],
    subject_id: str,
    progress_cb=None,
):
    """
    Embed and store flat chunks into ChromaDB (legacy/backward-compat).
    progress_cb(stage, done, total) — stage: 'embed' or 'store'
    """
    from core.document_processor.embedder import embed_chunks

    def _embed_progress(done, total):
        if progress_cb:
            progress_cb("embed", done, total)

    col = _get_collection(subject_id)
    vectors = embed_chunks(chunks, progress_cb=_embed_progress)

    ids = [f"{c.doc_name}_p{c.page_num}_c{c.chunk_idx}" for c in chunks]
    docs = [c.text for c in chunks]
    metas = [
        {
            "file_path": c.file_path,
            "page_num":  c.page_num,
            "doc_name":  c.doc_name,
            "chunk_idx": c.chunk_idx,
            "parent_id": getattr(c, "parent_id", ""),
            **getattr(c, "headers", {})
        }
        for c in chunks
    ]

    # Upsert in batches of 200
    batch = 200
    for i in range(0, len(ids), batch):
        col.upsert(
            ids=ids[i:i+batch],
            embeddings=vectors[i:i+batch],
            documents=docs[i:i+batch],
            metadatas=metas[i:i+batch],
        )
        if progress_cb:
            progress_cb("store", min(i + batch, len(ids)), len(ids))


def index_parent_chunks(
    parent_chunks: list,
    subject_id: str,
    progress_cb=None,
):
    """
    Embed và lưu child chunks vào ChromaDB, kèm parent_id và header metadata.
    parent_chunks: list[ParentChunk] từ chunk_pages_hierarchical().
    Parent text được lưu riêng trong SQLite (không lưu vào ChromaDB để tiết kiệm dung lượng).
    progress_cb(stage, done, total) — stage: 'embed' hoặc 'store'
    """
    from core.document_processor.embedder import embed_chunks

    # Flatten tất cả child chunks
    all_children: list[Chunk] = []
    for parent in parent_chunks:
        all_children.extend(parent.children)

    if not all_children:
        return

    def _embed_progress(done, total):
        if progress_cb:
            progress_cb("embed", done, total)

    col     = _get_collection(subject_id)
    vectors = embed_chunks(all_children, progress_cb=_embed_progress)

    ids  = [f"{c.doc_name}_p{c.page_num}_c{c.chunk_idx}" for c in all_children]
    docs = [c.text for c in all_children]
    metas = [
        {
            "file_path": c.file_path,
            "page_num":  c.page_num,
            "doc_name":  c.doc_name,
            "chunk_idx": c.chunk_idx,
            "parent_id": c.parent_id,   # key để lookup SQLite
            **getattr(c, "headers", {})
        }
        for c in all_children
    ]

    batch = 200
    for i in range(0, len(ids), batch):
        col.upsert(
            ids=ids[i:i+batch],
            embeddings=vectors[i:i+batch],
            documents=docs[i:i+batch],
            metadatas=metas[i:i+batch],
        )
        if progress_cb:
            progress_cb("store", min(i + batch, len(ids)), len(ids))



# ── Search ────────────────────────────────────────────────────────────────────────────────
def vector_search(query: str, subject_id: str, top_k: int = 5) -> list[dict]:
    """
    Search for top_k most similar chunks to query.
    Returns list of {text, score, file_path, page_num, doc_name, parent_id}.
    """
    col = _get_collection(subject_id)
    q_vec = embed_text(query)
    
    # Logging chiều dữ liệu vector embedding để debug
    print(f"[RAG DEBUG] Query embedding dimension: {len(q_vec)}")

    results = col.query(
        query_embeddings=[q_vec],
        n_results=min(top_k, col.count() or 1),
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        meta_dict = meta if meta is not None else {}
        hits.append({
            "text":      doc,
            "score":     1.0 - dist,   # cosine distance → similarity
            "file_path": meta_dict.get("file_path", ""),
            "page_num":  meta_dict.get("page_num", 0),
            "doc_name":  meta_dict.get("doc_name", ""),
            "parent_id": meta_dict.get("parent_id", ""),   # có thể rỗng với flat chunks cũ
        })
    return hits


def collection_count(subject_id: str) -> int:
    return _get_collection(subject_id).count()


def delete_chunks_by_doc(doc_name: str, subject_id: str) -> int:
    """
    Delete all ChromaDB chunks where metadata doc_name == doc_name.
    Returns the number of chunks deleted.
    """
    col = _get_collection(subject_id)
    # Query IDs matching this doc
    results = col.get(
        where={"doc_name": {"$eq": doc_name}},
        include=[],
    )
    ids = results.get("ids", [])
    if ids:
        col.delete(ids=ids)
    return len(ids)
