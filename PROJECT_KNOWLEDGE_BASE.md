# PROJECT KNOWLEDGE BASE

Tài liệu này cung cấp cái nhìn toàn diện về dự án RAG nội bộ (Local Study RAG Agent). Tài liệu này được thiết kế để làm tài liệu tham khảo cho các AI hoặc lập trình viên mới tham gia dự án, giúp họ hiểu kiến trúc hệ thống mà không cần đọc lại toàn bộ mã nguồn.

---

## 1. PROJECT OVERVIEW

* **Tên dự án:** Local Study RAG Agent (Local Study)
* **Mục tiêu dự án:** Cung cấp một trợ lý học tập cá nhân hóa chạy hoàn toàn offline (local), hỗ trợ giải đáp thắc mắc dựa trên tài liệu học tập của chính người dùng (đặc biệt là tài liệu kỹ thuật/IT).
* **Bài toán giải quyết:** Vấn đề bảo mật dữ liệu học tập, khả năng truy xuất nhanh chóng các khái niệm kỹ thuật trong tài liệu dài (PDF, DOCX) mà không cần phụ thuộc vào internet hoặc API trả phí (OpenAI).
* **Người dùng mục tiêu:** Sinh viên, lập trình viên, nhà nghiên cứu cần hệ thống phân tích và truy vấn tài liệu cá nhân offline.
* **Các tính năng chính:**
  - Agentic RAG: Tự động phân tích, mở rộng câu hỏi và trích xuất ngữ cảnh.
  - Xử lý tài liệu (PDF, DOCX) với cơ chế Parent-Child chunking và Heuristic Semantic Chunking.
  - Hybrid Retrieval (Vector Search + BM25) kết hợp Reciprocal Rank Fusion (RRF).
  - Đánh giá chất lượng tự động (Benchmark) tích hợp thư viện `ragas`.
  - Giao diện người dùng Desktop (PyQt6).

---

## 2. SYSTEM ARCHITECTURE

Hệ thống được thiết kế theo mô hình **Monolithic Desktop Application** (Ứng dụng Desktop nguyên khối) kết nối với các service nền tảng cục bộ.

* **Frontend:** PyQt6 GUI (Giao diện cửa sổ Desktop, có các tab tính năng).
* **Backend:** Python Core (Xử lý luồng Agentic RAG, điều phối chunking/retrieval).
* **Database:** SQLite (Lưu trữ Metadata, Config, Parent Chunks) và ChromaDB (Lưu trữ Vector Embedding của Child Chunks).
* **AI Components:** Ollama Service (Chạy ngầm ở `localhost:11434` cung cấp LLM và Embedding model).
* **External Services:** Không có (Hoàn toàn Offline).
* **Third-party APIs:** Ollama Local API.

**Sơ đồ kiến trúc (Architecture Text Map):**
```text
[PyQt6 UI (Frontend)] <--(Qt Signals)--> [Main Application Controller]
                                                  |
                                                  v
[Agentic RAG Pipeline] <-----------------> [Ollama API (Localhost:11434)]
          |                                       |
          v                                       v
 [Hybrid Retriever]                        [LLM / Embeddings]
    |           |
    v           v
[BM25]     [ChromaDB]
    |           |
    +-----> [SQLite (Parent Chunks / Metadata)]
```

---

## 3. TECHNOLOGY STACK

* **Programming Languages:** Python 3.12+
* **Frameworks:** LangChain (hỗ trợ wrappers), PyQt6 (GUI).
* **Libraries:** `ragas` (Evaluation), `PyMuPDF` (PDF parsing), `python-docx` (DOCX parsing), `rank-bm25`, `httpx` (API Client).
* **Database (Relational):** SQLite3 (`data/study_agent.db`)
* **Vector Database:** ChromaDB (`data/chroma_db/`)
* **AI Models:** Qwen2.5:14b (Default Judge/Generator), Llama3.
* **Embedding Models:** nomic-embed-text (Default).
* **Deployment Technologies:** Local Python Virtual Environment (`venv`), Git.

