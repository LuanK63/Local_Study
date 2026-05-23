"""
modules/visualizer/canvas.py — PyQt6 Canvas Widgets
=====================================================
Tập hợp các QWidget chuyên biệt cho từng loại trực quan hóa.
Mỗi Canvas đăng ký lắng nghe signal `frame_ready` từ RenderEngine.

Canvas KHÔNG gọi bất kỳ logic thuật toán nào — nó chỉ VẼ theo payload.
"""
from __future__ import annotations

import math
from typing import Any

from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPen, QBrush,
    QFontMetrics, QPainterPath,
)
from PyQt6.QtWidgets import QWidget

# ── Màu sắc (Catppuccin Mocha palette) ───────────────────────────────────────
C_BG      = QColor("#1e1e2e")
C_SURFACE = QColor("#313244")
C_BORDER  = QColor("#45475a")
C_TEXT    = QColor("#cdd6f4")
C_SUBTEXT = QColor("#6c7086")
C_RED     = QColor("#f38ba8")
C_YELLOW  = QColor("#f9e2af")
C_GREEN   = QColor("#a6e3a1")
C_BLUE    = QColor("#89b4fa")
C_PURPLE  = QColor("#cba6f7")
C_TEAL    = QColor("#94e2d5")
C_PINK    = QColor("#f5c2e7")


# ══════════════════════════════════════════════════════════════════════════════
# Dijkstra Grid Canvas
# ══════════════════════════════════════════════════════════════════════════════

