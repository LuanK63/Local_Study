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
        self._log_tracer    = LogTracer("Nhật ký")
        self._code_tracer   = CodeTracer("Mã giả")

        self._grid_tracer.cell_clicked.connect(self._on_grid_cell_clicked)

        self._build_ui()
        self.apply_theme_styles()
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

        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.setHandleWidth(2)

        self._sidebar_widget = self._build_sidebar()
        self._main_splitter.addWidget(self._sidebar_widget)
        self._main_splitter.addWidget(self._build_center())
        self._main_splitter.addWidget(self._build_right_panel())

        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 4)
        self._main_splitter.setStretchFactor(2, 2)
        self._main_splitter.setSizes([200, 720, 300])

        root.addWidget(self._main_splitter)

    def _build_playback_controls(self) -> QWidget:
        """Nút điều khiển chạy / tạm dừng / bước / đặt lại + thanh tốc độ."""
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._run_btn = _btn("Chạy", "#a6e3a1", "#11111b", "#b4f4af", h=34)
        self._run_btn.setToolTip("Chạy thuật toán")
        self._pause_btn = _btn("Tạm dừng", "#313244", "#cdd6f4", "#45475a", h=32, bold=False)
        self._pause_btn.setToolTip("Tạm dừng / tiếp tục")
        self._step_btn = _btn("Bước", "#313244", "#cdd6f4", "#45475a", h=32, bold=False)
        self._step_btn.setToolTip("Chạy từng bước")
        self._reset_btn = _btn("Đặt lại", "#313244", "#cdd6f4", "#45475a", h=32, bold=False)
        self._reset_btn.setToolTip("Đặt lại về trạng thái ban đầu")
        self._pause_btn.setEnabled(False)

        for b in (self._run_btn, self._pause_btn, self._step_btn, self._reset_btn):
            layout.addWidget(b)

        layout.addSpacing(6)

        speed_lbl = QLabel("Tốc độ")
        speed_lbl.setObjectName("SpeedLabel")
        speed_lbl.setFont(QFont("Segoe UI", 9))
        layout.addWidget(speed_lbl)

        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(30, 1200)
        self._speed_slider.setValue(500)
        self._speed_slider.setInvertedAppearance(True)
        self._speed_slider.setFixedWidth(90)
        self._speed_slider.setObjectName("SpeedSlider")
        layout.addWidget(self._speed_slider)

        return wrap

    # ── SIDEBAR ───────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("background:#181825; border-right:1px solid #3a3c52;")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("Thuật toán")
        header.setObjectName("SidebarHeader")
        header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        header.setContentsMargins(12, 10, 12, 4)
        layout.addWidget(header)

        search_wrap = QWidget()
        self._search_wrap = search_wrap
        search_wrap.setStyleSheet("background:#181825;")
        sw_layout = QHBoxLayout(search_wrap)
        sw_layout.setContentsMargins(10, 0, 10, 6)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Tìm kiếm...")
        self._search_box.setFixedHeight(30)
        self._search_box.setFont(QFont("Segoe UI", 9))
        sw_layout.addWidget(self._search_box)
        layout.addWidget(search_wrap)

        self._algo_list = QListWidget()
        self._algo_list.setStyleSheet(_SIDEBAR_ITEM_STYLE)
        self._algo_list.setFont(QFont("Segoe UI", 10))
        self._algo_list.setSpacing(1)
        self._populate_algo_list()
        layout.addWidget(self._algo_list, stretch=1)
        return sidebar

    def _populate_algo_list(self, filter_text: str = ""):
        self._algo_list.clear()
        cats = get_categories()
        for cat, algos in cats.items():
            # Category header
            header = QListWidgetItem(cat)
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            header.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            try:
                from ui.theme_manager import get_theme, PALETTES
                c_muted = PALETTES[get_theme()]["COLOR_TEXT_MUTED"]
            except Exception:
                c_muted = "#6c7086"
            header.setForeground(QColor(c_muted))
            header.setData(Qt.ItemDataRole.UserRole, None)
            self._algo_list.addItem(header)

            for aid, aname in algos:
                if filter_text and filter_text.lower() not in aname.lower():
                    continue
                item = QListWidgetItem(f"  {aname}")
                item.setData(Qt.ItemDataRole.UserRole, aid)
                self._algo_list.addItem(item)

    def _build_input_panel(self) -> QWidget:
        """Thanh nhập liệu ngang phía trên vùng trực quan hóa."""
        frame = QFrame()
        self._input_panel_frame = frame
        frame.setObjectName("InputPanel")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(8)

        array_lbl = QLabel("Mảng")
        array_lbl.setFont(QFont("Segoe UI", 9))
        array_lbl.setObjectName("InputLabel")
        self._array_lbl = array_lbl
        row1.addWidget(array_lbl)

        self._array_input = QLineEdit("5, 3, 8, 1, 9, 2, 7, 4, 6")
        self._array_input.setPlaceholderText("VD: 5, 3, 8, 1, 9")
        self._array_input.setFixedHeight(30)
        row1.addWidget(self._array_input, stretch=1)

        self._target_lbl = QLabel("Giá trị")
        self._target_lbl.setFont(QFont("Segoe UI", 9))
        self._target_lbl.setObjectName("InputLabel")
        row1.addWidget(self._target_lbl)

        self._target_input = QLineEdit("7")
        self._target_input.setPlaceholderText("Target")
        self._target_input.setFixedHeight(30)
        self._target_input.setFixedWidth(72)
        self._target_input.setValidator(QIntValidator(-9999, 9999))
        row1.addWidget(self._target_input)

        rand_btn = _btn("Ngẫu nhiên", "#313244", "#cdd6f4", "#45475a", h=30, bold=False)
        rand_btn.clicked.connect(self._randomize_input)
        row1.addWidget(rand_btn)

        outer.addLayout(row1)

        self._grid_mode_group = QGroupBox("Lưới — chọn chế độ vẽ")
        self._grid_mode_group.setObjectName("GridModeGroup")
        gm_outer = QHBoxLayout(self._grid_mode_group)
        gm_outer.setContentsMargins(8, 4, 8, 6)
        gm_outer.setSpacing(10)

        self._mode_wall = QRadioButton("Tường")
        self._mode_start = QRadioButton("Start")
        self._mode_end = QRadioButton("End")
        self._mode_wall.setChecked(True)
        for rb in (self._mode_wall, self._mode_start, self._mode_end):
            rb.setFont(QFont("Segoe UI", 9))
            gm_outer.addWidget(rb)

        clear_walls_btn = _btn("Xóa tường", "#313244", "#cdd6f4", "#45475a", h=28, bold=False)
        clear_walls_btn.clicked.connect(self._clear_walls)
        gm_outer.addWidget(clear_walls_btn)

        self._maze_btn = _btn("Mê cung", "#313244", "#cdd6f4", "#45475a", h=28, bold=False)
        self._maze_btn.setToolTip("Sinh mê cung ngẫu nhiên")
        self._maze_btn.clicked.connect(self._generate_random_maze)
        gm_outer.addWidget(self._maze_btn)

        self._zoom_combo = QComboBox()
        self._zoom_combo.setFont(QFont("Segoe UI", 8))
        self._zoom_combo.addItem("Vừa cửa sổ", "fit")
        self._zoom_combo.addItem("Nhỏ", "0.75")
        self._zoom_combo.addItem("Vừa", "1.0")
        self._zoom_combo.addItem("Lớn", "1.5")
        self._zoom_combo.setCurrentIndex(0)
        self._zoom_combo.currentIndexChanged.connect(self._on_zoom_changed)
        gm_outer.addWidget(self._zoom_combo)
        gm_outer.addStretch()

        self._grid_mode_group.setVisible(False)
        outer.addWidget(self._grid_mode_group)

        self._show_index_cb = QCheckBox("Hiện chỉ số")
        self._show_index_cb.setChecked(False)
        self._show_index_cb.toggled.connect(self._on_show_index_toggled)
        self._show_index_cb.setVisible(False)
        outer.addWidget(self._show_index_cb)

        return frame

    # ── CENTER PANEL ──────────────────────────────────────────────────────────

    def _build_center(self) -> QWidget:
        self._center = QWidget()
        self._center.setStyleSheet("background:#1d1d2b;")
        self._center_layout = QVBoxLayout(self._center)
        self._center_layout.setContentsMargins(14, 12, 10, 10)
        self._center_layout.setSpacing(10)

        header = QWidget()
        header.setObjectName("CenterHeader")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self._algo_title_lbl = QLabel("Chọn thuật toán bên trái")
        self._algo_title_lbl.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title_col.addWidget(self._algo_title_lbl)

        self._complexity_lbl = QLabel("")
        self._complexity_lbl.setObjectName("ComplexityLabel")
        self._complexity_lbl.setFont(QFont("Consolas", 9))
        title_col.addWidget(self._complexity_lbl)
        h_layout.addLayout(title_col, stretch=1)

        h_layout.addWidget(self._build_playback_controls())
        self._center_layout.addWidget(header)

        self._center_layout.addWidget(self._build_input_panel())

        self._tracer_stack = QStackedWidget()
        self._tracer_stack.addWidget(self._chart_tracer)
        self._tracer_stack.addWidget(self._array_tracer)
        self._tracer_stack.addWidget(self._grid_tracer)
        self._tracer_stack.addWidget(self._linked_list_tracer)
        self._center_layout.addWidget(self._tracer_stack, stretch=1)

        self._log_tracer.setMinimumHeight(64)
        self._log_tracer.setMaximumHeight(100)
        self._center_layout.addWidget(self._log_tracer, stretch=0)

        return self._center

    # ── RIGHT PANEL ───────────────────────────────────────────────────────────

    def _build_right_panel(self) -> QWidget:
        right = QWidget()
        self._right_panel = right
        right.setStyleSheet("background:#181825; border-left:1px solid #313244;")
        layout = QVBoxLayout(right)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._code_tracer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self._code_tracer, stretch=3)

        from modules.visualizer.tracers import StatisticsPanel
        self._stats_panel = StatisticsPanel(parent=self)
        layout.addWidget(self._stats_panel, stretch=2)

        return right

    def apply_theme_styles(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            theme = get_theme()
            tokens = PALETTES[theme]
            
            # Apply _MAIN_STYLE translation
            main_qss = f"""
                QWidget#VisualizerController {{
                    background: {tokens["BG_MAIN"]};
                    color: {tokens["COLOR_TEXT"]};
                    font-family: 'Segoe UI';
                }}
                QSplitter::handle {{
                    background: {tokens["BORDER"]};
                }}
                QLineEdit {{
                    background: {tokens["BG_SIDEBAR"]};
                    border: 1px solid {tokens["BORDER"]};
                    border-radius: 6px;
                    color: {tokens["COLOR_TEXT"]};
                    padding: 4px 10px;
                }}
                QLineEdit:hover {{
                    border-color: {tokens["BORDER_HOVER"]};
                }}
                QLineEdit:focus {{
                    border-color: {tokens["COLOR_ACCENT"]};
                }}
                QLabel {{
                    color: {tokens["COLOR_TEXT"]};
                }}
                QScrollArea {{
                    border: none;
                    background: transparent;
                }}
            """
            self.setStyleSheet(main_qss)

            if hasattr(self, "_algo_title_lbl"):
                self._algo_title_lbl.setStyleSheet(
                    f"color: {tokens['COLOR_TEXT_TITLE']}; font-weight: bold; background: transparent;"
                )
            if hasattr(self, "_complexity_lbl"):
                self._complexity_lbl.setStyleSheet(
                    f"color: {tokens['COLOR_TEXT_MUTED']}; background: transparent;"
                )

            if hasattr(self, "_sidebar_widget"):
                self._sidebar_widget.setStyleSheet(f"""
                    background: {tokens["BG_SIDEBAR"]};
                    border-right: 1px solid {tokens["BORDER"]};
                """)

            for hdr in self.findChildren(QLabel, "SidebarHeader"):
                hdr.setStyleSheet(
                    f"color: {tokens['COLOR_TEXT_MUTED']}; background: transparent; padding: 0;"
                )

            if hasattr(self, "_search_wrap"):
                self._search_wrap.setStyleSheet(f"background: {tokens['BG_SIDEBAR']};")

            self._algo_list.setStyleSheet(f"""
                QListWidget {{
                    background: {tokens["BG_SIDEBAR"]};
                    border: none;
                    outline: 0;
                    color: {tokens["COLOR_TEXT"]};
                    font-size: 10px;
                }}
                QListWidget::item {{
                    padding: 6px 10px;
                    border-radius: 4px;
                }}
                QListWidget::item:selected {{
                    background: {tokens["BG_CHECKED"]};
                    color: {tokens["COLOR_ACCENT"]};
                    font-weight: bold;
                }}
                QListWidget::item:hover:!selected {{
                    background: {tokens["BG_HOVER"]};
                }}
            """)

            if hasattr(self, "_input_panel_frame"):
                self._input_panel_frame.setStyleSheet(f"""
                    QWidget#InputPanel {{
                        background: {tokens["BG_WIDGET"]};
                        border: 1px solid {tokens["BORDER"]};
                        border-radius: 8px;
                        padding: 4px;
                    }}
                """)

            for lbl in self.findChildren(QLabel, "InputLabel"):
                lbl.setStyleSheet(f"color: {tokens['COLOR_TEXT_MUTED']}; background: transparent;")

            if hasattr(self, "_grid_mode_group"):
                self._grid_mode_group.setStyleSheet(f"""
                    QGroupBox#GridModeGroup {{
                        border: 1px solid {tokens["BORDER"]};
                        border-radius: 6px;
                        margin-top: 4px;
                        padding-top: 6px;
                        color: {tokens["COLOR_TEXT_MUTED"]};
                        font-size: 9px;
                    }}
                    QGroupBox::title {{
                        subcontrol-origin: margin;
                        left: 8px;
                    }}
                """)
                for rb in (self._mode_wall, self._mode_start, self._mode_end):
                    rb.setStyleSheet(f"color: {tokens['COLOR_TEXT']};")

            if hasattr(self, "_zoom_combo"):
                self._zoom_combo.setStyleSheet(f"""
                    QComboBox {{
                        background: {tokens["BG_SIDEBAR"]};
                        color: {tokens["COLOR_TEXT"]};
                        border: 1px solid {tokens["BORDER"]};
                        border-radius: 4px;
                        padding: 2px 6px;
                        min-width: 72px;
                    }}
                    QComboBox QAbstractItemView {{
                        background: {tokens["BG_SIDEBAR"]};
                        color: {tokens["COLOR_TEXT"]};
                        selection-background-color: {tokens["BG_HOVER"]};
                        selection-color: {tokens["COLOR_ACCENT"]};
                    }}
                """)

            if hasattr(self, "_show_index_cb"):
                self._show_index_cb.setStyleSheet(
                    f"color: {tokens['COLOR_TEXT']}; font-family: 'Segoe UI'; font-size: 9pt;"
                )

            if hasattr(self, "_center"):
                self._center.setStyleSheet(f"background: {tokens['BG_MAIN']};")

            if hasattr(self, "_right_panel"):
                self._right_panel.setStyleSheet(
                    f"background: {tokens['BG_SIDEBAR']}; border-left: 1px solid {tokens['BORDER']};"
                )

            for lbl in self.findChildren(QLabel, "SpeedLabel"):
                lbl.setStyleSheet(f"color: {tokens['COLOR_TEXT_MUTED']}; font-size: 9px;")

            if hasattr(self, "_speed_slider"):
                self._speed_slider.setStyleSheet(f"""
                    QSlider#SpeedSlider::groove:horizontal {{
                        height: 4px;
                        background: {tokens["BORDER"]};
                        border-radius: 2px;
                    }}
                    QSlider#SpeedSlider::handle:horizontal {{
                        background: {tokens["COLOR_ACCENT"]};
                        width: 12px;
                        height: 12px;
                        margin: -4px 0;
                        border-radius: 6px;
                    }}
                """)

            self._restyle_button(self._run_btn, tokens["COLOR_GREEN"], "#FFFFFF", tokens["COLOR_ACCENT_HOVER"])
            self._restyle_button(self._pause_btn, tokens["BG_WIDGET"], tokens["COLOR_TEXT"], tokens["BG_HOVER"])
            self._restyle_button(self._step_btn, tokens["BG_WIDGET"], tokens["COLOR_TEXT"], tokens["BG_HOVER"])
            self._restyle_button(self._reset_btn, tokens["BG_WIDGET"], tokens["COLOR_TEXT"], tokens["BG_HOVER"])
            
            # Update active/highlighted text if custom pages or widgets are selected
            # Propagate theme change down to child tracers
            for tracer in (self._chart_tracer, self._array_tracer, self._grid_tracer, 
                           self._linked_list_tracer, self._log_tracer, self._code_tracer):
                if hasattr(tracer, "apply_theme_styles"):
                    tracer.apply_theme_styles()
                    
            if hasattr(self, "_stats_panel") and self._stats_panel:
                self._stats_panel.apply_theme_styles()

            if hasattr(self, "_grid_tracer") and self._grid_tracer:
                self._grid_tracer.apply_theme_styles()
                
        except Exception as e:
            print(f"[WARN] Failed to apply theme styles in visualizer: {e}")

    def _restyle_button(self, btn, bg: str, fg: str, hover: str):
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {bg};
                    color: {fg};
                    border: none;
                    border-radius: 6px;
                    padding: 0 14px;
                }}
                QPushButton:hover {{
                    background: {hover};
                }}
                QPushButton:disabled {{
                    background: {tokens["BG_HOVER"]};
                    color: {tokens["COLOR_TEXT_DISABLED"]};
                }}
            """)
        except Exception:
            pass

    # ── Connect Signals ───────────────────────────────────────────────────────

    def _connect_signals(self):
        self._run_btn.clicked.connect(self._on_run)
        self._pause_btn.clicked.connect(self._on_pause_resume)
        self._step_btn.clicked.connect(self._on_step)
        self._reset_btn.clicked.connect(self._on_reset)
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
        self._stats_panel.lbl_status.setText("Sẵn sàng")

        self._algo_title_lbl.setText(info["name"])
        cplx = info.get("complexity", {})
        time_c = cplx.get("time", "—")
        space_c = cplx.get("space", "—")
        self._complexity_lbl.setText(f"Thời gian: {time_c}   ·   Bộ nhớ: {space_c}")

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
        self._array_lbl.setVisible(not is_grid)

        is_ll = "linked_list" in tracers
        self._show_index_cb.setVisible(is_ll)

        input_type = info.get("input_type")
        show_target = input_type in ("array_target", "ll_insert_idx")
        self._target_input.setVisible(show_target)
        self._target_lbl.setVisible(show_target and not is_grid)
        if input_type == "ll_insert_idx":
            self._target_input.setValidator(None)
            self._target_input.setPlaceholderText("Vị trí, Giá trị (VD: 2, 9)")
        else:
            self._target_input.setValidator(QIntValidator(-9999, 9999))
            self._target_input.setPlaceholderText("Target (tìm kiếm/xóa)")

        # Load code
        self._code_tracer.set_code(info.get("code", "# no pseudocode"))
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
        self._pause_btn.setText("Tạm dừng")
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
            self._pause_btn.setText("Tạm dừng")
            self._stats_panel.lbl_status.setText("Đang chạy")
        else:
            if self._start_time > 0:
                self._accumulated_time += (time.monotonic() - self._start_time)
            self._start_time = 0.0
            self._engine.pause()
            self._pause_btn.setText("Tiếp tục")
            self._stats_panel.lbl_status.setText("Tạm dừng")

    def _on_step(self):
        """Chế độ Step: pause rồi resume ngay để chạy 1 frame."""
        if not self._engine.is_running():
            self._on_run()
            self._engine.pause()
            self._pause_btn.setText("Tiếp tục")
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
        self._stats_panel.lbl_status.setText("Sẵn sàng")
        
        self._chart_tracer.reset()
        self._array_tracer.reset()
        self._grid_tracer.reset_overlay()
        self._linked_list_tracer.reset()
        self._log_tracer.reset()
        self._code_tracer.reset()
        self._run_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._pause_btn.setText("Tạm dừng")
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

        status_str = "Đang chạy"
        if self._engine.is_paused():
            status_str = "Tạm dừng"
        elif not self._engine.is_running():
            status_str = "Hoàn tất"

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
        self._pause_btn.setText("Tạm dừng")
        self._stats_panel.lbl_status.setText("Đang chạy")

    def _on_finished(self, msg: str):
        self._run_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._pause_btn.setText("Tạm dừng")
        
        # Dừng timer
        import time
        if self._start_time > 0:
            self._accumulated_time += (time.monotonic() - self._start_time)
        self._start_time = 0.0
        self._elapsed_update_timer.stop()

        icon = "Xong" if msg == "done" else "Dừng"
        self._log_tracer.log(f"[{icon}] {msg}")

        algo_name = "Thuật toán"
        if self._current_algo_id:
            algo_name = ALGO_LIBRARY[self._current_algo_id].get("name", "Thuật toán")

        if msg == "done":
            self._stats_panel.lbl_status.setText("Hoàn tất")
        else:
            self._stats_panel.lbl_status.setText("Đã dừng")
            
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

        if not self._engine.is_running():
            self._grid_tracer.canvas._overlay.clear()
        self._grid_tracer.canvas.refresh_from_grid()

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

    def _on_delay_request(self, delay: int):
        """Handle delay from command interpreter."""
        QTimer.singleShot(delay, lambda: None)
