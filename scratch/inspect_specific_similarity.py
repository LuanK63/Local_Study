"""
scratch/inspect_specific_similarity.py
Calculate similarity score of child chunks belonging to parent 152 against the query 'stack là gì'.
"""
import sys
import numpy as np

# Reconfigure stdout to use UTF-8
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.append("c:\\Users\\LUAN\\Desktop\\Local_Study_RAG_Agent")

from core.retrieval.vector_search import _get_collection
from core.document_processor.embedder import embed_text

def cosine_similarity(v1, v2):
    dot = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot / (norm1 * norm2))

def main():
    query = "stack là gì"
    target_parent_id = "Giai thuat va Lap Trinh - cau truc du lieu va giai thuat by Lê Minh Hoàng (z-lib.org)_p64_parent152"
    
    q_vec = embed_text(query)
    
    col = _get_collection("dsa")
    all_data = col.get(include=["documents", "metadatas", "embeddings"])
    
    found = False
    for doc, meta, emb in zip(all_data["documents"], all_data["metadatas"], all_data["embeddings"]):
        if meta.get("parent_id") == target_parent_id:
            found = True
            sim = cosine_similarity(q_vec, emb)
            print(f"Child doc: {doc.strip()}")
            print(f"Metadata: {meta}")
            print(f"Cosine Similarity: {sim:.4f}")
            print("-" * 80)
            
    if not found:
        print(f"No child chunks found with parent_id: {target_parent_id}")

if __name__ == "__main__":
    main()