---

## 4. FOLDER STRUCTURE

```text
/
├── audit_reports/     # Chứa các báo cáo kiểm toán kiến trúc, rác (Dead Code, Reachability).
├── core/              # Trái tim của dự án (Logic RAG, Document, Evaluation).
│   ├── document_processor/ # Logic đọc (PDF/DOCX) và cắt văn bản (Chunking).
│   ├── evaluation/    # Logic chạy benchmark (Ragas).
│   ├── pipeline/      # Luồng chạy chính của RAG (Agentic RAG, Generator).
│   └── retrieval/     # Logic tìm kiếm (Hybrid, Vector, BM25).
├── data/              # Thư mục lưu trữ database (SQLite, ChromaDB) và file cấu hình.
├── experiments/       # Các script chạy thử nghiệm, benchmark (Ablation study, Chunking comparison).
├── modules/           # Các module mở rộng (Visualizer, flashcard, concept explainer).
├── scratch/           # Thư mục nháp (Chứa script test, gỡ lỗi tạm thời).
├── subjects/          # Thư mục chứa tài liệu gốc của người dùng (vd: dsa/documents).
├── ui/                # Giao diện PyQt6 (Tabs, Widgets, MainWindow).
├── utils/             # Các hàm tiện ích (Config, DB Schema, Logger).
├── main.py            # Entry point chính để chạy ứng dụng PyQt6.
└── global_config.yaml # File cấu hình tổng của hệ thống.
```

---

## 5. SOURCE CODE MAP

### `main.py` & `ui/main_window.py`
- **Mục đích:** Khởi tạo ứng dụng Desktop, kết nối UI với Backend.
- **Class chính:** `MainWindow` (PyQt6).
- **Luồng hoạt động:** Nạp cấu hình -> Khởi tạo SQLite/Chroma -> Hiển thị GUI -> Đợi sự kiện từ người dùng.

### `core/pipeline/agentic_rag.py`
- **Mục đích:** Điều phối toàn bộ luồng RAG (Agentic workflow).
- **Functions chính:** `agentic_chat()`, `evaluate_chunks()`.
- **Luồng hoạt động:** Nhận câu hỏi -> Sinh câu hỏi phụ (Query Expansion) -> Gọi Hybrid Retriever -> Đánh giá độ phù hợp (CRAG) -> Gọi Generator.

### `core/retrieval/hybrid_retriever.py`
- **Mục đích:** Kết hợp tìm kiếm ngữ nghĩa và từ khóa.
- **Functions chính:** `search()`, `ingest_document()`, `_resolve_parents()`.
- **Luồng hoạt động:** Ingest (Đọc tài liệu -> Chia Parent/Child -> Lưu Chroma & SQLite) và Retrieve (Tìm Chroma + BM25 -> Trộn RRF -> Trả về Parent chunk).

### `core/document_processor/chunking/semantic_chunker.py`
- **Mục đích:** Phân tích cấu trúc đoạn văn (Heuristic) để chia văn bản thay vì dùng cosine distance đắt đỏ.
- **Class chính:** `SemanticChunker`.

---

## 6. DATA FLOW

```text
[Input] Tệp tài liệu PDF/DOCX (hoặc câu hỏi từ UI)
   ↓
[Processing - Ingestion] Đọc tệp → Semantic Chunker chia thành Parent/Child chunks
   ↓
[Storage] Child Chunks (Vector hóa bằng Ollama) → ChromaDB | Parent Chunks (Text) → SQLite
   ↓
[Processing - Retrieval] Câu hỏi → Query Expansion → Tìm ChromaDB (Vector) + Tìm BM25 (Keyword)
   ↓
[Retrieval] RRF Fusion → Map Child ID về Parent ID → Lấy Text từ SQLite
   ↓
[Processing - Generation] Lọc chunk rác (CRAG) → Đưa Context + Question vào Prompt → Gọi Ollama LLM
   ↓
[Output] Kết quả văn bản trả về UI
```

