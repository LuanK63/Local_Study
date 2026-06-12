"""
scratch/reingest_dsa.py
Re-ingest Lê Minh Hoàng book to clean duplicate characters, then test hybrid search.
"""
import sys
import os

# Reconfigure stdout to use UTF-8
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.append("c:\\Users\\LUAN\\Desktop\\Local_Study_RAG_Agent")

from core.retrieval.hybrid_retriever import delete_document, ingest_document, search, warm_up_bm25

def main():
    subject_id = "dsa"
    file_path = "subjects/dsa/documents/Giai thuat va Lap Trinh - cau truc du lieu va giai thuat by Lê Minh Hoàng (z-lib.org).pdf"
    
    print("=== DELETING EXISTING INGESTED BOOK ===")
    deleted = delete_document(file_path, subject_id)
    print(f"Deleted {deleted} child chunks.")
    
    print("\n=== RE-INGESTING BOOK WITH OCR CLEANING ===")
    def progress_cb(stage, done, total):
        print(f"Stage '{stage}': {done}/{total}")
        
    chunks_indexed = ingest_document(file_path, subject_id, progress_cb=progress_cb)
    print(f"Successfully indexed {chunks_indexed} child chunks.")
    
    print("\n=== WARMING UP BM25 ===")
    warm_up_bm25([subject_id])
    
    print("\n=== RUNNING HYBRID SEARCH FOR 'stack là gì' ===")
    results, mode = search(
        query="stack là gì",
        subject_id=subject_id,
        top_k=5,
        use_hyde=False
    )
    
    print("\n=== HYBRID SEARCH RESULTS ===")
    for i, r in enumerate(results, 1):
        print(f"[{i}] Score={r.get('fused', r.get('score', 0)):.4f} | Page={r['page_num']} | Doc={r['doc_name']}")
        print(f"    Text: {r['text'].strip()[:250]}...")
        print("-" * 80)

if __name__ == "__main__":
    main()
