"""
modules/visualizer/algo_library.py — Algorithm Library
=======================================================
Mỗi entry trong ALGO_LIBRARY mô tả một thuật toán:
  - "name":     Tên hiển thị
  - "category": Nhóm thuật toán
  - "code":     Pseudocode/Python code hiển thị ở CodeTracer
  - "tracers":  Danh sách tracer cần khởi tạo
  - "run":      Callable(engine, params) → chạy trong Worker Thread

Quy ước frame payload:
  Mọi frame PHẢI có key "algo" = algo_id (để controller dispatch đúng tracer).
  Mỗi tracer đọc key riêng của nó từ payload.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.visualizer.render_engine import RenderEngine


# ────────────────────────────────────────────────────────────────────────────
# SORTING ALGORITHMS
# ────────────────────────────────────────────────────────────────────────────

def _bubble_sort(engine: "RenderEngine", data: list[int]):
    n = len(data)
    arr = data[:]
    sorted_set = set()
    compares = 0
    swaps = 0
    for i in range(n):
        for j in range(n - i - 1):
            if engine.should_stop(): return
            compares += 1
            engine.emit_frame({
                "algo": "bubble_sort",
                "data": arr[:],
                "status": "comparing",
                "message": f"🔍 So sánh arr[{j}]={arr[j]} và arr[{j+1}]={arr[j+1]}",
                "compare_indices": [j, j+1],
                "swap_indices": [],
                "sorted_indices": list(sorted_set),
                "current_line": 3,
                "stats": {"comparisons": compares, "swaps": swaps, "visited_nodes": 0}
            })
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
                swaps += 1
                engine.emit_frame({
                    "algo": "bubble_sort",
                    "data": arr[:],
                    "status": "swapping",
                    "message": f"🔄 Hoán đổi → arr[{j}]={arr[j]}, arr[{j+1}]={arr[j+1]}",
                    "compare_indices": [],
                    "swap_indices": [j, j+1],
                    "sorted_indices": list(sorted_set),
                    "current_line": 5,
                    "stats": {"comparisons": compares, "swaps": swaps, "visited_nodes": 0}
                })
        sorted_set.add(n - i - 1)
        engine.emit_frame({
            "algo": "bubble_sort",
            "data": arr[:],
            "status": "sorted",
            "message": f"✅ Pass {i+1}/{n-1} xong. Phần tử {arr[n-i-1]} đã đúng vị trí.",
            "compare_indices": [],
            "swap_indices": [],
            "sorted_indices": list(sorted_set),
            "current_line": 2,
            "stats": {"comparisons": compares, "swaps": swaps, "visited_nodes": 0}
        })
    engine.emit_frame({
        "algo": "bubble_sort",
        "data": arr[:],
        "status": "done",
        "message": "✅ Sắp xếp hoàn tất!",
        "compare_indices": [],
        "swap_indices": [],
        "sorted_indices": list(range(n)),
        "current_line": 7,
        "stats": {"comparisons": compares, "swaps": swaps, "visited_nodes": 0}
    })


def _selection_sort(engine: "RenderEngine", data: list[int]):
    n = len(data)
    arr = data[:]
    sorted_set = set()
    compares = 0
    swaps = 0
    for i in range(n):
        min_idx = i
        for j in range(i+1, n):
            if engine.should_stop(): return
            compares += 1
            engine.emit_frame({
                "algo": "selection_sort",
                "data": arr[:],
                "status": "comparing",
                "message": f"🔍 Tìm min: arr[{j}]={arr[j]} vs min hiện tại arr[{min_idx}]={arr[min_idx]}",
                "compare_indices": [j],
                "swap_indices": [min_idx],
                "sorted_indices": list(sorted_set),
                "current_line": 3,
                "stats": {"comparisons": compares, "swaps": swaps, "visited_nodes": 0}
            })
            if arr[j] < arr[min_idx]:
                min_idx = j
        if min_idx != i:
            arr[i], arr[min_idx] = arr[min_idx], arr[i]
            swaps += 1
            engine.emit_frame({
                "algo": "selection_sort",
                "data": arr[:],
                "status": "swapping",
                "message": f"🔄 Hoán đổi arr[{i}] ↔ arr[{min_idx}]",
                "compare_indices": [],
                "swap_indices": [i, min_idx],
                "sorted_indices": list(sorted_set),
                "current_line": 6,
                "stats": {"comparisons": compares, "swaps": swaps, "visited_nodes": 0}
            })
        sorted_set.add(i)
        engine.emit_frame({
            "algo": "selection_sort",
            "data": arr[:],
            "status": "sorted",
            "message": f"✅ Đã đặt {arr[i]} vào vị trí {i}",
            "compare_indices": [],
            "swap_indices": [],
            "sorted_indices": list(sorted_set),
            "current_line": 2,
            "stats": {"comparisons": compares, "swaps": swaps, "visited_nodes": 0}
        })
    engine.emit_frame({
        "algo": "selection_sort",
        "data": arr[:],
        "status": "done",
        "message": "✅ Sắp xếp hoàn tất!",
        "compare_indices": [],
        "swap_indices": [],
        "sorted_indices": list(range(n)),
        "current_line": 8,
        "stats": {"comparisons": compares, "swaps": swaps, "visited_nodes": 0}
    })


def _insertion_sort(engine: "RenderEngine", data: list[int]):
    arr = data[:]
    n = len(arr)
    compares = 0
    swaps = 0
    for i in range(1, n):
        key = arr[i]
        j = i - 1
        engine.emit_frame({
            "algo": "insertion_sort",
            "data": arr[:],
            "status": "comparing",
            "message": f"🔍 Xét phần tử chèn key = arr[{i}]={key}",
            "compare_indices": [i],
            "swap_indices": [],
            "sorted_indices": list(range(i)),
            "current_line": 2,
            "stats": {"comparisons": compares, "swaps": swaps, "visited_nodes": 0}
        })
        while j >= 0:
            if engine.should_stop(): return
            compares += 1
            if arr[j] > key:
                arr[j+1] = arr[j]
                swaps += 1
                engine.emit_frame({
                    "algo": "insertion_sort",
                    "data": arr[:],
                    "status": "swapping",
                    "message": f"🔄 Dịch chuyển arr[{j}]={arr[j]} sang phải",
                    "compare_indices": [],
                    "swap_indices": [j, j+1],
                    "sorted_indices": list(range(i+1)),
                    "current_line": 4,
                    "stats": {"comparisons": compares, "swaps": swaps, "visited_nodes": 0}
                })
                j -= 1
            else:
                break
        arr[j+1] = key
        engine.emit_frame({
            "algo": "insertion_sort",
            "data": arr[:],
            "status": "swapping",
            "message": f"🎯 Đặt key={key} vào vị trí {j+1}",
            "compare_indices": [j+1],
            "swap_indices": [],
            "sorted_indices": list(range(i+1)),
            "current_line": 6,
            "stats": {"comparisons": compares, "swaps": swaps, "visited_nodes": 0}
        })
    engine.emit_frame({
        "algo": "insertion_sort",
        "data": arr[:],
        "status": "done",
        "message": "✅ Sắp xếp hoàn tất!",
        "compare_indices": [],
        "swap_indices": [],
        "sorted_indices": list(range(n)),
        "current_line": 7,
        "stats": {"comparisons": compares, "swaps": swaps, "visited_nodes": 0}
    })


def _merge_sort_run(engine, arr, l, r, state):
    if engine.should_stop() or l >= r: return
    mid = (l + r) // 2
    _merge_sort_run(engine, arr, l, mid, state)
    _merge_sort_run(engine, arr, mid+1, r, state)
    
    # Merge
    left, right = arr[l:mid+1][:], arr[mid+1:r+1][:]
    i = j = 0
    k = l
    while i < len(left) and j < len(right):
        if engine.should_stop(): return
        state["compares"] += 1
        if left[i] <= right[j]:
            arr[k] = left[i]; i += 1
        else:
            arr[k] = right[j]; j += 1
            state["swaps"] += 1
        engine.emit_frame({
            "algo": "merge_sort",
            "data": arr[:],
            "status": "comparing",
            "message": f"🔍 Trộn [{l}:{r}] → arr[{k}]={arr[k]}",
            "compare_indices": list(range(l, k+1)),
            "swap_indices": [],
            "sorted_indices": [],
            "current_line": 6,
            "stats": {"comparisons": state["compares"], "swaps": state["swaps"], "visited_nodes": 0}
        })
        k += 1
    while i < len(left):
        arr[k] = left[i]; i += 1; k += 1
    while j < len(right):
        arr[k] = right[j]; j += 1; k += 1


def _merge_sort(engine: "RenderEngine", data: list[int]):
    arr = data[:]
    state = {"compares": 0, "swaps": 0}
    _merge_sort_run(engine, arr, 0, len(arr)-1, state)
    engine.emit_frame({
        "algo": "merge_sort",
        "data": arr[:],
        "status": "done",
        "message": "✅ Merge Sort hoàn tất!",
        "compare_indices": [],
        "swap_indices": [],
        "sorted_indices": list(range(len(arr))),
        "current_line": 9,
        "stats": {"comparisons": state["compares"], "swaps": state["swaps"], "visited_nodes": 0}
    })


def _quick_sort_run(engine, arr, low, high, state):
    if engine.should_stop() or low >= high: return
    pivot = arr[high]
    engine.emit_frame({
        "algo": "quick_sort",
        "data": arr[:],
        "status": "comparing",
        "message": f"🔍 Chọn Pivot = arr[{high}] = {pivot}",
        "compare_indices": [],
        "swap_indices": [],
        "sorted_indices": [],
        "pivot": high,
        "current_line": 2,
        "stats": {"comparisons": state["compares"], "swaps": state["swaps"], "visited_nodes": 0}
    })
    i = low - 1
    for j in range(low, high):
        if engine.should_stop(): return
        state["compares"] += 1
        engine.emit_frame({
            "algo": "quick_sort",
            "data": arr[:],
            "status": "comparing",
            "message": f"🔍 So sánh arr[{j}]={arr[j]} và pivot={pivot}",
            "compare_indices": [j],
            "swap_indices": [],
            "pivot": high,
            "current_line": 4,
            "stats": {"comparisons": state["compares"], "swaps": state["swaps"], "visited_nodes": 0}
        })
        if arr[j] <= pivot:
            i += 1
            arr[i], arr[j] = arr[j], arr[i]
            state["swaps"] += 1
            engine.emit_frame({
                "algo": "quick_sort",
                "data": arr[:],
                "status": "swapping",
                "message": f"🔄 Hoán đổi phân vùng: arr[{i}] ↔ arr[{j}]",
                "compare_indices": [],
                "swap_indices": [i, j],
                "pivot": high,
                "current_line": 6,
                "stats": {"comparisons": state["compares"], "swaps": state["swaps"], "visited_nodes": 0}
            })
    arr[i+1], arr[high] = arr[high], arr[i+1]
    state["swaps"] += 1
    engine.emit_frame({
        "algo": "quick_sort",
        "data": arr[:],
        "status": "swapping",
        "message": f"🎯 Đặt pivot vào vị trí phân chia {i+1}",
        "compare_indices": [],
        "swap_indices": [i+1, high],
        "current_line": 8,
        "stats": {"comparisons": state["compares"], "swaps": state["swaps"], "visited_nodes": 0}
    })
    p = i + 1
    _quick_sort_run(engine, arr, low, p-1, state)
    _quick_sort_run(engine, arr, p+1, high, state)


def _quick_sort(engine: "RenderEngine", data: list[int]):
    arr = data[:]
    state = {"compares": 0, "swaps": 0}
    _quick_sort_run(engine, arr, 0, len(arr)-1, state)
    engine.emit_frame({
        "algo": "quick_sort",
        "data": arr[:],
        "status": "done",
        "message": "✅ Quick Sort hoàn tất!",
        "compare_indices": [],
        "swap_indices": [],
        "sorted_indices": list(range(len(arr))),
        "current_line": 10,
        "stats": {"comparisons": state["compares"], "swaps": state["swaps"], "visited_nodes": 0}
    })


def _heap_sort(engine: "RenderEngine", data: list[int]):
    arr = data[:]
    n = len(arr)
    state = {"compares": 0, "swaps": 0}

    def heapify(arr, n, i):
        largest = i; l = 2*i+1; r = 2*i+2
        if l < n:
            state["compares"] += 1
            if arr[l] > arr[largest]: largest = l
        if r < n:
            state["compares"] += 1
            if arr[r] > arr[largest]: largest = r
        if largest != i:
            arr[i], arr[largest] = arr[largest], arr[i]
            state["swaps"] += 1
            engine.emit_frame({
                "algo": "heap_sort",
                "data": arr[:],
                "status": "swapping",
                "message": f"🔄 Heapify: hoán đổi arr[{i}]={arr[i]} và arr[{largest}]={arr[largest]}",
                "compare_indices": [],
                "swap_indices": [i, largest],
                "sorted_indices": [],
                "current_line": 5,
                "stats": {"comparisons": state["compares"], "swaps": state["swaps"], "visited_nodes": 0}
            })
            heapify(arr, n, largest)

    for i in range(n//2-1, -1, -1):
        if engine.should_stop(): return
        heapify(arr, n, i)
    engine.emit_frame({
        "algo": "heap_sort",
        "data": arr[:],
        "status": "comparing",
        "message": "✅ Max-Heap đã xây dựng xong!",
        "compare_indices": [],
        "swap_indices": [],
        "sorted_indices": [],
        "current_line": 7,
        "stats": {"comparisons": state["compares"], "swaps": state["swaps"], "visited_nodes": 0}
    })

    sorted_set = set()
    for i in range(n-1, 0, -1):
        if engine.should_stop(): return
        arr[0], arr[i] = arr[i], arr[0]
        state["swaps"] += 1
        sorted_set.add(i)
        engine.emit_frame({
            "algo": "heap_sort",
            "data": arr[:],
            "status": "swapping",
            "message": f"🔄 Đưa max={arr[i]} xuống cuối vị trí {i}",
            "compare_indices": [],
            "swap_indices": [0, i],
            "sorted_indices": list(sorted_set),
            "current_line": 9,
            "stats": {"comparisons": state["compares"], "swaps": state["swaps"], "visited_nodes": 0}
        })
        heapify(arr, i, 0)
    sorted_set.add(0)
    engine.emit_frame({
        "algo": "heap_sort",
        "data": arr[:],
        "status": "done",
        "message": "✅ Heap Sort hoàn tất!",
        "compare_indices": [],
        "swap_indices": [],
        "sorted_indices": list(range(n)),
        "current_line": 11,
        "stats": {"comparisons": state["compares"], "swaps": state["swaps"], "visited_nodes": 0}
    })


# ────────────────────────────────────────────────────────────────────────────
# SEARCH ALGORITHMS
# ────────────────────────────────────────────────────────────────────────────

def _linear_search(engine: "RenderEngine", data: list[int], target: int):
    arr = data[:]
    compares = 0
    visited = 0
    engine.emit_frame({
        "algo": "linear_search",
        "data": arr,
        "status": "comparing",
        "message": f"🔎 Bắt đầu tìm kiếm {target} trong mảng {arr}",
        "compare_indices": [],
        "swap_indices": [],
        "visited_indices": [],
        "current_line": 1,
        "stats": {"comparisons": compares, "swaps": 0, "visited_nodes": visited}
    })
    for i, v in enumerate(arr):
        if engine.should_stop(): return
        compares += 1
        visited += 1
        is_match = (v == target)
        status = "done" if is_match else "comparing"
        msg = f"🎯 Tìm thấy {target} tại index {i}!" if is_match else f"🔍 So sánh: arr[{i}]={v} ≠ {target}"
        
        engine.emit_frame({
            "algo": "linear_search",
            "data": arr,
            "status": status,
            "message": msg,
            "compare_indices": [i],
            "swap_indices": [],
            "sorted_indices": [i] if is_match else [],
            "visited_indices": list(range(i)) if not is_match else list(range(i+1)),
            "current_line": 3,
            "stats": {"comparisons": compares, "swaps": 0, "visited_nodes": visited}
        })
        if v == target:
            return
    engine.emit_frame({
        "algo": "linear_search",
        "data": arr,
        "status": "done",
        "message": f"❌ Không tìm thấy {target} trong mảng",
        "compare_indices": [],
        "swap_indices": [],
        "visited_indices": list(range(len(arr))),
        "current_line": 6,
        "stats": {"comparisons": compares, "swaps": 0, "visited_nodes": visited}
    })


def _binary_search(engine: "RenderEngine", data: list[int], target: int):
    arr = sorted(data)
    l, r = 0, len(arr)-1
    compares = 0
    visited = 0
    visited_set = set()
    engine.emit_frame({
        "algo": "binary_search",
        "data": arr,
        "status": "comparing",
        "message": f"🔎 Bắt đầu Binary Search tìm {target} trong mảng {arr}",
        "compare_indices": [],
        "swap_indices": [],
        "visited_indices": [],
        "current_line": 1,
        "stats": {"comparisons": compares, "swaps": 0, "visited_nodes": visited}
    })
    while l <= r:
        if engine.should_stop(): return
        mid = (l + r) // 2
        compares += 1
        visited += 1
        visited_set.add(mid)
        
        engine.emit_frame({
            "algo": "binary_search",
            "data": arr,
            "status": "comparing",
            "message": f"🔍 Kiểm tra mid={mid} (arr[mid]={arr[mid]}). Vùng tìm kiếm: [{l}:{r}]",
            "compare_indices": [mid],
            "swap_indices": list(range(l, r+1)),
            "visited_indices": list(visited_set),
            "current_line": 3,
            "stats": {"comparisons": compares, "swaps": 0, "visited_nodes": visited}
        })
        if arr[mid] == target:
            engine.emit_frame({
                "algo": "binary_search",
                "data": arr,
                "status": "done",
                "message": f"🎯 Tìm thấy {target} tại index {mid}!",
                "compare_indices": [],
                "swap_indices": [],
                "sorted_indices": [mid],
                "visited_indices": list(visited_set),
                "current_line": 4,
                "stats": {"comparisons": compares, "swaps": 0, "visited_nodes": visited}
            })
            return
        elif arr[mid] < target:
            engine.emit_frame({
                "algo": "binary_search",
                "data": arr,
                "status": "comparing",
                "message": f"🔍 arr[{mid}]={arr[mid]} < {target} → thu hẹp sang nửa phải [{mid+1}:{r}]",
                "compare_indices": [mid],
                "swap_indices": [],
                "visited_indices": list(visited_set),
                "current_line": 6,
                "stats": {"comparisons": compares, "swaps": 0, "visited_nodes": visited}
            })
            l = mid + 1
        else:
            engine.emit_frame({"algo":"binary_search","array":arr,"selected":[mid],"line":8,"log":f"arr[{mid}]={arr[mid]} > {target} → tìm nửa trái"})
            r = mid - 1
    engine.emit_frame({"algo":"binary_search","array":arr,"line":10,"log":f"❌ Không tìm thấy {target}"})


# ────────────────────────────────────────────────────────────────────────────
# PATHFINDING
# ────────────────────────────────────────────────────────────────────────────

def _dijkstra(engine: "RenderEngine", grid: list[list[str]], rows: int, cols: int):
    import heapq, math
    INF = math.inf
    dist = [[INF]*cols for _ in range(rows)]
    prev = {}
    sr = sc = er = ec = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == "start": sr, sc = r, c
            if grid[r][c] == "end":   er, ec = r, c
            
    dist[sr][sc] = 0
    heap = [(0.0, sr, sc)]
    visited_nodes = []  # processed nodes
    frontier_nodes = {(sr, sc)}
    
    # 1. Khởi tạo frame
    engine.emit_frame({
        "algo": "dijkstra",
        "grid": grid,
        "visited_nodes": list(visited_nodes),
        "frontier_nodes": list(frontier_nodes),
        "current_node": None,
        "current_distance": 0.0,
        "path_nodes": [],
        "message": f"🏁 Khởi tạo Dijkstra: Điểm bắt đầu tại ({sr}, {sc}), Điểm đích tại ({er}, {ec})",
        "current_line": 0
    })
    
    found = False
    while heap:
        if engine.should_stop(): return
        d, r, c = heapq.heappop(heap)
        if (r, c) in visited_nodes: continue
        
        visited_nodes.append((r, c))
        frontier_nodes.discard((r, c))
        
        # Emit frame khi dequeue
        engine.emit_frame({
            "algo": "dijkstra",
            "grid": grid,
            "visited_nodes": list(visited_nodes),
            "frontier_nodes": list(frontier_nodes),
            "current_node": (r, c),
            "current_distance": d,
            "path_nodes": [],
            "message": f"🔍 Duyệt ô ({r}, {c}) có khoảng cách ngắn nhất là {d:.0f}",
            "current_line": 3
        })
        
        if (r, c) == (er, ec):
            found = True
            break
            
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols): continue
            if grid[nr][nc] == "wall" or (nr, nc) in visited_nodes: continue
            
            nd = d + 1
            if nd < dist[nr][nc]:
                dist[nr][nc] = nd
                prev[(nr, nc)] = (r, c)
                heapq.heappush(heap, (nd, nr, nc))
                frontier_nodes.add((nr, nc))
                
                # Emit frame khi cập nhật khoảng cách ô lân cận
                engine.emit_frame({
                    "algo": "dijkstra",
                    "grid": grid,
                    "visited_nodes": list(visited_nodes),
                    "frontier_nodes": list(frontier_nodes),
                    "current_node": (r, c),
                    "current_distance": d,
                    "path_nodes": [],
                    "message": f"🗺️ Cập nhật ô lân cận ({nr}, {nc}) với khoảng cách = {nd}",
                    "current_line": 10
                })
                
    if found:
        # Reconstruct path
        path = []
        node = (er, ec)
        while node:
            path.append(node)
            node = prev.get(node)
        path.reverse()
        
        # Hoạt ảnh vẽ đường đi từ Start -> End
        for i in range(1, len(path) + 1):
            if engine.should_stop(): return
            engine.emit_frame({
                "algo": "dijkstra",
                "grid": grid,
                "visited_nodes": list(visited_nodes),
                "frontier_nodes": list(frontier_nodes),
                "current_node": path[i-1],
                "current_distance": dist[er][ec],
                "path_nodes": path[:i],
                "message": f"📈 Hoạt ảnh đường đi ngắn nhất: Bước {i}/{len(path)}",
                "current_line": 7
            })
    else:
        # Xử lý khi không tìm thấy đường đi
        engine.emit_frame({
            "algo": "dijkstra",
            "grid": grid,
            "visited_nodes": list(visited_nodes),
            "frontier_nodes": [],
            "current_node": None,
            "current_distance": INF,
            "path_nodes": [],
            "message": "❌ Kết thúc: Không tìm thấy đường đi!",
            "current_line": 11
        })


def _bfs(engine: "RenderEngine", grid: list[list[str]], rows: int, cols: int):
    from collections import deque
    sr = sc = er = ec = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == "start": sr, sc = r, c
            if grid[r][c] == "end":   er, ec = r, c
            
    visited_nodes = []  # processed nodes
    pushed = {(sr, sc)}  # to avoid pushing multiple times
    frontier_nodes = [(sr, sc)]
    queue = deque([(sr, sc)])
    prev = {}
    
    # 1. Khởi tạo frame
    engine.emit_frame({
        "algo": "bfs",
        "grid": grid,
        "visited_nodes": list(visited_nodes),
        "frontier_nodes": list(frontier_nodes),
        "current_node": None,
        "path_nodes": [],
        "message": f"🏁 Khởi tạo BFS: Điểm bắt đầu tại ({sr}, {sc}), Điểm đích tại ({er}, {ec})",
        "current_line": 0
    })
    
    found = False
    while queue:
        if engine.should_stop(): return
        r, c = queue.popleft()
        frontier_nodes.remove((r, c))
        visited_nodes.append((r, c))
        
        # Emit frame khi dequeue
        engine.emit_frame({
            "algo": "bfs",
            "grid": grid,
            "visited_nodes": list(visited_nodes),
            "frontier_nodes": list(frontier_nodes),
            "current_node": (r, c),
            "path_nodes": [],
            "message": f"🔍 Duyệt ô ({r}, {c}) từ Queue và xét các ô lân cận",
            "current_line": 3
        })
        
        if (r, c) == (er, ec):
            found = True
            break
            
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                if grid[nr][nc] != "wall" and (nr, nc) not in pushed:
                    pushed.add((nr, nc))
                    prev[(nr, nc)] = (r, c)
                    queue.append((nr, nc))
                    frontier_nodes.append((nr, nc))
                    
                    # Emit frame khi thêm vào queue
                    engine.emit_frame({
                        "algo": "bfs",
                        "grid": grid,
                        "visited_nodes": list(visited_nodes),
                        "frontier_nodes": list(frontier_nodes),
                        "current_node": (r, c),
                        "path_nodes": [],
                        "message": f"🗺️ Thêm ô lân cận ({nr}, {nc}) vào Queue",
                        "current_line": 10
                    })
                    
    if found:
        # Reconstruct path
        path = []
        node = (er, ec)
        while node:
            path.append(node)
            node = prev.get(node)
        path.reverse()
        
        # Hoạt ảnh vẽ đường đi từ Start -> End
        for i in range(1, len(path) + 1):
            if engine.should_stop(): return
            engine.emit_frame({
                "algo": "bfs",
                "grid": grid,
                "visited_nodes": list(visited_nodes),
                "frontier_nodes": list(frontier_nodes),
                "current_node": path[i-1],
                "path_nodes": path[:i],
                "message": f"📈 Hoạt ảnh đường đi: Bước {i}/{len(path)}",
                "current_line": 5
            })
    else:
        # Xử lý khi không tìm thấy đường đi
        engine.emit_frame({
            "algo": "bfs",
            "grid": grid,
            "visited_nodes": list(visited_nodes),
            "frontier_nodes": [],
            "current_node": None,
            "path_nodes": [],
            "message": "❌ Kết thúc: Không tìm thấy đường đi!",
            "current_line": 11
        })


# ────────────────────────────────────────────────────────────────────────────
# LINKED LIST OPERATIONS
# ────────────────────────────────────────────────────────────────────────────

import uuid as _uuid


class _LLNode:
    __slots__ = ("val", "nxt", "id")
    def __init__(self, v: int):
        self.val = v
        self.nxt = None
        self.id: str = str(_uuid.uuid4())[:8]


def _ll_snapshot(head) -> tuple[list, list]:
    nodes, arrows = [], []
    cur = head
    while cur:
        nodes.append({"val": cur.val, "id": cur.id})
        if cur.nxt:
            arrows.append((cur.id, cur.nxt.id))
        cur = cur.nxt
    return nodes, arrows


def _ll_emit(engine, head, highlight=None, active=None,
             broken_at=None, found=None, new_node=None, new_node_val=None, message="",
             operation=None, insert_index=None):
    nodes, arrows = _ll_snapshot(head)
    engine.emit_frame({
        "mode":      "linked_list",
        "nodes":     nodes,
        "highlight": highlight or set(),
        "active":    active,
        "arrows":    arrows,
        "broken_at": broken_at,
        "found":     found,
        "new_node":  new_node,
        "new_node_val": new_node_val,
        "message":   message,
        "operation": operation,
        "insert_index": insert_index,
    })


def _ll_build_from(data: list[int], node_ids: list[str] | None = None):
    """Tạo linked list từ list Python."""
    head = None
    for i, v in enumerate(reversed(data)):
        nd = _LLNode(v)
        if node_ids and i < len(node_ids):
            orig_idx = len(data) - 1 - i
            nd.id = node_ids[orig_idx]
        nd.nxt = head
        head = nd
    return head, len(data)


def _ll_insert_head(engine, data: list[int], target: int, node_ids: list[str] | None = None):
    """Insert at Head với hoạt ảnh."""
    head, size = _ll_build_from(data, node_ids)
    _ll_emit(engine, head, message=f"⏳ List hiện tại — sắp chèn {target} vào đầu...", operation="insert_head", insert_index=0)
    if engine.should_stop(): return

    new_nd = _LLNode(target)
    _ll_emit(engine, head, new_node=new_nd.id, new_node_val=target,
             message=f"✨ Tạo node mới [{target}] — chưa nối vào list", operation="insert_head", insert_index=0)
    if engine.should_stop(): return

    new_nd.nxt = head
    head = new_nd
    size += 1
    _ll_emit(engine, head, active=new_nd.id, broken_at=new_nd.id,
             message=f"✂️ Nối node mới → node cũ (old HEAD)...", operation="insert_head", insert_index=0)
    if engine.should_stop(): return

    _ll_emit(engine, head, active=new_nd.id,
             message=f"✅ Đã chèn [{target}] vào đầu danh sách! Size = {size}", operation="insert_head", insert_index=0)


def _ll_insert_tail(engine, data: list[int], target: int, node_ids: list[str] | None = None):
    """Insert at Tail với hoạt ảnh."""
    head, size = _ll_build_from(data, node_ids)
    _ll_emit(engine, head, message=f"⏳ Chuẩn bị chèn {target} vào cuối danh sách...", operation="insert_tail", insert_index=size)
    if engine.should_stop(): return

    new_nd = _LLNode(target)
    _ll_emit(engine, head, new_node=new_nd.id, new_node_val=target,
             message=f"✨ Tạo node mới [{target}]", operation="insert_tail", insert_index=size)
    if engine.should_stop(): return

    if head is None:
        head = new_nd
        size += 1
        _ll_emit(engine, head, active=new_nd.id,
                 message=f"✅ List rỗng → [{target}] là HEAD. Insert hoàn tất!", operation="insert_tail", insert_index=size)
        return

    cur = head
    visited: set = set()
    while cur.nxt:
        if engine.should_stop(): return
        visited.add(cur.id)
        _ll_emit(engine, head, highlight=set(visited), active=cur.id,
                 message=f"🔍 Duyệt node [{cur.val}] — tìm cuối list...", operation="insert_tail", insert_index=size)
        cur = cur.nxt

    _ll_emit(engine, head, highlight=set(visited), active=cur.id, broken_at=cur.id,
             message=f"✂️ Tìm thấy cuối [{cur.val}] — cắt liên kết NULL...", operation="insert_tail", insert_index=size)
    if engine.should_stop(): return

    cur.nxt = new_nd
    size += 1
    _ll_emit(engine, head, active=new_nd.id,
             message=f"✅ Nối [{cur.val}] → [{target}]. Insert hoàn tất! Size = {size}", operation="insert_tail", insert_index=size)


def _ll_insert_idx(engine, data: list[int], index: int, value: int, node_ids: list[str] | None = None):
    """Insert at Index với index và value riêng biệt."""
    head, size = _ll_build_from(data, node_ids)
    index = max(0, min(index, size))

    if index <= 0:
        _ll_insert_head(engine, data, value, node_ids)
        return
    if index >= size:
        _ll_insert_tail(engine, data, value, node_ids)
        return

    _ll_emit(engine, head, message=f"⏳ Chèn giá trị [{value}] tại vị trí [{index}]...", operation="insert_idx", insert_index=index)
    if engine.should_stop(): return

    new_nd = _LLNode(value)
    _ll_emit(engine, head, new_node=new_nd.id, new_node_val=value,
             message=f"✨ Tạo node mới [{value}]", operation="insert_idx", insert_index=index)
    if engine.should_stop(): return

    cur = head
    visited: set = set()
    for i in range(index - 1):
        if engine.should_stop(): return
        visited.add(cur.id)
        _ll_emit(engine, head, highlight=set(visited), active=cur.id,
                 message=f"🔍 Duyệt node [{cur.val}] (vị trí {i})...", operation="insert_idx", insert_index=index)
        cur = cur.nxt

    old_next = cur.nxt
    _ll_emit(engine, head, highlight=set(visited), active=cur.id, broken_at=cur.id,
             message=f"✂️ Cắt liên kết [{cur.val}] → [{old_next.val if old_next else 'None'}]", operation="insert_idx", insert_index=index)
    if engine.should_stop(): return

    new_nd.nxt = old_next
    cur.nxt = new_nd
    size += 1
    _ll_emit(engine, head, active=new_nd.id,
             message=f"✅ Chèn [{value}] tại vị trí {index} — hoàn tất! Size = {size}", operation="insert_idx", insert_index=index)


def _ll_delete(engine, data: list[int], target: int, node_ids: list[str] | None = None):
    """Xóa node đầu tiên có value = target."""
    head, size = _ll_build_from(data, node_ids)
    _ll_emit(engine, head, message=f"⏳ Tìm kiếm [{target}] để xóa...", operation="delete")
    if engine.should_stop(): return

    if head is None:
        _ll_emit(engine, head, message="❌ Danh sách rỗng!", operation="delete")
        return

    if head.val == target:
        old_id = head.id
        _ll_emit(engine, head, active=old_id,
                 message=f"🎯 Tìm thấy [{target}] tại HEAD — đang xóa...", operation="delete")
        if engine.should_stop(): return
        head = head.nxt
        size -= 1
        _ll_emit(engine, head, message=f"✅ Đã xóa [{target}] khỏi HEAD! Size = {size}", operation="delete")
        return

    cur = head
    visited: set = set()
    found = False
    while cur.nxt:
        if engine.should_stop(): return
        visited.add(cur.id)
        if cur.nxt.val == target:
            target_nd = cur.nxt
            _ll_emit(engine, head, highlight=set(visited), active=target_nd.id,
                     message=f"🎯 Tìm thấy [{target}] — chuẩn bị cắt liên kết...", operation="delete")
            if engine.should_stop(): return

            _ll_emit(engine, head, highlight=set(visited), active=target_nd.id,
                     broken_at=cur.id,
                     message=f"✂️ Cắt [{cur.val}] → [{target}]...", operation="delete")
            if engine.should_stop(): return

            cur.nxt = target_nd.nxt
            target_nd.nxt = None
            size -= 1
            found = True
            _ll_emit(engine, head, active=cur.id,
                     message=f"✅ Đã xóa [{target}]. Nối lại [{cur.val}] → "
                             f"[{cur.nxt.val if cur.nxt else 'None'}]. Size = {size}", operation="delete")
            break

        _ll_emit(engine, head, highlight=set(visited), active=cur.id,
                 message=f"🔍 [{cur.val}] ≠ {target}, tiếp tục duyệt...", operation="delete")
        cur = cur.nxt

    if not found:
        _ll_emit(engine, head, message=f"❌ Không tìm thấy [{target}] để xóa!", operation="delete")


def _ll_search(engine, data: list[int], target: int, node_ids: list[str] | None = None):
    """Tìm kiếm tuần tự với hoạt ảnh."""
    head, _ = _ll_build_from(data, node_ids)
    _ll_emit(engine, head, message=f"🔍 Bắt đầu tìm kiếm [{target}]...", operation="search")
    if engine.should_stop(): return

    cur = head
    idx = 0
    visited: set = set()
    while cur:
        if engine.should_stop(): return
        _ll_emit(engine, head, highlight=set(visited), active=cur.id,
                 message=f"🔍 Kiểm tra node [{cur.val}] tại vị trí {idx}...", operation="search")
        if cur.val == target:
            _ll_emit(engine, head, found=cur.id,
                     message=f"✅ Tìm thấy [{target}] tại vị trí {idx}!", operation="search")
            return
        visited.add(cur.id)
        cur = cur.nxt
        idx += 1

    _ll_emit(engine, head, message=f"❌ Không tìm thấy [{target}] trong danh sách!", operation="search")


# Pseudocode strings
_LL_INSERT_HEAD_CODE = """\
function insertHead(value):
    newNode = Node(value)
    newNode.next = head    # trỏ vào old HEAD
    head = newNode         # cập nhật head mới
    size += 1"""

_LL_INSERT_TAIL_CODE = """\
function insertTail(value):
    newNode = Node(value)
    if head == null:
        head = newNode; return
    cur = head
    while cur.next != null:
        cur = cur.next   # duyệt đến cuối
    cur.next = newNode   # nối vào cuối
    size += 1"""

_LL_INSERT_IDX_CODE = """\
function insertAt(index, value):
    if index == 0: insertHead(value); return
    cur = head
    for i in range(index - 1):
        cur = cur.next    # dịch đến node trước
    newNode = Node(value)
    newNode.next = cur.next
    cur.next = newNode
    size += 1"""

_LL_DELETE_CODE = """\
function delete(value):
    if head.val == value:
        head = head.next; return
    cur = head
    while cur.next != null:
        if cur.next.val == value:
            cur.next = cur.next.next
            size -= 1; return
        cur = cur.next
    # Không tìm thấy"""