---

## 7. DATABASE DESIGN

Hệ thống sử dụng **SQLite** làm Database Relational chính.

* **Bảng `parent_chunks`:**
  - `subject_id`, `parent_id` (Primary Keys).
  - `parent_text` (Lưu văn bản đầy đủ).
  - `doc_name`, `page_num`, `file_path`.
  - Mục đích: Tránh việc lưu văn bản lớn vào ChromaDB, tối ưu tốc độ LLM và Retrieval.

* **Bảng `benchmark_runs` & `benchmark_queries`:**
  - Lưu cấu hình đợt chạy thử nghiệm (strategy, chunk_size, llm_model).
  - Lưu lịch sử các câu hỏi, kết quả trả về, thời gian chạy và điểm số IR (Recall, Precision).

* **Bảng `subjects` & `config`:**
  - Quản lý các môn học (tập tài liệu) và lưu cấu hình động của người dùng trên UI.

---

## 8. API DOCUMENTATION

Dự án **không** expose public API. Dự án hoạt động như một Client giao tiếp với **Ollama API (Local)**.

* **Giao tiếp ra ngoài (Ollama):**
  - `POST http://localhost:11434/api/chat`: Nhận prompt và sinh text (Generation).
  - `POST http://localhost:11434/api/embeddings`: Nhận text và sinh Vector 1D (Embedding).
  - `GET http://localhost:11434/api/tags`: Kiểm tra trạng thái server.

---

## 9. AI / RAG ARCHITECTURE

* **LLM đang dùng:** Cấu hình qua `global_config.yaml` (Ưu tiên: `qwen2.5:14b`).
* **Embedding model:** `nomic-embed-text`.
* **Retrieval strategy:** Hybrid Search = Semantic Search (ChromaDB Vector) + Exact Match (BM25) kết hợp bằng thuật toán Reciprocal Rank Fusion (RRF).
* **Chunking strategy:** Parent-Child Chunking kết hợp Heuristic Semantic. (Child 300 token để search, Parent 1200 token để LLM đọc).
* **Reranking strategy:** RRF (BM25 weight=0.7, Vector weight=0.3), kết hợp với kỹ thuật CRAG (Corrective RAG) để loại bỏ chunk rác trước khi đưa vào LLM.
* **Evaluation strategy:** Tự động hóa qua thư viện `ragas` (Đo Faithfulness, Answer Relevancy, Context Recall, Context Precision).
* **Memory strategy:** LLM hoàn toàn vô trạng thái (Stateless), không lưu trữ hội thoại lịch sử.
* **Prompt strategy:** Explicit Few-shot (RAG Prompt) giới hạn LLM không được bịa thông tin nếu không có trong context.

---

## 10. EXECUTION FLOW

**Quy trình người dùng đặt câu hỏi:**
1. Người dùng gõ câu hỏi vào thanh chat trên giao diện PyQt6.
2. `ui/main_window.py` gửi tín hiệu (Signal) qua thread phụ.
3. `agentic_rag.py` tiếp nhận, làm sạch câu hỏi.
4. Hệ thống tách từ khóa (Query Expansion).
5. `hybrid_retriever.py` tìm top 20 kết quả từ BM25 và ChromaDB, hợp nhất lấy Top 5.
6. Hệ thống phân giải Child chunk thành Parent chunk từ SQLite.
7. Prompt RAG được tạo và gửi HTTP POST tới Ollama Server cục bộ.
8. Text trả về (Streaming) được emit lại cho giao diện PyQt6 để hiển thị từng chữ.

---

## 11. CONFIGURATION

* **Config Files:** `global_config.yaml` (Chứa cấu hình mặc định).
* **Database Config:** `data/study_agent.db` bảng `config` (Ghi đè cấu hình yaml).
* **Environment Variables:** Không lạm dụng env, ưu tiên cấu hình yaml.
* **Secret References:** Không có bí mật (Dự án Local hoàn toàn).

---

## 12. DEPENDENCY ANALYSIS

