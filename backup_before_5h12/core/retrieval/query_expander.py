""""
core/retrieval/query_expander.py
Hai kỹ thuật cải thiện retrieval recall:

1. Multi-query expansion  — tạo N biến thể câu hỏi để search song song
2. HyDE (Hypothetical Document Embeddings) — tạo câu TRẢ LỜI giả,
   embed câu trả lời đó để search thay vì embed câu hỏi.

Tại sao HyDE hiệu quả hơn?
  Query: "stack là gì?"        → embedding của CÂU HỎI (dạng hỏi)
  Doc:   "Stack là danh sách..." → embedding của CÂU KHẲNG ĐỊNH
  → Similarity thấp dù nội dung liên quan

  HyDE: sinh ra "Stack là cấu trúc dữ liệu..." → embed → gần với doc hơn nhiều
"""
import re
import httpx
from utils.config import get_config


# ── System prompts ────────────────────────────────────────────────────────────

_EXPAND_SYSTEM = """\
Bạn là trợ lý tìm kiếm tài liệu học tập. Nhiệm vụ: tạo ra các cách diễn đạt khác nhau \
của câu hỏi để tìm kiếm tài liệu hiệu quả hơn.

QUY TẮC:
- Mỗi biến thể giữ nguyên ý nghĩa gốc nhưng dùng từ ngữ / góc độ khác.
- Chỉ trả về danh sách câu hỏi, mỗi câu một dòng, không đánh số, không giải thích.
- Viết bằng cùng ngôn ngữ với câu hỏi gốc.
- Có thể thêm thuật ngữ kỹ thuật liên quan để tăng khả năng tìm kiếm.\
"""

_HYDE_SYSTEM = """\
Bạn là chuyên gia về khoa học máy tính. Hãy viết một đoạn văn ngắn (2-4 câu) trả lời \
câu hỏi sau như thể bạn đang viết cho giáo trình đại học.

QUY TẮC:
- Viết dưới dạng định nghĩa/khẳng định, KHÔNG viết dưới dạng hỏi đáp.
- Dùng thuật ngữ kỹ thuật chính xác.
- Ngắn gọn, súc tích, không giải thích dài dòng.
- Viết bằng cùng ngôn ngữ với câu
<truncated 3477 bytes>