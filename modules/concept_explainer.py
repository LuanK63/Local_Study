"""
modules/concept_explainer.py — M1
RAG Q&A with citations. Explains concepts using retrieved document chunks.
"""
from core.retrieval.hybrid_retriever import hybrid_search
from core.pipeline.answer_generator import generate_with_context
from utils.db_schema import get_connection
from datetime import datetime


SYSTEM_HINT = (
    "Hãy giải thích khái niệm rõ ràng với: "
    "1) Định nghĩa, 2) Ví dụ minh họa, 3) Khi nào dùng. "
    "Kèm trích dẫn nguồn tài liệu."
)


def explain(
    query: str,
    subject_id: str,
    subject_hint: str = "",
    top_k: int = 5,
    stream: bool = False,
):
    """
    Retrieve relevant chunks and generate an explanation.
    Returns (answer, sources) or (generator, sources) if stream=True.
    """
    chunks = hybrid_search(query, subject_id, top_k=top_k)
    hint = SYSTEM_HINT + " " + subject_hint
    answer = generate_with_context(query, chunks, system_hint=hint, stream=stream)

    sources = [
        {"doc_name": c["doc_name"], "page_num": c["page_num"],
         "score": round(c.get("fused", c.get("score", 0)), 3)}
        for c in chunks
    ]

    # Persist (only for non-streaming)
    if not stream:
        _save(query, answer, sources, subject_id)

    return answer, sources


def _save(query: str, answer: str, sources: list, subject_id: str):
    import json
    conn = get_connection()
    conn.execute(
        "INSERT INTO conversations (timestamp, subject_id, module, query, answer, sources) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), subject_id, "concept_explainer",
         query, answer, json.dumps(sources))
    )
    conn.commit()
    conn.close()
