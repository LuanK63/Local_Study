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

from PyQt6.QtCore import Qt, QRect, QRectF, QPointF, pyqtSignal, QTimer, QParallelAnimationGroup, QEasingCurve, QPropertyAnimation
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPen, QBrush,
    QPainterPath, QFontMetrics, QTextCursor, QPolygonF,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QTextBrowser,
    QSizePolicy, QScrollArea, QGraphicsView, QGraphicsScene, QGraphicsObject, QGraphicsItem,
)

# ── Animation Manager ─────────────────────────────────────────────────────────
class AnimationManager(QTimer):
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = AnimationManager()
        return cls._instance

    def __init__(self):
        super().__init__()
        self.setInterval(16)  # ~60fps
        self.timeout.connect(self._on_tick)
        self._canvases = set()

    def register_canvas(self, canvas):
        self._canvases.add(canvas)
        if not self.isActive():
            self.start()

    def unregister_canvas(self, canvas):
        self._canvases.discard(canvas)
        if not self._canvases and self.isActive():
            self.stop()

    def _on_tick(self):
        active = False
        for canvas in list(self._canvases):
            try:
                # If animate_step returns True, it means color transitions are still in progress
                if canvas.animate_step():
                    active = True
            except Exception:
                pass


def interpolate_color(c1: QColor, c2: QColor, factor: float) -> QColor:
    r = c1.red() + (c2.red() - c1.red()) * factor
    g = c1.green() + (c2.green() - c1.green()) * factor
    b = c1.blue() + (c2.blue() - c1.blue()) * factor
    a = c1.alpha() + (c2.alpha() - c1.alpha()) * factor
    return QColor(int(r), int(g), int(b), int(a))


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
_CANVAS_STYLE = "#tracer_canvas { background:#1e1e2e; border:1px solid #45475a; border-radius:0 0 6px 6px; }"


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
    canvas.setObjectName("tracer_canvas")
    canvas.setStyleSheet(_CANVAS_STYLE)
    layout.addWidget(canvas)
    return frame