_LL_SEARCH_CODE = """\
function search(value):
    cur = head; idx = 0
    while cur != null:
        if cur.val == value:
            return idx   # Tìm thấy
        cur = cur.next
        idx += 1
    return -1            # Không tìm thấy"""


# ────────────────────────────────────────────────────────────────────────────
# ALGORITHM LIBRARY CATALOG
# ────────────────────────────────────────────────────────────────────────────

_BUBBLE_CODE = """\
for i in range(n):
    for j in range(n - i - 1):
        # So sánh hai phần tử kề nhau
        if arr[j] > arr[j + 1]:
            # Hoán đổi nếu sai thứ tự
            arr[j], arr[j + 1] = arr[j + 1], arr[j]
    # arr[n-i-1] đã đứng đúng chỗ
# Sắp xếp hoàn tất"""

_SELECTION_CODE = """\
for i in range(n):
    min_idx = i
    for j in range(i + 1, n):
        if arr[j] < arr[min_idx]:
            min_idx = j
    arr[i], arr[min_idx] = arr[min_idx], arr[i]
    # arr[0..i] đã được sắp xếp
# Sắp xếp hoàn tất"""

_INSERTION_CODE = """\
for i in range(1, n):
    key = arr[i]
    j = i - 1
    while j >= 0 and arr[j] > key:
        arr[j + 1] = arr[j]
        j -= 1
    arr[j + 1] = key
# Sắp xếp hoàn tất"""

