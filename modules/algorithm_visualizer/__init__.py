"""
modules/algorithm_visualizer/__init__.py
Stub implementation for side-branches (like feature/sandbox)
to prevent crash when the visualizer module is not present on this branch.
"""

def get_algo_categories() -> dict:
    """Return a dictionary of algorithm categories."""
    return {
        "Sắp xếp (Sorting)": [
            ("bubble_sort", "Bubble Sort"),
            ("insertion_sort", "Insertion Sort"),
            ("selection_sort", "Selection Sort")
        ]
    }

def generate_steps(algo_id: str, input_data: str) -> dict:
    """Return a stub list of steps for the visualizer."""
    try:
        arr = [int(x.strip()) for x in input_data.split(",") if x.strip()]
    except Exception:
        arr = [5, 3, 8, 1, 9, 2]
        
    return {
        "complexity": {
            "time": "O(N^2)",
            "space": "O(1)"
        },
        "summary": "Mô phỏng thuật toán trên nhánh sandbox (Stub)",
        "steps": [
            {
                "title": "Khởi tạo dữ liệu",
                "description": f"Bắt đầu với mảng đầu vào: {arr}",
                "array_state": arr,
                "highlight": [],
                "comparing": [],
                "sorted": []
            },
            {
                "title": "Kết thúc mô phỏng",
                "description": "Nhánh hiện tại là feature/sandbox. Tính năng visualizer hoàn chỉnh nằm ở nhánh feature/visualizer.",
                "array_state": arr,
                "highlight": [],
                "comparing": [],
                "sorted": list(range(len(arr)))
            }
        ]
    }
