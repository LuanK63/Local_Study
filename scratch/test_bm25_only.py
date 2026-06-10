"""
scratch/test_bm25_only.py
Test script to run BM25-only search for 'stack là gì' and print top chunks and their scores.
"""
import sys

# Reconfigure stdout to use UTF-8
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.append("c:\\Users\\LUAN\\Desktop\\Local_Study_RAG_Agent")

from core.retrieval.hybrid_retriever import warm_up_bm25, bm25_search

def main():
    subject_id = "dsa"
    query = "stack là gì"
    
    print("=== WARMING UP BM25 ===")
    warm_up_bm25([subject_id])
    
    print("\n=== RUNNING BM25 SEARCH ===")
    hits = bm25_search(query, subject_id, top_k=15)
    
    print(f"Total BM25 hits returned: {len(hits)}")
    for i, h in enumerate(hits, 1):
        print(f"[{i}] Score={h['score']:.4f} | Page={h['page_num']} | Doc={h['doc_name']}")
        print(f"    Text: {h['text'].strip()[:180]}...")
        print("-" * 80)

if __name__ == "__main__":
    main()
