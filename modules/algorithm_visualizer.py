"""
modules/algorithm_visualizer.py — M2
Generate step-by-step algorithm visualizations.
Returns structured steps that the UI renders as a tree/graph.
"""
import json
import re
from core.pipeline.answer_generator import generate


# ── Supported algorithms ──────────────────────────────────────────────────────
ALGO_CATALOG = {
    # Sorting
    "bubble_sort":    "Bubble Sort",
    "selection_sort": "Selection Sort",
    "insertion_sort": "Insertion Sort",
    "merge_sort":     "Merge Sort",
    "quick_sort":     "Quick Sort",
    "heap_sort":      "Heap Sort",
    # Search
    "binary_search":  "Binary Search",
    "linear_search":  "Linear Search",
    # Tree ops
    "bst_insert":     "BST Insert",
    "bst_search":     "BST Search",
    "bst_delete":     "BST Delete",
    "avl_insert":     "AVL Insert",
    # Heap ops
    "min_heap_insert": "Min-Heap Insert",
    "max_heap_insert": "Max-Heap Insert",
    "heap_extract":    "Heap Extract",
    # Graph
    "bfs":  "BFS (Breadth-First Search)",
    "dfs":  "DFS (Depth-First Search)",
    "dijkstra": "Dijkstra's Algorithm",
    # Data structure ops
    "stack_push": "Stack Push",
    "stack_pop":  "Stack Pop",
    "queue_enqueue": "Queue Enqueue",
    "queue_dequeue": "Queue Dequeue",
    "ll_insert": "Linked List Insert",
    "ll_delete": "Linked List Delete",
}

SYSTEM_STEPS = """Bạn là giáo viên DSA. Hãy tạo SIMULATION từng bước cho thuật toán/thao tác được yêu cầu.

Trả về JSON CHÍNH XÁC theo định dạng sau (KHÔNG thêm text nào khác):
{
  "algorithm": "Tên thuật toán",
  "input_description": "Mô tả input",
  "steps": [
    {
      "step": 1,
      "title": "Tiêu đề bước",
      "description": "Giải thích ngắn gọn xảy ra gì",
      "array_state": [4, 2, 8, 1, 5],
      "highlight": [0, 1],
      "comparing": [0, 1],
      "sorted": [],
      "pointer": {"i": 0, "j": 1},
      "note": "Ghi chú thêm nếu cần"
    }
  ],
  "complexity": {"time": "O(n²)", "space": "O(1)"},
  "summary": "Tóm tắt thuật toán"
}

Quy tắc:
- array_state: trạng thái mảng SAU bước này (hoặc null nếu không dùng mảng)
- highlight: index các phần tử đang được chú ý (màu vàng)
- comparing: index các phần tử đang so sánh (màu đỏ)
- sorted: index các phần tử đã được sắp xếp (màu xanh)
- Tạo đủ steps để sinh viên hiểu, KHÔNG bỏ qua bước nào
"""


def generate_steps(algorithm: str, input_data: str) -> dict:
    """
    Generate step-by-step simulation for an algorithm.
    Returns dict with steps, complexity, and summary.
    """
    algo_name = ALGO_CATALOG.get(algorithm, algorithm)
    user = f"Thuật toán: {algo_name}\nInput: {input_data}\n\nTạo simulation từng bước."

    raw = generate(SYSTEM_STEPS, user, stream=False)

    # Extract JSON
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        return {"error": "Không thể parse kết quả từ AI", "raw": raw}

    try:
        data = json.loads(match.group())
        return data
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}", "raw": raw[:500]}


def get_algo_categories() -> dict[str, list[tuple[str, str]]]:
    """Return algorithms grouped by category for UI display."""
    return {
        "🔃 Sắp xếp": [
            ("bubble_sort",    "Bubble Sort"),
            ("selection_sort", "Selection Sort"),
            ("insertion_sort", "Insertion Sort"),
            ("merge_sort",     "Merge Sort"),
            ("quick_sort",     "Quick Sort"),
            ("heap_sort",      "Heap Sort"),
        ],
        "🔍 Tìm kiếm": [
            ("binary_search", "Binary Search"),
            ("linear_search", "Linear Search"),
        ],
        "🌳 Cây (BST/AVL)": [
            ("bst_insert", "BST Insert"),
            ("bst_search", "BST Search"),
            ("bst_delete", "BST Delete"),
            ("avl_insert", "AVL Insert"),
        ],
        "📊 Heap": [
            ("min_heap_insert", "Min-Heap Insert"),
            ("max_heap_insert", "Max-Heap Insert"),
            ("heap_extract",    "Heap Extract"),
        ],
        "🕸️ Đồ thị": [
            ("bfs",       "BFS"),
            ("dfs",       "DFS"),
            ("dijkstra",  "Dijkstra"),
        ],
        "📦 CTDL cơ bản": [
            ("stack_push",    "Stack Push"),
            ("stack_pop",     "Stack Pop"),
            ("queue_enqueue", "Queue Enqueue"),
            ("queue_dequeue", "Queue Dequeue"),
            ("ll_insert",     "Linked List Insert"),
            ("ll_delete",     "Linked List Delete"),
        ],
    }
