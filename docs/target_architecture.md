# Target Architecture — DSA Tutor RAG (Advanced RAG + Chunking Benchmark)

**Phiên bản:** 2.0 (Refactor từ Agentic RAG → Advanced RAG)  
**Ngày cập nhật:** 2026-06-23  
**Mục tiêu:** Nghiên cứu và đánh giá ảnh hưởng của các phương pháp Chunking trong hệ thống Advanced RAG cho bài toán trợ lý học tập Cấu trúc Dữ liệu và Giải thuật (DSA).

---

## 1. Tổng quan kiến trúc

Hệ thống được xây dựng theo mô hình **Advanced RAG** với các thành phần:
- **Giao diện:** PyQt6 Desktop Application (giữ nguyên, bao gồm Algorithm Visualizer)
- **Retrieval:** Hybrid Search (BM25 + Dense Vector) + MiniLM Cross-Encoder Reranker
- **Chunking:** Framework 5 chiến lược với `BaseChunker` interface chuẩn hóa
- **Benchmark:** Engine tự động chạy ma trận cấu hình, lưu kết quả SQLite, xuất CSV/Excel

---

## 2. Default Pipeline (Áp dụng cho mọi chiến lược trừ Parent-Child)

```
┌─────────────────────────────────────────────────────────────┐
│                     PyQt6 Desktop UI                         │
│               (main.py + ui/tabs/chat_tab.py)               │
└────────────────────────┬────────────────────────────────────┘
                         │ User Question
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Hybrid Retriever                           │
│         BM25 (weight=0.4) + Dense Vector (weight=0.6)       │
│              Reciprocal Rank Fusion (RRF)                    │
│                    → Top 20 Chunks                           │
│              [core/retrieval/hybrid_retriever.py]            │
└────────────────────────┬────────────────────────────────────┘
                         │ Top 20 Candidates
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               MiniLM Cross-Encoder Reranker                  │
│        cross-encoder/ms-marco-MiniLM-L-6-v2 (local)         │
│                    → Top 4 Chunks                            │
│              [core/retrieval/hybrid_retriever.py]            │
└────────────────────────┬────────────────────────────────────┘
                         │ Top 4 Reranked Chunks
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Context Builder                            │
│        Ghép các chunk thành ngữ cảnh cho LLM               │
└────────────────────────┬────────────────────────────────────┘
                         │ Prompt = Question + Context
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               LLM Generator (Qwen2.5-Coder 7B)              │
│                  Strict RAG Prompt (no hallucination)        │
│                  Streaming Response                          │
└────────────────────────┬────────────────────────────────────┘
                         │ Answer + Citations
                         ▼
                    PyQt6 Chat UI
```

---

## 3. Parent-Child Pipeline (Chỉ kích hoạt với chiến lược Parent-Child Chunking)

> **LƯU Ý QUAN TRỌNG:** Parent Expansion là đặc tính nội tại của chiến lược Parent-Child Chunking. Nó KHÔNG được áp dụng cho các chiến lược Fixed, Sentence, Recursive, hay Semantic.

```
┌─────────────────────────────────────────────────────────────┐
│                     User Question                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Retrieve Child Chunks                           │
│     BM25 + Dense Vector trên các Child Chunks nhỏ (~300c)   │
│                    → Top-K Child Chunks                      │
└────────────────────────┬────────────────────────────────────┘
                         │ Child IDs → SQLite lookup
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Expand to Parent Context                        │
│     Từ child_id → truy vấn SQLite lấy parent_chunk (~1200c) │
│     Parent chứa đầy đủ ngữ cảnh xung quanh child           │
└────────────────────────┬────────────────────────────────────┘
                         │ Parent Chunks (ngữ cảnh đầy đủ)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               MiniLM Cross-Encoder Reranker                  │
│        cross-encoder/ms-marco-MiniLM-L-6-v2 (local)         │
│                    → Top 4 Parent Chunks                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              LLM Generator → Answer
```

