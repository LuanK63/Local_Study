"""
scratch/test_hyde_pipeline.py
Test script to verify HyDE search compared to normal search on 'dsa' subject.
"""
import sys
import os

# Reconfigure stdout to use UTF-8 to prevent encoding errors on Windows
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add workspace root to python path
sys.path.append("c:\\Users\\LUAN\\Desktop\\Local_Study_RAG_Agent")

from core.retrieval.hybrid_retriever import search, warm_up_bm25
from utils.config import get_config

def main():
    subject_id = "dsa"
    query = "ngăn xếp là gì và các phép toán cơ bản"

    print("=== WARMING UP BM25 ===")
    warm_up_bm25([subject_id])
    
    print("\n" + "="*50)
    print("TEST 1: SEARCH WITHOUT HyDE")
    print("="*50)
    results_normal, mode_normal = search(
        query=query,
        subject_id=subject_id,
        top_k=3,
        use_hyde=False
    )
    
    print("\n" + "="*50)
    print("TEST 2: SEARCH WITH HyDE")
    print("="*50)
    results_hyde, mode_hyde = search(
        query=query,
        subject_id=subject_id,
        top_k=3,
        use_hyde=True
    )

    print("\n" + "="*50)
    print("SUMMARY COMPARISON")
    print("="*50)
    print(f"Original Query: '{query}'")
    print("\n--- Chunks retrieved WITHOUT HyDE ---")
    for i, r in enumerate(results_normal, 1):
        print(f"[{i}] Score={r.get('fused', r.get('score', 0)):.4f} | Page={r['page_num']} | Doc={r['doc_name']}")
        print(f"    Text: {r['text'][:120].strip()}...")
        
    print("\n--- Chunks retrieved WITH HyDE ---")
    for i, r in enumerate(results_hyde, 1):
        print(f"[{i}] Score={r.get('fused', r.get('score', 0)):.4f} | Page={r['page_num']} | Doc={r['doc_name']}")
        print(f"    Text: {r['text'][:120].strip()}...")

if __name__ == "__main__":
    main()
