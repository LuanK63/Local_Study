"""
modules/visualizer/visualizer_controller.py
============================================
Controller chính với layout 3-panel:
  LEFT   : Sidebar chọn thuật toán (có search + categories)
  CENTER : Khu vực tracer động (chart / array / grid)
  RIGHT  : Code panel + Log panel

Phong cách thiết kế giống algorithm-visualizer.org nhưng thuần PyQt6.
"""
from __future__ import annotations

import random
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QIntValidator
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QLineEdit, QFrame, QSplitter, QScrollArea,
    QSizePolicy, QStackedWidget, QButtonGroup, QRadioButton,
    QGroupBox, QListWidget, QListWidgetItem,
)

from modules.visualizer.render_engine import RenderEngine
from modules.visualizer.tracers import (
    ChartTracer, Array1DTracer, LogTracer,
    GridTracer, CodeTracer,
)
from modules.visualizer.algo_library import ALGO_LIBRARY, get_categories
from modules.visualizer.command_interpreter import CommandInterpreter


# ── Palette helpers ────────────────────────────────────────────────────────────
def _btn(text: str, bg="#45475a", fg="#cdd6f4", hover="#585b70",
         h=34, bold=True) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(h)
    b.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold if bold else QFont.Weight.Normal))
    b.setStyleSheet(f"""
        QPushButton {{
            background:{bg}; color:{fg}; border:none;
            border-radius:6px; padding:0 14px;
        }}
        QPushButton:hover {{ background:{hover}; }}
        QPushButton:disabled {{ background:#313244; color:#6c7086; }}
    """)
    return b


_SIDEBAR_ITEM_STYLE = """
    QListWidget {{
        background:#181825; border:none; outline:0;
        color:#cdd6f4; font-size:10px;
    }}
    QListWidget::item {{ padding:6px 12px; border-radius:4px; }}
    QListWidget::item:selected {{
        background:#89b4fa; color:#1e1e2e; font-weight:bold;
    }}
    QListWidget::item:hover:!selected {{ background:#313244; }}
"""

_MAIN_STYLE = """
    QWidget {{ background:#1e1e2e; color:#cdd6f4; font-family:'Segoe UI'; }}
    QSplitter::handle {{ background:#45475a; }}
    QLineEdit {{
        background:#313244; border:1px solid #45475a;
        border-radius:6px; color:#cdd6f4; padding:4px 10px;
    }}
    QLabel {{ color:#cdd6f4; }}
    QScrollArea {{ border:none; background:transparent; }}
"""