---

## 4. Chunking Framework — 5 Chiến lược

| Chiến lược | Class | Mô tả | Đặc điểm |
|---|---|---|---|
| Fixed | `FixedChunker` | Cắt theo số token cố định | Đơn giản, không phụ thuộc cấu trúc |
| Sentence | `SentenceChunker` | Cắt theo ranh giới câu | Giữ nguyên ý nghĩa câu |
| Recursive | `RecursiveChunker` | Cắt đệ quy theo separator | Ưu tiên cấu trúc đoạn, câu |
| Semantic | `SemanticChunker` | Cắt theo ngữ nghĩa (cosine similarity) | Thông minh nhất, chi phí cao |
| Parent-Child | `ParentChildChunker` | Cắt 2 cấp: Parent (lớn) + Child (nhỏ) | Tối ưu retrieval + ngữ cảnh |

**Interface chuẩn hóa** — Tất cả chunker kế thừa `BaseChunker`:
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class Chunk:
    text: str
    chunk_id: str
    parent_id: str | None
    metadata: dict  # {"doc_name": str, "file_path": str, "page_num": int | None}

class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, document) -> list[Chunk]:
        pass
```

---

## 5. Model Configuration (Cố định cho toàn bộ Benchmark)

| Role | Model | Ghi chú |
|---|---|---|
| **Generator (LLM)** | `qwen2.5-coder:7b` | Sinh câu trả lời, streaming |
| **Embedding** | `nomic-embed-text` | Chạy qua Ollama API |
| **Reranker** | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Chạy local qua `sentence-transformers` |
| **Judge (Ragas)** | `qwen2.5:14b` | Chấm điểm benchmark, không dùng trong runtime |

> **Quy tắc:** Embedding Model và Reranker Model KHÔNG được thay đổi giữa các lần chạy benchmark để đảm bảo tính công bằng và tái lập kết quả.

---

## 6. Benchmark Matrix

```
configs/benchmark.yaml
└── chunking: [fixed, sentence, recursive, semantic, parent_child]
└── chunk_sizes: [200, 300, 500]
└── seed: 42
└── dataset: datasets/dsa_benchmark_v1.json
```

**Ma trận tự động:** 5 chunkers × 3 sizes = **15 cấu hình**

**Index Naming Convention:** `{chunking}_{chunk_size}` (ví dụ: `semantic_300`, `fixed_200`)

---

## 7. File Structure Mapping

### Module cần GIỮ NGUYÊN (bảo tồn hoàn toàn)
```
modules/visualizer/          ← KHÔNG CHẠM VÀO
ui/tabs/*visualizer*         ← KHÔNG CHẠM VÀO
```

### Module cần SỬA ĐỔI
```
core/retrieval/hybrid_retriever.py   ← Thêm MiniLM Reranker
core/document_processor/chunking/    ← Chuẩn hóa interface
ui/tabs/chat_tab.py                  ← Nối vào Advanced RAG pipeline mới
utils/db_schema.py                   ← Thêm benchmark_runs, benchmark_scores
```

### Module cần TẠO MỚI
```
benchmark.py                         ← CLI Benchmark Engine
configs/benchmark.yaml               ← Ma trận benchmark cấu hình
configs/quick_test.yaml              ← Kiểm tra nhanh
core/document_processor/chunking/sentence_chunker.py  ← [NEW]
datasets/dsa_benchmark_v1.json       ← ✅ Đã tạo (20 câu hỏi)
```

### Module sẽ bị XÓA/ARCHIVE (Chỉ sau Phase 6)
```
core/pipeline/agentic_rag.py         ← Xóa sau khi UI tích hợp xong
experiments/                         ← Archive → archive/experiments_old/
```

---

## 8. Output Structure

```
outputs/
├── benchmark_results.csv
├── benchmark_results.xlsx
└── benchmark_summary.json    ← best_by_faithfulness, overall_best, v.v.
```
