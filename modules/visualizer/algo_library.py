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
    for i in range(n):
        for j in range(n - i - 1):
            if engine.should_stop(): return
            engine.emit_frame({"algo":"bubble_sort","array":arr[:],"selected":[j,j+1],"sorted":list(sorted_set),"line":3,"log":f"So sánh arr[{j}]={arr[j]} và arr[{j+1}]={arr[j+1]}"})
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
                engine.emit_frame({"algo":"bubble_sort","array":arr[:],"patched":[j,j+1],"sorted":list(sorted_set),"line":5,"log":f"Hoán đổi → arr[{j}]={arr[j]}, arr[{j+1}]={arr[j+1]}"})
        sorted_set.add(n - i - 1)
        engine.emit_frame({"algo":"bubble_sort","array":arr[:],"sorted":list(sorted_set),"line":2,"log":f"Pass {i+1}/{n-1} xong. Phần tử {arr[n-i-1]} đã về đúng vị trí."})
    engine.emit_frame({"algo":"bubble_sort","array":arr[:],"sorted":list(range(n)),"line":7,"log":"✅ Sắp xếp hoàn tất!"})


def _selection_sort(engine: "RenderEngine", data: list[int]):
    n = len(data)
    arr = data[:]
    sorted_set = set()
    for i in range(n):
        min_idx = i
        for j in range(i+1, n):
            if engine.should_stop(): return
            engine.emit_frame({"algo":"selection_sort","array":arr[:],"selected":[j],"patched":[min_idx],"sorted":list(sorted_set),"line":3,"log":f"Tìm min: arr[{j}]={arr[j]} vs min hiện tại arr[{min_idx}]={arr[min_idx]}"})
            if arr[j] < arr[min_idx]:
                min_idx = j
        if min_idx != i:
            arr[i], arr[min_idx] = arr[min_idx], arr[i]
            engine.emit_frame({"algo":"selection_sort","array":arr[:],"patched":[i,min_idx],"sorted":list(sorted_set),"line":6,"log":f"Hoán đổi arr[{i}]↔arr[{min_idx}]"})
        sorted_set.add(i)
        engine.emit_frame({"algo":"selection_sort","array":arr[:],"sorted":list(sorted_set),"line":2,"log":f"Đã đặt {arr[i]} vào vị trí {i}"})
    engine.emit_frame({"algo":"selection_sort","array":arr[:],"sorted":list(range(n)),"line":8,"log":"✅ Sắp xếp hoàn tất!"})


def _insertion_sort(engine: "RenderEngine", data: list[int]):
    arr = data[:]
    n = len(arr)
    for i in range(1, n):
        key = arr[i]
        j = i - 1
        engine.emit_frame({"algo":"insertion_sort","array":arr[:],"selected":[i],"line":2,"log":f"Chèn arr[{i}]={key} vào phần đã sắp xếp"})
        while j >= 0 and arr[j] > key:
            if engine.should_stop(): return
            arr[j+1] = arr[j]
            engine.emit_frame({"algo":"insertion_sort","array":arr[:],"patched":[j,j+1],"line":4,"log":f"Dịch arr[{j}]={arr[j]} sang phải"})
            j -= 1
        arr[j+1] = key
        engine.emit_frame({"algo":"insertion_sort","array":arr[:],"selected":[j+1],"line":6,"log":f"Chèn {key} vào vị trí {j+1}"})
    engine.emit_frame({"algo":"insertion_sort","array":arr[:],"sorted":list(range(n)),"line":7,"log":"✅ Sắp xếp hoàn tất!"})


def _merge_sort_run(engine, arr, l, r, sorted_set):
    if engine.should_stop() or l >= r: return
    mid = (l + r) // 2
    _merge_sort_run(engine, arr, l, mid, sorted_set)
    _merge_sort_run(engine, arr, mid+1, r, sorted_set)
    # Merge
    left, right = arr[l:mid+1][:], arr[mid+1:r+1][:]
    i = j = 0
    k = l
    while i < len(left) and j < len(right):
        if engine.should_stop(): return
        if left[i] <= right[j]:
            arr[k] = left[i]; i += 1
        else:
            arr[k] = right[j]; j += 1
        engine.emit_frame({"algo":"merge_sort","array":arr[:],"selected":list(range(l,k+1)),"line":6,"log":f"Merge [{l}:{r}] → arr[{k}]={arr[k]}"})
        k += 1
    while i < len(left):
        arr[k] = left[i]; i += 1; k += 1
    while j < len(right):
        arr[k] = right[j]; j += 1; k += 1