_MERGE_CODE = """\
def merge_sort(arr, l, r):
    if l >= r: return
    mid = (l + r) // 2
    merge_sort(arr, l, mid)
    merge_sort(arr, mid+1, r)
    merge(arr, l, mid, r)
    # Mảng arr[l..r] đã được sắp xếp
# Sắp xếp hoàn tất"""

_QUICK_CODE = """\
def quick_sort(arr, low, high):
    pivot = arr[high]
    i = low - 1
    for j in range(low, high):
        if arr[j] <= pivot:
            i += 1
            arr[i], arr[j] = arr[j], arr[i]
    arr[i+1], arr[high] = arr[high], arr[i+1]
    p = i + 1
    quick_sort(arr, low, p - 1)
# Sắp xếp hoàn tất"""

_HEAP_CODE = """\
def heapify(arr, n, i):
    largest = i
    if arr[2i+1] > arr[largest]: largest = 2i+1
    if arr[2i+2] > arr[largest]: largest = 2i+2
    if largest != i: swap; heapify(arr, n, largest)
build_max_heap(arr)
for i in range(n-1, 0, -1):
    arr[0], arr[i] = arr[i], arr[0]
    heapify(arr, i, 0)
# Sắp xếp hoàn tất"""

_LINEAR_SEARCH_CODE = """\
def linear_search(arr, target):
    for i in range(len(arr)):
        if arr[i] == target:
            return i   # Tìm thấy tại index i
    return -1          # Không tìm thấy"""

