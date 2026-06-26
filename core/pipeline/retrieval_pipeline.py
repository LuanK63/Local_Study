"""
core/pipeline/retrieval_pipeline.py
===================================
Abstraction for the Retrieval process.
Encapsulates Hybrid Search -> Reranker -> CRAG Filter.
This serves as the single entry point for the Benchmark Runner,
ensuring isolation between research and production code.
"""
import time
from typing import Dict, Any, List
from core.retrieval.hybrid_retriever import search as retrieval_search
from core.pipeline.agentic_rag import evaluate_chunks
from utils.config import get_config

class RetrievalPipeline:
    def __init__(self, subject_id: str, top_k: int = 5, search_mode: str = None, use_crag: bool = False):
        """
        Khởi tạo RetrievalPipeline.
        Args:
            subject_id: ID của môn học.
            top_k: Số lượng chunk tối đa trả về sau Reranker.
            search_mode: Chế độ tìm kiếm ('hybrid', 'semantic', 'bm25'). Nếu None, lấy từ cấu hình.
        """
        self.subject_id = subject_id
        self.top_k = top_k
        self.search_mode = search_mode
        self.use_crag = use_crag
        self.rag_cfg = get_config().get("rag", {})

    def run(self, query: str) -> Dict[str, Any]:
        """
        Thực thi toàn bộ luồng tìm kiếm và lọc:
        Hybrid Search -> Reranker -> CRAG Filter.
        
        Returns:
            Dict chứa:
                - final_chunks: list[dict] (các chunk sống sót sau CRAG)
                - retrieval_latency: float (ms)
        """
        start_time = time.time()
        
        # Bước 1 & 2: Hybrid Search và MiniLM Reranker
        # Lưu ý: core.retrieval.hybrid_retriever.search đã bao gồm cả Reranker
        retrieved_chunks, mode_used = retrieval_search(
            query=query,
            subject_id=self.subject_id,
            top_k=self.top_k,
            mode=self.search_mode
        )
        
        # Bước 3: CRAG Filter (Sử dụng RRF fused score threshold)
        if self.use_crag:
            final_chunks = evaluate_chunks(query, retrieved_chunks)
        else:
            final_chunks = retrieved_chunks
            
        retrieval_latency = (time.time() - start_time) * 1000
        
        return {
            "final_chunks": final_chunks,
            "retrieval_latency": retrieval_latency
        }
