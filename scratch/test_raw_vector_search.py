"""
scratch/test_raw_vector_search.py
Test script to run raw vector search and BM25 search and print results before RRF fusion.
"""
import sys

# Reconfigure stdout to use UTF-8
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.append("c:\\Users\\LUAN\\Desktop\\Local_Study_RAG_Agent")

from core.retrieval.vector_search import vector_search
from core.retrieval.bm25_search import bm25_search
from core.retrieval.hybrid_retriever import warm_up_bm25

def main():
    subject_id = "dsa"
    query = "stack là gì"
    
    print("=== WARMING UP BM25 ===")
    warm_up_bm25([subject_id])
    
    print("\n=== RAW VECTOR SEARCH RESULTS ===")
    vec_results = vector_search(query, subject_id, top_k=15)
    for i, h in enumerate(vec_results, 1):
        print(f"[{i}] Score (1-dist)={h['score']:.4f} | Page={h['page_num']} | Doc={h['doc_name']}")
        print(f"    Text: {h['text'].strip()[:180]}...")
        print("-" * 80)
        
    print("\n=== RAW BM25 SEARCH RESULTS ===")
    bm25_results = bm25_search(query, subject_id, top_k=15)
    for i, h in enumerate(bm25_results, 1):
        print(f"[{i}] Score={h['score']:.4f} | Page={h['page_num']} | Doc={h['doc_name']}")
        print(f"    Text: {h['text'].strip()[:180]}...")
        print("-" * 80)

if __name__ == "__main__":
    main()