class VisualizerController(QWidget):
    """
    3-panel Algorithm Visualizer.
    Nhúng vào bất kỳ layout PyQt6 nào.
    """
    return_requested = pyqtSignal()

    # ── Init ──────────────────────────────────────────────────────────────────

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VisualizerController")
        self.setStyleSheet(_MAIN_STYLE)

        self._current_algo_id: str | None = None
        self._grid_rows = 18
        self._grid_cols = 30
        self._grid_interact_mode = "wall"  # "wall" | "start" | "end"

        # RenderEngine (shared)
        self._engine = RenderEngine(
            speed_fn=lambda: self._speed_slider.value(),
            parent=self,
        )
        self._engine.frame_ready.connect(self._on_frame)
        self._engine.algo_started.connect(self._on_started)
        self._engine.algo_finished.connect(self._on_finished)

        # Command Interpreter for custom code
        self._cmd_interpreter = CommandInterpreter()
        self._cmd_interpreter.frame_update.connect(self._on_frame)
        self._cmd_interpreter.delay_request.connect(self._on_delay_request)

        # Tracers (created once, swapped in center panel)
        self._chart_tracer  = ChartTracer("Biểu đồ Sắp xếp")
        self._array_tracer  = Array1DTracer("Mảng Tìm kiếm")
        self._grid_tracer   = GridTracer("Lưới Pathfinding", self._grid_rows, self._grid_cols)
        self._log_tracer    = LogTracer("Nhật ký thực thi")
        self._code_tracer   = CodeTracer("Pseudocode")

        self._grid_tracer.cell_clicked.connect(self._on_grid_cell_clicked)

        self._build_ui()
        self._connect_signals()

        # Chọn algo đầu tiên mặc định
        if self._algo_list.count() > 0:
            self._algo_list.setCurrentRow(0)
            self._on_algo_selected()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── TOP BAR ───────────────────────────────────────────────────────────
        root.addWidget(self._build_topbar())

        # ── MAIN SPLITTER (left | center | right) ─────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_center())
        splitter.addWidget(self._build_right_panel())

        splitter.setStretchFactor(0, 0)   # sidebar: fixed
        splitter.setStretchFactor(1, 3)   # center: flex
        splitter.setStretchFactor(2, 1)   # right: fixed
        splitter.setSizes([210, 700, 340])

        root.addWidget(splitter)

    # ── TOP BAR ───────────────────────────────────────────────────────────────

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setStyleSheet("background:#181825; border-bottom:1px solid #313244;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        # Logo + title
        logo = QLabel("⚡")
        logo.setFont(QFont("Segoe UI", 18))
        layout.addWidget(logo)

        title = QLabel("Algorithm Visualizer")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color:#cba6f7;")
        layout.addWidget(title)

        layout.addSpacing(20)

        # Complexity badges
        self._time_badge  = self._make_badge("Time: —", "#313244")
        self._space_badge = self._make_badge("Space: —", "#313244")
        layout.addWidget(self._time_badge)
        layout.addWidget(self._space_badge)

        layout.addStretch()

        # Mode toggle
        self._mode_builtin = _btn("Built-in", "#f38ba8", "#1e1e2e", "#f5a8b8", h=30)
        self._mode_custom = _btn("Custom Code", "#45475a", "#cdd6f4", "#585b70", h=30)
        self._mode_builtin.setCheckable(True)
        self._mode_custom.setCheckable(True)
        self._mode_builtin.setChecked(True)
        layout.addWidget(self._mode_builtin)
        layout.addWidget(self._mode_custom)

        # Controls
        self._run_btn    = _btn("▶  Run",    "#a6e3a1", "#1e1e2e", "#94d3a2", h=36)
        self._pause_btn  = _btn("⏸  Pause",  "#f9e2af", "#1e1e2e", "#e6d09f", h=36)
        self._step_btn   = _btn("⏭  Step",   "#89b4fa", "#1e1e2e", "#7ba6f2", h=36)
        self._reset_btn  = _btn("↺  Reset",  "#45475a", "#cdd6f4", "#585b70", h=36)

        self._pause_btn.setEnabled(False)
        for b in (self._run_btn, self._pause_btn, self._step_btn, self._reset_btn):
            layout.addWidget(b)

        layout.addSpacing(10)

        # Speed
        speed_lbl = QLabel("Speed:")
        speed_lbl.setStyleSheet("color:#6c7086; font-size:9px;")
        layout.addWidget(speed_lbl)

        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(30, 1200)
        self._speed_slider.setValue(500)
        self._speed_slider.setInvertedAppearance(True)
        self._speed_slider.setFixedWidth(100)
        self._speed_slider.setStyleSheet("""
            QSlider::groove:horizontal { height:4px; background:#45475a; border-radius:2px; }
            QSlider::handle:horizontal {
                background:#89b4fa; width:12px; height:12px;
                margin:-4px 0; border-radius:6px;
            }
        """)
        layout.addWidget(self._speed_slider)

        layout.addSpacing(20)

        self._return_btn = _btn("✕  Đóng", "#f38ba8", "#1e1e2e", "#eb6f92", h=36)
        layout.addWidget(self._return_btn)

        return bar

    def _make_badge(self, text: str, bg: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Consolas", 9))
        lbl.setStyleSheet(
            f"background:{bg}; color:#cdd6f4; border-radius:4px; padding:3px 8px;"
        )
        return lbl

    # ── SIDEBAR ───────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(210)
        sidebar.setStyleSheet("background:#181825; border-right:1px solid #313244;")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Mode stack
        self._sidebar_stack = QStackedWidget()

        # Page 1: Built-in algorithms
        builtin_page = self._build_builtin_page()
        self._sidebar_stack.addWidget(builtin_page)

        # Page 2: Custom code
        custom_page = self._build_custom_page()
        self._sidebar_stack.addWidget(custom_page)

        layout.addWidget(self._sidebar_stack)
        return sidebar

    def _build_builtin_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Search bar
        search_wrap = QWidget()
        search_wrap.setStyleSheet("background:#181825; padding:8px 10px;")
        sw_layout = QHBoxLayout(search_wrap)
        sw_layout.setContentsMargins(8, 8, 8, 4)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("🔎  Tìm thuật toán...")
        self._search_box.setFixedHeight(30)
        self._search_box.setFont(QFont("Segoe UI", 9))
        self._search_box.setStyleSheet(
            "background:#313244; border:1px solid #45475a; border-radius:15px; "
            "color:#cdd6f4; padding:0 12px;"
        )
        sw_layout.addWidget(self._search_box)
        layout.addWidget(search_wrap)

        # Algorithm list
        self._algo_list = QListWidget()
        self._algo_list.setStyleSheet(_SIDEBAR_ITEM_STYLE)
        self._algo_list.setFont(QFont("Segoe UI", 10))
        self._algo_list.setSpacing(1)
        self._populate_algo_list()
        layout.addWidget(self._algo_list)

        # Input panel at bottom
        layout.addWidget(self._build_input_panel())
        return page

    def _build_custom_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title
        title = QLabel("Custom Code")
        title.setStyleSheet("color:#cba6f7; font-size:12px; font-weight:bold; padding:8px 10px;")
        layout.addWidget(title)

        # Code editor
        from PyQt6.QtWidgets import QTextEdit
        self._code_editor = QTextEdit()
        self._code_editor.setStyleSheet("""
            background:#1e1e2e; color:#cdd6f4; border:none;
            font-family:'Consolas'; font-size:10px; padding:8px;
        """)
        self._code_editor.setPlaceholderText("""
# Example: Bubble Sort
from algorithm_visualizer import Array1DTracer, LogTracer

tracer = Array1DTracer("My Array")
log = LogTracer("Log")
tracer.set([5, 3, 8, 1])
log.println("Starting bubble sort")

for i in range(len(arr)):
    for j in range(len(arr) - i - 1):
        tracer.select(j, j+1)
        if arr[j] > arr[j+1]:
            arr[j], arr[j+1] = arr[j+1], arr[j]
            tracer.patch(j, arr[j])
            tracer.patch(j+1, arr[j+1])
        tracer.deselect(j, j+1)
""")
        layout.addWidget(self._code_editor)

        # Run button
        run_custom_btn = _btn("Run Custom Code", "#a6e3a1", "#1e1e2e", "#94d3a2", h=36)
        run_custom_btn.clicked.connect(self._run_custom_code)
        layout.addWidget(run_custom_btn)

        return page

    def _populate_algo_list(self, filter_text: str = ""):
        self._algo_list.clear()
        cats = get_categories()
        for cat, algos in cats.items():
            # Category header
            header = QListWidgetItem(cat)
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            header.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            header.setForeground(QColor("#6c7086"))
            header.setData(Qt.ItemDataRole.UserRole, None)
            self._algo_list.addItem(header)

            for aid, aname in algos:
                if filter_text and filter_text.lower() not in aname.lower():
                    continue
                item = QListWidgetItem(f"  {aname}")
                item.setData(Qt.ItemDataRole.UserRole, aid)
                self._algo_list.addItem(item)

    def _build_input_panel(self) -> QWidget:
        """Panel nhập liệu ở cuối sidebar."""
        frame = QFrame()
        frame.setStyleSheet(
            "background:#1e1e2e; border-top:1px solid #313244;"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)

        lbl = QLabel("Input dữ liệu")
        lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl.setStyleSheet("color:#6c7086;")
        layout.addWidget(lbl)

        self._array_input = QLineEdit("5, 3, 8, 1, 9, 2, 7, 4, 6")
        self._array_input.setPlaceholderText("Mảng: 5, 3, 8, 1, 9")
        self._array_input.setFixedHeight(30)
        layout.addWidget(self._array_input)

        self._target_input = QLineEdit("7")
        self._target_input.setPlaceholderText("Target (tìm kiếm)")
        self._target_input.setFixedHeight(30)
        self._target_input.setValidator(QIntValidator(-9999, 9999))
        layout.addWidget(self._target_input)

        # Random button
        rand_btn = _btn("🎲  Ngẫu nhiên", "#313244", "#cdd6f4", "#45475a", h=28, bold=False)
        rand_btn.clicked.connect(self._randomize_input)
        layout.addWidget(rand_btn)

        # Grid interaction mode (ẩn mặc định)
        self._grid_mode_group = QGroupBox("Chế độ vẽ lưới")
        self._grid_mode_group.setStyleSheet(
            "QGroupBox { border:1px solid #45475a; border-radius:6px; "
            "margin-top:8px; padding-top:8px; color:#6c7086; font-size:9px; }"
            "QGroupBox::title { subcontrol-origin:margin; left:8px; }"
        )
        gm_layout = QVBoxLayout(self._grid_mode_group)
        gm_layout.setSpacing(2)
        self._mode_wall  = QRadioButton("🟫 Vẽ Tường")
        self._mode_start = QRadioButton("🟢 Đặt Start")
        self._mode_end   = QRadioButton("🔴 Đặt End")
        self._mode_wall.setChecked(True)
        for rb in (self._mode_wall, self._mode_start, self._mode_end):
            rb.setFont(QFont("Segoe UI", 9))
            rb.setStyleSheet("color:#cdd6f4;")
            gm_layout.addWidget(rb)

        clear_walls_btn = _btn("🗑️ Xóa tường", "#313244", "#cdd6f4", "#45475a", h=26, bold=False)
        clear_walls_btn.clicked.connect(self._clear_walls)
        gm_layout.addWidget(clear_walls_btn)

        self._grid_mode_group.setVisible(False)
        layout.addWidget(self._grid_mode_group)

        return frame

    # ── CENTER PANEL ──────────────────────────────────────────────────────────

    def _build_center(self) -> QWidget:
        self._center = QWidget()
        self._center.setStyleSheet("background:#1e1e2e;")
        self._center_layout = QVBoxLayout(self._center)
        self._center_layout.setContentsMargins(12, 10, 6, 10)
        self._center_layout.setSpacing(8)

        # Algo info header
        self._algo_title_lbl = QLabel("Chọn thuật toán từ sidebar →")
        self._algo_title_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._algo_title_lbl.setStyleSheet("color:#cba6f7;")
        self._center_layout.addWidget(self._algo_title_lbl)

        # Stacked: chart / array / grid
        self._tracer_stack = QStackedWidget()
        self._tracer_stack.addWidget(self._chart_tracer)   # index 0
        self._tracer_stack.addWidget(self._array_tracer)   # index 1
        self._tracer_stack.addWidget(self._grid_tracer)    # index 2
        self._center_layout.addWidget(self._tracer_stack, stretch=1)

        # Log tracer
        self._center_layout.addWidget(self._log_tracer, stretch=0)
        self._log_tracer.setMinimumHeight(100)
        self._log_tracer.setMaximumHeight(160)

        return self._center

    # ── RIGHT PANEL ───────────────────────────────────────────────────────────

    def _build_right_panel(self) -> QWidget:
        right = QWidget()
        right.setStyleSheet("background:#181825; border-left:1px solid #313244;")
        layout = QVBoxLayout(right)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # CodeTracer chiếm phần lớn
        self._code_tracer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self._code_tracer, stretch=1)

        return right

    # ── Connect Signals ───────────────────────────────────────────────────────

    def _connect_signals(self):
        self._return_btn.clicked.connect(self.return_requested.emit)
        self._run_btn.clicked.connect(self._on_run)
        self._pause_btn.clicked.connect(self._on_pause_resume)
        self._step_btn.clicked.connect(self._on_step)
        self._reset_btn.clicked.connect(self._on_reset)
        self._mode_builtin.clicked.connect(self._on_mode_builtin)
        self._mode_custom.clicked.connect(self._on_mode_custom)
        self._algo_list.itemClicked.connect(lambda _: self._on_algo_selected())
        self._search_box.textChanged.connect(
            lambda t: self._populate_algo_list(t)
        )
        self._mode_wall.toggled.connect(
            lambda: setattr(self, "_grid_interact_mode", "wall"))
        self._mode_start.toggled.connect(
            lambda: setattr(self, "_grid_interact_mode", "start"))
        self._mode_end.toggled.connect(
            lambda: setattr(self, "_grid_interact_mode", "end"))

    # ── Algo Selection ────────────────────────────────────────────────────────

    def _on_algo_selected(self):
        item = self._algo_list.currentItem()
        if item is None:
            return
        algo_id = item.data(Qt.ItemDataRole.UserRole)
        if not algo_id:
            return   # category header

        self._engine.stop()
        self._current_algo_id = algo_id
        info = ALGO_LIBRARY[algo_id]

        # Update title + badges
        self._algo_title_lbl.setText(f"{info['name']}")
        cplx = info.get("complexity", {})
        self._time_badge.setText(f"⏱ Time: {cplx.get('time','?')}")
        self._space_badge.setText(f"💾 Space: {cplx.get('space','?')}")

        # Swap tracer in center
        tracers = info.get("tracers", [])
        if "chart" in tracers:
            self._tracer_stack.setCurrentIndex(0)
        elif "array1d" in tracers:
            self._tracer_stack.setCurrentIndex(1)
        elif "grid" in tracers:
            self._tracer_stack.setCurrentIndex(2)

        # Show/hide grid mode panel
        is_grid = info.get("input_type") == "grid"
        self._grid_mode_group.setVisible(is_grid)
        self._array_input.setVisible(not is_grid)
        self._target_input.setVisible(info.get("input_type") == "array_target")

        # Load code
        self._code_tracer.set_code(info.get("code", "# no pseudocode"))
        self._log_tracer.reset()

        # Reset tracers
        self._chart_tracer.reset()
        self._array_tracer.reset()
        self._grid_tracer.reset_overlay()

        # Preview data
        if info.get("input_type") in ("array", "array_target"):
            try:
                data = self._parse_array()
                if "chart" in tracers:
                    self._chart_tracer.set_state(data=data)
                elif "array1d" in tracers:
                    self._array_tracer.set_state(data=data)
            except Exception:
                pass

        self._run_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._pause_btn.setText("⏸  Pause")
        self._step_btn.setEnabled(True)

    # ── Run / Control ─────────────────────────────────────────────────────────

    def _on_run(self):
        if not self._current_algo_id:
            return
        self._engine.stop()
        self._log_tracer.reset()
        self._code_tracer.reset()
        info = ALGO_LIBRARY[self._current_algo_id]

        try:
            run_fn = info["run"]
            input_type = info.get("input_type", "array")

            if input_type == "array":
                data = self._parse_array()
                target_fn = lambda: run_fn(self._engine, data)

            elif input_type == "array_target":
                data = self._parse_array()
                try:
                    target = int(self._target_input.text().strip())
                except ValueError:
                    target = data[0] if data else 0
                target_fn = lambda: run_fn(self._engine, data, target)

            elif input_type == "grid":
                grid_copy = [row[:] for row in self._grid_tracer.canvas._grid]
                target_fn = lambda: run_fn(self._engine, grid_copy, self._grid_rows, self._grid_cols)

            else:
                return

            self._engine.start(target_fn)

        except Exception as e:
            self._log_tracer.log(f"❌ Lỗi: {e}")

    def _on_pause_resume(self):
        if self._engine.is_paused():
            self._engine.resume()
            self._pause_btn.setText("⏸  Pause")
        else:
            self._engine.pause()
            self._pause_btn.setText("▶  Resume")

    def _on_step(self):
        """Chế độ Step: pause rồi resume ngay để chạy 1 frame."""
        if not self._engine.is_running():
            # Khởi chạy và pause ngay
            self._on_run()
            self._engine.pause()
            self._pause_btn.setText("▶  Resume")
        else:
            # Resume 1 frame rồi pause lại
            self._engine.resume()
            QTimer.singleShot(self._speed_slider.value() + 50, self._engine.pause)

    def _on_reset(self):
        self._engine.stop()
        self._chart_tracer.reset()
        self._array_tracer.reset()
        self._grid_tracer.reset_overlay()
        self._log_tracer.reset()
        self._code_tracer.reset()
        self._run_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._pause_btn.setText("⏸  Pause")
        if self._current_algo_id:
            info = ALGO_LIBRARY[self._current_algo_id]
            if info.get("input_type") in ("array", "array_target"):
                try:
                    data = self._parse_array()
                    if "chart" in info.get("tracers", []):
                        self._chart_tracer.set_state(data=data)
                    elif "array1d" in info.get("tracers", []):
                        self._array_tracer.set_state(data=data)
                except Exception:
                    pass

    # ── Frame Handler ─────────────────────────────────────────────────────────

    def _on_frame(self, payload: dict):
        """Nhận frame từ RenderEngine hoặc CommandInterpreter và dispatch đến đúng tracer."""
        # Check if it's a command payload
        if 'method' in payload and 'key' in payload:
            # Command-based payload
            self._handle_command_payload(payload)
            return

        # Original payload-based handling
        algo = payload.get("algo", "")
        info = ALGO_LIBRARY.get(algo, {})
        tracers = info.get("tracers", [])

        # Chart / Array
        if "chart" in tracers and "array" in payload:
            self._chart_tracer.set_state(
                data=payload["array"],
                selected=payload.get("selected", []),
                patched=payload.get("patched", []),
                sorted_=payload.get("sorted", []),
                pivot=payload.get("pivot"),
            )
        elif "array1d" in tracers and "array" in payload:
            self._array_tracer.set_state(
                data=payload["array"],
                selected=payload.get("selected", []),
                patched=payload.get("patched", []),
                sorted_=payload.get("sorted", []),
            )

        # Grid
        if "grid" in tracers:
            self._grid_tracer.update_from_frame(payload)

        # Log
        if "log" in payload:
            self._log_tracer.log(payload["log"])

        # Code highlight
        if "line" in payload:
            self._code_tracer.highlight_line(payload["line"])

    def _handle_command_payload(self, payload: dict):
        """Handle command-based payload from custom code."""
        method = payload['method']
        args = payload.get('args', [])
        key = payload['key']

        # Map to tracer updates
        if method == 'set' and len(args) > 0:
            data = args[0]
            if isinstance(data, list):
                self._array_tracer.set_state(data=data)
        elif method == 'patch' and len(args) >= 2:
            index, value = args[0], args[1]
            self._array_tracer.set_state(patched=[(index, value)])
        elif method == 'select' and len(args) >= 1:
            indices = args if len(args) > 1 else [args[0]]
            self._array_tracer.set_state(selected=indices)
        elif method == 'deselect':
            self._array_tracer.set_state(selected=[])
        elif method == 'print' and len(args) > 0:
            self._log_tracer.log(str(args[0]))
        elif method == 'println' and len(args) > 0:
            self._log_tracer.log(str(args[0]))
        elif method == 'printf' and len(args) >= 1:
            format_str = args[0]
            values = args[1:]
            try:
                message = format_str % tuple(values)
                self._log_tracer.log(message)
            except:
                self._log_tracer.log(format_str + str(values))
        # Add more command handlers as needed

    def _on_started(self):
        self._run_btn.setEnabled(False)
        self._pause_btn.setEnabled(True)
        self._pause_btn.setText("⏸  Pause")

    def _on_finished(self, msg: str):
        self._run_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._pause_btn.setText("⏸  Pause")
        icon = "✅" if msg == "done" else "⏹"
        self._log_tracer.log(f"\n{icon} {msg}")

    # ── Grid Interaction ──────────────────────────────────────────────────────

    def _on_grid_cell_clicked(self, r: int, c: int):
        grid = self._grid_tracer.canvas._grid
        mode = self._grid_interact_mode

        if mode == "wall":
            if grid[r][c] not in ("start", "end"):
                grid[r][c] = "empty" if grid[r][c] == "wall" else "wall"
        elif mode == "start":
            for rr in range(self._grid_rows):
                for cc in range(self._grid_cols):
                    if grid[rr][cc] == "start":
                        grid[rr][cc] = "empty"
            if grid[r][c] != "end":
                grid[r][c] = "start"
        elif mode == "end":
            for rr in range(self._grid_rows):
                for cc in range(self._grid_cols):
                    if grid[rr][cc] == "end":
                        grid[rr][cc] = "empty"
            if grid[r][c] != "start":
                grid[r][c] = "end"

        self._grid_tracer.canvas.update()

    def _clear_walls(self):
        grid = self._grid_tracer.canvas._grid
        for r in range(self._grid_rows):
            for c in range(self._grid_cols):
                if grid[r][c] == "wall":
                    grid[r][c] = "empty"
        self._grid_tracer.canvas.update()

    # ── Input helpers ─────────────────────────────────────────────────────────

    def _parse_array(self) -> list[int]:
        text = self._array_input.text().strip()
        vals = [int(x.strip()) for x in text.split(",") if x.strip()]
        if not vals:
            raise ValueError("Mảng trống!")
        return vals

    def _randomize_input(self):
        n = random.randint(8, 18)
        arr = random.sample(range(1, 100), min(n, 99))
        self._array_input.setText(", ".join(map(str, arr)))
        self._target_input.setText(str(random.choice(arr) if random.random() > 0.3 else random.randint(1, 99)))
        if self._current_algo_id:
            self._on_algo_selected()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._engine.stop()
        super().closeEvent(event)

    # ── Mode Toggle ───────────────────────────────────────────────────────────

    def _on_mode_builtin(self):
        self._mode_builtin.setChecked(True)
        self._mode_custom.setChecked(False)
        self._sidebar_stack.setCurrentIndex(0)
        self._algo_title_lbl.setText("Chọn thuật toán từ sidebar →")

    def _on_mode_custom(self):
        self._mode_builtin.setChecked(False)
        self._mode_custom.setChecked(True)
        self._sidebar_stack.setCurrentIndex(1)
        self._algo_title_lbl.setText("Nhập code tùy chỉnh →")

    def _run_custom_code(self):
        """Execute custom code using algorithm_visualizer library."""
        code = self._code_editor.toPlainText()
        if not code.strip():
            return

        # Reset interpreter
        self._cmd_interpreter.reset()

        # Execute code in a safe way
        try:
            # Import algorithm_visualizer
            from modules import algorithm_visualizer

            # Create a restricted globals
            restricted_globals = {
                '__builtins__': {
                    'len': len,
                    'range': range,
                    'int': int,
                    'str': str,
                    'list': list,
                    'print': print,
                    'enumerate': enumerate,
                    'zip': zip,
                    'min': min,
                    'max': max,
                    'abs': abs,
                    'sum': sum,
                },
                'algorithm_visualizer': algorithm_visualizer,
                'Array1DTracer': algorithm_visualizer.Array1DTracer,
                'LogTracer': algorithm_visualizer.LogTracer,
                'ChartTracer': algorithm_visualizer.ChartTracer,
                'GraphTracer': algorithm_visualizer.GraphTracer,
                'Randomize': algorithm_visualizer.Randomize,
            }

            exec(code, restricted_globals)

            # Interpret commands
            self._cmd_interpreter.interpret_commands(algorithm_visualizer.Commander.commands)

        except Exception as e:
            self._log_tracer.log(f"Lỗi thực thi code: {e}")
            import traceback
            self._log_tracer.log(traceback.format_exc())

    def _on_delay_request(self, delay: int):
        """Handle delay from command interpreter."""
        QTimer.singleShot(delay, lambda: None)  # Simple delay
