"""
scratch/inspect_raw_vector_scores.py
Print top 15 vector search results with no truncation.
"""
import sys

# Reconfigure stdout to use UTF-8
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.append("c:\\Users\\LUAN\\Desktop\\Local_Study_RAG_Agent")

from core.retrieval.vector_search import vector_search

def main():
    subject_id = "dsa"
    query = "stack là gì"
    
    hits = vector_search(query, subject_id, top_k=15)
    print("=== RAW VECTOR SEARCH RESULTS ===")
    for i, h in enumerate(hits, 1):
        print(f"[{i}] Score={h['score']:.4f} | Page={h['page_num']} | Doc={h['doc_name']}")
        print(f"    Text: {h['text'].strip()[:200]}...")
        print("-" * 80)

if __name__ == "__main__":
    main()
