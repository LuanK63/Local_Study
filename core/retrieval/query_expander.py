"""
core/retrieval/query_expander.py
Query Expansion: tự động thêm thuật ngữ tiếng Việt tương đương cho BM25 search.

Vấn đề giải quyết: Học thuật Việt Nam dùng lẫn lộn Anh-Việt.
  User hỏi: "stack là gì"
  Tài liệu định nghĩa dùng: "ngăn xếp là..."
  → BM25 không match → trang định nghĩa bị xếp sau trang ứng dụng code

Cách hoạt động:
  1. Phát hiện từ kỹ thuật tiếng Anh trong query
  2. Thêm thuật ngữ tiếng Việt tương đương vào query
  "stack là gì" → "stack ngăn xếp là gì"
  → BM25 bây giờ match cả 2: trang định nghĩa (ngăn xếp) và trang code (stack)
"""

import re

# ── Từ điển thuật ngữ kỹ thuật EN → VI ───────────────────────────────────────
# Thêm thuật ngữ mới vào đây khi cần
_TECH_DICT: dict[str, list[str]] = {
    # Cấu trúc dữ liệu
    "stack":        ["ngăn xếp", "ngăn-xếp"],
    "queue":        ["hàng đợi", "hàng-đợi"],
    "deque":        ["hàng đợi hai đầu"],
    "array":        ["mảng", "dãy"],
    "linked list":  ["danh sách liên kết", "danh sách móc nối"],
    "tree":         ["cây"],
    "binary tree":  ["cây nhị phân"],
    "graph":        ["đồ thị"],
    "heap":         ["đống", "vun đống"],
    "hash":         ["băm", "bảng băm"],
    "hash table":   ["bảng băm", "bảng tăng"],
    "trie":         ["cây tiền tố"],

    # Giải thuật sắp xếp
    "sort":         ["sắp xếp"],
    "bubble sort":  ["sắp xếp nổi bọt", "sắp xếp bong bóng"],
    "merge sort":   ["sắp xếp trộn", "sắp xếp ghép"],
    "quick sort":   ["sắp xếp nhanh"],
    "insertion sort": ["sắp xếp chèn"],
    "selection sort": ["sắp xếp chọn"],
    "heap sort":    ["sắp xếp đống"],
    "counting sort": ["sắp xếp đếm"],
    "radix sort":   ["sắp xếp cơ số"],

    # Giải thuật tìm kiếm
    "search":       ["tìm kiếm"],
    "binary search": ["tìm kiếm nhị phân", "tìm nhị phân"],
    "linear search": ["tìm kiếm tuyến tính"],

    # Đồ thị
    "bfs":          ["tìm kiếm theo chiều rộng", "duyệt theo chiều rộng"],
    "dfs":          ["tìm kiếm theo chiều sâu", "duyệt theo chiều sâu"],
    "shortest path": ["đường đi ngắn nhất"],
    "dijkstra":     ["dijkstra", "thuật toán dijkstra"],
    "topological sort": ["sắp xếp topo"],

    # Khái niệm lập trình
    "recursion":    ["đệ quy"],
    "pointer":      ["con trỏ"],
    "node":         ["nút", "đỉnh"],
    "edge":         ["cạnh", "cung"],
    "vertex":       ["đỉnh"],
    "complexity":   ["độ phức tạp"],
    "time complexity": ["độ phức tạp thời gian"],
    "space complexity": ["độ phức tạp không gian"],
    "algorithm":    ["giải thuật", "thuật toán"],
    "data structure": ["cấu trúc dữ liệu"],
    "dynamic programming": ["quy hoạch động"],
    "greedy":       ["tham lam", "thuật toán tham lam"],
    "divide and conquer": ["chia để trị"],
    "backtracking": ["quay lui"],

    # Cây
    "bst":          ["cây tìm kiếm nhị phân", "cây nhị phân tìm kiếm"],
    "avl":          ["cây avl", "cây cân bằng avl"],
    "red black tree": ["cây đen đỏ", "cây đỏ đen"],

    # Liên kết
    "singly linked list": ["danh sách liên kết đơn", "danh sách đơn"],
    "doubly linked list": ["danh sách liên kết đôi", "danh sách kép"],
    "circular linked list": ["danh sách liên kết vòng"],
}

# Build reverse mapping from Vietnamese terms to English terms
_REVERSE_TECH_DICT: dict[str, str] = {}
for en_term, vi_terms in _TECH_DICT.items():
    for vi_term in vi_terms:
        # Map Vietnamese term to English equivalent
        _REVERSE_TECH_DICT[vi_term.lower()] = en_term


def _normalize(text: str) -> str:
    """Lowercase + strip diacritics-agnostic comparison."""
    return text.lower().strip()


def _is_vietnamese(text: str) -> bool:
    # Check for Vietnamese diacritical marks
    vi_pattern = re.compile(
        r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]',
        re.IGNORECASE
    )
    return bool(vi_pattern.search(text))


def expand_query(query: str) -> str:
    """
    Thêm thuật ngữ tương đương (Anh -> Việt và Việt -> Anh) vào query.

    Ví dụ:
        "stack là gì"          → "stack ngăn xếp ngăn-xếp là gì"
        "ngăn xếp là gì"       → "ngăn xếp là gì stack"
    """
    q_lower  = _normalize(query)
    expansions: list[str] = []
    already_added: set[str] = set()

    # 1. English -> Vietnamese expansion (chỉ thực hiện nếu câu hỏi chứa tiếng Việt)
    if _is_vietnamese(query):
        sorted_terms = sorted(_TECH_DICT.keys(), key=lambda k: len(k), reverse=True)
        for en_term in sorted_terms:
            # Tìm EN term trong query (word boundary)
            pattern = r'\b' + re.escape(en_term) + r'\b'
            if re.search(pattern, q_lower):
                for vi_term in _TECH_DICT[en_term]:
                    # Chỉ thêm nếu VI term chưa có trong query gốc và chưa được thêm
                    if _normalize(vi_term) not in q_lower and vi_term not in already_added:
                        expansions.append(vi_term)
                        already_added.add(vi_term)

    # 2. Vietnamese -> English expansion
    sorted_vi_terms = sorted(_REVERSE_TECH_DICT.keys(), key=lambda k: len(k), reverse=True)
    for vi_term in sorted_vi_terms:
        if vi_term in q_lower:
            en_term = _REVERSE_TECH_DICT[vi_term]
            if en_term not in q_lower and en_term not in already_added:
                expansions.append(en_term)
                already_added.add(en_term)

    if expansions:
        expanded = query.rstrip() + " " + " ".join(expansions)
        return expanded

    return query

