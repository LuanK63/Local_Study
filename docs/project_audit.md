# PROJECT AUDIT REPORT - PHASE 0

**Mục tiêu dự án mới:** Chuyển đổi từ Agentic RAG sang Advanced RAG phục vụ nghiên cứu phương pháp Chunking (Benchmark) với giao diện Streamlit.

---

## 1. Active Modules (Module đang được sử dụng)
Những module này là nòng cốt của hệ thống RAG hiện hành và đang được tham chiếu nhiều.

* **`core/retrieval/hybrid_retriever.py`**: Thực hiện Hybrid Search (BM25 + ChromaDB) và kết hợp Reciprocal Rank Fusion (RRF). Đang hoạt động tốt, có hỗ trợ Parent-Child.
* **`core/document_processor/chunking/semantic_chunker.py`**: Đảm nhiệm heuristic chunking.
* **`core/evaluation/ragas_eval.py`**: Luồng đánh giá tự động dựa trên thư viện Ragas (Faithfulness, Answer Relevancy, Context Recall, Context Precision).
* **`utils/config.py` & `utils/db_schema.py`**: Cấu hình và schema cơ sở dữ liệu SQLite, được toàn bộ hệ thống phụ thuộc.
* **`app.py`**: Entrypoint cho Streamlit (mặc dù đang rất sơ khai).

## 2. Dead Modules (Module sẽ không còn cần thiết cho kiến trúc mới)
Dựa theo yêu cầu "Không triển khai Agentic RAG" và "KHÔNG chuyển sang PyQt6", các module sau trở thành Legacy/Dead code đối với mục tiêu khóa luận.

* **`main.py`**: Entrypoint của PyQt6.
* **`ui/` (toàn bộ thư mục)**: Chứa các Widget và logic của PyQt6.
* **`core/pipeline/agentic_rag.py`**: Workflow quá phức tạp (Query classification, code sandbox, self-reflection) không phục vụ cho bài toán benchmark chunking.
* **`modules/code_sandbox.py`**: Module thực thi Python nội bộ, không liên quan đến Advanced RAG.
* **`audit_reports/`**: Các file báo cáo của đợt dọn dẹp trước, không thuộc về kiến trúc runtime.

## 3. High Risk Modules (Module nhiều phụ thuộc)
Bất kỳ thay đổi nào ở các module này đều có thể làm gãy (break) hệ thống.

* **`utils/db_schema.py`**: Chứa định nghĩa cấu trúc DB (bảng `parent_chunks`, `benchmark_runs`). Nếu thêm Reranker hay Chunking Matrix, cần phải migrate cẩn thận.
* **`core/retrieval/hybrid_retriever.py`**: Vừa làm nhiệm vụ Ingest tài liệu, vừa làm nhiệm vụ truy vấn. Đang bị tight-coupling (liên kết chặt chẽ) với ChromaDB client và SQLite.

## 4. Refactor Candidates (Module cần tinh chỉnh mạnh mẽ)

* **`core/document_processor/chunking/`**: Cần đập đi xây lại theo mô hình hướng đối tượng với `BaseChunker` interface để dễ dàng support 5 chiến lược (Fixed, Recursive, Sentence, Semantic, Parent-Child).
* **`experiments/`**: Đang phân mảnh thành nhiều script nhỏ (`ablation_study.py`, `chunking_comparison.py`, `run_all_experiments.py`). Cần gộp thành một `benchmark.py` thống nhất.
* **`app.py`**: Cần thiết kế lại UI hoàn toàn mới với 3 tabs (Chat, Documents, Benchmark Dashboard) như yêu cầu.