def _merge_sort(engine: "RenderEngine", data: list[int]):
    arr = data[:]
    _merge_sort_run(engine, arr, 0, len(arr)-1, set())
    engine.emit_frame({"algo":"merge_sort","array":arr[:],"sorted":list(range(len(arr))),"line":9,"log":"✅ Merge Sort hoàn tất!"})


def _quick_sort_run(engine, arr, low, high):
    if engine.should_stop() or low >= high: return
    pivot = arr[high]
    engine.emit_frame({"algo":"quick_sort","array":arr[:],"pivot":high,"line":2,"log":f"Pivot = arr[{high}] = {pivot}"})
    i = low - 1
    for j in range(low, high):
        if engine.should_stop(): return
        engine.emit_frame({"algo":"quick_sort","array":arr[:],"selected":[j],"pivot":high,"line":4,"log":f"arr[{j}]={arr[j]} {'<=' if arr[j]<=pivot else '>'} pivot={pivot}"})
        if arr[j] <= pivot:
            i += 1
            arr[i], arr[j] = arr[j], arr[i]
            engine.emit_frame({"algo":"quick_sort","array":arr[:],"patched":[i,j],"pivot":high,"line":6,"log":f"Hoán đổi arr[{i}]↔arr[{j}]"})
    arr[i+1], arr[high] = arr[high], arr[i+1]
    engine.emit_frame({"algo":"quick_sort","array":arr[:],"patched":[i+1,high],"line":8,"log":f"Đặt pivot {pivot} vào vị trí {i+1}"})
    p = i + 1
    _quick_sort_run(engine, arr, low, p-1)
    _quick_sort_run(engine, arr, p+1, high)

def _quick_sort(engine: "RenderEngine", data: list[int]):
    arr = data[:]
    _quick_sort_run(engine, arr, 0, len(arr)-1)
    engine.emit_frame({"algo":"quick_sort","array":arr[:],"sorted":list(range(len(arr))),"line":10,"log":"✅ Quick Sort hoàn tất!"})


