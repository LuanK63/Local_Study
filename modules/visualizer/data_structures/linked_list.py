"""
modules/visualizer/data_structures/linked_list.py — Linked List Visualizer
===========================================================================
Cho phép người dùng Insert, Delete, Search trên Linked List.
Mỗi thao tác phát từng frame để hoạt ảnh: mũi tên đứt gãy → node mới → mũi tên nối lại.

Cách dùng:
    engine = RenderEngine(speed_fn=...)
    ll_viz = LinkedListVisualizer(engine)
    engine.start(lambda: ll_viz.insert(42))  # Insert từ worker thread

Mỗi frame payload:
    {
        "mode":       "linked_list",
        "nodes":      [{"val": int, "id": str}, ...],   # thứ tự danh sách
        "highlight":  set of node_id,   # màu vàng — đang chú ý
        "active":     str | None,       # node_id đang được tác động (màu đỏ/xanh)
        "arrows":     list[(from_id, to_id)],  # tất cả mũi tên hiện tại
        "broken_at":  str | None,       # node_id nơi mũi tên bị đứt (để vẽ ảnh đứt gãy)
        "message":    str,
        "found":      str | None,       # node_id tìm thấy khi Search
    }
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.visualizer.render_engine import RenderEngine


class _Node:
    """Một node nội bộ của Linked List."""
    def __init__(self, value: int):
        self.val: int  = value
        self.nxt: "_Node | None" = None
        # Mỗi node có ID duy nhất để canvas vẽ hoạt ảnh chính xác
        self.id: str = str(uuid.uuid4())[:8]


class LinkedListVisualizer:
    """
    Linked List có hoạt ảnh. Tất cả public method có thể chạy trong Worker Thread.
    """

    def __init__(self, engine: "RenderEngine"):
        self._engine = engine
        self._head: _Node | None = None
        self._size: int = 0

    # ── Helpers để lấy snapshot hiện tại của list ────────────────────────────

    def _snapshot(self) -> tuple[list[dict], list[tuple[str, str]]]:
        """
        Trả về:
            nodes  = [{"val": v, "id": id}, ...]  — thứ tự từ head đến tail
            arrows = [(from_id, to_id), ...]       — các mũi tên hiện có
        """
        nodes: list[dict] = []
        arrows: list[tuple[str, str]] = []
        cur = self._head
        while cur:
            nodes.append({"val": cur.val, "id": cur.id})
            if cur.nxt:
                arrows.append((cur.id, cur.nxt.id))
            cur = cur.nxt
        return nodes, arrows

    def _emit(
        self,
        highlight: set[str] | None = None,
        active: str | None = None,
        broken_at: str | None = None,
        message: str = "",
        found: str | None = None,
    ) -> None:
        """Gửi frame hiện tại lên Main Thread."""
        nodes, arrows = self._snapshot()
        self._engine.emit_frame({
            "mode":      "linked_list",
            "nodes":     nodes,
            "highlight": highlight or set(),
            "active":    active,
            "arrows":    arrows,
            "broken_at": broken_at,
            "message":   message,
            "found":     found,
        })

    # ── Thao tác Insert ───────────────────────────────────────────────────────

    def insert_at_head(self, value: int) -> None:
        """Chèn node mới vào đầu danh sách với hoạt ảnh."""
        engine = self._engine

        # Bước 1: Hiển thị trạng thái hiện tại, thông báo chuẩn bị chèn
        self._emit(message=f"⏳ Chuẩn bị chèn {value} vào đầu danh sách...")

        # Bước 2: Tạo node mới (chưa nối vào list — vẽ node "lơ lửng")
        new_node = _Node(value)
        # Tạm thời thêm vào đầu snapshot để vẽ node mới
        self._head = new_node  # chèn thật vào head tạm để snapshot thấy
        self._emit(
            active=new_node.id,
            broken_at=new_node.id,   # mũi tên từ new_node đến old_head chưa vẽ
            message=f" Tạo node mới [{value}] — chưa nối vào list",
        )

        # Bước 3: Không cần hoàn nguyên vì đã chèn đúng thật sự
        # Nối new_node → old_head đã xảy ra tự động nhì _head đặt trên
        self._size += 1
        self._emit(
            active=new_node.id,
            message=f" Nối node [{value}] vào đầu — Insert hoàn tất!",
        )

    def insert_at_tail(self, value: int) -> None:
        """Chèn node mới vào cuối danh sách với hoạt ảnh."""
        new_node = _Node(value)

        self._emit(message=f"⏳ Chuẩn bị chèn {value} vào cuối danh sách...")

        if self._head is None:
            # List rỗng — chỉ cần đặt head
            self._head = new_node
            self._size += 1
            self._emit(
                active=new_node.id,
                message=f" List rỗng → [{value}] là head. Insert hoàn tất!",
            )
            return

        # Duyệt đến cuối list — highlight từng node đang duyệt
        cur = self._head
        visited: set[str] = set()
        while cur.nxt:
            if self._engine.should_stop():
                return
            visited.add(cur.id)
            self._emit(
                highlight=set(visited),
                active=cur.id,
                message=f" Duyệt đến node [{cur.val}] để tìm cuối list...",
            )
            cur = cur.nxt

        # Tìm thấy cuối — Bước đứt gãy mũi tên (Tail → None → new_node)
        self._emit(
            highlight=set(visited),
            active=cur.id,
            broken_at=cur.id,
            message=f" Tìm thấy cuối [{cur.val}] — chuẩn bị nối node mới...",
        )

        # Nối thật sự
        cur.nxt = new_node
        self._size += 1

        self._emit(
            active=new_node.id,
            message=f" Nối [{cur.val}] → [{value}] — Insert hoàn tất!",
        )

    def insert_at_index(self, index: int, value: int) -> None:
        """Chèn node tại vị trí index (0-based) với hoạt ảnh."""
        if index <= 0:
            self.insert_at_head(value)
            return
        if index >= self._size:
            self.insert_at_tail(value)
            return

        new_node = _Node(value)
        self._emit(message=f"⏳ Chèn {value} tại vị trí {index}...")

        cur = self._head
        visited: set[str] = set()
        for i in range(index - 1):   # dừng ở node TRƯỚC vị trí cần chèn
            if self._engine.should_stop():
                return
            visited.add(cur.id)
            self._emit(
                highlight=set(visited),
                active=cur.id,
                message=f" Duyệt node [{cur.val}] (vị trí {i})...",
            )
            cur = cur.nxt

        # cur đang ở node tại index-1
        # Bước đứt gãy: cắt liên kết cur → cur.nxt
        old_next = cur.nxt
        self._emit(
            highlight=set(visited),
            active=cur.id,
            broken_at=cur.id,
            message=f" Cắt liên kết [{cur.val}] → [{old_next.val if old_next else 'None'}]",
        )

        # Nối: new_node → old_next
        new_node.nxt = old_next
        # Nối: cur → new_node
        cur.nxt = new_node
        self._size += 1

        self._emit(
            active=new_node.id,
            message=f" Chèn [{value}] tại vị trí {index} — hoàn tất!",
        )

    # ── Thao tác Delete ───────────────────────────────────────────────────────

    def delete_by_value(self, value: int) -> bool:
        """Xóa node đầu tiên có giá trị = value. Trả về True nếu tìm thấy."""
        self._emit(message=f"⏳ Tìm kiếm [{value}] để xóa...")

        if self._head is None:
            self._emit(message=" Danh sách rỗng, không thể xóa!")
            return False

        # Xóa head
        if self._head.val == value:
            old_id = self._head.id
            self._emit(
                active=old_id,
                message=f" Tìm thấy [{value}] tại HEAD — đang xóa...",
            )
            self._head = self._head.nxt
            self._size -= 1
            self._emit(message=f" Đã xóa [{value}] khỏi HEAD!")
            return True

        # Duyệt tìm node trước node cần xóa
        cur = self._head
        visited: set[str] = set()
        while cur.nxt:
            if self._engine.should_stop():
                return False
            visited.add(cur.id)
            if cur.nxt.val == value:
                # Tìm thấy!
                target = cur.nxt
                self._emit(
                    highlight=set(visited),
                    active=target.id,
                    message=f" Tìm thấy [{value}] — chuẩn bị cắt liên kết...",
                )

                # Bước đứt gãy
                self._emit(
                    highlight=set(visited),
                    active=target.id,
                    broken_at=cur.id,
                    message=f" Cắt [{cur.val}] → [{value}]...",
                )

                # Nối cur → target.nxt (bỏ qua target)
                cur.nxt = target.nxt
                target.nxt = None   # dọn dẹp node đã xóa
                self._size -= 1

                self._emit(
                    active=cur.id,
                    message=f" Đã xóa [{value}] — nối lại [{cur.val}] → "
                            f"[{cur.nxt.val if cur.nxt else 'None'}]",
                )
                return True

            self._emit(
                highlight=set(visited),
                active=cur.id,
                message=f" [{cur.val}] ≠ {value}, tiếp tục duyệt...",
            )
            cur = cur.nxt

        self._emit(message=f" Không tìm thấy [{value}] để xóa!")
        return False

    # ── Thao tác Search ───────────────────────────────────────────────────────

    def search(self, value: int) -> bool:
        """Tìm kiếm tuần tự với hoạt ảnh, highlight node khi tìm thấy."""
        self._emit(message=f" Bắt đầu tìm kiếm [{value}]...")

        cur = self._head
        index = 0
        visited: set[str] = set()

        while cur:
            if self._engine.should_stop():
                return False

            # Highlight node đang kiểm tra
            self._emit(
                highlight=set(visited),
                active=cur.id,
                message=f" Kiểm tra node [{cur.val}] (vị trí {index})...",
            )

            if cur.val == value:
                self._emit(
                    found=cur.id,
                    active=cur.id,
                    message=f" Tìm thấy [{value}] tại vị trí {index}!",
                )
                return True

            visited.add(cur.id)
            cur = cur.nxt
            index += 1

        self._emit(message=f" Không tìm thấy [{value}] trong danh sách!")
        return False

    # ── Utility ───────────────────────────────────────────────────────────────

    def clear(self) -> None:
        """Xóa toàn bộ danh sách."""
        self._head = None
        self._size = 0
        self._emit(message=" Đã xóa toàn bộ danh sách.")

    @property
    def size(self) -> int:
        return self._size

    def to_list(self) -> list[int]:
        """Chuyển linked list thành Python list (để debug)."""
        result = []
        cur = self._head
        while cur:
            result.append(cur.val)
            cur = cur.nxt
        return result
