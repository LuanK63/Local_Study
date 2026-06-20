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
    QGroupBox, QListWidget, QListWidgetItem, QComboBox, QCheckBox,
)

from modules.visualizer.render_engine import RenderEngine
from modules.visualizer.tracers import (
    ChartTracer, Array1DTracer, LogTracer,
    GridTracer, CodeTracer, LinkedListTracer,
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

        # Khởi tạo các trường thống kê
        self._stats_step = 0
        self._stats_compares = 0
        self._stats_swaps = 0
        self._stats_visited = 0
        self._stats_queue_size = 0
        self._stats_frontier_size = 0
        self._stats_path_length = 0
        self._stats_current_distance = 0.0
        self._stats_list_size = 0
        self._stats_current_node = "—"
        self._stats_current_value = "—"
        self._stats_current_index = "—"
        self._start_time = 0.0
        self._accumulated_time = 0.0
        self._total_steps = None
        
        # Khởi tạo timer cập nhật thời gian trôi qua
        self._elapsed_update_timer = QTimer(self)
        self._elapsed_update_timer.setInterval(100) # Cập nhật mỗi 100ms
        self._elapsed_update_timer.timeout.connect(self._update_elapsed_time_ui)

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
        self._linked_list_tracer = LinkedListTracer("Danh sách liên kết")
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
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.setHandleWidth(2)

        self._sidebar_widget = self._build_sidebar()
        self._main_splitter.addWidget(self._sidebar_widget)
        self._main_splitter.addWidget(self._build_center())
        self._main_splitter.addWidget(self._build_right_panel())

        self._main_splitter.setStretchFactor(0, 0)   # sidebar: fixed
        self._main_splitter.setStretchFactor(1, 3)   # center: flex
        self._main_splitter.setStretchFactor(2, 1)   # right: fixed
        self._main_splitter.setSizes([210, 700, 340])

        root.addWidget(self._main_splitter)

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

        # Sidebar toggle button for Tablet
        self._sidebar_toggle_btn = _btn("◀ Sidebar", "#313244", "#cdd6f4", "#45475a", h=30, bold=False)
        self._sidebar_toggle_btn.setToolTip("Thu gọn / Mở rộng Sidebar danh sách thuật toán")
        self._sidebar_toggle_btn.clicked.connect(self._toggle_sidebar)
        layout.addWidget(self._sidebar_toggle_btn)

        layout.addSpacing(10)

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
        self._run_btn    = _btn("▶  Run",    "#a6e3a1", "#11111b", "#b4f4af", h=38) # Nút chính nổi bật
        self._run_btn.setToolTip("Chạy thuật toán trực quan hóa")
        
        self._pause_btn  = _btn("⏸  Pause",  "#313244", "#cdd6f4", "#45475a", h=34, bold=False) # Nút phụ
        self._pause_btn.setToolTip("Tạm dừng / Tiếp tục thuật toán")
        
        self._step_btn   = _btn("⏭  Step",   "#313244", "#cdd6f4", "#45475a", h=34, bold=False)
        self._step_btn.setToolTip("Chạy từng bước tiếp theo")
        
        self._reset_btn  = _btn("↺  Reset",  "#313244", "#cdd6f4", "#45475a", h=34, bold=False)
        self._reset_btn.setToolTip("Đặt lại thuật toán về trạng thái ban đầu")

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

        self._return_btn = _btn("✕  Đóng", "#313244", "#f38ba8", "#45475a", h=34, bold=False)
        self._return_btn.setToolTip("Đóng visualizer và trở lại màn hình chính")
        layout.addWidget(self._return_btn)

        return bar

    def _toggle_sidebar(self):
        if self._sidebar_widget.isVisible():
            self._sidebar_widget.setVisible(False)
            self._sidebar_toggle_btn.setText("▶ Sidebar")
        else:
            self._sidebar_widget.setVisible(True)
            self._sidebar_toggle_btn.setText("◀ Sidebar")

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

        # Maze button
        self._maze_btn = _btn("🎲  Mê cung", "#313244", "#cdd6f4", "#45475a", h=26, bold=False)
        self._maze_btn.setToolTip("Sinh mê cung ngẫu nhiên liên thông Start-End")
        self._maze_btn.clicked.connect(self._generate_random_maze)
        gm_layout.addWidget(self._maze_btn)

        # Zoom layout & combobox
        zoom_layout = QHBoxLayout()
        zoom_layout.setSpacing(4)
        zoom_label = QLabel("🔍 Zoom:")
        zoom_label.setStyleSheet("color:#a6adc8; font-size:9px;")
        zoom_layout.addWidget(zoom_label)
        
        self._zoom_combo = QComboBox()
        self._zoom_combo.setFont(QFont("Segoe UI", 8))
        self._zoom_combo.setStyleSheet("""
            QComboBox {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 2px 4px;
                min-width: 80px;
            }
        """)
        self._zoom_combo.addItem("Fit Window", "fit")
        self._zoom_combo.addItem("Small (0.75x)", "0.75")
        self._zoom_combo.addItem("Medium (1.0x)", "1.0")
        self._zoom_combo.addItem("Large (1.5x)", "1.5")
        self._zoom_combo.setCurrentIndex(0) # Default to Fit Window
        self._zoom_combo.currentIndexChanged.connect(self._on_zoom_changed)
        zoom_layout.addWidget(self._zoom_combo)
        
        gm_layout.addLayout(zoom_layout)

        self._grid_mode_group.setVisible(False)
        layout.addWidget(self._grid_mode_group)

        # Checkbox "Hiện Chỉ Số (Index)"
        self._show_index_cb = QCheckBox("Hiện Chỉ Số (Index)")
        self._show_index_cb.setChecked(False)
        self._show_index_cb.setStyleSheet("color: #cdd6f4; font-family: 'Segoe UI'; font-size: 10pt; margin-top: 6px;")
        self._show_index_cb.toggled.connect(self._on_show_index_toggled)
        self._show_index_cb.setVisible(False)
        layout.addWidget(self._show_index_cb)

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

        # Visual Status Panel ngay trên tracer stack
        from PyQt6.QtWidgets import QFrame
        self._visual_status_panel = QFrame()
        self._visual_status_panel.setFixedHeight(32)
        self._visual_status_panel.setStyleSheet("""
            QFrame {
                background: #181825;
                border: 1px solid #313244;
                border-radius: 6px;
            }
            QLabel {
                color: #f9e2af;
                font-size: 11px;
                font-weight: bold;
                font-family: 'Segoe UI';
            }
        """)
        vsp_layout = QHBoxLayout(self._visual_status_panel)
        vsp_layout.setContentsMargins(12, 0, 12, 0)
        self._visual_status_lbl = QLabel("Sẵn sàng chạy thuật toán...")
        vsp_layout.addWidget(self._visual_status_lbl)
        self._center_layout.addWidget(self._visual_status_panel)

        # Stacked: chart / array / grid / linked_list
        self._tracer_stack = QStackedWidget()
        self._tracer_stack.addWidget(self._chart_tracer)   # index 0
        self._tracer_stack.addWidget(self._array_tracer)   # index 1
        self._tracer_stack.addWidget(self._grid_tracer)    # index 2
        self._tracer_stack.addWidget(self._linked_list_tracer) # index 3
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

        # Tab widget ở cột bên phải
        from PyQt6.QtWidgets import QTabWidget
        self._right_tabs = QTabWidget()
        self._right_tabs.setStyleSheet("""
            QTabWidget::panel {
                border: none;
                background: #181825;
            }
            QTabBar::tab {
                background: #1e1e2e;
                color: #a6adc8;
                border: 1px solid #313244;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 6px 12px;
                margin-right: 2px;
                font-family: 'Segoe UI';
                font-size: 11px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #181825;
                color: #cba6f7;
                border-color: #45475a;
            }
            QTabBar::tab:hover {
                background: #313244;
            }
        """)

        # Tab 1: Pseudocode & Stats
        tab1 = QWidget()
        t1_layout = QVBoxLayout(tab1)
        t1_layout.setContentsMargins(0, 0, 0, 0)
        t1_layout.setSpacing(0)

        self._code_tracer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        t1_layout.addWidget(self._code_tracer, stretch=1)

        # Thêm StatisticsPanel dưới CodeTracer
        from modules.visualizer.tracers import StatisticsPanel
        self._stats_panel = StatisticsPanel(parent=self)
        t1_layout.addWidget(self._stats_panel, stretch=0)

        # Tab 2: Explanation
        from modules.visualizer.tracers import ExplanationPanel
        self._explanation_panel = ExplanationPanel(parent=self)

        self._right_tabs.addTab(tab1, "💻 Code & Stats")
        self._right_tabs.addTab(self._explanation_panel, "📖 Explanation")

        layout.addWidget(self._right_tabs)
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
        self._speed_slider.valueChanged.connect(self._linked_list_tracer.canvas.update_animation_speeds)

    # ── Algo Selection ────────────────────────────────────────────────────────

    def _on_algo_selected(self):
        item = self._algo_list.currentItem()
        if item is None:
            return
        algo_id = item.data(Qt.ItemDataRole.UserRole)
        if not algo_id:
            return   # category header

        self._engine.stop()
        self._elapsed_update_timer.stop()
        self._current_algo_id = algo_id
        info = ALGO_LIBRARY[algo_id]

        # Reset statistics & status variables
        self._stats_step = 0
        self._stats_compares = 0
        self._stats_swaps = 0
        self._stats_visited = 0
        self._stats_queue_size = 0
        self._stats_frontier_size = 0
        self._stats_path_length = 0
        self._stats_current_distance = 0.0
        self._stats_list_size = 0
        self._stats_current_node = "—"
        self._stats_current_value = "—"
        self._stats_current_index = "—"
        self._start_time = 0.0
        self._accumulated_time = 0.0
        self._total_steps = None

        # Update UI panels
        self._stats_panel.reset()
        self._visual_status_lbl.setText("Sẵn sàng chạy thuật toán...")

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
        elif "linked_list" in tracers:
            self._tracer_stack.setCurrentIndex(3)

        # Show/hide grid mode panel
        is_grid = info.get("input_type") == "grid"
        self._grid_mode_group.setVisible(is_grid)
        self._array_input.setVisible(not is_grid)

        # Show/hide show index checkbox
        is_ll = "linked_list" in tracers
        self._show_index_cb.setVisible(is_ll)
        
        input_type = info.get("input_type")
        self._target_input.setVisible(input_type in ("array_target", "ll_insert_idx"))
        if input_type == "ll_insert_idx":
            self._target_input.setValidator(None)
            self._target_input.setPlaceholderText("Vị trí, Giá trị (VD: 2, 9)")
        else:
            self._target_input.setValidator(QIntValidator(-9999, 9999))
            self._target_input.setPlaceholderText("Target (tìm kiếm/xóa)")

        # Load code & Explanation
        self._code_tracer.set_code(info.get("code", "# no pseudocode"))
        self._explanation_panel.set_explanation(info)
        self._log_tracer.reset()

        # Reset tracers
        self._chart_tracer.reset()
        self._array_tracer.reset()
        self._grid_tracer.reset_overlay()
        self._linked_list_tracer.reset()

        # Preview data
        if info.get("input_type") in ("array", "array_target", "ll_insert_idx"):
            try:
                data = self._parse_array()
                if "chart" in tracers:
                    self._chart_tracer.canvas.set_state(data=data)
                elif "array1d" in tracers:
                    self._array_tracer.canvas.set_state(data=data)
                elif "linked_list" in tracers:
                    self._linked_list_tracer.show_initial(data=data)
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
        
        # Reset counters & timer
        self._stats_step = 0
        self._stats_compares = 0
        self._stats_swaps = 0
        self._stats_visited = 0
        self._stats_queue_size = 0
        self._stats_frontier_size = 0
        self._stats_path_length = 0
        self._stats_current_distance = 0.0
        self._stats_list_size = 0
        self._stats_current_node = "—"
        self._stats_current_value = "—"
        self._stats_current_index = "—"
        import time
        self._start_time = time.monotonic()
        self._accumulated_time = 0.0
        self._total_steps = None  # Built-in chạy real-time trong Thread nên không tính trước Total Steps
        
        self._stats_panel.reset()
        self._visual_status_lbl.setText("Đang khởi chạy thuật toán...")
        self._log_tracer.reset()
        self._code_tracer.reset()
        
        self._elapsed_update_timer.start()

        info = ALGO_LIBRARY[self._current_algo_id]

        if info.get("mode") == "linked_list":
            data = self._parse_array()
            current_canvas_vals = [nd["val"] for nd in self._linked_list_tracer.canvas._nodes]
            if current_canvas_vals != data:
                self._linked_list_tracer.show_initial(data)
            node_ids = list(self._linked_list_tracer.canvas.get_node_ids())
        else:
            node_ids = None

        try:
            run_fn = info["run"]
            input_type = info.get("input_type", "array")

            if input_type == "array":
                data = self._parse_array()
                if info.get("mode") == "linked_list":
                    target_fn = lambda: run_fn(self._engine, data, node_ids=node_ids)
                else:
                    target_fn = lambda: run_fn(self._engine, data)

            elif input_type == "array_target":
                data = self._parse_array()
                target_text = self._target_input.text().strip()
                if not target_text:
                    raise ValueError("Giá trị cần tìm kiếm/xóa/chèn không được để trống!")
                try:
                    target = int(target_text)
                except ValueError:
                    raise ValueError("Giá trị cần tìm kiếm/xóa/chèn phải là một số nguyên!")
                if info.get("mode") == "linked_list":
                    target_fn = lambda: run_fn(self._engine, data, target, node_ids=node_ids)
                else:
                    target_fn = lambda: run_fn(self._engine, data, target)

            elif input_type == "grid":
                grid_copy = [row[:] for row in self._grid_tracer.canvas._grid]
                target_fn = lambda: run_fn(self._engine, grid_copy, self._grid_rows, self._grid_cols)

            elif input_type == "ll_insert_idx":
                data = self._parse_array()
                target_str = self._target_input.text().strip()
                if not target_str:
                    raise ValueError("Chỉ số chèn và giá trị chèn không được để trống! Định dạng: index, value (ví dụ: 2, 9)")
                if "," not in target_str:
                    raise ValueError("Thiếu dấu phẩy! Định dạng chèn vị trí yêu cầu: index, value (ví dụ: 2, 9)")
                parts = target_str.split(",")
                if len(parts) != 2:
                    raise ValueError("Định dạng không hợp lệ! Vui lòng nhập: index, value (ví dụ: 2, 9)")
                try:
                    idx = int(parts[0].strip())
                    val = int(parts[1].strip())
                except ValueError:
                    raise ValueError("Chỉ số index và giá trị value phải là số nguyên!")
                target_fn = lambda: run_fn(self._engine, data, idx, val, node_ids=node_ids)

            else:
                return

            self._engine.start(target_fn)

        except Exception as e:
            self._log_tracer.log(f"❌ Lỗi: {e}")

    def _on_pause_resume(self):
        import time
        if self._engine.is_paused():
            self._start_time = time.monotonic()
            self._engine.resume()
            self._pause_btn.setText("⏸  Pause")
            self._stats_panel.lbl_status.setText("Running")
        else:
            if self._start_time > 0:
                self._accumulated_time += (time.monotonic() - self._start_time)
            self._start_time = 0.0
            self._engine.pause()
            self._pause_btn.setText("▶  Resume")
            self._stats_panel.lbl_status.setText("Paused")

    def _on_step(self):
        """Chế độ Step: pause rồi resume ngay để chạy 1 frame."""
        if not self._engine.is_running():
            self._on_run()
            self._engine.pause()
            self._pause_btn.setText("▶  Resume")
        else:
            self._engine.resume()
            QTimer.singleShot(self._speed_slider.value() + 50, self._engine.pause)

    def _on_reset(self):
        self._engine.stop()
        self._elapsed_update_timer.stop()
        
        self._stats_step = 0
        self._stats_compares = 0
        self._stats_swaps = 0
        self._stats_visited = 0
        self._stats_queue_size = 0
        self._stats_frontier_size = 0
        self._stats_path_length = 0
        self._stats_current_distance = 0.0
        self._stats_list_size = 0
        self._stats_current_node = "—"
        self._stats_current_value = "—"
        self._stats_current_index = "—"
        self._start_time = 0.0
        self._accumulated_time = 0.0
        self._total_steps = None
        
        self._stats_panel.reset()
        self._visual_status_lbl.setText("Sẵn sàng chạy thuật toán...")
        
        self._chart_tracer.reset()
        self._array_tracer.reset()
        self._grid_tracer.reset_overlay()
        self._linked_list_tracer.reset()
        self._log_tracer.reset()
        self._code_tracer.reset()
        self._run_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._pause_btn.setText("⏸  Pause")
        if self._current_algo_id:
            info = ALGO_LIBRARY[self._current_algo_id]
            tracers = info.get("tracers", [])
            if info.get("input_type") in ("array", "array_target", "ll_insert_idx"):
                try:
                    data = self._parse_array()
                    if "chart" in tracers:
                        self._chart_tracer.canvas.set_state(data=data)
                    elif "array1d" in tracers:
                        self._array_tracer.canvas.set_state(data=data)
                    elif "linked_list" in tracers:
                        self._linked_list_tracer.show_initial(data=data)
                except Exception:
                    pass

    # ── Frame Handler ─────────────────────────────────────────────────────────

    def _on_frame(self, payload: dict):
        """Nhận frame chuẩn hóa và dispatch đến các thành phần."""
        # Check if it's a command payload
        if 'method' in payload and 'key' in payload:
            self._handle_command_payload(payload)
            return

        algo = payload.get("algo", "")
        info = ALGO_LIBRARY.get(algo, {})
        tracers = info.get("tracers", [])

        # Tăng bước chạy
        self._stats_step += 1

        # Trích xuất dữ liệu frame chuẩn hóa
        data = payload.get("data", payload.get("array"))
        message = payload.get("message", payload.get("log", ""))
        current_line = payload.get("current_line", payload.get("line"))
        
        compare_indices = payload.get("compare_indices", payload.get("selected", []))
        swap_indices = payload.get("swap_indices", payload.get("patched", []))
        sorted_indices = payload.get("sorted_indices", payload.get("sorted", []))
        visited_indices = payload.get("visited_indices", [])

        # Cập nhật Visual Status Panel & Log
        if message:
            self._visual_status_lbl.setText(message)
            self._log_tracer.log(message)

        # Cập nhật code highlight
        if current_line is not None:
            self._code_tracer.highlight_line(current_line)

        # Cập nhật Canvas tương ứng
        if "chart" in tracers and data is not None:
            self._chart_tracer.canvas.set_state(
                data=data,
                compare_indices=compare_indices,
                swap_indices=swap_indices,
                sorted_indices=sorted_indices,
                pivot=payload.get("pivot")
            )
        elif "array1d" in tracers and data is not None:
            self._array_tracer.canvas.set_state(
                data=data,
                compare_indices=compare_indices,
                swap_indices=swap_indices,
                sorted_indices=sorted_indices,
                visited_indices=visited_indices
            )
        elif "grid" in tracers:
            self._grid_tracer.update_from_frame(payload)
        elif "linked_list" in tracers or payload.get("mode") == "linked_list":
            self._linked_list_tracer.on_frame_received(payload)

        # Đọc stats từ payload
        stats_payload = payload.get("stats", {})
        if stats_payload:
            self._stats_compares = stats_payload.get("comparisons", 0)
            self._stats_swaps = stats_payload.get("swaps", 0)
            self._stats_visited = stats_payload.get("visited_nodes", 0)
        
        # Fallback tính toán cơ bản và trích xuất stats động cho các visualizer
        if algo in ("bubble_sort", "selection_sort", "insertion_sort", "merge_sort", "quick_sort", "heap_sort"):
            if not stats_payload:
                if compare_indices:
                    self._stats_compares += 1
                if swap_indices:
                    self._stats_swaps += 1
        elif algo in ("linear_search", "binary_search"):
            if not stats_payload:
                if compare_indices:
                    self._stats_compares += 1
            # Lấy current index
            if compare_indices:
                self._stats_current_index = str(compare_indices[0])
            else:
                self._stats_current_index = "—"
        elif "grid" in tracers:
            if algo == "bfs":
                self._stats_queue_size = payload.get("queue_size", len(payload.get("frontier_nodes", [])))
                self._stats_visited = len(payload.get("visited_nodes", []))
                self._stats_path_length = max(0, len(payload.get("path_nodes", [])) - 1)
            elif algo == "dijkstra":
                self._stats_frontier_size = payload.get("frontier_size", len(payload.get("frontier_nodes", [])))
                self._stats_visited = len(payload.get("visited_nodes", []))
                self._stats_current_distance = payload.get("current_distance", 0.0)
                self._stats_path_length = max(0, len(payload.get("path_nodes", [])) - 1)
            else:
                self._stats_visited = len(payload.get("visited", []))
        elif payload.get("mode") == "linked_list":
            nodes = payload.get("nodes", [])
            self._stats_list_size = len(nodes)
            self._stats_current_node = str(nodes[0]["val"]) if nodes else "—"
            self._stats_current_value = str(nodes[-1]["val"]) if nodes else "—"
            
            op = payload.get("operation")
            insert_idx_val = payload.get("insert_index")
            new_node_val = payload.get("new_node_val")
            
            if op == "insert_head":
                self._stats_current_index = f"Chèn Đầu ({new_node_val})" if new_node_val is not None else "Chèn Đầu"
            elif op == "insert_tail":
                self._stats_current_index = f"Chèn Cuối ({new_node_val})" if new_node_val is not None else "Chèn Cuối"
            elif op == "insert_idx":
                idx_str = str(insert_idx_val) if insert_idx_val is not None else "?"
                val_str = f" ({new_node_val})" if new_node_val is not None else ""
                self._stats_current_index = f"Chèn vị trí {idx_str}{val_str}"
            elif op == "delete":
                self._stats_current_index = "Xóa Node"
            elif op == "search":
                self._stats_current_index = "Tìm kiếm"
            else:
                self._stats_current_index = "—"

        # Cập nhật stats panel
        self._update_elapsed_time_ui()

    def _update_elapsed_time_ui(self):
        import time
        elapsed = 0.0
        if self._start_time > 0:
            if self._engine.is_running() and not self._engine.is_paused():
                elapsed = self._accumulated_time + (time.monotonic() - self._start_time)
            else:
                elapsed = self._accumulated_time
        else:
            elapsed = self._accumulated_time

        algo_name = "Custom Code"
        if self._current_algo_id:
            algo_name = ALGO_LIBRARY[self._current_algo_id].get("name", "Thuật toán")

        status_str = "Running"
        if self._engine.is_paused():
            status_str = "Paused"
        elif not self._engine.is_running():
            status_str = "Finished"

        self._stats_panel.update_stats(
            algo_name=algo_name,
            status=status_str,
            step=self._stats_step,
            total_steps=self._total_steps,
            compares=self._stats_compares,
            swaps=self._stats_swaps,
            visited=self._stats_visited,
            elapsed_time=elapsed,
            algo_id=self._current_algo_id or "",
            queue_size=self._stats_queue_size,
            frontier_size=self._stats_frontier_size,
            path_length=self._stats_path_length,
            current_distance=self._stats_current_distance,
            list_size=self._stats_list_size,
            current_node=self._stats_current_node,
            current_value=self._stats_current_value,
            current_index=self._stats_current_index
        )

    def _handle_command_payload(self, payload: dict):
        """Handle command-based payload from custom code."""
        method = payload['method']
        args = payload.get('args', [])
        key = payload['key']

        # Map to tracer updates
        if method == 'set' and len(args) > 0:
            data = args[0]
            if isinstance(data, list):
                self._array_tracer.canvas.set_state(data=data)
        elif method == 'patch' and len(args) >= 2:
            index, value = args[0], args[1]
            self._array_tracer.canvas.set_state(data=self._array_tracer.canvas._data, swap_indices=[index])
            self._stats_swaps += 1
        elif method == 'select' and len(args) >= 1:
            indices = args if len(args) > 1 else [args[0]]
            self._array_tracer.canvas.set_state(data=self._array_tracer.canvas._data, compare_indices=indices)
            self._stats_compares += 1
        elif method == 'deselect':
            self._array_tracer.canvas.set_state(data=self._array_tracer.canvas._data, compare_indices=[])
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

    def _on_started(self):
        self._run_btn.setEnabled(False)
        self._pause_btn.setEnabled(True)
        self._pause_btn.setText("⏸  Pause")
        self._stats_panel.lbl_status.setText("Running")

    def _on_finished(self, msg: str):
        self._run_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._pause_btn.setText("⏸  Pause")
        
        # Dừng timer
        import time
        if self._start_time > 0:
            self._accumulated_time += (time.monotonic() - self._start_time)
        self._start_time = 0.0
        self._elapsed_update_timer.stop()

        icon = "✅" if msg == "done" else "⏹"
        self._log_tracer.log(f"{icon} {msg}")

        algo_name = "Thuật toán"
        if self._current_algo_id:
            algo_name = ALGO_LIBRARY[self._current_algo_id].get("name", "Thuật toán")

        if msg == "done":
            self._visual_status_lbl.setText(f"✅ Thuật toán {algo_name} đã hoàn tất thành công!")
            self._stats_panel.lbl_status.setText("Finished")
        else:
            self._visual_status_lbl.setText(f"⏹ Thuật toán đã dừng: {msg}")
            self._stats_panel.lbl_status.setText("Stopped")
            
        self._update_elapsed_time_ui()

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
        self._grid_tracer.canvas.reset_overlay()

    def _on_zoom_changed(self, index: int):
        val = self._zoom_combo.currentData()
        if val == "fit":
            self._grid_tracer.canvas.set_zoom("fit", 1.0)
        else:
            factor = float(val)
            self._grid_tracer.canvas.set_zoom("fixed", factor)

    def _on_show_index_toggled(self, checked: bool):
        self._linked_list_tracer.canvas.show_index = checked

    def _generate_random_maze(self):
        if self._engine.is_running():
            return
            
        def is_solvable(g: list[list[str]], rows: int, cols: int) -> bool:
            sr = sc = er = ec = 0
            found_s = found_e = False
            for r in range(rows):
                for c in range(cols):
                    if g[r][c] == "start":
                        sr, sc = r, c
                        found_s = True
                    elif g[r][c] == "end":
                        er, ec = r, c
                        found_e = True
            if not found_s or not found_e:
                return False
                
            from collections import deque
            q = deque([(sr, sc)])
            visited = {(sr, sc)}
            while q:
                curr_r, curr_c = q.popleft()
                if (curr_r, curr_c) == (er, ec):
                    return True
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = curr_r + dr, curr_c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        if g[nr][nc] != "wall" and (nr, nc) not in visited:
                            visited.add((nr, nc))
                            q.append((nr, nc))
            return False

        grid = self._grid_tracer.canvas._grid
        rows = self._grid_rows
        cols = self._grid_cols
        
        # 1. Thử tối đa 20 lần với mật độ 30%
        solvable = False
        for attempt in range(20):
            for r in range(rows):
                for c in range(cols):
                    if grid[r][c] not in ("start", "end"):
                        grid[r][c] = "wall" if random.random() < 0.3 else "empty"
            if is_solvable(grid, rows, cols):
                solvable = True
                break
                
        # 2. Fallback nếu sau 20 lần vẫn thất bại: sinh mật độ tường 10%
        if not solvable:
            for attempt in range(5):
                for r in range(rows):
                    for c in range(cols):
                        if grid[r][c] not in ("start", "end"):
                            grid[r][c] = "wall" if random.random() < 0.1 else "empty"
                if is_solvable(grid, rows, cols):
                    solvable = True
                    break
            # Nếu vẫn không được, xóa hết tường
            if not solvable:
                for r in range(rows):
                    for c in range(cols):
                        if grid[r][c] not in ("start", "end"):
                            grid[r][c] = "empty"
                            
        self._grid_tracer.canvas.reset_overlay()

    # ── Input helpers ─────────────────────────────────────────────────────────

    def _parse_array(self) -> list[int]:
        text = self._array_input.text().strip()
        if not text:
            raise ValueError("Mảng dữ liệu không được để trống!")
        try:
            vals = [int(x.strip()) for x in text.split(",") if x.strip()]
        except ValueError:
            raise ValueError("Mảng dữ liệu chỉ được chứa các số nguyên cách nhau bằng dấu phẩy!")
        if not vals:
            raise ValueError("Mảng dữ liệu trống!")
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

        # Reset interpreter & stats
        self._cmd_interpreter.reset()
        
        self._stats_step = 0
        self._stats_compares = 0
        self._stats_swaps = 0
        self._stats_visited = 0
        import time
        self._start_time = time.monotonic()
        self._accumulated_time = 0.0
        self._total_steps = None
        self._stats_panel.reset()
        self._elapsed_update_timer.start()

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

            # Get total steps from built commands list
            self._total_steps = len(algorithm_visualizer.Commander.commands)

            # Interpret commands
            self._cmd_interpreter.interpret_commands(algorithm_visualizer.Commander.commands)

            # Done
            self._elapsed_update_timer.stop()
            if self._start_time > 0:
                self._accumulated_time += (time.monotonic() - self._start_time)
            self._start_time = 0.0
            self._update_elapsed_time_ui()
            self._visual_status_lbl.setText("✅ Chạy Custom Code hoàn tất!")
            self._stats_panel.lbl_status.setText("Finished")

        except Exception as e:
            self._elapsed_update_timer.stop()
            self._start_time = 0.0
            self._log_tracer.log(f"Lỗi thực thi code: {e}")
            import traceback
            self._log_tracer.log(traceback.format_exc())
            self._visual_status_lbl.setText("❌ Lỗi Custom Code!")
            self._stats_panel.lbl_status.setText("Error")

    def _on_delay_request(self, delay: int):
        """Handle delay from command interpreter."""
        QTimer.singleShot(delay, lambda: None)  # Simple delay
