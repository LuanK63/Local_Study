"""
modules/weakness_detector.py
Stub implementation for side-branches (like feature/sandbox)
to prevent crash when the weakness detector module is not present on this branch.
"""

def get_weak_topics(subject_id: str) -> list[dict]:
    """Return mock weak topics for testing side-branches."""
    return [
        {
            "topic_id": "recursion",
            "attempts": 10,
            "wrong": 6,
            "wrong_rate": 0.6
        },
        {
            "topic_id": "linked_list",
            "attempts": 8,
            "wrong": 3,
            "wrong_rate": 0.375
        },
        {
            "topic_id": "sorting",
            "attempts": 5,
            "wrong": 1,
            "wrong_rate": 0.2
        }
    ]

def generate_review_plan(weak_topics: list[dict], subject_id: str) -> str:
    """Return a mock AI review plan for side-branches."""
    return """## 💡 Kế hoạch ôn tập đề xuất (Sandbox Stub)

Dựa trên dữ liệu học tập của bạn ở môn học này, dưới đây là phân tích và gợi ý ôn tập:

1. **Đệ quy (Recursion) - Tỷ lệ sai: 60%** (Cần ưu tiên gấp!)
   - **Lý do:** Đây là chủ đề bạn gặp khó khăn nhất.
   - **Đề xuất:** Xem lại khái niệm base case (điều kiện dừng) và call stack. Thử vẽ cây đệ quy cho bài toán tháp Hà Nội hoặc Fibonacci.

2. **Danh sách liên kết (Linked List) - Tỷ lệ sai: 38%**
   - **Đề xuất:** Thực hành thêm các thao tác thêm/xoá nút ở đầu, giữa và cuối danh sách liên kết đơn/kép.

3. **Sắp xếp (Sorting) - Tỷ lệ sai: 20%**
   - **Đề xuất:** Bạn đang làm khá tốt. Hãy tiếp tục củng cố kiến thức về độ phức tạp thuật toán (Time Complexity).
"""
