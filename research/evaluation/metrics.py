"""
research/evaluation/metrics.py
==============================
Metrics Engine tính toán các chỉ số Retrieval cho Benchmark.
Quy tắc cố định: k=5.
"""
from typing import List

def calculate_metrics(relevant_flags: List[bool], k: int = 5) -> dict:
    """
    Tính các chỉ số đo lường hiệu suất retrieval từ danh sách relevant/irrelevant.
    Cố định mẫu số là k khi tính Precision@k.
    
    Args:
        relevant_flags: Danh sách True/False biểu thị mỗi chunk trả về có relevant không.
                        Được đánh giá dựa trên `final_chunks` của pipeline.
        k: Số lượng chunk tối đa trả về, cố định bằng 5.
        
    Returns:
        dict: Chứa các giá trị Precision@5, Recall@5, F1@5, HitRate@5, MRR.
    """
    if not relevant_flags:
        return {
            "precision_at_k": 0.0,
            "recall_at_k": 0.0,
            "f1_at_k": 0.0,
            "hit_rate_at_k": 0.0,
            "mrr": 0.0
        }
        
    # Vì output của CRAG filter có thể <= k, chúng ta chỉ xét đến min(k, len(relevant_flags))
    # Tuy nhiên, the rules explicitly say: 
    # "Dù sau khi đi qua CRAG Filter, hệ thống chỉ trả về 2 chunk (thay vì 5), khi tính toán bắt buộc vẫn phải chia cho 5."
    # Wait, the relevant_chunks are the ones that are relevant within the returned list.
    
    hits = sum(1 for is_relevant in relevant_flags if is_relevant)
    
    # Precision@5 = Số chunk relevant / 5
    precision_at_k = hits / k
    
    # Recall@5 = Số chunk relevant trả về / Tổng số lượng reference_contexts của câu hỏi (Giả định max là 1 reference_context để tính đơn giản,
    # Tuy nhiên trong evaluation, thông thường nếu ta không biết tổng số lượng chunks chứa reference trong toàn bộ DB,
    # recall được chuẩn hóa: nếu có bất kỳ ref nào thì recall = 1.0 (như HitRate).
    # Nhìn lại yêu cầu khóa luận, Recall có thể được tính đơn giản là hits / tổng_số_câu_trả_lời_cần_thiết.
    # Trong Local Study RAG, thường chỉ có 1 đoạn văn chứa câu trả lời. 
    # Nên Recall@5 thường được gán bằng HitRate hoặc là min(hits/1, 1.0).
    # Để chắc chắn, we assume total_relevant_in_db = 1. So Recall = min(hits, 1.0)
    recall_at_k = min(float(hits), 1.0)
    
    if precision_at_k + recall_at_k > 0:
        f1_at_k = 2 * (precision_at_k * recall_at_k) / (precision_at_k + recall_at_k)
    else:
        f1_at_k = 0.0
        
    hit_rate_at_k = 1.0 if hits > 0 else 0.0
    
    mrr = 0.0
    for i, is_relevant in enumerate(relevant_flags):
        if is_relevant:
            mrr = 1.0 / (i + 1)
            break
            
    return {
        "precision_at_k": precision_at_k,
        "recall_at_k": recall_at_k,
        "f1_at_k": f1_at_k,
        "hit_rate_at_k": hit_rate_at_k,
        "mrr": mrr
    }