def _heap_sort(engine: "RenderEngine", data: list[int]):
    arr = data[:]
    n = len(arr)

    def heapify(arr, n, i):
        largest = i; l = 2*i+1; r = 2*i+2
        if l < n and arr[l] > arr[largest]: largest = l
        if r < n and arr[r] > arr[largest]: largest = r
        if largest != i:
            arr[i], arr[largest] = arr[largest], arr[i]
            engine.emit_frame({"algo":"heap_sort","array":arr[:],"patched":[i,largest],"line":5,"log":f"Heapify: hoán đổi arr[{i}]={arr[i]} và arr[{largest}]={arr[largest]}"})
            heapify(arr, n, largest)

    for i in range(n//2-1, -1, -1):
        if engine.should_stop(): return
        heapify(arr, n, i)
    engine.emit_frame({"algo":"heap_sort","array":arr[:],"line":7,"log":"Max-Heap đã xây dựng xong"})

    sorted_set = set()
    for i in range(n-1, 0, -1):
        if engine.should_stop(): return
        arr[0], arr[i] = arr[i], arr[0]
        sorted_set.add(i)
        engine.emit_frame({"algo":"heap_sort","array":arr[:],"patched":[0,i],"sorted":list(sorted_set),"line":9,"log":f"Đưa max={arr[i]} xuống vị trí {i}"})
        heapify(arr, i, 0)
    sorted_set.add(0)
    engine.emit_frame({"algo":"heap_sort","array":arr[:],"sorted":list(range(n)),"line":11,"log":"✅ Heap Sort hoàn tất!"})


# ────────────────────────────────────────────────────────────────────────────
# SEARCH ALGORITHMS
# ────────────────────────────────────────────────────────────────────────────

def _linear_search(engine: "RenderEngine", data: list[int], target: int):
    arr = data[:]
    engine.emit_frame({"algo":"linear_search","array":arr,"line":1,"log":f"Tìm kiếm {target} trong mảng {arr}"})
    for i, v in enumerate(arr):
        if engine.should_stop(): return
        engine.emit_frame({"algo":"linear_search","array":arr,"selected":[i],"line":3,"log":f"arr[{i}]={v} {'== ✅' if v==target else '≠'} {target}"})
        if v == target:
            engine.emit_frame({"algo":"linear_search","array":arr,"patched":[i],"line":4,"log":f"✅ Tìm thấy {target} tại index {i}!"})
            return
    engine.emit_frame({"algo":"linear_search","array":arr,"line":6,"log":f"❌ Không tìm thấy {target}"})


def _binary_search(engine: "RenderEngine", data: list[int], target: int):
    arr = sorted(data)
    l, r = 0, len(arr)-1
    engine.emit_frame({"algo":"binary_search","array":arr,"line":1,"log":f"Tìm {target} trong mảng ĐÃ SẮP XẾP {arr}"})
    while l <= r:
        if engine.should_stop(): return
        mid = (l + r) // 2
        engine.emit_frame({"algo":"binary_search","array":arr,"selected":[mid],"patched":list(range(l,r+1)),"line":3,"log":f"mid={mid} (arr[mid]={arr[mid]}), tìm kiếm [{l}:{r}]"})
        if arr[mid] == target:
            engine.emit_frame({"algo":"binary_search","array":arr,"patched":[mid],"sorted":[mid],"line":4,"log":f"✅ Tìm thấy {target} tại index {mid}!"})
            return
        elif arr[mid] < target:
            engine.emit_frame({"algo":"binary_search","array":arr,"selected":[mid],"line":6,"log":f"arr[{mid}]={arr[mid]} < {target} → tìm nửa phải"})
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
    visited, frontier = set(), {(sr,sc)}
    engine.emit_frame({"algo":"dijkstra","grid":grid,"visited":set(),"frontier":frontier,"current":None,"path":None,"line":1,"log":f"Khởi tạo: start=({sr},{sc}), end=({er},{ec})"})
    while heap:
        if engine.should_stop(): return
        d, r, c = heapq.heappop(heap)
        if (r,c) in visited: continue
        visited.add((r,c)); frontier.discard((r,c))
        engine.emit_frame({"algo":"dijkstra","grid":grid,"visited":set(visited),"frontier":set(frontier),"current":(r,c),"path":None,"line":4,"log":f"Xử lý ({r},{c}) dist={d:.0f}"})
        if (r,c) == (er,ec):
            path = []
            node = (er,ec)
            while node: path.append(node); node = prev.get(node)
            path.reverse()
            engine.emit_frame({"algo":"dijkstra","grid":grid,"visited":set(visited),"frontier":set(),"current":None,"path":path,"line":6,"log":f"✅ Đường đi ngắn nhất: {len(path)} bước!"})
            return
        for dr,dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr,nc = r+dr, c+dc
            if not(0<=nr<rows and 0<=nc<cols): continue
            if grid[nr][nc]=="wall" or (nr,nc) in visited: continue
            nd = d + 1
            if nd < dist[nr][nc]:
                dist[nr][nc] = nd; prev[(nr,nc)] = (r,c)
                heapq.heappush(heap, (nd,nr,nc))
                frontier.add((nr,nc))
    engine.emit_frame({"algo":"dijkstra","grid":grid,"visited":set(visited),"frontier":set(),"current":None,"path":None,"line":8,"log":"❌ Không tìm thấy đường đi!"})


def _bfs(engine: "RenderEngine", grid: list[list[str]], rows: int, cols: int):
    from collections import deque
    sr = sc = er = ec = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == "start": sr, sc = r, c
            if grid[r][c] == "end":   er, ec = r, c
    visited = set(); frontier = {(sr,sc)}
    queue = deque([(sr,sc)]); prev = {}; visited.add((sr,sc))
    engine.emit_frame({"algo":"bfs","grid":grid,"visited":set(visited),"frontier":set(frontier),"current":None,"path":None,"line":1,"log":f"BFS từ ({sr},{sc})"})
    while queue:
        if engine.should_stop(): return
        r,c = queue.popleft(); frontier.discard((r,c))
        engine.emit_frame({"algo":"bfs","grid":grid,"visited":set(visited),"frontier":set(frontier),"current":(r,c),"path":None,"line":3,"log":f"Dequeue ({r},{c})"})
        if (r,c) == (er,ec):
            path = []; node = (er,ec)
            while node: path.append(node); node = prev.get(node)
            path.reverse()
            engine.emit_frame({"algo":"bfs","grid":grid,"visited":set(visited),"frontier":set(),"current":None,"path":path,"line":5,"log":f"✅ Tìm thấy! Đường đi: {len(path)} bước"})
            return
        for dr,dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr,nc = r+dr,c+dc
            if 0<=nr<rows and 0<=nc<cols and grid[nr][nc]!="wall" and (nr,nc) not in visited:
                visited.add((nr,nc)); prev[(nr,nc)]=(r,c)
                queue.append((nr,nc)); frontier.add((nr,nc))
    engine.emit_frame({"algo":"bfs","grid":grid,"visited":set(visited),"frontier":set(),"current":None,"path":None,"line":8,"log":"❌ Không tìm thấy đường đi!"})


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
             broken_at=None, found=None, new_node=None, message=""):
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
        "message":   message,
    })


