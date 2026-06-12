"""
scratch/test_hybrid_search.py
Run hybrid search without HyDE for 'stack là gì' and print top chunks and their fusion scores.
"""
import sys

# Reconfigure stdout to use UTF-8
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.append("c:\\Users\\LUAN\\Desktop\\Local_Study_RAG_Agent")

from core.retrieval.hybrid_retriever import warm_up_bm25, search

def main():
    subject_id = "dsa"
    query = "stack là gì"
    
    print("=== WARMING UP BM25 ===")
    warm_up_bm25([subject_id])
    
    print("\n=== RUNNING HYBRID SEARCH ===")
    results, mode = search(
        query=query,
        subject_id=subject_id,
        top_k=5,
        use_hyde=False
    )
    
    print(f"\nFinal search mode used: {mode}")
    print(f"Total results: {len(results)}")
    for i, h in enumerate(results, 1):
        print(f"[{i}] Score={h.get('fused', h.get('score', 0)):.4f} | Page={h['page_num']} | Doc={h['doc_name']}")
        print(f"    Text: {h['text'].strip()[:200]}...")
        print("-" * 80)

if __name__ == "__main__":
    main()