* **Mức độ Coupling (Phụ thuộc):**
  - Toàn bộ `core/` phụ thuộc vào `utils/config.py` và `utils/db_schema.py`.
  - `experiments/` phụ thuộc chặt chẽ vào `core/` và `ragas`.
* **Điểm dễ gây lỗi (Bottlenecks):**
  - **Ollama Connection:** Nếu Ollama service tắt hoặc thiếu RAM, pipeline sẽ crash (Đã có `httpx` timeout handling).
  - **ChromaDB Lock:** Chạy đồng thời Ingestion và Retrieval có thể gây database locked.

---

## 13. CURRENT DEVELOPMENT STATUS

* **Tính năng đã hoàn thành:** UI cơ bản, Hybrid Retrieval, Parent-Child Semantic Chunking, Ragas Benchmark, Agentic RAG pipeline.
* **Tính năng đang phát triển / Refactoring:** Cleanup mã nguồn (Vừa hoàn tất Phase A & B dọn dẹp các thư mục nháp và đoạn code thừa trong `core/`).
* **TODO tồn tại trong source code:** Gộp các script evaluation rải rác thành một CLI tool thống nhất (Nằm trong Phase C Cleanup Roadmap).

---

## 14. KNOWN ISSUES

* **Technical Debt:** Các file giao diện trong `modules/visualizer/` chứa nhiều lớp đồ họa cũ (Dijkstra, LinkedList) không còn tương thích tốt hoặc không được dùng, tiềm ẩn rủi ro UI Crash nếu người dùng click nhầm.
* **Bottleneck hiệu năng:** Ingest tài liệu lớn (vài nghìn trang) qua `PyMuPDF` và gửi request embedding cục bộ khá chậm (Ollama CPU bottleneck).
* **Code Smell:** Còn một số script rải rác trong `scratch/` không có entrypoint rõ ràng.

---

## 15. FUTURE ROADMAP

* **Refactor (Phase C):** Gom toàn bộ code benchmark (các file `.py` trong `experiments/`) thành một CLI app chuẩn mực (dùng `click` hoặc `argparse` tập trung).
* **Optimization:** Tích hợp Batch Embedding thay vì gửi từng request cho Ollama để tăng tốc độ Ingest PDF.
* **Scalability:** Tách biệt hoàn toàn luồng UI và luồng Background Job bằng Celery hoặc Asyncio queues thay vì dùng QThread thuần túy.

---

## 16. QUICK START FOR ANOTHER AI

**Tóm tắt (Dành cho AI mới):**
Đây là một ứng dụng Desktop RAG hoàn toàn offline, sử dụng Python (PyQt6) và Ollama.
* **Mục tiêu:** Trả lời câu hỏi dựa trên PDF của người dùng một cách chính xác nhất.
* **Kiến trúc & Công nghệ:** SQLite (Lưu metadata/parent chunks), ChromaDB (Vector store), PyQt6 (UI), Langchain/Ragas (Tiện ích và Đánh giá).
* **Luồng xử lý cốt lõi:** User -> `agentic_rag.py` -> `hybrid_retriever.py` (Chroma+BM25) -> Ollama Generate -> UI.
* **Các file quan trọng nhất cần chú ý:**
  1. `core/pipeline/agentic_rag.py` (Brain của hệ thống).
  2. `core/retrieval/hybrid_retriever.py` (Luồng lấy dữ liệu phức tạp với RRF và Parent-Child resolution).
  3. `data/study_agent.db` (Nơi lưu toàn bộ dữ liệu quan trọng ngoài vector).
* **Lời khuyên (Must know):** Toàn bộ file rác (Dead Code Phase A, B) đã được dọn dẹp. Đừng thay đổi `hybrid_retriever.py` hoặc `ragas_eval.py` trừ khi bạn hiểu rõ cơ chế *Parent-child mapping* và *Thư viện Ragas compatibility fix* nằm trong đó. Mọi thay đổi về cấu trúc DB phải được update vào `utils/db_schema.py`.
