"""
modules/visualizer/tracers.py — Tracer Widgets (PyQt6)
=======================================================
Mỗi Tracer là một QWidget độc lập, nhận dữ liệu qua slot và tự vẽ lại.
Giống kiến trúc algorithm-visualizer.org nhưng native PyQt6.

Tracers có sẵn:
  - ChartTracer    : Thanh bar dọc (dùng cho Sorting)
  - Array1DTracer  : Ô vuông hàng ngang (dùng cho Array, Search)
  - LogTracer      : Text log cuộn (dùng cho mọi algo)
  - GridTracer     : Lưới 2D click được (dùng cho Pathfinding)
  - CodeTracer     : Code với highlight dòng real-time
"""
from __future__ import annotations
import math
from typing import Any

from PyQt6.QtCore import Qt, QRect, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPen, QBrush,
    QPainterPath, QFontMetrics, QTextCursor,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QSizePolicy, QScrollArea,
)

# ── Palette ────────────────────────────────────────────────────────────────────
C = {
    "bg":       QColor("#1e1e2e"),
    "surface":  QColor("#313244"),
    "border":   QColor("#45475a"),
    "text":     QColor("#cdd6f4"),
    "subtext":  QColor("#6c7086"),
    "red":      QColor("#f38ba8"),
    "yellow":   QColor("#f9e2af"),
    "green":    QColor("#a6e3a1"),
    "blue":     QColor("#89b4fa"),
    "purple":   QColor("#cba6f7"),
    "teal":     QColor("#94e2d5"),
    "pink":     QColor("#f5c2e7"),
    "orange":   QColor("#fab387"),
    "mauve":    QColor("#cba6f7"),
}

_TITLE_STYLE = (
    "background:#313244; color:#cba6f7; font-weight:bold; "
    "font-size:11px; padding:4px 10px; border-radius:4px 4px 0 0;"
)
_CANVAS_STYLE = "background:#1e1e2e; border:1px solid #45475a; border-radius:0 0 6px 6px;"


def _make_tracer_frame(title: str, canvas: QWidget) -> QWidget:
    """Bọc canvas trong một frame có tiêu đề compact (label chỉ rộng bằng text)."""
    frame = QWidget()
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    # Header bar: nền tối, label trái + stretch phải
    header = QWidget()
    header.setStyleSheet(
        "background:#181825; border-radius:6px 6px 0 0;"
        "border-bottom:1px solid #313244;"
    )
    header.setFixedHeight(28)
    h_layout = QHBoxLayout(header)
    h_layout.setContentsMargins(10, 0, 10, 0)
    h_layout.setSpacing(0)

    lbl = QLabel(title)
    lbl.setStyleSheet(
        "background:#313244; color:#cba6f7; font-weight:bold;"
        "font-size:10px; padding:3px 10px; border-radius:4px;"
    )
    lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    h_layout.addWidget(lbl)
    h_layout.addStretch()

    layout.addWidget(header)
    canvas.setStyleSheet(_CANVAS_STYLE)
    layout.addWidget(canvas)
    return frame


