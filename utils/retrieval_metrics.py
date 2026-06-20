import os

def compute_retrieval_metrics(retrieved_chunks: list[dict], ground_truth_docs: list[str], ground_truth_pages: list[int]) -> dict:
    """
    Computes Hit@k, Recall@k, and first_relevant_rank for k = 1, 3, 5.
    
    Rules:
    - A chunk is relevant when document_name is in ground_truth_docs AND page is in ground_truth_pages.
    - Matches are normalized by lowercase and stripping extensions.
    - If ground_truth_pages is empty, matching is based only on document name.
    """
    if not ground_truth_docs:
        return {
            "hit_at_1": 0, "hit_at_3": 0, "hit_at_5": 0,
            "recall_at_1": 0.0, "recall_at_3": 0.0, "recall_at_5": 0.0,
            "first_relevant_rank": 999
        }
        
    gt_docs_norm = set(os.path.splitext(d.lower())[0] for d in ground_truth_docs)
    gt_pages = ground_truth_pages if ground_truth_pages else []
    gt_pairs = set()
    
    for d in gt_docs_norm:
        if gt_pages:
            for p in gt_pages:
                gt_pairs.add((d, p))
        else:
            gt_pairs.add((d, None))
            
    first_relevant_rank = 999
    metrics = {}
    
    for k in (1, 3, 5):
        sub_chunks = retrieved_chunks[:k]
        found_pairs = set()
        
        for idx, c in enumerate(sub_chunks, 1):
            # Extract document/doc_name
            c_doc_raw = c.get("document") or c.get("doc_name") or ""
            c_doc = os.path.splitext(c_doc_raw.lower())[0]
            
            # Extract page/page_num
            c_page_raw = c.get("page") or c.get("page_num")
            try:
                c_page = int(c_page_raw) if c_page_raw is not None else None
            except (ValueError, TypeError):
                c_page = None
                
            is_match = False
            if (c_doc, c_page) in gt_pairs or (c_doc, None) in gt_pairs:
                is_match = True
                
            if is_match:
                found_pairs.add((c_doc, c_page) if c_page is not None else (c_doc, None))
                if first_relevant_rank == 999 or idx < first_relevant_rank:
                    first_relevant_rank = idx
                    
        hit = 1 if len(found_pairs) > 0 else 0
        recall = len(found_pairs) / len(gt_pairs) if len(gt_pairs) > 0 else 0.0
        metrics[f"hit_at_{k}"] = hit
        metrics[f"recall_at_{k}"] = recall

    # If not found in top 5, search through the remaining chunks
    if first_relevant_rank == 999:
        for idx, c in enumerate(retrieved_chunks, 1):
            c_doc_raw = c.get("document") or c.get("doc_name") or ""
            c_doc = os.path.splitext(c_doc_raw.lower())[0]
            c_page_raw = c.get("page") or c.get("page_num")
            try:
                c_page = int(c_page_raw) if c_page_raw is not None else None
            except (ValueError, TypeError):
                c_page = None
            if (c_doc, c_page) in gt_pairs or (c_doc, None) in gt_pairs:
                first_relevant_rank = idx
                break

    return {
        "hit_at_1": metrics["hit_at_1"],
        "hit_at_3": metrics["hit_at_3"],
        "hit_at_5": metrics["hit_at_5"],
        "recall_at_1": metrics["recall_at_1"],
        "recall_at_3": metrics["recall_at_3"],
        "recall_at_5": metrics["recall_at_5"],
        "first_relevant_rank": first_relevant_rank
    }
