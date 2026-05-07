"""
ui/tabs/tab_visualize.py — M2 Algorithm Visualizer Tab
Step-by-step visualization of DSA algorithms.
No external dependencies — renders purely with PyQt6 widgets.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QComboBox, QLabel, QLineEdit,
    QScrollArea, QFrame, QSlider, QTreeWidget, QTreeWidgetItem,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush

from ui.widgets import SectionHeader, StatusLabel
from ui.worker import LLMWorker, run_in_thread


# ── Array Visualizer Widget ───────────────────────────────────────────────────
class ArrayVisualWidget(QWidget):
    """Renders an array as colored bars/boxes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(160)
        self._data: list[int | str] = []
        self._highlight: list[int] = []
        self._comparing: list[int] = []
        self._sorted: list[int] = []

    def set_state(self, array: list, highlight: list = None,
                  comparing: list = None, sorted_: list = None):
        self._data = array or []
        self._highlight = highlight or []
        self._comparing = comparing or []
        self._sorted = sorted_ or []
        self.update()

    def paintEvent(self, event):
        if not self._data:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        n = len(self._data)
        if n == 0:
            return

        cell_w = min(72, (w - 20) // n)
        cell_h = 56
        start_x = (w - cell_w * n) // 2
        y = (h - cell_h) // 2

        for i, val in enumerate(self._data):
            x = start_x + i * cell_w

            # Pick color
            if i in self._comparing:
                bg = QColor("#f38ba8")   # red — comparing
            elif i in self._highlight:
                bg = QColor("#f9e2af")   # yellow — highlighted
            elif i in self._sorted:
                bg = QColor("#a6e3a1")   # green — sorted
            else:
                bg = QColor("#313244")   # default

            painter.setBrush(QBrush(bg))
            painter.setPen(QPen(QColor("#45475a"), 1))
            painter.drawRoundedRect(x + 2, y, cell_w - 4, cell_h, 6, 6)

            # Draw value
            painter.setPen(QPen(QColor("#1e1e2e") if i in (self._comparing + self._highlight + self._sorted) else QColor("#cdd6f4")))
            painter.setFont(QFont("Consolas", 13, QFont.Weight.Bold))
            painter.drawText(x + 2, y, cell_w - 4, cell_h,
                             Qt.AlignmentFlag.AlignCenter, str(val))

            # Draw index
            painter.setPen(QPen(QColor("#6c7086")))
            painter.setFont(QFont("Consolas", 9))
            painter.drawText(x + 2, y + cell_h + 2, cell_w - 4, 16,
                             Qt.AlignmentFlag.AlignCenter, f"[{i}]")


# ── Main Visualizer Tab ───────────────────────────────────────────────────────
class VisualizeTab(QWidget):
    def __init__(self, subject_id: str, subject_config, parent=None):
        super().__init__(parent)
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._steps: list[dict] = []
        self._current_step = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._auto_next)
        self._thread = None
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        layout.addWidget(SectionHeader("🌳 Algorithm Visualizer"))

        # ── Config row ─────────────────────────────────────────────────────────
        cfg = QHBoxLayout()

        # Algorithm selector — grouped by category
        cfg.addWidget(QLabel("Thuật toán:"))
        self.algo_combo = QComboBox()
        self.algo_combo.setMinimumWidth(200)
        self.algo_combo.setFixedHeight(36)
        self._populate_algo_combo()
        cfg.addWidget(self.algo_combo)

        # Input
        cfg.addWidget(QLabel("Input (cách nhau bởi dấu phẩy):"))
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Vd: 5, 3, 8, 1, 9, 2")
        self.input_field.setText("5, 3, 8, 1, 9, 2")
        self.input_field.setFixedHeight(36)
        self.input_field.setMinimumWidth(200)
        self.input_field.setStyleSheet(
            "background:#313244; border:1px solid #45475a; border-radius:6px; "
            "color:#cdd6f4; padding:0 10px;"
        )
        cfg.addWidget(self.input_field)

        cfg.addStretch()
        self.gen_btn = QPushButton("▶ Tạo Simulation")
        self.gen_btn.setFixedSize(150, 36)
        self.gen_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.gen_btn.setStyleSheet(
            "background:#cba6f7; color:#1e1e2e; border-radius:6px; font-weight:bold;"
        )
        self.gen_btn.clicked.connect(self._generate)
        cfg.addWidget(self.gen_btn)
        layout.addLayout(cfg)

        self.status = StatusLabel()
        layout.addWidget(self.status)

        # ── Main content (hidden until generated) ──────────────────────────────
        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setSpacing(10)

        # Complexity banner
        self.complexity_label = QLabel("")
        self.complexity_label.setFont(QFont("Segoe UI", 10))
        self.complexity_label.setStyleSheet(
            "background:#313244; border-radius:6px; padding:6px 12px; color:#cba6f7;"
        )
        content_layout.addWidget(self.complexity_label)

        # Array visualizer
        self.array_widget = ArrayVisualWidget()
        self.array_widget.setStyleSheet(
            "background:#1e1e2e; border:1px solid #313244; border-radius:8px;"
        )
        content_layout.addWidget(self.array_widget)

        # Step info
        step_info_row = QHBoxLayout()
        self.step_label = QLabel("Bước 0 / 0")
        self.step_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.step_label.setStyleSheet("color:#cba6f7;")
        step_info_row.addWidget(self.step_label)
        step_info_row.addStretch()
        content_layout.addLayout(step_info_row)

        self.step_title = QLabel("")
        self.step_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        content_layout.addWidget(self.step_title)

        self.step_desc = QLabel("")
        self.step_desc.setFont(QFont("Segoe UI", 10))
        self.step_desc.setWordWrap(True)
        self.step_desc.setStyleSheet(
            "background:#313244; border-radius:6px; padding:10px; color:#cdd6f4;"
        )
        content_layout.addWidget(self.step_desc)

        # Legend
        legend = QHBoxLayout()
        for color, text in [
            ("#f38ba8", "Đang so sánh"),
            ("#f9e2af", "Đang chú ý"),
            ("#a6e3a1", "Đã sắp xếp / Hoàn thành"),
            ("#313244", "Chưa xử lý"),
        ]:
            dot = QLabel(f"● {text}")
            dot.setFont(QFont("Segoe UI", 9))
            dot.setStyleSheet(f"color:{color};")
            legend.addWidget(dot)
        legend.addStretch()
        content_layout.addLayout(legend)

        # ── Controls ────────────────────────────────────────────────────────
        controls = QHBoxLayout()

        self.prev_btn = QPushButton("◀ Trước")
        self.prev_btn.setFixedSize(100, 36)
        self.prev_btn.clicked.connect(self._prev_step)
        controls.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Sau ▶")
        self.next_btn.setFixedSize(100, 36)
        self.next_btn.clicked.connect(self._next_step)
        controls.addWidget(self.next_btn)

        self.play_btn = QPushButton("⏵ Tự động")
        self.play_btn.setFixedSize(110, 36)
        self.play_btn.setCheckable(True)
        self.play_btn.clicked.connect(self._toggle_play)
        controls.addWidget(self.play_btn)

        controls.addWidget(QLabel("Tốc độ:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(200, 2000)
        self.speed_slider.setValue(1000)
        self.speed_slider.setFixedWidth(120)
        self.speed_slider.setInvertedAppearance(True)  # left=fast, right=slow
        controls.addWidget(self.speed_slider)

        controls.addStretch()

        self.step_counter = QLabel("0 / 0")
        self.step_counter.setFont(QFont("Segoe UI", 10))
        self.step_counter.setStyleSheet("color:#6c7086;")
        controls.addWidget(self.step_counter)

        content_layout.addLayout(controls)

        self.content.hide()
        layout.addWidget(self.content)
        layout.addStretch()

    def _populate_algo_combo(self):
        from modules.algorithm_visualizer import get_algo_categories
        for category, algos in get_algo_categories().items():
            # Add separator item as disabled
            sep_item = self.algo_combo.count()
            self.algo_combo.addItem(f"── {category} ──")
            # Disable separator
            model = self.algo_combo.model()
            from PyQt6.QtGui import QStandardItem
            item = model.item(sep_item)
            if item:
                item.setEnabled(False)
                item.setForeground(QColor("#6c7086"))

            for algo_id, algo_name in algos:
                self.algo_combo.addItem(algo_name, algo_id)

    def set_subject(self, subject_id: str, subject_config):
        self.subject_id = subject_id
        self.subject_cfg = subject_config

    def _get_selected_algo(self) -> tuple[str, str]:
        """Return (algo_id, algo_name). Skip separators."""
        idx = self.algo_combo.currentIndex()
        data = self.algo_combo.itemData(idx)
        text = self.algo_combo.currentText()
        if data is None:  # separator selected, find next valid
            return "", text
        return data, text

    def _generate(self):
        algo_id, algo_name = self._get_selected_algo()
        if not algo_id:
            self.status.set_error("Hãy chọn một thuật toán hợp lệ.")
            return

        input_data = self.input_field.text().strip()
        if not input_data:
            self.status.set_error("Hãy nhập dữ liệu đầu vào.")
            return

        self.gen_btn.setEnabled(False)
        self.content.hide()
        self._timer.stop()
        self.play_btn.setChecked(False)
        self.status.set_loading(f"Đang tạo simulation cho {algo_name}...")

        def _gen():
            from modules.algorithm_visualizer import generate_steps
            return generate_steps(algo_id, input_data)

        self._worker = LLMWorker(_gen)
        self._worker.result.connect(self._on_steps_ready)
        self._worker.error.connect(lambda e: (
            self.status.set_error(e), self.gen_btn.setEnabled(True)
        ))
        self._worker.finished.connect(lambda: self.gen_btn.setEnabled(True))
        self._thread = run_in_thread(self._worker)

    def _on_steps_ready(self, data: dict):
        if "error" in data:
            self.status.set_error(data["error"])
            return

        self._steps = data.get("steps", [])
        if not self._steps:
            self.status.set_error("Không có bước nào được tạo. Thử lại!")
            return

        # Show complexity
        cplx = data.get("complexity", {})
        self.complexity_label.setText(
            f"⏱ Time: {cplx.get('time', '?')}   💾 Space: {cplx.get('space', '?')}   "
            f"• {data.get('summary', '')}"
        )

        self._current_step = 0
        self.content.show()
        self._show_step()
        self.status.set_done(f"Tạo xong {len(self._steps)} bước!")

    def _show_step(self):
        if not self._steps:
            return
        step = self._steps[self._current_step]
        total = len(self._steps)

        self.step_label.setText(f"Bước {self._current_step + 1} / {total}")
        self.step_counter.setText(f"{self._current_step + 1} / {total}")
        self.step_title.setText(step.get("title", ""))
        self.step_desc.setText(
            step.get("description", "") +
            (f"\n\n💡 {step['note']}" if step.get("note") else "")
        )

        # Update array widget
        arr = step.get("array_state")
        if arr is not None:
            self.array_widget.set_state(
                arr,
                highlight=step.get("highlight", []),
                comparing=step.get("comparing", []),
                sorted_=step.get("sorted", []),
            )

        self.prev_btn.setEnabled(self._current_step > 0)
        self.next_btn.setEnabled(self._current_step < total - 1)

    def _prev_step(self):
        if self._current_step > 0:
            self._current_step -= 1
            self._show_step()

    def _next_step(self):
        if self._current_step < len(self._steps) - 1:
            self._current_step += 1
            self._show_step()

    def _toggle_play(self, checked: bool):
        if checked:
            speed = self.speed_slider.value()
            self._timer.start(speed)
            self.play_btn.setText("⏸ Dừng")
        else:
            self._timer.stop()
            self.play_btn.setText("⏵ Tự động")

    def _auto_next(self):
        if self._current_step < len(self._steps) - 1:
            self._current_step += 1
            self._show_step()
        else:
            self._timer.stop()
            self.play_btn.setChecked(False)
            self.play_btn.setText("⏵ Tự động")