# ══════════════════════════════════════════════════════════════════════════════
# ChartTracer  —  Bar chart dọc
# ══════════════════════════════════════════════════════════════════════════════
class ChartTracerCanvas(QWidget):
    """Canvas vẽ bar chart với Animation Manager dùng chung."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(240)  # Tăng chiều cao vùng biểu đồ
        self._data:      list[int|float] = []
        self._compare_indices: set[int] = set()
        self._swap_indices:    set[int] = set()
        self._sorted_indices:  set[int] = set()
        self._pivot_idx:       int | None = None
        
        self._current_colors:  list[QColor] = []
        self._target_colors:   list[QColor] = []
        AnimationManager.instance().register_canvas(self)

    def destroy(self, destroyWindow=True, destroySubWindows=True):
        AnimationManager.instance().unregister_canvas(self)
        super().destroy(destroyWindow, destroySubWindows)

    def set_state(self, data: list, compare_indices: list = None,
                  swap_indices: list = None, sorted_indices: list = None,
                  pivot: int = None, **kwargs):
        # Backward compatibility
        selected = kwargs.get("selected", None)
        patched = kwargs.get("patched", None)
        sorted_ = kwargs.get("sorted", None)
        
        self._data = list(data)
        n = len(self._data)
        
        self._compare_indices = set(compare_indices if compare_indices is not None else (selected or []))
        self._swap_indices = set(swap_indices if swap_indices is not None else (patched or []))
        self._sorted_indices = set(sorted_indices if sorted_indices is not None else (sorted_ or []))
        self._pivot_idx = pivot

        if len(self._current_colors) != n:
            self._current_colors = [C["surface"]] * n
            self._target_colors = [C["surface"]] * n
        else:
            self._target_colors = [C["surface"]] * n

        for i in range(n):
            if i == self._pivot_idx:
                self._target_colors[i] = C["purple"]  # Pivot màu tím
            elif i in self._swap_indices:
                self._target_colors[i] = C["orange"]  # Đang hoán đổi màu cam
            elif i in self._compare_indices:
                self._target_colors[i] = C["yellow"]  # Đang so sánh màu vàng
            elif i in self._sorted_indices:
                self._target_colors[i] = C["green"]   # Đã đúng vị trí cố định
            else:
                self._target_colors[i] = C["surface"]

        AnimationManager.instance().register_canvas(self)
        self.update()

    def reset(self):
        self._data = []
        self._compare_indices.clear()
        self._swap_indices.clear()
        self._sorted_indices.clear()
        self._pivot_idx = None
        self._current_colors.clear()
        self._target_colors.clear()
        AnimationManager.instance().unregister_canvas(self)
        self.update()

    def animate_step(self) -> bool:
        n = len(self._data)
        if n == 0 or len(self._current_colors) != n:
            return False

        changed = False
        factor = 0.2
        for i in range(n):
            curr = self._current_colors[i]
            tgt = self._target_colors[i]
            if curr != tgt:
                next_c = interpolate_color(curr, tgt, factor)
                if (abs(next_c.red() - tgt.red()) < 2 and
                    abs(next_c.green() - tgt.green()) < 2 and
                    abs(next_c.blue() - tgt.blue()) < 2):
                    self._current_colors[i] = tgt
                else:
                    self._current_colors[i] = next_c
                    changed = True

        if changed:
            self.update()
        return changed

    def paintEvent(self, _):
        if not self._data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        n   = len(self._data)
        w   = self.width()
        h   = self.height() - 32
        max_val = max(self._data) or 1
        
        bar_w = max(2, (w - n - 4) // n)
        gap   = max(1, (w - bar_w * n) // (n + 1))
        
        # Center the bars
        total_bars_width = n * bar_w + (n - 1) * gap
        start_x = max(gap, (w - total_bars_width) // 2)

        for i, val in enumerate(self._data):
            bh = int((val / max_val) * (h - 26))  # Leave room on top for values
            bx = start_x + i * (bar_w + gap)
            by = h - bh

            color = self._current_colors[i] if i < len(self._current_colors) else C["surface"]

            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(bx, by, bar_w, bh, 2, 2)

            # Draw value labels directly on top of each bar
            if bar_w >= 14:
                p.setPen(QPen(C["text"]))
                p.setFont(QFont("Consolas", max(7, min(9, bar_w // 2))))
                p.drawText(QRect(bx - 4, by - 16, bar_w + 8, 14),
                           Qt.AlignmentFlag.AlignCenter, str(val))
            elif bar_w >= 8:
                if i in self._compare_indices or i in self._swap_indices or i == self._pivot_idx:
                    p.setPen(QPen(C["text"]))
                    p.setFont(QFont("Consolas", 7))
                    p.drawText(QRect(bx - 6, by - 14, bar_w + 12, 12),
                               Qt.AlignmentFlag.AlignCenter, str(val))

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
        self._compare_indices: set[int] = set()
        self._swap_indices:    set[int] = set()
        self._sorted_indices:  set[int] = set()
        self._visited_indices: set[int] = set()
        
        self._current_colors:  list[QColor] = []
        self._target_colors:   list[QColor] = []
        AnimationManager.instance().register_canvas(self)

    def destroy(self, destroyWindow=True, destroySubWindows=True):
        AnimationManager.instance().unregister_canvas(self)
        super().destroy(destroyWindow, destroySubWindows)

    def set_state(self, data: list, compare_indices: list = None,
                  swap_indices: list = None, sorted_indices: list = None,
                  visited_indices: list = None, **kwargs):
        # Backward compatibility
        selected = kwargs.get("selected", None)
        patched = kwargs.get("patched", None)
        sorted_ = kwargs.get("sorted", None)
        
        self._data    = list(data)
        n = len(self._data)
        
        self._compare_indices = set(compare_indices if compare_indices is not None else (selected or []))
        self._swap_indices = set(swap_indices if swap_indices is not None else (patched or []))
        self._sorted_indices = set(sorted_indices if sorted_indices is not None else (sorted_ or []))
        self._visited_indices = set(visited_indices or [])

        if len(self._current_colors) != n:
            self._current_colors = [C["surface"]] * n
            self._target_colors = [C["surface"]] * n
        else:
            self._target_colors = [C["surface"]] * n

        for i in range(n):
            if i in self._sorted_indices:
                self._target_colors[i] = C["green"]
            elif i in self._swap_indices:
                self._target_colors[i] = C["orange"]
            elif i in self._compare_indices:
                self._target_colors[i] = C["yellow"]
            elif i in self._visited_indices:
                self._target_colors[i] = C["red"]
            else:
                self._target_colors[i] = C["surface"]

        AnimationManager.instance().register_canvas(self)
        self.update()

    def reset(self):
        self._data = []
        self._compare_indices.clear()
        self._swap_indices.clear()
        self._sorted_indices.clear()
        self._visited_indices.clear()
        self._current_colors.clear()
        self._target_colors.clear()
        AnimationManager.instance().unregister_canvas(self)
        self.update()

    def animate_step(self) -> bool:
        n = len(self._data)
        if n == 0 or len(self._current_colors) != n:
            return False

        changed = False
        factor = 0.2
        for i in range(n):
            curr = self._current_colors[i]
            tgt = self._target_colors[i]
            if curr != tgt:
                next_c = interpolate_color(curr, tgt, factor)
                if (abs(next_c.red() - tgt.red()) < 2 and
                    abs(next_c.green() - tgt.green()) < 2 and
                    abs(next_c.blue() - tgt.blue()) < 2):
                    self._current_colors[i] = tgt
                else:
                    self._current_colors[i] = next_c
                    changed = True

        if changed:
            self.update()
        return changed

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
            
            bg = self._current_colors[i] if i < len(self._current_colors) else C["surface"]

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
        self.setMinimumHeight(100)
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
            "background:#1e1e2e; border:1px solid #45475a; "
            "border-radius:0 0 6px 6px; padding:6px;"
        )
        layout.addWidget(self._text)
        self._log_history: list[str] = []

    def log(self, message: str):
        if not message.strip():
            return
        
        clean_msg = message.strip()
        emoji_prefix = ""
        # Auto-detect emojis if not present
        if not any(emoji in clean_msg for emoji in ("🔍", "🔄", "✅", "🎯", "❌", "⏹", "💡")):
            if "so sánh" in clean_msg.lower():
                emoji_prefix = "🔍 "
            elif "hoán đổi" in clean_msg.lower() or "dịch" in clean_msg.lower() or "đưa" in clean_msg.lower():
                emoji_prefix = "🔄 "
            elif "hoàn tất" in clean_msg.lower() or "hoàn thành" in clean_msg.lower() or "vị trí" in clean_msg.lower():
                emoji_prefix = "✅ "
            elif "tìm thấy" in clean_msg.lower():
                emoji_prefix = "🎯 "
            elif "lỗi" in clean_msg.lower():
                emoji_prefix = "❌ "
        
        formatted_msg = emoji_prefix + clean_msg
        self._log_history.append(formatted_msg)
        
        # Max limit 500 log lines to preserve CPU/memory
        if len(self._log_history) > 500:
            self._log_history.pop(0)
            
        html_parts = []
        for i, msg in enumerate(self._log_history):
            is_last = (i == len(self._log_history) - 1)
            escaped = (msg
                       .replace("&", "&amp;")
                       .replace("<", "&lt;")
                       .replace(">", "&gt;"))
            if is_last:
                html_parts.append(
                    f'<div style="background-color:#313244; color:#f9e2af; padding:2px 6px; '
                    f'margin:1px 0; border-radius:3px; font-weight:bold;">👉 {escaped}</div>'
                )
            else:
                html_parts.append(
                    f'<div style="color:#a6e3a1; padding:1px 6px; opacity:0.65;">{escaped}</div>'
                )
                
        self._text.setHtml("".join(html_parts))
        
        # Auto-scroll
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._text.setTextCursor(cursor)
        self._text.ensureCursorVisible()

    def reset(self):
        self._log_history.clear()
        self._text.clear()


# ══════════════════════════════════════════════════════════════════════════════
# GridTracer  —  Lưới 2D click được (Pathfinding)
# ══════════════════════════════════════════════════════════════════════════════
class GridTracerCanvas(QWidget):
    cell_clicked = pyqtSignal(int, int)   # row, col

    COLORS = {
        "empty":    QColor("#313244"),       # Unvisited
        "wall":     QColor("#45475a"),       # Wall
        "start":    QColor("#2e7d32"),       # Start Node: xanh lá đậm
        "end":      QColor("#d32f2f"),       # End Node: đỏ
        "visited":  QColor("#b4befe"),       # Visited Node: tím nhạt
        "frontier": QColor("#fab387"),       # Frontier: cam
        "path":     QColor("#a6e3a1"),       # Final Path: xanh lá sáng
        "current":  QColor("#f9e2af"),       # Current Node: vàng
    }

    def __init__(self, rows: int = 18, cols: int = 32, parent=None):
        super().__init__(parent)
        self.rows = rows
        self.cols = cols
        
        # Zoom / Scale configuration
        self._zoom_mode = "fit"          # "fit" | "fixed"
        self._scale_factor = 1.0         # 0.75 | 1.0 | 1.5 etc.
        
        self.setMinimumHeight(200)
        self._grid: list[list[str]] = [["empty"]*cols for _ in range(rows)]
        self._grid[0][0]             = "start"
        self._grid[rows-1][cols-1]   = "end"
        self._overlay: dict[tuple, str] = {}  # (r,c) → color_key
        self._dragging = False
        self.setMouseTracking(True)
        
        # Color buffers
        self._current_colors = [[self.COLORS["empty"] for _ in range(cols)] for _ in range(rows)]
        self._target_colors = [[self.COLORS["empty"] for _ in range(cols)] for _ in range(rows)]
        
        self._sync_all_target_colors()
        self._current_colors = [row[:] for row in self._target_colors]
        
        AnimationManager.instance().register_canvas(self)

    def destroy(self, destroyWindow=True, destroySubWindows=True):
        AnimationManager.instance().unregister_canvas(self)
        super().destroy(destroyWindow, destroySubWindows)

    def _sync_all_target_colors(self):
        for r in range(self.rows):
            for c in range(self.cols):
                key = self._overlay.get((r,c), self._grid[r][c])
                self._target_colors[r][c] = self.COLORS.get(key, self.COLORS["empty"])

    def update_from_frame(self, payload: dict):
        self._overlay.clear()
        
        # Priority mapping: Visited (lowest) -> Frontier -> Current -> Path (highest)
        visited = payload.get("visited_nodes") or payload.get("visited", set())
        for pos in visited:
            self._overlay[tuple(pos) if isinstance(pos, list) else pos] = "visited"
            
        frontier = payload.get("frontier_nodes") or payload.get("frontier", set())
        for pos in frontier:
            self._overlay[tuple(pos) if isinstance(pos, list) else pos] = "frontier"
            
        current = payload.get("current_node") or payload.get("current")
        if current:
            self._overlay[tuple(current)] = "current"
            
        path = payload.get("path_nodes") or payload.get("path")
        if path:
            for pos in path:
                self._overlay[tuple(pos) if isinstance(pos, list) else pos] = "path"
                
        self._sync_all_target_colors()
        AnimationManager.instance().register_canvas(self)
        self.update()

    def reset_overlay(self):
        self._overlay.clear()
        self._sync_all_target_colors()
        AnimationManager.instance().register_canvas(self)
        self.update()

    def animate_step(self) -> bool:
        changed = False
        factor = 0.2
        for r in range(self.rows):
            for c in range(self.cols):
                curr = self._current_colors[r][c]
                tgt = self._target_colors[r][c]
                if curr != tgt:
                    next_c = interpolate_color(curr, tgt, factor)
                    if (abs(next_c.red() - tgt.red()) < 2 and
                        abs(next_c.green() - tgt.green()) < 2 and
                        abs(next_c.blue() - tgt.blue()) < 2):
                        self._current_colors[r][c] = tgt
                    else:
                        self._current_colors[r][c] = next_c
                        changed = True
        if changed:
            self.update()
        return changed

    def set_zoom(self, mode: str, factor: float = 1.0):
        self._zoom_mode = mode
        self._scale_factor = factor
        
        # Find ancestor QScrollArea and adjust widgetResizable
        parent_widget = self.parent()
        while parent_widget:
            if isinstance(parent_widget, QScrollArea):
                parent_widget.setWidgetResizable(mode == "fit")
                break
            parent_widget = parent_widget.parent()
            
        self.update_size()
        self.update()

    def update_size(self):
        if self._zoom_mode == "fit":
            self.setMinimumSize(200, 200)
            self.setMaximumSize(16777215, 16777215)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        else:
            cs = self._cell_size()
            w = cs * self.cols + 6
            h = cs * self.rows + 6
            self.setFixedSize(w, h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()

    def _cell_size(self) -> int:
        if self._zoom_mode == "fit":
            p = self.parent()
            w = p.width() if p else 400
            h = p.height() if p else 300
            return max(6, min((w - 10) // self.cols, (h - 10) // self.rows))
        else:
            base_cell_size = 24
            return max(6, int(base_cell_size * self._scale_factor))

    def _offset(self) -> tuple[int,int]:
        cs = self._cell_size()
        if self._zoom_mode == "fit":
            return (self.width() - cs * self.cols) // 2, (self.height() - cs * self.rows) // 2
        else:
            return 2, 2

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
                color = self._current_colors[r][c]
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
        if cell:
            self._last_clicked_cell = cell
            self.cell_clicked.emit(*cell)

    def mouseMoveEvent(self, e):
        if self._dragging:
            cell = self._pos_to_cell(int(e.position().x()), int(e.position().y()))
            if cell and getattr(self, "_last_clicked_cell", None) != cell:
                self._last_clicked_cell = cell
                self.cell_clicked.emit(*cell)

    def mouseReleaseEvent(self, e):
        self._dragging = False
        self._last_clicked_cell = None


class GridTracer(QWidget):
    cell_clicked = pyqtSignal(int, int)

    def __init__(self, title: str = "Grid", rows: int = 18, cols: int = 32, parent=None):
        super().__init__(parent)
        self._canvas = GridTracerCanvas(rows, cols, parent=self)
        
        # Scroll Area wrapper
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidget(self._canvas)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll_area.setStyleSheet("QScrollArea { border: none; background: #1e1e2e; }")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_make_tracer_frame(f"🗺️ {title}", self._scroll_area))
        
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
        self._editor.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._editor)
        self._lines: list[str] = []

    def set_code(self, code: str):
        """Nạp code ban đầu (gọi 1 lần khi chọn algo)."""
        self._lines = code.splitlines()
        self.reset()

    def highlight_line(self, line_no: int):
        """Highlight dòng `line_no` (0-based). Gọi từ Main Thread."""
        if not self._lines:
            return
        
        html_lines = []
        for i, line in enumerate(self._lines):
            escaped = (line
                       .replace("&", "&amp;")
                       .replace("<", "&lt;")
                       .replace(">", "&gt;")
                       .replace(" ", "&nbsp;"))
            
            line_num_str = f'<span style="color:#6c7086; font-family:Consolas; font-size:10pt;">{i+1:2d} │ </span>'
            
            if i == line_no:
                html_lines.append(
                    f'<div style="background:#313244; color:#f9e2af; padding:1px 0; font-family:Consolas;">'
                    f'{line_num_str}<span style="color:#f9e2af; font-weight:bold;">👉 {escaped}</span>'
                    f'</div>'
                )
            else:
                html_lines.append(
                    f'<div style="padding:1px 0; font-family:Consolas;">'
                    f'{line_num_str}<span style="color:#cdd6f4;">&nbsp;&nbsp;{escaped}</span>'
                    f'</div>'
                )

        self._editor.setHtml(
            '<div style="font-family:Consolas,monospace; font-size:10pt; line-height:130%; white-space:nowrap;">'
            + "".join(html_lines) + '</div>'
        )
        
        # Scroll to highlighted line
        cursor = self._editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(line_no):
            cursor.movePosition(QTextCursor.MoveOperation.Down)
        self._editor.setTextCursor(cursor)
        self._editor.ensureCursorVisible()

    def reset(self):
        if not self._lines:
            self._editor.clear()
            return
            
        html_lines = []
        for i, line in enumerate(self._lines):
            escaped = (line
                       .replace("&", "&amp;")
                       .replace("<", "&lt;")
                       .replace(">", "&gt;")
                       .replace(" ", "&nbsp;"))
            line_num_str = f'<span style="color:#6c7086; font-family:Consolas; font-size:10pt;">{i+1:2d} │ </span>'
            html_lines.append(
                f'<div style="padding:1px 0; font-family:Consolas;">'
                f'{line_num_str}<span style="color:#cdd6f4;">&nbsp;&nbsp;{escaped}</span>'
                f'</div>'
            )
            
        self._editor.setHtml(
            '<div style="font-family:Consolas,monospace; font-size:10pt; line-height:130%; white-space:nowrap;">'
            + "".join(html_lines) + '</div>'
        )


# ══════════════════════════════════════════════════════════════════════════════
# LinkedListTracer  —  Linked List Canvas (visualgo-style)
# ══════════════════════════════════════════════════════════════════════════════
class NodeItem(QGraphicsObject):
    def __init__(self, node_id: str, value: int, state: str = "normal", parent=None):
        super().__init__(parent)
        self.node_id = node_id
        self.value = value
        self.state = state  # "normal", "active", "visited", "found", "new"
        self.indices_lbl = ""  # e.g., "[0]"
        self.pointer_lbl = ""  # e.g., "HEAD", "TAIL", "HEAD / TAIL"
        self._width = 100
        self._height = 60
        self.show_index = False
        self.connected_arrows = []
        self.setTransformOriginPoint(self._width / 2, self._height / 2)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(0.0)

    def set_state(self, state: str):
        if self.state != state:
            self.state = state
            self.update()

    def set_labels(self, index_lbl: str, pointer_lbl: str):
        if self.indices_lbl != index_lbl or self.pointer_lbl != pointer_lbl:
            self.indices_lbl = index_lbl
            self.pointer_lbl = pointer_lbl
            self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(-10, -45, self._width + 20, self._height + 70)

    def paint(self, painter: QPainter, option, widget) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.state == "found":
            bg = C["green"]
        elif self.state == "active":
            bg = C["yellow"]
        elif self.state == "visited":
            bg = C["purple"]
        elif self.state == "new":
            bg = C["orange"]
        else:
            bg = C["surface"]

        text_c = C["bg"] if bg != C["surface"] else C["text"]

        # Body rounded rect
        painter.setBrush(QBrush(bg))
        painter.setPen(QPen(C["border"], 1.5))
        painter.drawRoundedRect(QRectF(0, 0, self._width, self._height), 8, 8)

        # Divider data | next (70% - 30%)
        dw = int(self._width * 0.70)
        pw = self._width - dw
        painter.setPen(QPen(C["border"], 1.5))
        painter.drawLine(dw, 0, dw, self._height)

        # Value
        painter.setPen(QPen(text_c))
        painter.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(0, 0, dw, self._height), Qt.AlignmentFlag.AlignCenter, str(self.value))

        # Pointer arrow (Next)
        ptr_c = C["subtext"] if bg == C["surface"] else text_c
        painter.setPen(QPen(ptr_c))
        painter.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(dw, 0, pw, self._height), Qt.AlignmentFlag.AlignCenter, "→")

        # Index label below node (only when show_index is True)
        if self.show_index and self.indices_lbl:
            painter.setPen(QPen(C["subtext"]))
            painter.setFont(QFont("Consolas", 9))
            painter.drawText(QRectF(0, self._height + 4, self._width, 15), Qt.AlignmentFlag.AlignCenter, self.indices_lbl)

        # Pointer label (HEAD / TAIL) above node with arrow ↓
        if self.pointer_lbl:
            if "HEAD" in self.pointer_lbl and "TAIL" in self.pointer_lbl:
                lbl_text = "HEAD/TAIL"
                color = C["pink"]
            elif "HEAD" in self.pointer_lbl:
                lbl_text = "HEAD"
                color = C["purple"]
            else:
                lbl_text = "TAIL"
                color = C["teal"]
                
            painter.setPen(QPen(color))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.drawText(QRectF(0, -32, self._width, 16), Qt.AlignmentFlag.AlignCenter, lbl_text)
            
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            painter.drawText(QRectF(0, -16, self._width, 16), Qt.AlignmentFlag.AlignCenter, "↓")

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for arrow in self.connected_arrows:
                arrow.update_position()
        return super().itemChange(change, value)

    def cleanup(self):
        self.connected_arrows.clear()


class NullItem(QGraphicsObject):
    def __init__(self, node_id: str = "null_item", parent=None):
        super().__init__(parent)
        self.node_id = node_id
        self._width = 100
        self._height = 60
        self.connected_arrows = []
        self.setTransformOriginPoint(self._width / 2, self._height / 2)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(0.0)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter: QPainter, option, widget) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor("#181825")
        painter.setBrush(QBrush(bg))
        pen = QPen(QColor("#45475a"), 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRoundedRect(QRectF(1, 1, self._width - 2, self._height - 2), 8, 8)
        
        painter.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        painter.setPen(QPen(C["subtext"]))
        painter.drawText(QRectF(0, 0, self._width, self._height), Qt.AlignmentFlag.AlignCenter, "NULL")

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for arrow in self.connected_arrows:
                arrow.update_position()
        return super().itemChange(change, value)

    def cleanup(self):
        self.connected_arrows.clear()


class ArrowItem(QGraphicsItem):
    def __init__(self, source_item, target_item, is_broken: bool = False, parent=None):
        super().__init__(parent)
        self.source_item = source_item
        self.target_item = target_item
        self.is_broken = is_broken
        
        self.start_point = QPointF(0, 0)
        self.end_point = QPointF(0, 0)
        
        if source_item:
            source_item.connected_arrows.append(self)
        if target_item:
            target_item.connected_arrows.append(self)
            
        self.setZValue(-1.0)
        self.update_position()

    def update_position(self):
        if not self.source_item or not self.target_item:
            return
        p1 = self.source_item.pos()
        p2 = self.target_item.pos()
        
        start = QPointF(p1.x() + self.source_item._width, p1.y() + self.source_item._height / 2)
        end = QPointF(p2.x(), p2.y() + self.target_item._height / 2)
        self.set_points(start, end)

    def set_points(self, start: QPointF, end: QPointF):
        self.prepareGeometryChange()
        self.start_point = start
        self.end_point = end
        self.update()

    def boundingRect(self) -> QRectF:
        if not self.start_point or not self.end_point:
            return QRectF()
        x1, y1 = self.start_point.x(), self.start_point.y()
        x2, y2 = self.end_point.x(), self.end_point.y()
        extra = 15
        left = min(x1, x2) - extra
        right = max(x1, x2) + extra
        top = min(y1, y2) - extra
        bottom = max(y1, y2) + extra
        return QRectF(left, top, right - left, bottom - top)

    def paint(self, painter: QPainter, option, widget) -> None:
        if not self.start_point or not self.end_point:
            return
        
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        sx, sy = self.start_point.x(), self.start_point.y()
        ex, ey = self.end_point.x(), self.end_point.y()

        if self.is_broken:
            # mid_x = sx + 40, mid_y = sy + 50 as requested for broken link representation
            mid_x = sx + 40
            mid_y = sy + 50
            
            painter.setPen(QPen(C["red"], 2, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(sx, sy), QPointF(mid_x, mid_y))
            self._draw_arrowhead(painter, sx, sy, mid_x, mid_y, C["red"])
        else:
            color = C["blue"]
            painter.setPen(QPen(color, 2))
            painter.drawLine(QPointF(sx, sy), QPointF(ex, ey))
            self._draw_arrowhead(painter, sx, sy, ex, ey, color)

    def _draw_arrowhead(self, painter: QPainter, fx, fy, tx, ty, color: QColor) -> None:
        angle = math.atan2(ty - fy, tx - fx)
        size = 8
        a1 = angle + math.pi * 5 / 6
        a2 = angle - math.pi * 5 / 6
        
        path = QPainterPath()
        path.moveTo(QPointF(tx, ty))
        path.lineTo(QPointF(tx + size * math.cos(a1), ty + size * math.sin(a1)))
        path.lineTo(QPointF(tx + size * math.cos(a2), ty + size * math.sin(a2)))
        path.closeSubpath()
        
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)

    def cleanup(self):
        if self.source_item and self in getattr(self.source_item, "connected_arrows", []):
            self.source_item.connected_arrows.remove(self)
        if self.target_item and self in getattr(self.target_item, "connected_arrows", []):
            self.target_item.connected_arrows.remove(self)
        self.source_item = None
        self.target_item = None


class LinkedListTracerCanvas(QGraphicsView):
    def __init__(self, parent=None):
        scene = QGraphicsScene()
        super().__init__(scene, parent)
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Layout constants
        self.NODE_WIDTH = 100
        self.NODE_HEIGHT = 60
        self.NULL_WIDTH = 100
        self.NULL_HEIGHT = 60
        self.GAP = 60
        self.NULL_GAP = 60

        # Layout Cache
        self._current_layout_nodes = []
        self._current_operation = None
        self._current_insert_index = None

        self._show_index = False

        self._nodes: list[dict] = []
        self._node_items: dict[str, NodeItem] = {}
        self._null_item = NullItem("null_item")
        self.scene().addItem(self._null_item)
        self._arrow_items: list[ArrowItem] = []
        
        self._insert_idx = 0
        self._anim_group = QParallelAnimationGroup(self)
        self._pending_delete_items: list[QGraphicsObject] = []
        self._new_node_id = None

    @property
    def show_index(self) -> bool:
        return self._show_index

    @show_index.setter
    def show_index(self, value: bool):
        self._show_index = value
        for item in self._node_items.values():
            item.show_index = value
            item.update()

    def get_node_ids(self) -> list[str]:
        return [nd["id"] for nd in self._nodes]

    def get_nodes(self) -> list[dict]:
        return self._nodes

    def _compute_total_width(self, node_count: int) -> float:
        if node_count <= 0:
            return self.NULL_WIDTH
        return node_count * self.NODE_WIDTH + (node_count - 1) * self.GAP + self.NULL_GAP + self.NULL_WIDTH

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_layout_on_resize()

    def _update_layout_on_resize(self):
        total_width = self._compute_total_width(len(self._current_layout_nodes))
        viewport_width = self.viewport().width()
        viewport_height = self.viewport().height()
        
        if viewport_width > total_width:
            left_margin = (viewport_width - total_width) / 2
        else:
            left_margin = 60
            
        TOP_PADDING = 50
        BOTTOM_PADDING = 40
        if viewport_width >= total_width:
            scene_width = viewport_width
        else:
            scene_width = left_margin + total_width + 60
        scene_height = viewport_height + TOP_PADDING + BOTTOM_PADDING
        self.scene().setSceneRect(0, -TOP_PADDING, scene_width, scene_height)
        
        if self._anim_group.state() == QParallelAnimationGroup.State.Running:
            return
            
        target_positions = self._compute_target_positions(self._current_layout_nodes, self._new_node_id)
        if not target_positions:
            return
            
        for nid, item in self._node_items.items():
            if nid in target_positions:
                item.setPos(target_positions[nid])
                
        self._null_item.setPos(target_positions["null_item"])
        
        for arrow in self._arrow_items:
            arrow.update_position()

    def _get_animation_duration(self) -> int:
        from PyQt6.QtWidgets import QSlider
        win = self.window()
        if win:
            slider = win.findChild(QSlider)
            if slider:
                return max(50, min(slider.value() - 50, 600))
        return 300

    def update_animation_speeds(self, value: int):
        duration = max(50, min(value - 50, 600))
        if self._anim_group.state() == QParallelAnimationGroup.State.Running:
            for i in range(self._anim_group.animationCount()):
                anim = self._anim_group.animationAt(i)
                if isinstance(anim, QPropertyAnimation):
                    anim.setDuration(duration)

    def reset(self) -> None:
        self._stop_animations()
        for item in list(self._node_items.values()):
            try:
                item.cleanup()
                self.scene().removeItem(item)
            except Exception:
                pass
        self._node_items.clear()
        
        for arrow in self._arrow_items:
            try:
                arrow.cleanup()
                self.scene().removeItem(arrow)
            except Exception:
                pass
        self._arrow_items.clear()
        
        self._null_item.cleanup()
        self._new_node_id = None
        self._nodes = []
        self._current_layout_nodes = []
        self._current_operation = None
        self._current_insert_index = None
        
        # Center the null item dynamically on reset
        viewport_width = self.viewport().width()
        viewport_height = self.viewport().height()
        normal_y = (viewport_height - self.NODE_HEIGHT) / 2
        left_margin = (viewport_width - self.NULL_WIDTH) / 2
        self._null_item.setPos(left_margin, normal_y)
        
        TOP_PADDING = 50
        BOTTOM_PADDING = 40
        self.scene().setSceneRect(0, -TOP_PADDING, viewport_width, viewport_height + TOP_PADDING + BOTTOM_PADDING)

    def _stop_animations(self):
        if self._anim_group.state() == QParallelAnimationGroup.State.Running:
            self._anim_group.stop()
        self._on_animation_finished()

    def on_frame_received(self, payload: dict) -> None:
        if payload.get("mode") != "linked_list":
            return
            
        self._nodes = payload.get("nodes", [])
        highlight = set(payload.get("highlight", []))
        active = payload.get("active")
        arrows_conn = payload.get("arrows", [])
        broken_at = payload.get("broken_at")
        found = payload.get("found")
        new_node_id = payload.get("new_node")
        new_node_val = payload.get("new_node_val")
        operation = payload.get("operation")
        insert_idx = payload.get("insert_index")
        self._new_node_id = new_node_id
        
        self._current_layout_nodes = self._nodes
        self._current_operation = operation
        self._current_insert_index = insert_idx

        # Parse insertion index from metadata
        if operation == "insert_head":
            self._insert_idx = 0
        elif operation == "insert_tail":
            self._insert_idx = len(self._nodes)
        elif operation == "insert_idx" and insert_idx is not None:
            self._insert_idx = insert_idx

        self._stop_animations()
        
        target_positions = self._compute_target_positions(self._nodes, new_node_id)
        if not target_positions:
            return
            
        total_width = self._compute_total_width(len(self._nodes))
        viewport_width = self.viewport().width()
        viewport_height = self.viewport().height()
        
        if viewport_width > total_width:
            left_margin = (viewport_width - total_width) / 2
        else:
            left_margin = 60
            
        TOP_PADDING = 50
        BOTTOM_PADDING = 40
        if viewport_width >= total_width:
            scene_width = viewport_width
        else:
            scene_width = left_margin + total_width + 60
        scene_height = viewport_height + TOP_PADDING + BOTTOM_PADDING
        self.scene().setSceneRect(0, -TOP_PADDING, scene_width, scene_height)

        is_initial = "Nhấn Run để xem" in payload.get("message", "")
        duration = self._get_animation_duration()

        self._anim_group = QParallelAnimationGroup(self)
        nodes_to_keep = set()
        
        if new_node_id and new_node_val is not None:
            nodes_to_keep.add(new_node_id)
            if new_node_id not in self._node_items:
                floating_pos = target_positions[new_node_id]
                item = NodeItem(new_node_id, new_node_val, state="new")
                item.show_index = self._show_index
                item.setPos(floating_pos)
                if is_initial:
                     item.setOpacity(1.0)
                     item.setScale(1.0)
                else:
                     item.setOpacity(0.0)
                     item.setScale(0.1)
                self.scene().addItem(item)
                self._node_items[new_node_id] = item
                
                if not is_initial:
                    anim_fade = QPropertyAnimation(item, b"opacity")
                    anim_fade.setDuration(duration)
                    anim_fade.setStartValue(0.0)
                    anim_fade.setEndValue(1.0)
                    
                    anim_scale = QPropertyAnimation(item, b"scale")
                    anim_scale.setDuration(duration)
                    anim_scale.setStartValue(0.1)
                    anim_scale.setEndValue(1.0)
                    anim_scale.setEasingCurve(QEasingCurve.Type.OutBack)
                    
                    self._anim_group.addAnimation(anim_fade)
                    self._anim_group.addAnimation(anim_scale)

        for idx, nd in enumerate(self._nodes):
            nid = nd["id"]
            val = nd["val"]
            nodes_to_keep.add(nid)
            
            if nid == found:
                state = "found"
            elif nid == active:
                state = "active"
            elif nid == new_node_id:
                state = "new"
            elif nid in highlight:
                state = "visited"
            else:
                state = "normal"
                
            idx_lbl = f"[{idx}]"
            
            pointer_parts = []
            if idx == 0:
                pointer_parts.append("HEAD")
            if idx == len(self._nodes) - 1:
                pointer_parts.append("TAIL")
            ptr_lbl = " / ".join(pointer_parts) if pointer_parts else ""

            if nid not in self._node_items:
                item = NodeItem(nid, val, state=state)
                item.show_index = self._show_index
                item.setPos(target_positions[nid])
                if is_initial:
                    item.setOpacity(1.0)
                    item.setScale(1.0)
                else:
                    item.setOpacity(0.0)
                    item.setScale(0.1)
                self.scene().addItem(item)
                self._node_items[nid] = item
                
                if not is_initial:
                    anim_fade = QPropertyAnimation(item, b"opacity")
                    anim_fade.setDuration(duration)
                    anim_fade.setStartValue(0.0)
                    anim_fade.setEndValue(1.0)
                    
                    anim_scale = QPropertyAnimation(item, b"scale")
                    anim_scale.setDuration(duration)
                    anim_scale.setStartValue(0.1)
                    anim_scale.setEndValue(1.0)
                    
                    self._anim_group.addAnimation(anim_fade)
                    self._anim_group.addAnimation(anim_scale)
            else:
                item = self._node_items[nid]
                item.set_state(state)
                
            item.set_labels(idx_lbl, ptr_lbl)
            
            target_pos = target_positions[nid]
            if is_initial:
                item.setPos(target_pos)
                item.setOpacity(1.0)
                item.setScale(1.0)
            elif item.pos() != target_pos:
                anim_pos = QPropertyAnimation(item, b"pos")
                anim_pos.setDuration(duration)
                anim_pos.setStartValue(item.pos())
                anim_pos.setEndValue(target_pos)
                anim_pos.setEasingCurve(QEasingCurve.Type.InOutQuad)
                self._anim_group.addAnimation(anim_pos)

        null_target_pos = target_positions["null_item"]
        if is_initial:
            self._null_item.setPos(null_target_pos)
        elif self._null_item.pos() != null_target_pos:
            anim_null = QPropertyAnimation(self._null_item, b"pos")
            anim_null.setDuration(duration)
            anim_null.setStartValue(self._null_item.pos())
            anim_null.setEndValue(null_target_pos)
            anim_null.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self._anim_group.addAnimation(anim_null)

        for nid, item in list(self._node_items.items()):
            if nid not in nodes_to_keep:
                self._pending_delete_items.append(item)
                self._node_items.pop(nid)
                
                if is_initial:
                    pass
                else:
                    anim_fade = QPropertyAnimation(item, b"opacity")
                    anim_fade.setDuration(duration)
                    anim_fade.setStartValue(item.opacity())
                    anim_fade.setEndValue(0.0)
                    
                    anim_scale = QPropertyAnimation(item, b"scale")
                    anim_scale.setDuration(duration)
                    anim_scale.setStartValue(item.scale())
                    anim_scale.setEndValue(0.1)
                    
                    self._anim_group.addAnimation(anim_fade)
                    self._anim_group.addAnimation(anim_scale)

        for arrow in self._arrow_items:
            try:
                arrow.cleanup()
                self.scene().removeItem(arrow)
            except Exception:
                pass
        self._arrow_items.clear()
        
        for from_id, to_id in arrows_conn:
            if from_id in self._node_items and to_id in self._node_items:
                is_brk = (broken_at == from_id)
                arrow = ArrowItem(self._node_items[from_id], self._node_items[to_id], is_brk)
                self.scene().addItem(arrow)
                self._arrow_items.append(arrow)
                
        if self._nodes:
            last_id = self._nodes[-1]["id"]
            if last_id in self._node_items:
                is_brk = (broken_at == last_id)
                arrow = ArrowItem(self._node_items[last_id], self._null_item, is_brk)
                self.scene().addItem(arrow)
                self._arrow_items.append(arrow)

        if not is_initial and self._anim_group.animationCount() > 0:
            self._anim_group.finished.connect(self._on_animation_finished)
            self._anim_group.start()
        else:
            self._on_animation_finished()

    def _on_animation_finished(self):
        for item in self._pending_delete_items:
            try:
                item.cleanup()
                self.scene().removeItem(item)
            except Exception:
                pass
        self._pending_delete_items.clear()
        
        # Snap nodes to current target positions (safeguard for resize during animation)
        target_positions = self._compute_target_positions(self._current_layout_nodes, self._new_node_id)
        if target_positions:
            for nid, item in self._node_items.items():
                if nid in target_positions:
                    item.setPos(target_positions[nid])
            self._null_item.setPos(target_positions["null_item"])
        
        for arrow in self._arrow_items:
            arrow.update_position()

    def _compute_target_positions(self, nodes: list, new_node_id: str | None) -> dict[str, QPointF]:
        positions = {}
        viewport_width = self.viewport().width()
        viewport_height = self.viewport().height()
        
        normal_y = (viewport_height - self.NODE_HEIGHT) / 2
        
        total_width = self._compute_total_width(len(nodes))
        if viewport_width > total_width:
            left_margin = (viewport_width - total_width) / 2
        else:
            left_margin = 60
            
        for idx, nd in enumerate(nodes):
            nid = nd["id"]
            positions[nid] = QPointF(left_margin + idx * (self.NODE_WIDTH + self.GAP), normal_y)
            
        if new_node_id and new_node_id not in positions:
            insert_idx = getattr(self, "_insert_idx", 0)
            insert_idx = max(0, min(insert_idx, len(nodes)))
            floating_y = normal_y - 80
            positions[new_node_id] = QPointF(left_margin + insert_idx * (self.NODE_WIDTH + self.GAP), floating_y)
            
        null_idx = len(nodes)
        if null_idx > 0:
            null_x = left_margin + (null_idx - 1) * (self.NODE_WIDTH + self.GAP) + self.NODE_WIDTH + self.NULL_GAP
        else:
            null_x = left_margin
        positions["null_item"] = QPointF(null_x, normal_y)
        
        return positions
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


# ══════════════════════════════════════════════════════════════════════════════
# StatisticsPanel  —  Card thống kê realtime
# ══════════════════════════════════════════════════════════════════════════════
class StatisticsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(210)
        self.setStyleSheet("""
            QWidget {
                background: #181825;
                border-top: 1px solid #313244;
                color: #cdd6f4;
                font-family: 'Segoe UI';
            }
            QLabel {
                font-size: 11px;
                color: #a6adc8;
            }
            QLabel#title {
                font-size: 11px;
                font-weight: bold;
                color: #cba6f7;
                border-bottom: 1px solid #313244;
                padding-bottom: 4px;
            }
            QLabel.value {
                font-family: 'Consolas', monospace;
                font-weight: bold;
                color: #f9e2af;
                font-size: 11px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        
        title = QLabel("📊 THỐNG KÊ REALTIME")
        title.setObjectName("title")
        layout.addWidget(title)
        
        from PyQt6.QtWidgets import QGridLayout
        grid = QGridLayout()
        grid.setSpacing(4)
        
        grid.addWidget(QLabel("Thuật toán:"), 0, 0)
        self.lbl_algo = QLabel("—")
        self.lbl_algo.setObjectName("lbl_algo")
        self.lbl_algo.setStyleSheet("color: #89b4fa; font-weight: bold;")
        grid.addWidget(self.lbl_algo, 0, 1)
        
        grid.addWidget(QLabel("Trạng thái:"), 1, 0)
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        grid.addWidget(self.lbl_status, 1, 1)
        
        grid.addWidget(QLabel("Bước chạy:"), 2, 0)
        self.lbl_step = QLabel("0")
        self.lbl_step.setStyleSheet("color: #f9e2af; font-family: 'Consolas';")
        grid.addWidget(self.lbl_step, 2, 1)
        
        grid.addWidget(QLabel("Elapsed Time:"), 3, 0)
        self.lbl_time = QLabel("0.0s")
        self.lbl_time.setStyleSheet("color: #fab387; font-family: 'Consolas';")
        grid.addWidget(self.lbl_time, 3, 1)
        
        self.lbl_compares_title = QLabel("So sánh:")
        self.lbl_compares = QLabel("0")
        self.lbl_compares.setStyleSheet("color: #f9e2af; font-family: 'Consolas';")
        grid.addWidget(self.lbl_compares_title, 4, 0)
        grid.addWidget(self.lbl_compares, 4, 1)
        
        self.lbl_swaps_title = QLabel("Hoán đổi:")
        self.lbl_swaps = QLabel("0")
        self.lbl_swaps.setStyleSheet("color: #f9e2af; font-family: 'Consolas';")
        grid.addWidget(self.lbl_swaps_title, 5, 0)
        grid.addWidget(self.lbl_swaps, 5, 1)
        
        self.lbl_visited_title = QLabel("Đã duyệt node:")
        self.lbl_visited = QLabel("0")
        self.lbl_visited.setStyleSheet("color: #89b4fa; font-family: 'Consolas';")
        grid.addWidget(self.lbl_visited_title, 6, 0)
        grid.addWidget(self.lbl_visited, 6, 1)

        self.lbl_extra_title = QLabel("Độ dài đường đi:")
        self.lbl_extra = QLabel("0")
        self.lbl_extra.setStyleSheet("color: #a6e3a1; font-family: 'Consolas';")
        grid.addWidget(self.lbl_extra_title, 7, 0)
        grid.addWidget(self.lbl_extra, 7, 1)
        
        layout.addLayout(grid)
        layout.addStretch()
        
    def update_stats(self, algo_name: str, status: str, step: int, total_steps: int | None,
                     compares: int, swaps: int, visited: int, elapsed_time: float,
                     algo_id: str = "", queue_size: int = 0, frontier_size: int = 0,
                     path_length: int = 0, current_distance: float = 0.0,
                     list_size: int = 0, current_node: str = "—",
                     current_value: str = "—", current_index: str = "—"):
        self.lbl_algo.setText(algo_name)
        self.lbl_status.setText(status)
        
        if status == "Running":
            self.lbl_status.setStyleSheet("color: #89b4fa; font-weight: bold;")
        elif status == "Paused":
            self.lbl_status.setStyleSheet("color: #f9e2af; font-weight: bold;")
        elif status in ("Finished", "Ready", "Done", "done"):
            self.lbl_status.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        else:
            self.lbl_status.setStyleSheet("color: #f38ba8; font-weight: bold;")
            
        if total_steps is not None and total_steps > 0:
            self.lbl_step.setText(f"{step} / {total_steps}")
        else:
            self.lbl_step.setText(f"{step}")
            
        self.lbl_time.setText(f"{elapsed_time:.1f}s")

        is_ll = algo_id.startswith("ll_")
        is_search = algo_id in ("linear_search", "binary_search")
        is_sort = algo_id in ("bubble_sort", "selection_sort", "insertion_sort", "merge_sort", "quick_sort", "heap_sort")

        # Dynamic layout depending on algorithm type
        if algo_id == "bfs":
            self.lbl_compares_title.setText("Queue Size:")
            self.lbl_compares.setText(str(queue_size))
            self.lbl_swaps_title.setText("Path Length:")
            self.lbl_swaps.setText(str(path_length))
            self.lbl_visited_title.setText("Visited Nodes:")
            self.lbl_visited.setText(str(visited))
            
            self.lbl_compares_title.setVisible(True)
            self.lbl_compares.setVisible(True)
            self.lbl_swaps_title.setVisible(True)
            self.lbl_swaps.setVisible(True)
            self.lbl_visited_title.setVisible(True)
            self.lbl_visited.setVisible(True)
            self.lbl_extra_title.setVisible(False)
            self.lbl_extra.setVisible(False)
            
        elif algo_id == "dijkstra":
            self.lbl_compares_title.setText("Frontier Size:")
            self.lbl_compares.setText(str(frontier_size))
            self.lbl_swaps_title.setText("Current Distance:")
            self.lbl_swaps.setText(f"{current_distance:.0f}" if current_distance != float('inf') else "inf")
            self.lbl_visited_title.setText("Visited Nodes:")
            self.lbl_visited.setText(str(visited))
            self.lbl_extra_title.setText("Path Length:")
            self.lbl_extra.setText(str(path_length))
            
            self.lbl_compares_title.setVisible(True)
            self.lbl_compares.setVisible(True)
            self.lbl_swaps_title.setVisible(True)
            self.lbl_swaps.setVisible(True)
            self.lbl_visited_title.setVisible(True)
            self.lbl_visited.setVisible(True)
            self.lbl_extra_title.setVisible(True)
            self.lbl_extra.setVisible(True)
            
        elif is_ll:
            self.lbl_compares_title.setText("List Size:")
            self.lbl_compares.setText(str(list_size))
            self.lbl_swaps_title.setText("Current Node:")
            self.lbl_swaps.setText(str(current_node))
            self.lbl_visited_title.setText("Current Value:")
            self.lbl_visited.setText(str(current_value))
            
            self.lbl_compares_title.setVisible(True)
            self.lbl_compares.setVisible(True)
            self.lbl_swaps_title.setVisible(True)
            self.lbl_swaps.setVisible(True)
            self.lbl_visited_title.setVisible(True)
            self.lbl_visited.setVisible(True)
            self.lbl_extra_title.setVisible(False)
            self.lbl_extra.setVisible(False)
            
        elif is_search:
            self.lbl_compares_title.setText("Comparisons:")
            self.lbl_compares.setText(str(compares))
            self.lbl_swaps_title.setText("Current Index:")
            self.lbl_swaps.setText(str(current_index))
            
            self.lbl_compares_title.setVisible(True)
            self.lbl_compares.setVisible(True)
            self.lbl_swaps_title.setVisible(True)
            self.lbl_swaps.setVisible(True)
            self.lbl_visited_title.setVisible(False)
            self.lbl_visited.setVisible(False)
            self.lbl_extra_title.setVisible(False)
            self.lbl_extra.setVisible(False)
            
        else:
            # Default sorting
            self.lbl_compares_title.setText("Comparisons:")
            self.lbl_compares.setText(str(compares))
            self.lbl_swaps_title.setText("Swaps:")
            self.lbl_swaps.setText(str(swaps))
            
            self.lbl_compares_title.setVisible(True)
            self.lbl_compares.setVisible(True)
            self.lbl_swaps_title.setVisible(True)
            self.lbl_swaps.setVisible(True)
            self.lbl_visited_title.setVisible(False)
            self.lbl_visited.setVisible(False)
            self.lbl_extra_title.setVisible(False)
            self.lbl_extra.setVisible(False)
        
    def reset(self):
        self.lbl_algo.setText("—")
        self.lbl_status.setText("Ready")
        self.lbl_status.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        self.lbl_step.setText("0")
        self.lbl_time.setText("0.0s")
        self.lbl_compares.setText("0")
        self.lbl_swaps.setText("0")
        self.lbl_visited.setText("0")
        self.lbl_extra.setText("0")


# ══════════════════════════════════════════════════════════════════════════════
# ExplanationPanel  —  Tab giải thích thuật toán
# ══════════════════════════════════════════════════════════════════════════════
class ExplanationPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        lbl = QLabel("📖 Giải thích thuật toán")
        lbl.setStyleSheet(_TITLE_STYLE)
        layout.addWidget(lbl)
        
        self._browser = QTextBrowser()
        self._browser.setReadOnly(True)
        self._browser.setStyleSheet("""
            QTextBrowser {
                background: #181825;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 0 0 6px 6px;
                padding: 12px;
                font-family: 'Segoe UI';
                font-size: 11px;
                line-height: 140%;
            }
        """)
        layout.addWidget(self._browser)
        
    def set_explanation(self, metadata: dict):
        if not metadata:
            self._browser.setHtml("<p style='color:#6c7086;'>Không có thông tin giải thích.</p>")
            return
            
        html = f"""
        <div style="font-family:'Segoe UI', sans-serif; font-size:10pt; color:#cdd6f4; line-height:140%;">
            <h2 style="color:#cba6f7; margin-top:0; border-bottom:1px solid #313244; padding-bottom:6px;">{metadata.get('name', 'Thuật toán')}</h2>
            
            <p><b>Mô tả:</b><br>{metadata.get('description', '—')}</p>
            
            <p><b>Nguyên lý hoạt động:</b><br>{metadata.get('how_it_works', '—')}</p>
            
            <p><b>Ưu điểm:</b><br>{metadata.get('advantages', '—')}</p>
            
            <p><b>Nhược điểm:</b><br>{metadata.get('disadvantages', '—')}</p>
            
            <h3 style="color:#89b4fa; border-bottom:1px dashed #313244; padding-bottom:4px; margin-top:16px;">Độ phức tạp</h3>
            <table style="width:100%; border-collapse:collapse; margin-top:8px;">
                <tr style="background:#313244;">
                    <th style="padding:6px; text-align:left; border:1px solid #45475a;">Trường hợp</th>
                    <th style="padding:6px; text-align:left; border:1px solid #45475a;">Thời gian</th>
                </tr>
                <tr>
                    <td style="padding:6px; border:1px solid #45475a;">Tốt nhất (Best Case)</td>
                    <td style="padding:6px; border:1px solid #45475a; font-family:Consolas; color:#a6e3a1;">{metadata.get('best_case', '—')}</td>
                </tr>
                <tr style="background:#1e1e2e;">
                    <td style="padding:6px; border:1px solid #45475a;">Trung bình (Average Case)</td>
                    <td style="padding:6px; border:1px solid #45475a; font-family:Consolas; color:#f9e2af;">{metadata.get('average_case', '—')}</td>
                </tr>
                <tr>
                    <td style="padding:6px; border:1px solid #45475a;">Tệ nhất (Worst Case)</td>
                    <td style="padding:6px; border:1px solid #45475a; font-family:Consolas; color:#f38ba8;">{metadata.get('worst_case', '—')}</td>
                </tr>
                <tr style="background:#1e1e2e;">
                    <td style="padding:6px; border:1px solid #45475a;">Không gian (Space)</td>
                    <td style="padding:6px; border:1px solid #45475a; font-family:Consolas; color:#89b4fa;">{metadata.get('space_complexity', '—')}</td>
                </tr>
            </table>
        </div>
        """
        self._browser.setHtml(html)
        
    def reset(self):
        self._browser.clear()
