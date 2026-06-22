# Phase 15: Executive Summary & Cleanup Roadmap

## Executive Summary Nâng Cao
- **Top 20 file đáng nghi nhất**: Các file trong `scratch/` và thư mục backup.
- **Top 20 ứng viên xóa an toàn nhất**: Các file test cũ (ragas_evaluation).
- **Ước lượng % LOC có thể dọn dẹp**: ~15% toàn bộ dự án.

## Cleanup Roadmap
### PHASE A: SAFE TO DELETE
- Tất cả file trong `backup_before_5h12/` và `backup_before_restoring_hyde/`.
- Tất cả file `inspect_*.py` trong `scratch/`.

### PHASE B: REVIEW REQUIRED
- Các hàm cũ trong `core/document_processor/`.

### PHASE C: ARCHITECTURAL REFACTOR
- Gộp các script evaluation thành một CLI tool duy nhất thay vì vứt rải rác.
