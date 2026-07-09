"""
core/retrieval/hybrid_retriever.py
Combines BM25 + Vector search using Reciprocal Rank Fusion (RRF).
Also handles document ingestion pipeline (read → chunk → index).

Parent-Child Chunking:
  - Child chunks (nhỏ, 300 ký tự) được embed vào ChromaDB + BM25 để search chính xác.
  - Parent chunks (lớn, 1200 ký tự) được lưu bền vững trong SQLite (parent_chunks table).
  - Sau RRF fusion, _resolve_parents() thay thế child text bằng parent text từ SQLite.
  - _parent_cache là L1 in-memory cache để tránh query SQLite lặp lại trong 1 session.
"""
from pathlib import Path
import time
import unicodedata
from utils.config import get_config
from core.document_processor.pdf_reader import read_pdf
from core.document_processor.docx_reader import read_docx
from core.document_processor.chunker import ParentChunk
from core.document_processor.chunking.factory import get_chunker
from utils.experiment_logger import log_ingestion
from core.retrieval.vector_search import (
    index_parent_chunks, vector_search, delete_chunks_by_doc
)
from core.retrieval.bm25_search import (
    build_bm25_index, bm25_search
)

# ── In-memory stores ──────────────────────────────────────────────────────────
# BM25 chunks cache: {subject_id: list[dict]}
_chunks_cache: dict[str, list[dict]] = {}

# L1 cache cho parent text — tránh query SQLite mỗi lần search
# {subject_id: {parent_id: parent_text}}
_parent_cache: dict[str, dict[str, str]] = {}


def resolve_retrieval_subject_id(subject_id: str) -> str:
    """
    Chọn namespace ChromaDB / SQLite parent_chunks khi truy vấn.
    Ưu tiên collection chính (chroma_collection); nếu rỗng, thử {subject}_{chunking_strategy}.
    """
    from utils.subject_loader import get_subject
    from core.retrieval.vector_search import collection_count

    try:
        cfg = get_subject(subject_id)
        primary = cfg.chroma_collection or subject_id
    except ValueError:
        primary = subject_id

    try:
        if collection_count(primary) > 0:
            return primary
    except Exception:
        pass

    strategy = get_config().get("retrieval", {}).get("chunking_strategy", "parent_child")
    fallback = f"{subject_id}_{strategy}"
    if fallback != primary:
        try:
            fb_count = collection_count(fallback)
            if fb_count > 0:
                print(f"[Retrieval] Using '{fallback}' ({fb_count} chunks); '{primary}' is empty")
                return fallback
        except Exception as exc:
            print(f"[WARN] resolve_retrieval_subject_id fallback failed: {exc}")

    return primary