class DijkstraCanvas(QWidget):
    """
    Vẽ lưới 2D cho thuật toán Dijkstra.
    Hỗ trợ click/drag để đặt tường, start, end.
    """

    # Signal phát khi người dùng tương tác với ô (để controller xử lý)
    cell_clicked   = pyqtSignal(int, int, str)  # row, col, mode

    def __init__(self, rows: int = 15, cols: int = 25, parent=None):
        super().__init__(parent)
        self.rows = rows
        self.cols = cols
        self.setMinimumSize(400, 240)
        self.setMouseTracking(True)

        # Trạng thái nhận từ frame
        self._grid:     list[list[str]] | None = None
        self._dist:     list[list[float]] | None = None
        self._visited:  set = set()
        self._frontier: set = set()
        self._path:     list | None = None
        self._current:  tuple | None = None
        self._message:  str = ""

        # Chế độ tương tác: "wall" | "start" | "end"
        self._interact_mode: str = "wall"
        self._dragging = False

    def on_frame_received(self, payload: dict) -> None:
        """Nhận frame từ RenderEngine, lưu trạng thái và trigger repaint."""
        if payload.get("mode") != "dijkstra":
            return
        self._grid     = payload["grid"]
        self._dist     = payload["dist"]
        self._visited  = payload.get("visited", set())
        self._frontier = payload.get("frontier", set())
        self._path     = payload.get("path")
        self._current  = payload.get("current")
        self._message  = payload.get("message", "")
        self.update()   # yêu cầu Qt vẽ lại — an toàn từ Main Thread

    def set_grid(self, grid: list[list[str]]) -> None:
        """Dùng để hiển thị lưới trước khi chạy thuật toán."""
        self._grid = grid
        self.update()

    def set_interact_mode(self, mode: str) -> None:
        self._interact_mode = mode

    # ── Tính kích thước ô ─────────────────────────────────────────────────────

    def _cell_size(self) -> int:
        cw = (self.width()  - 4) // self.cols
        ch = (self.height() - 4) // self.rows
        return max(4, min(cw, ch))

    def _cell_rect(self, r: int, c: int) -> QRect:
        cs = self._cell_size()
        ox = (self.width()  - cs * self.cols) // 2
        oy = (self.height() - cs * self.rows) // 2
        return QRect(ox + c * cs + 1, oy + r * cs + 1, cs - 2, cs - 2)

    def _pos_to_cell(self, x: int, y: int) -> tuple[int, int] | None:
        cs = self._cell_size()
        ox = (self.width()  - cs * self.cols) // 2
        oy = (self.height() - cs * self.rows) // 2
        c = (x - ox) // cs
        r = (y - oy) // cs
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return (r, c)
        return None

    # ── Vẽ ───────────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        if not self._grid:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Xây path set để tra cứu nhanh
        path_set: set[tuple] = set(map(tuple, self._path)) if self._path else set()

        for r in range(self.rows):
            for c in range(self.cols):
                rect = self._cell_rect(r, c)
                cell_state = self._grid[r][c]
                pos = (r, c)

                # Chọn màu ô
                if self._path and pos in path_set:
                    color = C_YELLOW
                elif self._current and pos == self._current:
                    color = C_RED
                elif pos in self._frontier:
                    color = C_TEAL
                elif pos in self._visited:
                    color = C_BLUE.darker(140)
                elif cell_state == "wall":
                    color = C_SUBTEXT.darker(120)
                elif cell_state == "start":
                    color = C_GREEN
                elif cell_state == "end":
                    color = C_PINK
                else:
                    color = C_SURFACE

                p.setBrush(QBrush(color))
                p.setPen(QPen(C_BORDER, 0.5))
                p.drawRect(rect)

                # Vẽ nhãn start/end
                if cell_state in ("start", "end"):
                    p.setPen(QPen(C_BG))
                    p.setFont(QFont("Segoe UI", max(6, self._cell_size() // 3)))
                    p.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                               "S" if cell_state == "start" else "E")

    # ── Tương tác chuột ───────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        self._dragging = True
        cell = self._pos_to_cell(event.position().x(), event.position().y())
        if cell:
            self.cell_clicked.emit(cell[0], cell[1], self._interact_mode)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging and self._interact_mode == "wall":
            cell = self._pos_to_cell(event.position().x(), event.position().y())
            if cell:
                self.cell_clicked.emit(cell[0], cell[1], "wall")

    def mouseReleaseEvent(self, event) -> None:
        self._dragging = False


# ══════════════════════════════════════════════════════════════════════════════
# Linked List Canvas
# ══════════════════════════════════════════════════════════════════════════════

class LinkedListCanvas(QWidget):
    """
    Vẽ Linked List theo chiều ngang với mũi tên nối giữa các node.
    Hỗ trợ hoạt ảnh đứt gãy mũi tên (broken_at state).
    """

    NODE_W = 72
    NODE_H = 46
    ARROW_GAP = 32

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(160)

        self._nodes:     list[dict] = []       # [{"val": int, "id": str}, ...]
        self._highlight: set[str]   = set()    # node_id màu vàng
        self._active:    str | None = None     # node_id màu đỏ/xanh
        self._arrows:    list       = []       # [(from_id, to_id)]
        self._broken_at: str | None = None     # node_id nơi mũi tên bị đứt
        self._message:   str        = ""
        self._found:     str | None = None     # node_id tìm thấy (màu xanh đậm)

    def on_frame_received(self, payload: dict) -> None:
        if payload.get("mode") != "linked_list":
            return
        self._nodes     = payload.get("nodes", [])
        self._highlight = payload.get("highlight", set())
        self._active    = payload.get("active")
        self._arrows    = payload.get("arrows", [])
        self._broken_at = payload.get("broken_at")
        self._message   = payload.get("message", "")
        self._found     = payload.get("found")
        self.update()

    # ── Tính vị trí node ─────────────────────────────────────────────────────

    def _node_positions(self) -> dict[str, QRect]:
        """Trả về {node_id: QRect} cho mỗi node."""
        positions: dict[str, QRect] = {}
        n = len(self._nodes)
        if n == 0:
            return positions

        total_w = n * self.NODE_W + (n - 1) * self.ARROW_GAP
        start_x = max(8, (self.width() - total_w) // 2)
        y = (self.height() - self.NODE_H) // 2

        for i, node in enumerate(self._nodes):
            x = start_x + i * (self.NODE_W + self.ARROW_GAP)
            positions[node["id"]] = QRect(x, y, self.NODE_W, self.NODE_H)

        return positions

    # ── Vẽ ───────────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        positions = self._node_positions()

        # ── Vẽ mũi tên trước (để nằm dưới node) ────────────────────────────
        for from_id, to_id in self._arrows:
            if from_id not in positions or to_id not in positions:
                continue

            from_rect = positions[from_id]
            to_rect   = positions[to_id]

            # Điểm xuất phát từ cạnh phải của from_rect
            fx = from_rect.right()
            fy = from_rect.center().y()
            tx = to_rect.left()
            ty = to_rect.center().y()

            # Nếu mũi tên bị đứt tại from_id → vẽ đứt gãy
            if self._broken_at == from_id:
                pen = QPen(C_RED, 2, Qt.PenStyle.DashLine)
                p.setPen(pen)
                # Vẽ đến giữa khoảng trống (bị cắt)
                mid_x = (fx + tx) // 2
                p.drawLine(fx, fy, mid_x, ty)
                # Vẽ dấu X nhỏ ở điểm đứt
                p.setPen(QPen(C_RED, 2))
                p.drawLine(mid_x - 5, ty - 5, mid_x + 5, ty + 5)
                p.drawLine(mid_x - 5, ty + 5, mid_x + 5, ty - 5)
            else:
                pen = QPen(C_TEXT, 2)
                p.setPen(pen)
                p.drawLine(fx, fy, tx, ty)

                # Đầu mũi tên
                self._draw_arrowhead(p, fx, fy, tx, ty)

        # ── Vẽ NULL ở cuối (sau node cuối) ───────────────────────────────────
        if positions:
            last_id   = self._nodes[-1]["id"]
            last_rect = positions[last_id]
            null_x    = last_rect.right() + 8
            null_y    = last_rect.center().y()

            if self._broken_at == last_id:
                p.setPen(QPen(C_RED, 2, Qt.PenStyle.DashLine))
            else:
                p.setPen(QPen(C_SUBTEXT, 2))

            p.drawLine(last_rect.right(), null_y, null_x + 20, null_y)
            p.setFont(QFont("Consolas", 9))
            p.setPen(QPen(C_SUBTEXT))
            p.drawText(null_x + 20, null_y + 5, "NULL")

        # ── Vẽ các node ───────────────────────────────────────────────────────
        for node in self._nodes:
            nid  = node["id"]
            rect = positions.get(nid)
            if not rect:
                continue

            # Chọn màu
            if nid == self._found:
                bg = C_GREEN
            elif nid == self._active:
                bg = C_RED
            elif nid in self._highlight:
                bg = C_YELLOW
            else:
                bg = C_SURFACE

            # Vẽ node (hình chữ nhật bo tròn)
            p.setBrush(QBrush(bg))
            p.setPen(QPen(C_BORDER, 1))
            p.drawRoundedRect(rect, 8, 8)

            # Giá trị node
            text_color = C_BG if bg != C_SURFACE else C_TEXT
            p.setPen(QPen(text_color))
            p.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(node["val"]))

            # Label "HEAD" cho node đầu tiên
            if self._nodes and nid == self._nodes[0]["id"]:
                p.setFont(QFont("Segoe UI", 8))
                p.setPen(QPen(C_PURPLE))
                head_rect = QRect(rect.x(), rect.y() - 18, rect.width(), 16)
                p.drawText(head_rect, Qt.AlignmentFlag.AlignCenter, "HEAD")

        # ── Thông báo ─────────────────────────────────────────────────────────
        if self._message:
            p.setFont(QFont("Segoe UI", 10))
            p.setPen(QPen(C_TEXT))
            msg_rect = QRect(8, self.height() - 28, self.width() - 16, 24)
            p.drawText(msg_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       self._message)

    def _draw_arrowhead(self, p: QPainter, fx: int, fy: int, tx: int, ty: int) -> None:
        """Vẽ đầu mũi tên nhỏ tại điểm (tx, ty)."""
        angle = math.atan2(ty - fy, tx - fx)
        size  = 8
        a1 = angle + math.pi * 5 / 6
        a2 = angle - math.pi * 5 / 6

        path = QPainterPath()
        path.moveTo(tx, ty)
        path.lineTo(tx + size * math.cos(a1), ty + size * math.sin(a1))
        path.lineTo(tx + size * math.cos(a2), ty + size * math.sin(a2))
        path.closeSubpath()

        p.setBrush(QBrush(C_TEXT))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)
