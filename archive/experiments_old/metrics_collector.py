import numpy as np

def clean_doc_name(name):
    if not name:
        return ""
    # Normalize path and lowercase it
    return str(name).strip().lower()

def is_match(chunk, expected_sources):
    chunk_doc = clean_doc_name(chunk.get("doc_name", ""))
    chunk_page = int(chunk.get("page_num", -1))
    
    for src in expected_sources:
        src_doc = clean_doc_name(src.get("doc_name", ""))
        src_page = int(src.get("page_num", -2))
        
        # Check if the document name matches (or is a substring of the other to handle path stems)
        doc_matches = (src_doc in chunk_doc) or (chunk_doc in src_doc)
        if doc_matches and chunk_page == src_page:
            return True
    return False

def calculate_precision_recall_k(retrieved_chunks, expected_sources, k):
    """
    Calculate Precision@k and Recall@k.
    """
    if not expected_sources:
        return 0.0, 0.0

    # Get the top K retrieved chunks
    top_k_chunks = retrieved_chunks[:k]
    
    # Calculate Precision@k
    matches = [is_match(c, expected_sources) for c in top_k_chunks]
    precision_k = sum(matches) / k
    
    # Calculate Recall@k: percentage of expected sources found in top K
    unique_expected_found = set()
    for c in top_k_chunks:
        for src in expected_sources:
            src_doc = clean_doc_name(src.get("doc_name", ""))
            src_page = int(src.get("page_num", -2))
            
            chunk_doc = clean_doc_name(c.get("doc_name", ""))
            chunk_page = int(c.get("page_num", -1))
            
            doc_matches = (src_doc in chunk_doc) or (chunk_doc in src_doc)
            if doc_matches and chunk_page == src_page:
                unique_expected_found.add(f"{src_doc}:{src_page}")
                
    recall_k = len(unique_expected_found) / len(expected_sources)
    return precision_k, recall_k

def calculate_mean_std(values: list[float]) -> tuple[float, float]:
    """
    Calculate the mean and standard deviation of a list of numeric values.
    Returns (mean, std).
    """
    if not values:
        return 0.0, 0.0
    arr = np.array(values)
    return float(np.mean(arr)), float(np.std(arr))