_BINARY_SEARCH_CODE = """\
def binary_search(arr, target):
    l, r = 0, len(arr) - 1
    while l <= r:
        mid = (l + r) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            l = mid + 1
        else:
            r = mid - 1
    return -1  # Không tìm thấy"""

_DIJKSTRA_CODE = """\
dist[start] = 0
heap = [(0, start)]
while heap:
    d, u = heappop(heap)
    if u in visited: continue
    visited.add(u)
    if u == end:
        reconstruct_path()
        return
    for v in neighbors(u):
        heappush(heap, (d+1, v))
# Không tìm thấy"""

_BFS_CODE = """\
queue = deque([start])
visited = {start}
while queue:
    u = queue.popleft()
    if u == end:
        reconstruct_path()
        return
    for v in neighbors(u):
        if v not in visited:
            visited.add(v)
            queue.append(v)
# Không tìm thấy"""


ALGO_LIBRARY: dict[str, dict] = {
    # ── Sorting ──────────────────────────────────────────────────────────────
    "bubble_sort": {
        "name": "Bubble Sort",
        "category": "🔃 Sorting",
        "tracers": ["chart", "log", "code"],
        "code": _BUBBLE_CODE,
        "input_type": "array",
        "complexity": {"time": "O(n²)", "space": "O(1)"},
        "description": "Sắp xếp nổi bọt (Bubble Sort) là thuật toán sắp xếp đơn giản nhất, hoạt động bằng cách liên tục so sánh và hoán đổi các phần tử liền kề nếu chúng không đúng thứ tự.",
        "how_it_works": "Duyệt qua danh sách nhiều lần. Ở mỗi lần duyệt, so sánh các cặp phần tử đứng cạnh nhau. Nếu phần tử đứng trước lớn hơn phần tử đứng sau, hoán đổi chúng. Sau mỗi vòng duyệt, phần tử lớn nhất chưa sắp xếp sẽ được định vị đúng ở cuối danh sách.",
        "advantages": "Dễ hiểu, dễ cài đặt và gỡ lỗi. Không đòi hỏi thêm bộ nhớ phụ đáng kể (sắp xếp tại chỗ). Đạt O(n) nếu danh sách đã được sắp xếp sẵn (bằng cách tối ưu hóa dừng sớm).",
        "disadvantages": "Hiệu suất rất kém trên các tập dữ liệu lớn do độ phức tạp trung bình và tệ nhất đều là O(n²).",
        "best_case": "O(n)",
        "average_case": "O(n²)",
        "worst_case": "O(n²)",
        "space_complexity": "O(1)",
        "run": _bubble_sort,
    },
    "selection_sort": {
        "name": "Selection Sort",
        "category": "🔃 Sorting",
        "tracers": ["chart", "log", "code"],
        "code": _SELECTION_CODE,
        "input_type": "array",
        "complexity": {"time": "O(n²)", "space": "O(1)"},
        "description": "Sắp xếp chọn (Selection Sort) chia mảng thành phần đã sắp xếp và phần chưa sắp xếp, liên tục chọn phần tử nhỏ nhất từ phần chưa sắp xếp để đưa lên đầu phần đó.",
        "how_it_works": "1. Quét phần mảng chưa sắp xếp để tìm phần tử có giá trị nhỏ nhất.<br>2. Hoán đổi phần tử nhỏ nhất đó với phần tử đầu tiên của phân đoạn chưa sắp xếp.<br>3. Dịch ranh giới mảng đã sắp xếp lên một vị trí và lặp lại.",
        "advantages": "Đơn giản, trực quan. Số lượng phép hoán đổi (swaps) tối đa chỉ là O(n), lý tưởng khi chi phí ghi vào bộ nhớ đắt đỏ.",
        "disadvantages": "Độ phức tạp thời gian luôn là O(n²) bất kể trạng thái ban đầu của dữ liệu. Không giữ được tính ổn định của các khóa bằng nhau (Unstable).",
        "best_case": "O(n²)",
        "average_case": "O(n²)",
        "worst_case": "O(n²)",
        "space_complexity": "O(1)",
        "run": _selection_sort,
    },
    "insertion_sort": {
        "name": "Insertion Sort",
        "category": "🔃 Sorting",
        "tracers": ["chart", "log", "code"],
        "code": _INSERTION_CODE,
        "input_type": "array",
        "complexity": {"time": "O(n²)", "space": "O(1)"},
        "description": "Sắp xếp chèn (Insertion Sort) xây dựng danh sách đã sắp xếp từng phần tử một bằng cách chèn phần tử hiện tại vào vị trí chính xác của nó trong phần đã được sắp xếp trước đó.",
        "how_it_works": "Duyệt từ phần tử thứ hai của mảng. Coi phần tử hiện tại là khóa (key). So sánh và dịch chuyển toàn bộ các phần tử lớn hơn khóa ở bên trái sang phải một vị trí, sau đó đặt khóa vào khoảng trống được tạo ra.",
        "advantages": "Rất hiệu quả cho các mảng nhỏ hoặc các mảng gần như đã sắp xếp sẵn. Là thuật toán ổn định (Stable) và sắp xếp tại chỗ (In-place). Phù hợp cho việc sắp xếp luồng dữ liệu liên tục (Online).",
        "disadvantages": "Hiệu suất kém khi kích thước mảng lớn hoặc mảng bị đảo ngược thứ tự hoàn toàn.",
        "best_case": "O(n)",
        "average_case": "O(n²)",
        "worst_case": "O(n²)",
        "space_complexity": "O(1)",
        "run": _insertion_sort,
    },
    "merge_sort": {
        "name": "Merge Sort",
        "category": "🔃 Sorting",
        "tracers": ["chart", "log", "code"],
        "code": _MERGE_CODE,
        "input_type": "array",
        "complexity": {"time": "O(n log n)", "space": "O(n)"},
        "description": "Sắp xếp trộn (Merge Sort) sử dụng chiến lược Chia để trị (Divide and Conquer) để chia nhỏ mảng, sắp xếp các mảng con rồi trộn lại với nhau theo thứ tự tăng dần.",
        "how_it_works": "1. Chia mảng thành hai nửa bằng nhau cho đến khi các mảng con chỉ còn 1 phần tử.<br>2. Gọi đệ quy Merge Sort trên mỗi nửa.<br>3. Trộn hai nửa đã sắp xếp lại thành một mảng lớn thống nhất bằng cách so sánh phần tử đầu tiên của mỗi nửa.",
        "advantages": "Thời gian chạy ổn định ở mức O(n log n) trong mọi trường hợp (tốt nhất, trung bình, xấu nhất). Là thuật toán ổn định (Stable). Hoạt động cực kỳ hiệu quả trên dữ liệu tuần tự lớn.",
        "disadvantages": "Yêu cầu thêm bộ nhớ phụ O(n) để thực hiện quá trình trộn, điều này không tối ưu khi bộ nhớ bị giới hạn.",
        "best_case": "O(n log n)",
        "average_case": "O(n log n)",
        "worst_case": "O(n log n)",
        "space_complexity": "O(n)",
        "run": _merge_sort,
    },
    "quick_sort": {
        "name": "Quick Sort",
        "category": "🔃 Sorting",
        "tracers": ["chart", "log", "code"],
        "code": _QUICK_CODE,
        "input_type": "array",
        "complexity": {"time": "O(n log n) avg", "space": "O(log n)"},
        "description": "Sắp xếp nhanh (Quick Sort) là thuật toán chia để trị cực kỳ phổ biến và hiệu quả cao, hoạt động bằng cách phân hoạch mảng xung quanh một phần tử chốt (pivot).",
        "how_it_works": "1. Chọn một phần tử làm chốt (pivot).<br>2. Phân hoạch mảng: sắp xếp các phần tử sao cho những phần tử nhỏ hơn hoặc bằng pivot nằm bên trái, những phần tử lớn hơn pivot nằm bên phải.<br>3. Áp dụng đệ quy cho hai phân mảng bên trái và bên phải chốt.",
        "advantages": "Tốc độ thực tế rất nhanh nhờ tận dụng tốt bộ nhớ đệm (cache locality). Không đòi hỏi bộ nhớ phụ lớn như Merge Sort (sắp xếp tại chỗ in-place).",
        "disadvantages": "Độ phức tạp xấu nhất lên tới O(n²) nếu chọn chốt không tốt (ví dụ mảng đã sắp xếp sẵn và luôn chọn phần tử cuối). Không ổn định (Unstable).",
        "best_case": "O(n log n)",
        "average_case": "O(n log n)",
        "worst_case": "O(n²)",
        "space_complexity": "O(log n)",
        "run": _quick_sort,
    },
    "heap_sort": {
        "name": "Heap Sort",
        "category": "🔃 Sorting",
        "tracers": ["chart", "log", "code"],
        "code": _HEAP_CODE,
        "input_type": "array",
        "complexity": {"time": "O(n log n)", "space": "O(1)"},
        "description": "Sắp xếp vun đống (Heap Sort) là thuật toán sắp xếp so sánh dựa trên cấu trúc cây nhị phân Max-Heap.",
        "how_it_works": "1. Chuyển mảng đầu vào thành một Max-Heap.<br>2. Hoán đổi liên tục phần tử lớn nhất ở gốc cây (chỉ số 0) với phần tử cuối cùng chưa được sắp xếp của mảng.<br>3. Thu nhỏ kích thước Heap đi 1 và thực hiện vun lại đống (Heapify) cho đỉnh gốc. Lặp lại.",
        "advantages": "Độ phức tạp thời gian luôn đảm bảo O(n log n) trong mọi tình huống. Hoạt động tại chỗ (In-place) với lượng bộ nhớ bổ sung cố định O(1).",
        "disadvantages": "Không có tính ổn định (Unstable). Chạy thực tế chậm hơn Quick Sort do truy cập bộ nhớ nhảy cóc (không tận dụng được cache).",
        "best_case": "O(n log n)",
        "average_case": "O(n log n)",
        "worst_case": "O(n log n)",
        "space_complexity": "O(1)",
        "run": _heap_sort,
    },
    # ── Search ───────────────────────────────────────────────────────────────
    "linear_search": {
        "name": "Linear Search",
        "category": "🔍 Searching",
        "tracers": ["array1d", "log", "code"],
        "code": _LINEAR_SEARCH_CODE,
        "input_type": "array_target",
        "complexity": {"time": "O(n)", "space": "O(1)"},
        "description": "Tìm kiếm tuyến tính (Linear Search) quét qua toàn bộ mảng tuần tự từ đầu đến cuối để tìm khóa cần tìm.",
        "how_it_works": "Bắt đầu từ phần tử đầu tiên của mảng, so sánh giá trị của nó với khóa mục tiêu. Nếu bằng nhau, trả về chỉ số hiện tại. Nếu không bằng, tăng chỉ số lên 1 để kiểm tra phần tử tiếp theo. Quá trình tiếp tục đến hết mảng.",
        "advantages": "Dễ hiểu và dễ viết mã. Hoạt động tốt trên bất kỳ mảng nào mà không cần mảng phải sắp xếp trước.",
        "disadvantages": "Rất chậm đối với các tập dữ liệu có kích thước lớn vì số lượng phép so sánh tăng tuyến tính theo n.",
        "best_case": "O(1)",
        "average_case": "O(n)",
        "worst_case": "O(n)",
        "space_complexity": "O(1)",
        "run": _linear_search,
    },
    "binary_search": {
        "name": "Binary Search",
        "category": "🔍 Searching",
        "tracers": ["array1d", "log", "code"],
        "code": _BINARY_SEARCH_CODE,
        "input_type": "array_target",
        "complexity": {"time": "O(log n)", "space": "O(1)"},
        "description": "Tìm kiếm nhị phân (Binary Search) là thuật toán tìm kiếm hiệu năng cao hoạt động trên mảng đã được sắp xếp sẵn từ trước.",
        "how_it_works": "1. Đặt khoảng tìm kiếm từ l tới r. Tính chỉ số ở giữa mid = (l + r) // 2.<br>2. Nếu phần tử ở giữa bằng mục tiêu, trả về chỉ số mid.<br>3. Nếu phần tử ở giữa nhỏ hơn mục tiêu, thu hẹp khoảng tìm kiếm về nửa phải [mid + 1, r].<br>4. Ngược lại, thu hẹp về nửa trái [l, mid - 1]. Lặp lại.",
        "advantages": "Rất nhanh chóng với các tập dữ liệu cực kỳ lớn do không gian tìm kiếm được giảm đi một nửa sau mỗi bước (O(log n)).",
        "disadvantages": "Yêu cầu bắt buộc mảng phải được sắp xếp trước. Đòi hỏi mảng có khả năng truy cập ngẫu nhiên trực tiếp tới phần tử (Direct index access).",
        "best_case": "O(1)",
        "average_case": "O(log n)",
        "worst_case": "O(log n)",
        "space_complexity": "O(1)",
        "run": _binary_search,
    },
    # ── Pathfinding ───────────────────────────────────────────────────────────
    "dijkstra": {
        "name": "Dijkstra",
        "category": "🗺️ Pathfinding",
        "tracers": ["grid", "log", "code"],
        "code": _DIJKSTRA_CODE,
        "input_type": "grid",
        "complexity": {"time": "O((V+E) log V)", "space": "O(V)"},
        "description": "Thuật toán Dijkstra tìm đường đi ngắn nhất từ một đỉnh nguồn đến tất cả các đỉnh khác trên đồ thị có trọng số cạnh không âm.",
        "how_it_works": "Duy trì danh sách khoảng cách ngắn nhất ước lượng của các đỉnh và sử dụng hàng đợi ưu tiên (Min-Heap) để liên tục chọn đỉnh u chưa duyệt có khoảng cách ngắn nhất. Đánh dấu u là đã thăm và thực hiện cập nhật (nới lỏng) khoảng cách cho các đỉnh lân cận chưa thăm của u.",
        "advantages": "Đảm bảo luôn tìm thấy đường đi ngắn nhất chính xác nhất trên đồ thị có trọng số không âm.",
        "disadvantages": "Không hoạt động được trên đồ thị có các cạnh mang trọng số âm. Hiệu năng phụ thuộc nhiều vào cấu trúc hàng đợi ưu tiên.",
        "best_case": "O((V+E) log V)",
        "average_case": "O((V+E) log V)",
        "worst_case": "O((V+E) log V)",
        "space_complexity": "O(V)",
        "run": _dijkstra,
    },
    "bfs": {
        "name": "BFS Pathfinding",
        "category": "🗺️ Pathfinding",
        "tracers": ["grid", "log", "code"],
        "code": _BFS_CODE,
        "input_type": "grid",
        "complexity": {"time": "O(V+E)", "space": "O(V)"},
        "description": "Tìm kiếm theo chiều rộng (BFS) loang đều ra các hướng theo từng bước khoảng cách để duyệt đồ thị.",
        "how_it_works": "Sử dụng một hàng đợi (Queue) First-In-First-Out. Bắt đầu đẩy đỉnh nguồn vào Queue. Mỗi bước, lấy đỉnh đầu Queue ra, kiểm tra đích, nếu chưa phải thì duyệt các đỉnh lân cận chưa thăm của nó, đánh dấu đã thăm, lưu vết cha và đẩy chúng vào Queue.",
        "advantages": "Luôn tìm thấy đường đi ngắn nhất (chứa ít cạnh nhất) trên các đồ thị không có trọng số hoặc trọng số các cạnh bằng nhau.",
        "disadvantages": "Chi phí bộ nhớ lớn vì phải lưu trữ toàn bộ biên (frontier) của cấp độ duyệt hiện tại trong Queue.",
        "best_case": "O(V+E)",
        "average_case": "O(V+E)",
        "worst_case": "O(V+E)",
        "space_complexity": "O(V)",
        "run": _bfs,
    },
    # ── Linked List ───────────────────────────────────────────────────────────
    "ll_insert_head": {
        "name": "Insert at Head",
        "category": "🔗 Linked List",
        "tracers": ["linked_list", "log", "code"],
        "code": _LL_INSERT_HEAD_CODE,
        "input_type": "array_target",
        "complexity": {"time": "O(1)", "space": "O(1)"},
        "description": "Thêm một nút mới chứa giá trị được chỉ định vào ngay đầu Danh sách liên kết đơn.",
        "how_it_works": "1. Cấp phát bộ nhớ cho nút mới và gán giá trị.<br>2. Trỏ liên kết 'next' của nút mới vào đầu danh sách hiện tại (trỏ vào địa chỉ nút head cũ).<br>3. Cập nhật con trỏ head của danh sách trỏ tới nút mới vừa tạo.",
        "advantages": "Thời gian thực thi cố định O(1), cực kỳ nhanh và không phụ thuộc vào độ dài của danh sách liên kết.",
        "disadvantages": "Không có.",
        "best_case": "O(1)",
        "average_case": "O(1)",
        "worst_case": "O(1)",
        "space_complexity": "O(1)",
        "run": _ll_insert_head,
    },
    "ll_insert_tail": {
        "name": "Insert at Tail",
        "category": "🔗 Linked List",
        "tracers": ["linked_list", "log", "code"],
        "code": _LL_INSERT_TAIL_CODE,
        "input_type": "array_target",
        "complexity": {"time": "O(n)", "space": "O(1)"},
        "description": "Chèn một nút mới chứa giá trị được chỉ định vào cuối Danh sách liên kết đơn.",
        "how_it_works": "1. Khởi tạo nút mới.<br>2. Nếu danh sách đang rỗng, gán head trỏ trực tiếp tới nút mới.<br>3. Nếu danh sách không rỗng, dùng con trỏ tạm duyệt từ đầu danh sách đến nút cuối cùng (nút có nxt = Null).<br>4. Thiết lập thuộc tính nxt của nút cuối cùng trỏ tới nút mới.",
        "advantages": "Đảm bảo thứ tự chèn của các phần tử được bảo toàn.",
        "disadvantages": "Phải duyệt qua toàn bộ danh sách để tìm nút cuối (mất thời gian O(n)) trừ khi danh sách có duy trì một con trỏ tail quản lý nút cuối.",
        "best_case": "O(1) nếu danh sách rỗng hoặc có con trỏ tail quản lý",
        "average_case": "O(n)",
        "worst_case": "O(n)",
        "space_complexity": "O(1)",
        "run": _ll_insert_tail,
    },
    "ll_insert_idx": {
        "name": "Insert at Index",
        "category": "🔗 Linked List",
        "tracers": ["linked_list", "log", "code"],
        "code": _LL_INSERT_IDX_CODE,
        "input_type": "ll_insert_idx",
        "complexity": {"time": "O(n)", "space": "O(1)"},
        "description": "Chèn một nút mới chứa giá trị tại vị trí chỉ số (index) mong muốn trong Danh sách liên kết.",
        "how_it_works": "1. Nếu chỉ số index = 0, chèn vào đầu danh sách.<br>2. Nếu không, duyệt từ head để tìm nút đứng ngay trước vị trí cần chèn (nút ở vị trí index - 1).<br>3. Trỏ nxt của nút mới tới nxt của nút (index - 1).<br>4. Trỏ nxt của nút (index - 1) tới nút mới.",
        "advantages": "Linh hoạt chèn phần tử vào bất kỳ vị trí nào mà không cần dịch chuyển các phần tử phía sau như cấu trúc mảng.",
        "disadvantages": "Mất thời gian duyệt tuyến tính O(n) để đi đến vị trí chèn mong muốn.",
        "best_case": "O(1) nếu chèn ở vị trí đầu tiên",
        "average_case": "O(n)",
        "worst_case": "O(n)",
        "space_complexity": "O(1)",
        "run": _ll_insert_idx,
    },
    "ll_delete": {
        "name": "Delete by Value",
        "category": "🔗 Linked List",
        "tracers": ["linked_list", "log", "code"],
        "code": _LL_DELETE_CODE,
        "input_type": "array_target",
        "complexity": {"time": "O(n)", "space": "O(1)"},
        "description": "Xóa nút đầu tiên trong Danh sách liên kết có giá trị trùng khớp với giá trị chỉ định.",
        "how_it_works": "1. Nếu nút head chứa giá trị cần xóa, trỏ head tới head.next và giải phóng bộ nhớ của head cũ.<br>2. Nếu không, duyệt danh sách để tìm nút có giá trị bằng mục tiêu, đồng thời lưu vết nút liền trước (prev).<br>3. Khi tìm thấy, trỏ prev.next tới cur.next (bỏ qua nút hiện tại). Giải phóng cur.",
        "advantages": "Xóa phần tử nhanh chóng không cần dịch chuyển vị trí các ô nhớ phía sau.",
        "disadvantages": "Mất chi phí duyệt tuần tự O(n) để định vị được phần tử cần xóa.",
        "best_case": "O(1) nếu phần tử cần xóa nằm ngay đầu danh sách",
        "average_case": "O(n)",
        "worst_case": "O(n)",
        "space_complexity": "O(1)",
        "run": _ll_delete,
    },
    "ll_search": {
        "name": "Search",
        "category": "🔗 Linked List",
        "tracers": ["linked_list", "log", "code"],
        "code": _LL_SEARCH_CODE,
        "input_type": "array_target",
        "complexity": {"time": "O(n)", "space": "O(1)"},
        "description": "Tìm kiếm tuần tự một phần tử mang giá trị chỉ định trong Danh sách liên kết đơn.",
        "how_it_works": "Khởi hành từ head, dùng một biến con trỏ tạm duyệt qua từng nút. Tại mỗi nút, so sánh giá trị lưu trữ với mục tiêu. Nếu khớp, trả về vị trí index. Nếu không khớp, chuyển đến nút kế tiếp thông qua liên kết next. Quá trình tiếp diễn cho đến khi duyệt hết danh sách.",
        "advantages": "Đơn giản, dễ cài đặt trên cấu trúc danh sách liên kết.",
        "disadvantages": "Không thể áp dụng tìm kiếm nhị phân (Binary Search) do Linked List không hỗ trợ truy cập ngẫu nhiên trực tiếp tới phần tử bất kỳ theo chỉ số trong thời gian O(1). Luôn tốn thời gian O(n) trong trường hợp xấu nhất.",
        "best_case": "O(1)",
        "average_case": "O(n)",
        "worst_case": "O(n)",
        "space_complexity": "O(1)",
        "run": _ll_search,
    },
}



def get_categories() -> dict[str, list[tuple[str,str]]]:
    """Trả về {category: [(algo_id, algo_name), ...]}"""
    cats: dict[str, list] = {}
    for aid, info in ALGO_LIBRARY.items():
        cat = info["category"]
        cats.setdefault(cat, []).append((aid, info["name"]))
    return cats