# ── SQLite parent store helpers ───────────────────────────────────────────────
def _get_db_conn():
    """Trả về sqlite3 connection đến study_agent.db."""
    import sqlite3
    from utils.config import get_config
    path = get_config()["database"]["path"]
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _db_save_parents(parent_chunks: list[ParentChunk], subject_id: str) -> None:
    """
    Upsert tất cả parent chunks vào SQLite.
    Dùng INSERT OR REPLACE để xử lý re-ingest file (parent_id không đổi).
    """
    conn = _get_db_conn()
    try:
        conn.executemany(
            """
            INSERT OR REPLACE INTO parent_chunks
                (subject_id, parent_id, parent_text, file_path, page_num, doc_name)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (subject_id, p.parent_id, p.text, p.file_path, p.page_num, p.doc_name)
                for p in parent_chunks
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _db_load_parents(subject_id: str) -> dict[str, str]:
    """
    Load toàn bộ {parent_id: parent_text} của một subject từ SQLite.
    Dùng để populate _parent_cache khi warm_up hoặc cache miss.
    """
    conn = _get_db_conn()
    try:
        rows = conn.execute(
            "SELECT parent_id, parent_text FROM parent_chunks WHERE subject_id = ?",
            (subject_id,),
        ).fetchall()
        return {row["parent_id"]: row["parent_text"] for row in rows}
    finally:
        conn.close()


def _db_delete_parents_by_doc(doc_name: str, subject_id: str) -> int:
    """
    Xóa tất cả parent chunks của một file (theo doc_name = stem, không extension).
    Trả về số dòng đã xóa.
    """
    conn = _get_db_conn()
    try:
        cur = conn.execute(
            "DELETE FROM parent_chunks WHERE subject_id = ? AND doc_name = ?",
            (subject_id, doc_name),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def _get_parent_text(subject_id: str, parent_id: str) -> str | None:
    """
    Lấy parent text cho một parent_id cụ thể.
    Tra L1 cache trước, nếu miss thì load toàn bộ subject từ SQLite.
    """
    # L1 cache hit
    subj_cache = _parent_cache.get(subject_id)
    if subj_cache is not None:
        return subj_cache.get(parent_id)

    # Cache miss → load toàn bộ subject vào cache
    loaded = _db_load_parents(subject_id)
    _parent_cache[subject_id] = loaded
    return loaded.get(parent_id)


# ── Startup warm-up ───────────────────────────────────────────────────────────
def warm_up_bm25(subject_ids: list[str]) -> None:
    """
    Warm up or rebuild BM25 index from pickle cache or fall back to ChromaDB for all subjects.
    _parent_cache sẽ được populate lazy khi có query đầu tiên (từ SQLite).
    Phải gọi khi app khởi động.
    """
    from core.retrieval.bm25_search import load_bm25_index
    from core.retrieval.vector_search import _get_collection

    for sid in subject_ids:
        storage_id = resolve_retrieval_subject_id(sid)
        try:
            # 1. Thử tải index từ file pickle trước (logical id hoặc storage id)
            if load_bm25_index(sid):
                from core.retrieval.bm25_search import _indexes
                _chunks_cache[sid] = _indexes[sid][1]
                print(f"[WarmUp] Loaded BM25 index from pickle cache for '{sid}'")
                continue
            if storage_id != sid and load_bm25_index(storage_id):
                from core.retrieval.bm25_search import _indexes
                _indexes[sid] = _indexes[storage_id]
                _chunks_cache[sid] = _indexes[sid][1]
                print(f"[WarmUp] Loaded BM25 cache '{storage_id}' for subject '{sid}'")
                continue

            # 2. Fallback nếu không có file cache pickle
            col = _get_collection(storage_id)
            if col.count() == 0:
                continue

            results = col.get(include=["documents", "metadatas"])
            chunks = []
            for doc, meta in zip(results["documents"], results["metadatas"]):
                chunks.append({
                    "text":      doc,
                    "file_path": meta.get("file_path", ""),
                    "page_num":  meta.get("page_num", 0),
                    "doc_name":  meta.get("doc_name", ""),
                    "parent_id": meta.get("parent_id", ""),
                })

            _chunks_cache[sid] = chunks
            build_bm25_index(chunks, sid)
            print(f"[WarmUp] '{sid}': {len(chunks)} child chunks indexed from ChromaDB")
        except Exception as e:
            print(f"[WarmUp] Failed for '{sid}': {e}")


# ── Ingestion ─────────────────────────────────────────────────────────────────
def ingest_document(
    file_path: str | Path,
    subject_id: str,
    progress_cb=None,
    max_pages: int | None = None,
) -> int:
    """
    Full pipeline: read → hierarchical chunk → embed (child) → store.

    - Child chunks → ChromaDB (vector) + BM25 (keyword)
    - Parent chunks → SQLite (bền vững, không mất sau restart)

    progress_cb(stage, done, total): 'read' | 'embed' | 'store'
    Returns total number of child chunks indexed.
    """
    cfg  = get_config()["retrieval"]
    path = Path(file_path)
    ext  = path.suffix.lower()

    def _read_progress(done, total):
        if progress_cb:
            progress_cb("read", done, total)

    def _index_progress(stage, done, total):
        if progress_cb:
            progress_cb(stage, done, total)

    # ── Read ──────────────────────────────────────────────────────────────────
    if ext == ".pdf":
        pages = read_pdf(path, progress_cb=_read_progress, max_pages=max_pages)
    elif ext in (".docx", ".doc"):
        pages = read_docx(path)
        if progress_cb:
            progress_cb("read", len(pages), len(pages))
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    # ── Chunking ──────────────────────────────────────────────────────────────
    start_time = time.time()
    
    chunker = get_chunker()
    parent_chunks = chunker.split_documents(pages)

    if not parent_chunks:
        return 0
        
    indexing_time_s = time.time() - start_time

    # Xóa toàn bộ chunk cũ của file này trước khi index chunk mới
    try:
        delete_document(path, subject_id)
    except Exception as e:
        print(f"[WARN] Failed to delete old chunks for {path.name}: {e}")

    # ── Index child chunks vào ChromaDB ──────────────────────────────────────
    index_parent_chunks(parent_chunks, subject_id, progress_cb=_index_progress)

    # ── Lưu parent text vào SQLite (bền vững) ────────────────────────────────
    _db_save_parents(parent_chunks, subject_id)

    # ── Invalidate L1 cache cho subject này ──────────────────────────────────
    _parent_cache.pop(subject_id, None)

    # ── Build / update BM25 từ child chunks ──────────────────────────────────
    child_dicts = [
        {
            "text":      child.text,
            "file_path": child.file_path,
            "page_num":  child.page_num,
            "doc_name":  child.doc_name,
            "parent_id": child.parent_id,
        }
        for parent in parent_chunks
        for child in parent.children
    ]
    existing = _chunks_cache.get(subject_id, [])
    updated  = existing + child_dicts
    _chunks_cache[subject_id] = updated
    build_bm25_index(updated, subject_id)

    total_children = sum(len(p.children) for p in parent_chunks)
    
    # ── Log Ingestion to DB & CSV ─────────────────────────────────────────────
    try:
        strategy_name = type(chunker).__name__.replace("Chunker", "").lower()
        if hasattr(chunker, "child_size"):
            c_size = chunker.child_size
            c_overlap = chunker.child_overlap
        elif hasattr(chunker, "chunk_size"):
            c_size = chunker.chunk_size
            c_overlap = chunker.chunk_overlap
        else:
            c_size = 0
            c_overlap = 0
            
        chunk_lengths = [int(len(child["text"].split()) * 1.3) for child in child_dicts]
        total_tokens = sum(chunk_lengths)
        
        log_ingestion(
            subject_id=subject_id,
            strategy=strategy_name,
            chunk_size=c_size,
            chunk_overlap=c_overlap,
            num_chunks=total_children,
            chunk_lengths=chunk_lengths,
            total_tokens=total_tokens,
            indexing_time_s=indexing_time_s
        )
    except Exception as log_err:
        print(f"[WARN] Failed to log ingestion metrics: {log_err}")

    print(
        f"[Ingest] '{subject_id}': {len(parent_chunks)} parents saved to SQLite, "
        f"{total_children} child chunks indexed"
    )
    return total_children


# ── Deletion ──────────────────────────────────────────────────────────────────
def delete_document(file_path: str | Path, subject_id: str) -> int:
    """
    Remove all chunks of a file from ChromaDB, BM25, SQLite, và L1 cache.
    Returns number of child chunks removed from ChromaDB.
    """
    path     = Path(file_path)
    doc_stem = path.stem   # không extension — khớp doc_name lưu trong ChromaDB, BM25, SQLite
    # (ChromaDB, BM25, SQLite đều lưu doc_name = path.stem, không có extension)

    # 1. Xóa khỏi ChromaDB
    # doc_name lưu trong metadata = path.stem (không extension) — phải dùng doc_stem
    removed = delete_chunks_by_doc(doc_stem, subject_id)

    # 2. Rebuild BM25 không có doc này (BM25 cũng lưu doc_name = stem)
    existing = _chunks_cache.get(subject_id, [])
    updated  = [c for c in existing if c.get("doc_name") != doc_stem]
    _chunks_cache[subject_id] = updated
    if updated:
        build_bm25_index(updated, subject_id)
    else:
        from core.retrieval.bm25_search import delete_bm25_index
        delete_bm25_index(subject_id)

    # 3. Xóa parent rows khỏi SQLite (doc_name = stem, không extension)
    deleted_parents = _db_delete_parents_by_doc(doc_stem, subject_id)

    # 4. Invalidate L1 cache
    _parent_cache.pop(subject_id, None)

    print(
        f"[Delete] '{subject_id}/{doc_stem}': "
        f"{removed} child chunks, {deleted_parents} parents removed"
    )
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


# ── Parent Resolution ─────────────────────────────────────────────────────────
def _resolve_parents(child_hits: list[dict], subject_id: str) -> list[dict]:
    """
    Sau khi RRF fusion trên child chunks, thay thế child text bằng parent text
    từ SQLite (qua L1 cache) để LLM nhận ngữ cảnh đầy đủ hơn.

    Deduplication: nhiều child cùng parent → chỉ giữ lại 1 (fused score cao nhất,
    tức bản đầu tiên vì danh sách đã sort giảm dần).

    Backward-compat: nếu parent_id rỗng hoặc không tồn tại trong SQLite,
    giữ nguyên child text (hoạt động như flat chunking cũ).
    """
    result: list[dict] = []
    seen: set[str] = set()

    for hit in child_hits:
        pid = hit.get("parent_id", "")

        if pid:
            if pid in seen:
                continue  # bỏ qua child trùng parent
            seen.add(pid)

            parent_text = _get_parent_text(subject_id, pid)
            if parent_text:
                result.append({**hit, "text": parent_text})
            else:
                # parent_id có nhưng không tìm thấy trong SQLite → flat fallback
                result.append(hit)
        else:
            # Flat chunk (không có parent_id) → passthrough, dedup theo text prefix
            fallback_key = hit["text"][:40]
            if fallback_key not in seen:
                seen.add(fallback_key)
                result.append(hit)

    return result


# ── Hybrid Search (main entry) ────────────────────────────────────────────────
def hybrid_search(query: str, subject_id: str, top_k: int = 5) -> list[dict]:
    """
    Combine BM25 + Vector results using Reciprocal Rank Fusion,
    sau đó resolve child chunks → parent chunks (từ SQLite) để LLM có đủ ngữ cảnh.

    Returns top_k results sorted by fused score (text là parent text nếu có).
    """
    cfg    = get_config()["retrieval"]
    bm25_w = cfg["bm25_weight"]
    vec_w  = cfg["vector_weight"]

    # Fetch nhiều hơn top_k để sau dedup parent vẫn đủ kết quả
    fetch_k = top_k * 3
    storage_id = resolve_retrieval_subject_id(subject_id)

    vec_results  = vector_search(query, storage_id, top_k=fetch_k)
    bm25_results = bm25_search(query, subject_id, top_k=fetch_k)

    # Logging trung gian số lượng kết quả thô thu được
    print(f"[RAG DEBUG] -> Hybrid Search: Vector retrieved {len(vec_results)} chunks, BM25 retrieved {len(bm25_results)} chunks.")

    # RRF score map: key = (file_path:page_num:text[:40])
    scores: dict[str, dict] = {}

    for rank, hit in enumerate(vec_results):
        key = f"{hit['file_path']}:{hit['page_num']}:{hit['text'][:40]}"
        if key not in scores:
            scores[key] = {**hit, "fused": 0.0}
        scores[key]["fused"] += vec_w * _rrf_score(rank)

    for rank, hit in enumerate(bm25_results):
        key = f"{hit['file_path']}:{hit['page_num']}:{hit['text'][:40]}"
        if key not in scores:
            scores[key] = {**hit, "fused": 0.0}
        scores[key]["fused"] += bm25_w * _rrf_score(rank)

    ranked = sorted(scores.values(), key=lambda x: x["fused"], reverse=True)[:fetch_k]

    # Resolve child → parent text từ SQLite, top_k sau dedup
    resolved = _resolve_parents(ranked, storage_id)
    return resolved[:top_k]


# ── Semantic Search (pure vector) ─────────────────────────────────────────────
def semantic_search(query: str, subject_id: str, top_k: int = 5) -> list[dict]:
    """
    Pure vector/embedding search — không dùng BM25.
    Tìm kiếm theo nghĩa (semantic similarity) thay vì từ khóa.

    Ưu điểm: tốt với câu hỏi diễn đạt khác từ ngữ trong tài liệu.
    Nhược điểm: yếu hơn khi query có thuật ngữ kỹ thuật cụ thể (tên hàm, ký hiệu toán).
    """
    fetch_k = top_k * 3
    storage_id = resolve_retrieval_subject_id(subject_id)
    hits    = vector_search(query, storage_id, top_k=fetch_k)
    # Đặt fused = score để _resolve_parents có thể sort (nếu cần)
    for h in hits:
        h.setdefault("fused", h.get("score", 0.0))
    resolved = _resolve_parents(hits, storage_id)
    return resolved[:top_k]


# ── BM25-only Search (pure keyword) ───────────────────────────────────────────
def bm25_only_search(query: str, subject_id: str, top_k: int = 5) -> list[dict]:
    """
    Pure BM25 keyword search — không dùng vector embedding.
    Nhanh hơn (không cần query ChromaDB), tốt với từ khóa chính xác.

    Ưu điểm: tốt với thuật ngữ kỹ thuật, tên hàm, ký hiệu toán.
    Nhược điểm: yếu hơn khi paraphrase (cùng nghĩa khác từ).
    """
    fetch_k = top_k * 3
    storage_id = resolve_retrieval_subject_id(subject_id)
    hits    = bm25_search(query, subject_id, top_k=fetch_k)
    for h in hits:
        h.setdefault("fused", h.get("score", 0.0))
    resolved = _resolve_parents(hits, storage_id)
    return resolved[:top_k]


# ── Unified Search Dispatcher ─────────────────────────────────────────────────

# Stopwords tiếng Việt + tiếng Anh thường gặp trong câu hỏi học thuật
_STOPWORDS = {
    # VI
    "là", "gì", "và", "hay", "hoặc", "như", "thế", "nào", "sao", "vì",
    "để", "cách", "làm", "trong", "của", "với", "về", "các", "một",
    "cho", "khi", "nếu", "bằng", "có", "không", "được", "theo", "tại",
    "mà", "ra", "lên", "xuống", "từ", "đến", "này", "đó", "những",
    "giải", "thích", "hãy", "liệt", "kê", "so", "sánh", "trình", "bày",
    # EN
    "what", "is", "are", "how", "does", "do", "the", "a", "an",
    "in", "of", "to", "and", "or", "for", "with", "from",
    "explain", "describe", "list", "compare",
}


def _filter_by_keywords(
    results: list[dict],
    query: str,
    min_keep: int = 1,
) -> list[dict]:
    """
    Lọc các chunk mà parent text KHÔNG chứa bất kỳ KEY PHRASE quan trọng nào của query.
    """
    from core.retrieval.query_expander import _TECH_DICT, _normalize
    import re

    q_lower = query.lower()
    key_phrases: list[str] = []

    # Ưu tiên phrase dài trước
    sorted_terms = sorted(_TECH_DICT.keys(), key=lambda k: len(k), reverse=True)
    for en_term in sorted_terms:
        pattern = r'\b' + re.escape(en_term) + r'\b'
        if re.search(pattern, q_lower):
            key_phrases.append(en_term)           # "stack"
            key_phrases.extend(_TECH_DICT[en_term])  # "ngăn xếp", "ngăn-xếp"

    # Thêm non-stopword tokens dài từ query (e.g., "đệ quy", "vun đống")
    raw_tokens = re.findall(r'\w+', q_lower)
    for tok in raw_tokens:
        if tok not in _STOPWORDS and len(tok) >= 4:
            if not any(tok in ph for ph in key_phrases):
                key_phrases.append(tok)

    if not key_phrases:
        return results

    kept = []
    dropped = []
    for chunk in results:
        text_lower = chunk.get("text", "").lower()
        # Phrase check: tìm exact phrase trong text (không phải từng token riêng)
        matched = any(phrase.lower() in text_lower for phrase in key_phrases)
        if matched:
            kept.append(chunk)
        else:
            label = f"{chunk.get('doc_name','?')[:30]} Tr.{chunk.get('page_num','?')}"
            dropped.append(label)

    if dropped:
        sample_phrases = [p for p in key_phrases[:4]]
        print(f"[Filter] Loại {len(dropped)} chunk (không chứa phrases {sample_phrases}): {dropped}")

    if len(kept) < min_keep:
        print(f"[Filter] Fallback: trả về {len(results)} chunk (filter quá chặt)")
        return results

    return kept


def search(
    query: str,
    subject_id: str,
    top_k: int = 5,
    mode: str | None = None,
) -> tuple[list[dict], str]:
    """
    Dispatch tới đúng search function theo mode.
    Thực hiện tiền xử lý chuẩn hóa Unicode NFC và ghi log chi tiết phục vụ debug.
    HyDE đã bị gỡ bỏ hoàn toàn khỏi pipeline để tránh làm nhiễu kết quả.
    """
    import unicodedata
    import re

    # Chuẩn hóa Unicode NFC để đồng bộ với văn bản đã normalize khi đọc PDF/DOCX
    query_norm = unicodedata.normalize('NFC', query)

    # ── [RAG DEBUG] LOGGING CÂU HỎI GỐC ──────────────────────────────────────
    print("\n" + "="*80)
    print("[RAG DEBUG]")
    print(f"Original Query:\n{query}\n")

    if mode is None:
        mode = get_config()["retrieval"].get("search_mode", "hybrid")

    mode = mode.lower().strip()
    storage_id = resolve_retrieval_subject_id(subject_id)

    # 1. Chạy Vector Search (Lấy top 20 kết quả thô)
    vec_results = vector_search(query_norm, storage_id, top_k=20)
    print("Vector Search Top 20:")
    for idx, hit in enumerate(vec_results, 1):
        print(f"- [{idx}] Score={hit['score']:.4f} | Page={hit['page_num']} | Doc={hit['doc_name']}")
    print()

    # 2. Chạy BM25 Search (Lấy top 20 kết quả thô)
    bm25_results = bm25_search(query_norm, subject_id, top_k=20)
    print("BM25 Top 20:")
    for idx, hit in enumerate(bm25_results, 1):
        print(f"- [{idx}] Score={hit['score']:.4f} | Page={hit['page_num']} | Doc={hit['doc_name']}")
    print()

    # ── Thiết lập trọng số RRF Fusion ──
    # Tăng trọng số BM25 = 0.7 và giảm Vector = 0.3 để ưu tiên exact keyword match
    if mode == "semantic":
        bm25_w = 0.0
        vec_w  = 1.0
    elif mode == "bm25":
        bm25_w = 1.0
        vec_w  = 0.0
    else:
        # default: hybrid
        mode   = "hybrid"
        bm25_w = 0.5
        vec_w  = 0.5

    # RRF fusion score map: key = (file_path:page_num:text[:40])
    scores: dict[str, dict] = {}

    for rank, hit in enumerate(vec_results):
        key = f"{hit['file_path']}:{hit['page_num']}:{hit['text'][:40]}"
        if key not in scores:
            scores[key] = {**hit, "fused": 0.0}
        scores[key]["fused"] += vec_w * _rrf_score(rank)

    for rank, hit in enumerate(bm25_results):
        key = f"{hit['file_path']}:{hit['page_num']}:{hit['text'][:40]}"
        if key not in scores:
            scores[key] = {**hit, "fused": 0.0}
        scores[key]["fused"] += bm25_w * _rrf_score(rank)

    # Sắp xếp và lấy top 20 của RRF Fusion
    hybrid_top = sorted(scores.values(), key=lambda x: x["fused"], reverse=True)[:20]
    
    print("Hybrid Top 20 (before rerank):")
    for idx, hit in enumerate(hybrid_top, 1):
        print(f"- [{idx}] RRF={hit['fused']:.4f} | Page={hit['page_num']} | Doc={hit['doc_name']}")
    print()

    # 3. Resolve child -> parent text từ SQLite (chuan bi cho Reranker)
    resolved = _resolve_parents(hybrid_top, storage_id)

    # 4. MiniLM Reranker (Top 20 -> Top 4)
    # -------------------------------------------------------------------------
    if resolved:
        try:
            from sentence_transformers import CrossEncoder
            cfg_models = get_config().get("models", {})
            reranker_model = cfg_models.get("reranker_model", "cross-encoder/ms-marco-MiniLM-L-6-v2")

            print(f"[Reranker] Loading CrossEncoder: {reranker_model}...")
            reranker = CrossEncoder(reranker_model)

            pairs = [[query_norm, chunk["text"]] for chunk in resolved]
            rerank_scores = reranker.predict(pairs)

            for idx, chunk in enumerate(resolved):
                chunk["rerank_score"] = float(rerank_scores[idx])
                chunk["fused"] = chunk["rerank_score"]

            resolved = sorted(resolved, key=lambda x: x["rerank_score"], reverse=True)
            print("[Reranker] Reranking thanh cong.")
        except Exception as e:
            print(f"[WARNING] Loi chay MiniLM Reranker, fallback ve RRF: {e}")
    # -------------------------------------------------------------------------
    
    final_top = resolved[:top_k]

    print(f"Final Top {len(final_top)} (after Rerank):")
    for idx, hit in enumerate(final_top, 1):
        print(f"- [{idx}] Score={hit['fused']:.4f} | Page={hit['page_num']} | Doc={hit['doc_name']}")
        safe_text = hit['text'].strip()[:180].replace('\n', ' ')
        print(f"    Text: {safe_text}...")
    print("="*80 + "\n")

    return final_top, mode



