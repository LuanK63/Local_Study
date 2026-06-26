# DEPENDENCY AUDIT REPORT - PHASE 1

Mục tiêu: Đánh giá sự phụ thuộc của các module cần dọn dẹp để ra quyết định xóa/sửa (nhưng KHÔNG xóa ở phase này).

---

## 1. `modules/visualizer` (DSA Algorithm Visualizer)
* **Phân loại:** `ACTIVE_DEPENDENCY` (Tạm thời)
* **Imported by:** 
  - `ui/tabs/visualizer_tab.py`
  - Tham chiếu cấu hình gián tiếp qua `app.py` (`subject.has_visualizer`).
* **Phân tích:** Mặc dù luồng UI cũ (PyQt6) đang gọi module này, nhưng trong `app.py` (Streamlit), tab Visualizer đang được đánh dấu là "Đang xây dựng - Sprint 5". Hơn nữa, mục tiêu khóa luận là RAG Chunking Benchmark, không tập trung vào Visualizer. Tuy nhiên, theo nguyên tắc "KHÔNG xóa nếu chưa chứng minh an toàn", ta tạm thời giữ lại.

## 2. `scratch` (Thư mục nháp)
* **Phân loại:** `SAFE_TO_DELETE`
* **Imported by:** (Không có module nào trong `core/` hoặc `app.py` import `scratch`).
* **Phân tích:** Thư mục này chỉ chứa các script test dùng một lần (như `test_qwen_judge.py`, `test_modes.py`). Các file này nằm cô lập hoàn toàn khỏi runtime.

## 3. `audit_reports` (Báo cáo kiến trúc cũ)
* **Phân loại:** `SAFE_TO_DELETE`
* **Imported by:** (Không có)
* **Phân tích:** Chứa các file `.json`, `.md` của các đợt dọn dẹp trước. Không đóng góp vào source code thực thi.

## 4. `experiments` (Benchmark Scripts cũ)
* **Phân loại:** `NEEDS_REFACTOR`
* **Imported by:** Lẫn nhau (VD: `ablation_study.py` gọi `chunking_comparison.py`).
* **Phân tích:** Đây là nền tảng của hệ thống đo lường cũ. Thay vì xóa toàn bộ, ta cần gộp chúng lại thành một Framework Benchmark hợp nhất ở Phase 4 (`benchmark.py`). Sau khi Phase 4 hoàn thành, thư mục này sẽ trở thành `SAFE_TO_DELETE`.

## 5. `core/pipeline/agentic_rag.py` (Agent Workflows)
* **Phân loại:** `SAFE_TO_DELETE` (Đợi Phase 2 hoàn thiện)
* **Imported by:** `ui/tabs/chat_tab.py` (PyQt6).
* **Phân tích:** File này chứa logic phức tạp như Query Routing (CODE/CHAT/RAG), Code Sandbox Interpreter và CRAG (Self-Reflection). Tuy nhiên, vì chúng ta chuyển hẳn sang "Advanced RAG" (đơn giản, ổn định cho luận văn) và bỏ PyQt6, luồng Agentic này không còn được tham chiếu trong `app.py` hiện tại. Nó sẽ được gỡ bỏ hoàn toàn sau khi pipeline Reranker mới hoàn thành.

## 6. `ui` & `main.py` (PyQt6 UI)
* **Phân loại:** `SAFE_TO_DELETE`
* **Imported by:** Nhau.
* **Phân tích:** Việc quyết định chuyển 100% sang Streamlit (`app.py`) khiến toàn bộ mã nguồn PyQt6 mất đi tác dụng. Chúng đang tồn tại độc lập và không liên quan gì đến Streamlit.