# ══════════════════════════════════════════════════════════════════════════════
# ChartTracer  —  Bar chart dọc
# ══════════════════════════════════════════════════════════════════════════════
class ChartTracerCanvas(QWidget):
    """Canvas vẽ bar chart."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(180)
        self._data:      list[int|float] = []
        self._selected:  set[int] = set()   # màu xanh
        self._patched:   set[int] = set()   # màu đỏ (đang hoán đổi)
        self._sorted:    set[int] = set()   # màu green
        self._pivot_idx: int | None = None  # màu cam (QuickSort pivot)

    def set_state(self, data: list, selected: list = None,
                  patched: list = None, sorted_: list = None,
                  pivot: int = None):
        self._data     = list(data)
        self._selected = set(selected or [])
        self._patched  = set(patched  or [])
        self._sorted   = set(sorted_  or [])
        self._pivot_idx = pivot
        self.update()

    def reset(self):
        self._data = []; self._selected.clear()
        self._patched.clear(); self._sorted.clear()
        self._pivot_idx = None
        self.update()

    def paintEvent(self, _):
        if not self._data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        n   = len(self._data)
        w   = self.width()
        h   = self.height() - 28   # bottom margin for labels
        max_val = max(self._data) or 1
        bar_w = max(2, (w - n - 4) // n)
        gap   = max(1, (w - bar_w * n) // (n + 1))
        start_x = gap

        for i, val in enumerate(self._data):
            bh = int((val / max_val) * (h - 10))
            bx = start_x + i * (bar_w + gap)
            by = h - bh

            if i == self._pivot_idx:
                color = C["orange"]
            elif i in self._patched:
                color = C["red"]
            elif i in self._selected:
                color = C["blue"]
            elif i in self._sorted:
                color = C["green"]
            else:
                color = C["surface"]

            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(bx, by, bar_w, bh, 2, 2)

            # Index label
            if bar_w > 10:
                p.setPen(QPen(C["subtext"]))
                p.setFont(QFont("Consolas", max(7, bar_w // 4)))
                p.drawText(QRect(bx, h + 4, bar_w, 18),
                           Qt.AlignmentFlag.AlignCenter, str(i))


class ChartTracer(QWidget):
    def __init__(self, title: str = "Chart", parent=None):
        super().__init__(parent)
        self._canvas = ChartTracerCanvas()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_make_tracer_frame(f"📊 {title}", self._canvas))

    @property
    def canvas(self) -> ChartTracerCanvas:
        return self._canvas

    def set_state(self, **kwargs):
        self._canvas.set_state(**kwargs)

    def reset(self):
        self._canvas.reset()


# ══════════════════════════════════════════════════════════════════════════════
# Array1DTracer  —  Ô vuông hàng ngang
# ══════════════════════════════════════════════════════════════════════════════
class Array1DTracerCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(90)
        self._data:     list = []
        self._selected: set[int] = set()
        self._patched:  set[int] = set()
        self._sorted:   set[int] = set()

    def set_state(self, data: list, selected: list = None,
                  patched: list = None, sorted_: list = None):
        self._data    = list(data)
        self._selected = set(selected or [])
        self._patched  = set(patched  or [])
        self._sorted   = set(sorted_  or [])
        self.update()

    def reset(self):
        self._data = []; self._selected.clear()
        self._patched.clear(); self._sorted.clear()
        self.update()

    def paintEvent(self, _):
        if not self._data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        n = len(self._data)
        cell_w = min(64, max(28, (self.width() - 20) // n))
        cell_h = 46
        start_x = (self.width() - cell_w * n) // 2
        y = (self.height() - cell_h - 18) // 2

        for i, val in enumerate(self._data):
            x = start_x + i * cell_w
            if i in self._patched:
                bg = C["red"]
            elif i in self._selected:
                bg = C["blue"]
            elif i in self._sorted:
                bg = C["green"]
            else:
                bg = C["surface"]

            p.setBrush(QBrush(bg))
            p.setPen(QPen(C["border"], 1))
            p.drawRoundedRect(x + 1, y, cell_w - 2, cell_h, 6, 6)

            fg = C["bg"] if bg != C["surface"] else C["text"]
            p.setPen(QPen(fg))
            p.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
            p.drawText(QRect(x + 1, y, cell_w - 2, cell_h),
                       Qt.AlignmentFlag.AlignCenter, str(val))

            # Index
            p.setPen(QPen(C["subtext"]))
            p.setFont(QFont("Consolas", 8))
            p.drawText(QRect(x + 1, y + cell_h + 2, cell_w - 2, 14),
                       Qt.AlignmentFlag.AlignCenter, str(i))


class Array1DTracer(QWidget):
    def __init__(self, title: str = "Array", parent=None):
        super().__init__(parent)
        self._canvas = Array1DTracerCanvas()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_make_tracer_frame(f"🔢 {title}", self._canvas))

    @property
    def canvas(self) -> Array1DTracerCanvas:
        return self._canvas

    def set_state(self, **kwargs):
        self._canvas.set_state(**kwargs)

    def reset(self):
        self._canvas.reset()


# ══════════════════════════════════════════════════════════════════════════════
# LogTracer  —  Text log cuộn
# ══════════════════════════════════════════════════════════════════════════════
class LogTracer(QWidget):
    def __init__(self, title: str = "Log", parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        lbl = QLabel(f"📝 {title}")
        lbl.setStyleSheet(_TITLE_STYLE)
        layout.addWidget(lbl)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(QFont("Consolas", 9))
        self._text.setStyleSheet(
            "background:#1e1e2e; color:#a6e3a1; border:1px solid #45475a; "
            "border-radius:0 0 6px 6px; padding:6px;"
        )
        layout.addWidget(self._text)

    def log(self, message: str):
        self._text.append(message)
        # Auto-scroll xuống dưới
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._text.setTextCursor(cursor)

    def reset(self):
        self._text.clear()


# ══════════════════════════════════════════════════════════════════════════════
# GridTracer  —  Lưới 2D click được (Pathfinding)
# ══════════════════════════════════════════════════════════════════════════════
class GridTracerCanvas(QWidget):
    cell_clicked = pyqtSignal(int, int)   # row, col

    COLORS = {
        "empty":    QColor("#313244"),
        "wall":     QColor("#45475a"),
        "start":    QColor("#a6e3a1"),
        "end":      QColor("#f38ba8"),
        "visited":  QColor("#89b4fa").darker(160),
        "frontier": QColor("#94e2d5"),
        "path":     QColor("#f9e2af"),
        "current":  QColor("#cba6f7"),
    }

    def __init__(self, rows: int = 18, cols: int = 32, parent=None):
        super().__init__(parent)
        self.rows = rows
        self.cols = cols
        self.setMinimumHeight(180)
        self._grid: list[list[str]] = [["empty"]*cols for _ in range(rows)]
        self._grid[0][0]             = "start"
        self._grid[rows-1][cols-1]   = "end"
        self._overlay: dict[tuple, str] = {}  # (r,c) → color_key
        self._dragging = False
        self.setMouseTracking(True)

    def update_from_frame(self, payload: dict):
        self._overlay.clear()
        for pos in payload.get("visited", set()):
            self._overlay[tuple(pos) if isinstance(pos, list) else pos] = "visited"
        for pos in payload.get("frontier", set()):
            self._overlay[tuple(pos) if isinstance(pos, list) else pos] = "frontier"
        if payload.get("current"):
            self._overlay[tuple(payload["current"])] = "current"
        if payload.get("path"):
            for pos in payload["path"]:
                self._overlay[tuple(pos) if isinstance(pos, list) else pos] = "path"
        self.update()

    def reset_overlay(self):
        self._overlay.clear()
        self.update()

    def _cell_size(self) -> int:
        return max(4, min((self.width()-4)//self.cols, (self.height()-4)//self.rows))

    def _offset(self) -> tuple[int,int]:
        cs = self._cell_size()
        return (self.width()-cs*self.cols)//2, (self.height()-cs*self.rows)//2

    def _cell_rect(self, r: int, c: int) -> QRect:
        cs = self._cell_size()
        ox, oy = self._offset()
        return QRect(ox+c*cs+1, oy+r*cs+1, cs-2, cs-2)

    def _pos_to_cell(self, x: int, y: int) -> tuple[int,int]|None:
        cs = self._cell_size()
        ox, oy = self._offset()
        c, r = (x-ox)//cs, (y-oy)//cs
        return (r,c) if 0<=r<self.rows and 0<=c<self.cols else None

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for r in range(self.rows):
            for c in range(self.cols):
                rect = self._cell_rect(r, c)
                key = self._overlay.get((r,c), self._grid[r][c])
                color = self.COLORS.get(key, self.COLORS["empty"])
                p.setBrush(QBrush(color))
                p.setPen(QPen(C["border"], 0.5))
                p.drawRect(rect)
                if self._grid[r][c] in ("start","end"):
                    p.setPen(QPen(C["bg"]))
                    p.setFont(QFont("Segoe UI", max(6, self._cell_size()//3), QFont.Weight.Bold))
                    p.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                               "S" if self._grid[r][c]=="start" else "E")

    def mousePressEvent(self, e):
        self._dragging = True
        cell = self._pos_to_cell(int(e.position().x()), int(e.position().y()))
        if cell: self.cell_clicked.emit(*cell)

    def mouseMoveEvent(self, e):
        if self._dragging:
            cell = self._pos_to_cell(int(e.position().x()), int(e.position().y()))
            if cell: self.cell_clicked.emit(*cell)

    def mouseReleaseEvent(self, e):
        self._dragging = False


class GridTracer(QWidget):
    cell_clicked = pyqtSignal(int, int)

    def __init__(self, title: str = "Grid", rows: int = 18, cols: int = 32, parent=None):
        super().__init__(parent)
        self._canvas = GridTracerCanvas(rows, cols)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_make_tracer_frame(f"🗺️ {title}", self._canvas))
        self._canvas.cell_clicked.connect(self.cell_clicked)

    @property
    def canvas(self) -> GridTracerCanvas:
        return self._canvas

    def update_from_frame(self, payload: dict):
        self._canvas.update_from_frame(payload)

    def reset_overlay(self):
        self._canvas.reset_overlay()


# ══════════════════════════════════════════════════════════════════════════════
# CodeTracer  —  Code + Line Highlight real-time
# ══════════════════════════════════════════════════════════════════════════════
class CodeTracer(QWidget):
    def __init__(self, title: str = "Code", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        lbl = QLabel(f"💻 {title}")
        lbl.setStyleSheet(_TITLE_STYLE)
        layout.addWidget(lbl)

        self._editor = QTextEdit()
        self._editor.setReadOnly(True)
        self._editor.setFont(QFont("Consolas", 10))
        self._editor.setStyleSheet(
            "background:#181825; color:#cdd6f4; border:1px solid #45475a; "
            "border-radius:0 0 6px 6px; padding:6px; selection-background-color:#45475a;"
        )
        layout.addWidget(self._editor)
        self._lines: list[str] = []

    def set_code(self, code: str):
        """Nạp code ban đầu (gọi 1 lần khi chọn algo)."""
        self._lines = code.splitlines()
        self._editor.setPlainText(code)

    def highlight_line(self, line_no: int):
        """Highlight dòng `line_no` (0-based). Gọi từ Main Thread."""
        if not self._lines:
            return
        # Tô màu từng dòng bằng HTML
        html_lines = []
        for i, line in enumerate(self._lines):
            escaped = (line
                       .replace("&", "&amp;")
                       .replace("<", "&lt;")
                       .replace(">", "&gt;")
                       .replace(" ", "&nbsp;"))
            if i == line_no:
                html_lines.append(
                    f'<span style="background:#313244;color:#f9e2af;">'
                    f'<b>{escaped}</b></span>'
                )
            else:
                html_lines.append(f'<span style="color:#cdd6f4;">{escaped}</span>')

        self._editor.setHtml(
            '<pre style="margin:0;font-family:Consolas,monospace;font-size:10pt;">'
            + "<br>".join(html_lines) + "</pre>"
        )
        # Scroll đến dòng highlight
        cursor = self._editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(line_no):
            cursor.movePosition(QTextCursor.MoveOperation.Down)
        self._editor.setTextCursor(cursor)
        self._editor.ensureCursorVisible()

    def reset(self):
        if self._lines:
            self._editor.setPlainText("\n".join(self._lines))


# ══════════════════════════════════════════════════════════════════════════════
# LinkedListTracer  —  Linked List Canvas (visualgo-style)
# ══════════════════════════════════════════════════════════════════════════════
class LinkedListTracerCanvas(QWidget):
    """
    Vẽ Linked List với phong cách visualgo.net.
    Kích thước node tự động thu nhỏ khi nhiều node để luôn vừa màn hình.
    """

    # Kích thước tối đa (default)
    MAX_NODE_W = 76    # data(52) + ptr(24)
    MAX_NODE_H = 50
    MAX_ARROW_W = 38
    MIN_NODE_W = 42
    MIN_NODE_H = 36
    MIN_ARROW_W = 18

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._nodes:     list[dict] = []
        self._highlight: set[str]   = set()
        self._active:    str | None = None
        self._arrows:    list       = []
        self._broken_at: str | None = None
        self._message:   str        = ""
        self._found:     str | None = None
        self._new_node:  str | None = None

        # Layout computed each paintEvent
        self._nw = self.MAX_NODE_W
        self._nh = self.MAX_NODE_H
        self._aw = self.MAX_ARROW_W

    def on_frame_received(self, payload: dict) -> None:
        if payload.get("mode") != "linked_list":
            return
        self._nodes     = payload.get("nodes",    [])
        self._highlight = set(payload.get("highlight", set()))
        self._active    = payload.get("active")
        self._arrows    = payload.get("arrows",   [])
        self._broken_at = payload.get("broken_at")
        self._message   = payload.get("message",  "")
        self._found     = payload.get("found")
        self._new_node  = payload.get("new_node")
        self.update()

    def reset(self) -> None:
        self._nodes = []; self._highlight = set()
        self._active = None; self._arrows = []
        self._broken_at = None; self._message = ""
        self._found = None; self._new_node = None
        self.update()

    # ── Adaptive layout ───────────────────────────────────────────────────────

    def _compute_layout(self) -> dict[str, tuple[int, int]]:
        """Tính kích thước node theo số node và chiều rộng canvas, trả về positions."""
        n = len(self._nodes)
        if n == 0:
            self._nw, self._nh, self._aw = self.MAX_NODE_W, self.MAX_NODE_H, self.MAX_ARROW_W
            return {}

        pad = 60   # padding trái-phải + chỗ NULL
        available = max(200, self.width() - pad)
        ideal_total = n * self.MAX_NODE_W + (n - 1) * self.MAX_ARROW_W

        if ideal_total <= available:
            nw, aw = self.MAX_NODE_W, self.MAX_ARROW_W
        else:
            ratio = available / ideal_total
            nw = max(self.MIN_NODE_W, int(self.MAX_NODE_W * ratio))
            aw = max(self.MIN_ARROW_W, int(self.MAX_ARROW_W * ratio))

        nh = self.MAX_NODE_H if nw >= 56 else self.MIN_NODE_H
        self._nw, self._nh, self._aw = nw, nh, aw

        total_w = n * nw + (n - 1) * aw
        sx = max(16, (self.width() - total_w - 50) // 2)
        sy = (self.height() - nh) // 2 - 14
        return {nd["id"]: (sx + i * (nw + aw), sy) for i, nd in enumerate(self._nodes)}

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), C["bg"])

        if not self._nodes:
            self._draw_empty(p)
            return

        pos = self._compute_layout()

        self._draw_arrows(p, pos)
        self._draw_null(p, pos)
        for nd in self._nodes:
            self._draw_node(p, nd, pos)
        self._draw_labels(p, pos)
        self._draw_message(p)

    def _draw_empty(self, p: QPainter) -> None:
        p.setPen(QPen(C["subtext"]))
        p.setFont(QFont("Segoe UI", 11))
        r = self.rect().adjusted(0, 0, 0, -30)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter,
                   "📭  Danh sách rỗng — nhập giá trị và nhấn thao tác")
        self._draw_message(p)

    def _draw_node(self, p: QPainter, nd: dict, pos: dict) -> None:
        nid = nd["id"]
        if nid not in pos:
            return
        x, y = pos[nid]
        nw, nh = self._nw, self._nh

        if nid == self._found:        bg = C["green"]
        elif nid == self._active:     bg = C["red"]
        elif nid == self._new_node:   bg = C["purple"]
        elif nid in self._highlight:  bg = C["yellow"]
        else:                         bg = C["surface"]

        text_c = C["bg"] if bg != C["surface"] else C["text"]

        # Node box
        r = 5 if nw < 56 else 7
        p.setBrush(QBrush(bg))
        p.setPen(QPen(C["border"], 1.5))
        p.drawRoundedRect(QRect(x, y, nw, nh), r, r)

        # divider data | ptr  (data = 68% width)
        dw = max(26, int(nw * 0.68))
        pw = nw - dw
        div_x = x + dw
        p.setPen(QPen(C["border"], 1))
        p.drawLine(div_x, y + 5, div_x, y + nh - 5)

        # Value
        font_sz = 13 if nw >= 56 else 9
        p.setPen(QPen(text_c))
        p.setFont(QFont("Consolas", font_sz, QFont.Weight.Bold))
        p.drawText(QRect(x, y, dw, nh), Qt.AlignmentFlag.AlignCenter, str(nd["val"]))

        # Ptr arrow symbol
        ptr_c = C["subtext"] if bg == C["surface"] else text_c
        p.setPen(QPen(ptr_c))
        p.setFont(QFont("Consolas", max(7, font_sz - 4)))
        p.drawText(QRect(div_x, y, pw, nh), Qt.AlignmentFlag.AlignCenter, "→")

        # Index label below
        idx = next((i for i, n in enumerate(self._nodes) if n["id"] == nid), None)
        if idx is not None and nw >= 40:
            p.setPen(QPen(C["subtext"]))
            p.setFont(QFont("Consolas", 7))
            p.drawText(QRect(x, y + nh + 2, nw, 12),
                       Qt.AlignmentFlag.AlignCenter, f"[{idx}]")

    def _draw_arrows(self, p: QPainter, pos: dict) -> None:
        nw, nh = self._nw, self._nh
        for from_id, to_id in self._arrows:
            if from_id not in pos or to_id not in pos:
                continue
            fx, fy = pos[from_id]
            tx, ty = pos[to_id]
            sx = fx + nw;  sy = fy + nh // 2
            ex = tx;        ey = ty + nh // 2

            if self._broken_at == from_id:
                mid_x = (sx + ex) // 2
                p.setPen(QPen(C["red"], 2, Qt.PenStyle.DashLine))
                p.drawLine(sx, sy, mid_x, sy)
                p.setPen(QPen(C["red"], 2.5))
                p.drawLine(mid_x - 5, sy - 5, mid_x + 5, sy + 5)
                p.drawLine(mid_x - 5, sy + 5, mid_x + 5, sy - 5)
            else:
                p.setPen(QPen(C["blue"], 2))
                p.drawLine(sx, sy, ex, ey)
                self._draw_arrowhead(p, sx, sy, ex, ey, C["blue"])

    def _draw_null(self, p: QPainter, pos: dict) -> None:
        if not self._nodes:
            return
        last = self._nodes[-1]
        if last["id"] not in pos:
            return
        lx, ly = pos[last["id"]]
        nw, nh = self._nw, self._nh
        null_sx = lx + nw
        null_sy = ly + nh // 2

        if self._broken_at == last["id"]:
            p.setPen(QPen(C["red"], 2, Qt.PenStyle.DashLine))
            p.drawLine(null_sx, null_sy, null_sx + 14, null_sy)
        else:
            null_ex = null_sx + 24
            p.setPen(QPen(C["subtext"], 2))
            p.drawLine(null_sx, null_sy, null_ex, null_sy)
            p.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            p.setPen(QPen(C["subtext"]))
            p.drawText(QRect(null_ex + 2, null_sy - 9, 34, 18),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "NULL")

    def _draw_labels(self, p: QPainter, pos: dict) -> None:
        if not self._nodes:
            return
        nw, nh = self._nw, self._nh
        dw = max(26, int(nw * 0.68))
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))

        head_id = self._nodes[0]["id"]
        tail_id = self._nodes[-1]["id"]

        if head_id in pos:
            hx, hy = pos[head_id]
            p.setPen(QPen(C["purple"]))
            p.drawText(QRect(hx, hy - 18, dw, 14), Qt.AlignmentFlag.AlignCenter, "HEAD")

        if tail_id in pos and tail_id != head_id:
            tx, ty = pos[tail_id]
            p.setPen(QPen(C["teal"]))
            p.drawText(QRect(tx, ty - 18, dw, 14), Qt.AlignmentFlag.AlignCenter, "TAIL")

    def _draw_message(self, p: QPainter) -> None:
        if not self._message:
            return
        bar_h = 30
        bar_y = self.height() - bar_h
        p.fillRect(QRect(0, bar_y, self.width(), bar_h), QColor("#181825"))
        p.setPen(QPen(C["text"]))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(QRect(12, bar_y, self.width() - 24, bar_h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self._message)

    def _draw_arrowhead(self, p: QPainter, fx, fy, tx, ty, color: QColor) -> None:
        angle = math.atan2(ty - fy, tx - fx)
        size  = 8
        a1 = angle + math.pi * 5 / 6
        a2 = angle - math.pi * 5 / 6
        path = QPainterPath()
        path.moveTo(tx, ty)
        path.lineTo(tx + size * math.cos(a1), ty + size * math.sin(a1))
        path.lineTo(tx + size * math.cos(a2), ty + size * math.sin(a2))
        path.closeSubpath()
        p.setBrush(QBrush(color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)



class LinkedListTracer(QWidget):
    """Tracer bọc LinkedListTracerCanvas trong frame tiêu đề."""

    def __init__(self, title: str = "Linked List", parent=None):
        super().__init__(parent)
        self._canvas = LinkedListTracerCanvas()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_make_tracer_frame(f"🔗 {title}", self._canvas))

    @property
    def canvas(self) -> LinkedListTracerCanvas:
        return self._canvas

    def on_frame_received(self, payload: dict) -> None:
        self._canvas.on_frame_received(payload)

    def show_initial(self, data: list[int]) -> None:
        """
        Hiển thị trạng thái ban đầu của Linked List từ `data`
        (gọi ngay khi chọn thuật toán, trước khi nhấn Run).
        Không có highlight/active — chỉ hiện cấu trúc list.
        """
        if not data:
            self._canvas.reset()
            return

        # Xây dựng snapshot nodes + arrows từ data
        import uuid
        ids = [str(uuid.uuid4())[:8] for _ in data]
        nodes  = [{"val": v, "id": ids[i]} for i, v in enumerate(data)]
        arrows = [(ids[i], ids[i + 1]) for i in range(len(data) - 1)]

        self._canvas.on_frame_received({
            "mode":      "linked_list",
            "nodes":     nodes,
            "highlight": set(),
            "active":    None,
            "arrows":    arrows,
            "broken_at": None,
            "found":     None,
            "new_node":  None,
            "message":   "▶  Nhấn Run để xem hoạt ảnh thao tác...",
        })

    def reset(self) -> None:
        self._canvas.reset()