def _ll_build_from(data: list[int]):
    """Tạo linked list từ list Python."""
    head = None
    for v in reversed(data):
        nd = _LLNode(v)
        nd.nxt = head
        head = nd
    return head, len(data)


def _ll_insert_head(engine, data: list[int], target: int):
    """Insert at Head với hoạt ảnh."""
    head, size = _ll_build_from(data)
    _ll_emit(engine, head, message=f"⏳ List hiện tại — sắp chèn {target} vào đầu...")
    if engine.should_stop(): return

    new_nd = _LLNode(target)
    _ll_emit(engine, head, new_node=new_nd.id,
             message=f"✨ Tạo node mới [{target}] — chưa nối vào list")
    if engine.should_stop(): return

    new_nd.nxt = head
    head = new_nd
    size += 1
    _ll_emit(engine, head, active=new_nd.id, broken_at=new_nd.id,
             message=f"✂️ Nối node mới → node cũ (old HEAD)...")
    if engine.should_stop(): return

    _ll_emit(engine, head, active=new_nd.id,
             message=f"✅ Đã chèn [{target}] vào đầu danh sách! Size = {size}")


def _ll_insert_tail(engine, data: list[int], target: int):
    """Insert at Tail với hoạt ảnh."""
    head, size = _ll_build_from(data)
    _ll_emit(engine, head, message=f"⏳ Chuẩn bị chèn {target} vào cuối danh sách...")
    if engine.should_stop(): return

    new_nd = _LLNode(target)
    _ll_emit(engine, head, new_node=new_nd.id,
             message=f"✨ Tạo node mới [{target}]")
    if engine.should_stop(): return

    if head is None:
        head = new_nd
        size += 1
        _ll_emit(engine, head, active=new_nd.id,
                 message=f"✅ List rỗng → [{target}] là HEAD. Insert hoàn tất!")
        return

    cur = head
    visited: set = set()
    while cur.nxt:
        if engine.should_stop(): return
        visited.add(cur.id)
        _ll_emit(engine, head, highlight=set(visited), active=cur.id,
                 message=f"🔍 Duyệt node [{cur.val}] — tìm cuối list...")
        cur = cur.nxt

    _ll_emit(engine, head, highlight=set(visited), active=cur.id, broken_at=cur.id,
             message=f"✂️ Tìm thấy cuối [{cur.val}] — cắt liên kết NULL...")
    if engine.should_stop(): return

    cur.nxt = new_nd
    size += 1
    _ll_emit(engine, head, active=new_nd.id,
             message=f"✅ Nối [{cur.val}] → [{target}]. Insert hoàn tất! Size = {size}")


