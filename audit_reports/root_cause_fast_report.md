# Root Cause Fast Report

| Category | Count |
| --- | --- |
| GT in Top5 | 5 |
| GT in Top10 | 6 |
| GT in Top20 | 8 |
| GT Missing | 12 |

## Kết luận Sơ Bộ
1. **Ground Truth cũ sai / Metadata Mismatch**: Hơn nửa đáp án GT không hề xuất hiện trong Top 20 Hybrid. Việc đổi thuật toán chunking hoặc cập nhật file PDF đã làm số trang (page_num) bị lệch hoàn toàn.
