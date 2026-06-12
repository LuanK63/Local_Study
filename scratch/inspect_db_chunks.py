"""
scratch/inspect_db_chunks.py
Diagnostic script to inspect ChromaDB child chunks and SQLite parent chunks
for stack-related terms, calculate similarity scores, and print detailed comparison.
"""
import sys
import os
import sqlite3
import numpy as np

# Reconfigure stdout to use UTF-8
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add workspace to sys.path
sys.path.append("c:\\Users\\LUAN\\Desktop\\Local_Study_RAG_Agent")

from core.retrieval.vector_search import _get_collection
from core.document_processor.embedder import embed_text
from utils.config import get_config

def cosine_similarity(v1, v2):
    dot = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot / (norm1 * norm2))

def main():
    subject_id = "dsa"
    query = "stack là gì"
    search_terms = ["stack", "ngăn xếp", "lifo", "push", "pop"]
    
    print(f"=== SEARCHING EMBEDDINGS FOR QUERY: '{query}' ===")
    try:
        q_vec = embed_text(query)
        print(f"Query embedding generated. Dimension: {len(q_vec)}")
    except Exception as e:
        print(f"Failed to embed query: {e}")
        return

    # 1. Search SQLite Parent Chunks
    print("\n=== SEARCHING SQLITE PARENT CHUNKS ===")
    cfg = get_config()
    db_path = cfg["database"]["path"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    parent_matches = []
    try:
        cursor = conn.cursor()
        # Find all parent chunks containing any of the search terms
        cursor.execute("SELECT parent_id, page_num, doc_name, parent_text FROM parent_chunks WHERE subject_id = ?", (subject_id,))
        rows = cursor.fetchall()
        print(f"Total parent chunks in SQLite for '{subject_id}': {len(rows)}")
        
        for row in rows:
            text = row["parent_text"].lower()
            if any(term in text for term in search_terms):
                parent_matches.append({
                    "parent_id": row["parent_id"],
                    "page_num": row["page_num"],
                    "doc_name": row["doc_name"],
                    "text": row["parent_text"]
                })
        print(f"Found {len(parent_matches)} parent chunks matching search terms.")
    except Exception as e:
        print(f"Failed to query SQLite: {e}")
    finally:
        conn.close()

    # 2. Search ChromaDB Child Chunks and Compute Similarity
    print("\n=== SEARCHING CHROMADB CHILD CHUNKS & COMPUTING SIMILARITY ===")
    try:
        col = _get_collection(subject_id)
        count = col.count()
        print(f"Total child chunks in ChromaDB: {count}")
        
        # Get all child chunks
        all_data = col.get(include=["documents", "metadatas", "embeddings"])
        docs = all_data["documents"]
        metas = all_data["metadatas"]
        embeddings = all_data["embeddings"]
        
        child_matches = []
        for doc_text, meta, emb in zip(docs, metas, embeddings):
            text_lower = doc_text.lower()
            if any(term in text_lower for term in search_terms):
                sim = cosine_similarity(q_vec, emb)
                child_matches.append({
                    "doc_name": meta.get("doc_name"),
                    "page_num": meta.get("page_num"),
                    "parent_id": meta.get("parent_id"),
                    "text": doc_text,
                    "similarity": sim
                })
        
        # Sort by similarity descending
        child_matches.sort(key=lambda x: x["similarity"], reverse=True)
        
        print(f"\nFound {len(child_matches)} child chunks matching search terms.")
        print("\nTOP 15 MOST SIMILAR STACK-RELATED CHILD CHUNKS:")
        print("-" * 100)
        for i, match in enumerate(child_matches[:15], 1):
            print(f"[{i}] Sim={match['similarity']:.4f} | Page={match['page_num']} | Doc={match['doc_name']} | ParentID={match['parent_id']}")
            print(f"    Text: {match['text'].strip()[:180]}...")
            print("-" * 100)
            
    except Exception as e:
        print(f"Failed to query ChromaDB: {e}")

if __name__ == "__main__":
    main()