def _ll_insert_idx(engine, data: list[int], index: int, value: int):
    """Insert at Index với index và value riêng biệt."""
    head, size = _ll_build_from(data)
    index = max(0, min(index, size))

    if index <= 0:
        _ll_insert_head(engine, data, value)
        return
    if index >= size:
        _ll_insert_tail(engine, data, value)
        return

    _ll_emit(engine, head, message=f"⏳ Chèn giá trị [{value}] tại vị trí [{index}]...")
    if engine.should_stop(): return

    new_nd = _LLNode(value)
    _ll_emit(engine, head, new_node=new_nd.id,
             message=f"✨ Tạo node mới [{value}]")
    if engine.should_stop(): return

    cur = head
    visited: set = set()
    for i in range(index - 1):
        if engine.should_stop(): return
        visited.add(cur.id)
        _ll_emit(engine, head, highlight=set(visited), active=cur.id,
                 message=f"🔍 Duyệt node [{cur.val}] (vị trí {i})...")
        cur = cur.nxt

    old_next = cur.nxt
    _ll_emit(engine, head, highlight=set(visited), active=cur.id, broken_at=cur.id,
             message=f"✂️ Cắt liên kết [{cur.val}] → [{old_next.val if old_next else 'None'}]")
    if engine.should_stop(): return

    new_nd.nxt = old_next
    cur.nxt = new_nd
    size += 1
    _ll_emit(engine, head, active=new_nd.id,
             message=f"✅ Chèn [{value}] tại vị trí {index} — hoàn tất! Size = {size}")


def _ll_delete(engine, data: list[int], target: int):
    """Xóa node đầu tiên có value = target."""
    head, size = _ll_build_from(data)
    _ll_emit(engine, head, message=f"⏳ Tìm kiếm [{target}] để xóa...")
    if engine.should_stop(): return

    if head is None:
        _ll_emit(engine, head, message="❌ Danh sách rỗng!")
        return

    if head.val == target:
        old_id = head.id
        _ll_emit(engine, head, active=old_id,
                 message=f"🎯 Tìm thấy [{target}] tại HEAD — đang xóa...")
        if engine.should_stop(): return
        head = head.nxt
        size -= 1
        _ll_emit(engine, head, message=f"✅ Đã xóa [{target}] khỏi HEAD! Size = {size}")
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
                     message=f"🎯 Tìm thấy [{target}] — chuẩn bị cắt liên kết...")
            if engine.should_stop(): return

            _ll_emit(engine, head, highlight=set(visited), active=target_nd.id,
                     broken_at=cur.id,
                     message=f"✂️ Cắt [{cur.val}] → [{target}]...")
            if engine.should_stop(): return

            cur.nxt = target_nd.nxt
            target_nd.nxt = None
            size -= 1
            found = True
            _ll_emit(engine, head, active=cur.id,
                     message=f"✅ Đã xóa [{target}]. Nối lại [{cur.val}] → "
                             f"[{cur.nxt.val if cur.nxt else 'None'}]. Size = {size}")
            break

        _ll_emit(engine, head, highlight=set(visited), active=cur.id,
                 message=f"🔍 [{cur.val}] ≠ {target}, tiếp tục duyệt...")
        cur = cur.nxt

    if not found:
        _ll_emit(engine, head, message=f"❌ Không tìm thấy [{target}] để xóa!")


def _ll_search(engine, data: list[int], target: int):
    """Tìm kiếm tuần tự với hoạt ảnh."""
    head, _ = _ll_build_from(data)
    _ll_emit(engine, head, message=f"🔍 Bắt đầu tìm kiếm [{target}]...")
    if engine.should_stop(): return

    cur = head
    idx = 0
    visited: set = set()
    while cur:
        if engine.should_stop(): return
        _ll_emit(engine, head, highlight=set(visited), active=cur.id,
                 message=f"🔍 Kiểm tra node [{cur.val}] tại vị trí {idx}...")
        if cur.val == target:
            _ll_emit(engine, head, found=cur.id,
                     message=f"✅ Tìm thấy [{target}] tại vị trí {idx}!")
            return
        visited.add(cur.id)
        cur = cur.nxt
        idx += 1

    _ll_emit(engine, head, message=f"❌ Không tìm thấy [{target}] trong danh sách!")


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
        "run": _bubble_sort,
    },
    "selection_sort": {
        "name": "Selection Sort",
        "category": "🔃 Sorting",
        "tracers": ["chart", "log", "code"],
        "code": _SELECTION_CODE,
        "input_type": "array",
        "complexity": {"time": "O(n²)", "space": "O(1)"},
        "run": _selection_sort,
    },
    "insertion_sort": {
        "name": "Insertion Sort",
        "category": "🔃 Sorting",
        "tracers": ["chart", "log", "code"],
        "code": _INSERTION_CODE,
        "input_type": "array",
        "complexity": {"time": "O(n²)", "space": "O(1)"},
        "run": _insertion_sort,
    },
    "merge_sort": {
        "name": "Merge Sort",
        "category": "🔃 Sorting",
        "tracers": ["chart", "log", "code"],
        "code": _MERGE_CODE,
        "input_type": "array",
        "complexity": {"time": "O(n log n)", "space": "O(n)"},
        "run": _merge_sort,
    },
    "quick_sort": {
        "name": "Quick Sort",
        "category": "🔃 Sorting",
        "tracers": ["chart", "log", "code"],
        "code": _QUICK_CODE,
        "input_type": "array",
        "complexity": {"time": "O(n log n) avg", "space": "O(log n)"},
        "run": _quick_sort,
    },
    "heap_sort": {
        "name": "Heap Sort",
        "category": "🔃 Sorting",
        "tracers": ["chart", "log", "code"],
        "code": _HEAP_CODE,
        "input_type": "array",
        "complexity": {"time": "O(n log n)", "space": "O(1)"},
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
        "run": _linear_search,
    },
    "binary_search": {
        "name": "Binary Search",
        "category": "🔍 Searching",
        "tracers": ["array1d", "log", "code"],
        "code": _BINARY_SEARCH_CODE,
        "input_type": "array_target",
        "complexity": {"time": "O(log n)", "space": "O(1)"},
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
        "run": _dijkstra,
    },
    "bfs": {
        "name": "BFS Pathfinding",
        "category": "🗺️ Pathfinding",
        "tracers": ["grid", "log", "code"],
        "code": _BFS_CODE,
        "input_type": "grid",
        "complexity": {"time": "O(V+E)", "space": "O(V)"},
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
        "run": _ll_insert_head,
    },
    "ll_insert_tail": {
        "name": "Insert at Tail",
        "category": "🔗 Linked List",
        "tracers": ["linked_list", "log", "code"],
        "code": _LL_INSERT_TAIL_CODE,
        "input_type": "array_target",
        "complexity": {"time": "O(n)", "space": "O(1)"},
        "run": _ll_insert_tail,
    },
    "ll_insert_idx": {
        "name": "Insert at Index",
        "category": "🔗 Linked List",
        "tracers": ["linked_list", "log", "code"],
        "code": _LL_INSERT_IDX_CODE,
        "input_type": "ll_insert_idx",
        "complexity": {"time": "O(n)", "space": "O(1)"},
        "run": _ll_insert_idx,
    },
    "ll_delete": {
        "name": "Delete by Value",
        "category": "🔗 Linked List",
        "tracers": ["linked_list", "log", "code"],
        "code": _LL_DELETE_CODE,
        "input_type": "array_target",
        "complexity": {"time": "O(n)", "space": "O(1)"},
        "run": _ll_delete,
    },
    "ll_search": {
        "name": "Search",
        "category": "🔗 Linked List",
        "tracers": ["linked_list", "log", "code"],
        "code": _LL_SEARCH_CODE,
        "input_type": "array_target",
        "complexity": {"time": "O(n)", "space": "O(1)"},
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
