"""
ui/tabs/tab_code.py — M3 Code Explainer + M4 Code Generator tab
Split view: left = code editor, right = LLM output
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QComboBox, QLabel, QTabWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.widgets import CodeEditor, OutputDisplay, SectionHeader, StatusLabel
from ui.worker import StreamWorker, run_in_thread


class CodeTab(QWidget):
    def __init__(self, subject_id: str, subject_config, parent=None):
        super().__init__(parent)
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._thread = None
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        layout.addWidget(SectionHeader("💻 Code Generator & Explainer"))

        # Sub-tabs: Generator | Explainer | Complexity
        self.sub_tabs = QTabWidget()
        self.sub_tabs.setFont(QFont("Inter", 10))
        self.sub_tabs.addTab(self._build_generator(), "✨ Generator")
        self.sub_tabs.addTab(self._build_explainer(), "🔍 Explainer")
        self.sub_tabs.addTab(self._build_complexity(), "⏱ Complexity")
        layout.addWidget(self.sub_tabs)

    # ── Generator ─────────────────────────────────────────────────────────────
    def _build_generator(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Mô tả yêu cầu:"))

        from PyQt6.QtWidgets import QTextEdit
        self.gen_input = QTextEdit()
        self.gen_input.setPlaceholderText("Vd: Viết thuật toán QuickSort bằng C++")
        self.gen_input.setFont(QFont("Inter", 10))
        self.gen_input.setFixedHeight(80)
        self.gen_input.setStyleSheet(
            "background:#2a2b3d; border:1px solid #3a3c52; border-radius:6px; "
            "color:#cdd6f4; padding:8px;"
        )
        layout.addWidget(self.gen_input)

        # Controls
        ctrl = QHBoxLayout()
        self.gen_lang = QComboBox()
        self.gen_lang.addItems(["C++", "C", "Python"])
        self.gen_lang.setFixedHeight(36)
        ctrl.addWidget(QLabel("Ngôn ngữ:"))
        ctrl.addWidget(self.gen_lang)
        ctrl.addStretch()
        self.gen_btn = QPushButton("✨ Tạo code")
        self.gen_btn.setFixedSize(120, 36)
        self.gen_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.gen_btn.clicked.connect(self._on_generate)
        ctrl.addWidget(self.gen_btn)
        layout.addLayout(ctrl)

        self.gen_status = StatusLabel()
        layout.addWidget(self.gen_status)

        self.gen_output = OutputDisplay()
        layout.addWidget(self.gen_output)
        return w

    # ── Explainer ─────────────────────────────────────────────────────────────
    def _build_explainer(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: code input
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.addWidget(QLabel("Nhập code cần giải thích:"))
        self.exp_editor = CodeEditor("cpp")
        self.exp_editor.setMinimumHeight(300)
        ll.addWidget(self.exp_editor)
        exp_ctrl = QHBoxLayout()
        self.exp_lang = QComboBox()
        self.exp_lang.addItems(["C++", "C", "Python"])
        exp_ctrl.addWidget(QLabel("Ngôn ngữ:"))
        exp_ctrl.addWidget(self.exp_lang)
        exp_ctrl.addStretch()
        self.exp_btn = QPushButton("🔍 Giải thích")
        self.exp_btn.setFixedSize(120, 36)
        self.exp_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.exp_btn.clicked.connect(self._on_explain)
        exp_ctrl.addWidget(self.exp_btn)
        ll.addLayout(exp_ctrl)
        self.exp_status = StatusLabel()
        ll.addWidget(self.exp_status)
        splitter.addWidget(left)

        # Right: output
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.addWidget(QLabel("Kết quả giải thích:"))
        self.exp_output = OutputDisplay()
        rl.addWidget(self.exp_output)
        splitter.addWidget(right)

        splitter.setSizes([400, 500])
        layout.addWidget(splitter)
        return w

    # ── Complexity ────────────────────────────────────────────────────────────
    def _build_complexity(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Nhập code hoặc mô tả thuật toán:"))
        self.cplx_editor = CodeEditor("cpp")
        self.cplx_editor.setMinimumHeight(200)
        layout.addWidget(self.cplx_editor)

        ctrl = QHBoxLayout()
        ctrl.addStretch()
        self.cplx_btn = QPushButton("⏱ Phân tích Complexity")
        self.cplx_btn.setFixedSize(180, 36)
        self.cplx_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.cplx_btn.clicked.connect(self._on_complexity)
        ctrl.addWidget(self.cplx_btn)
        layout.addLayout(ctrl)

        self.cplx_status = StatusLabel()
        layout.addWidget(self.cplx_status)
        self.cplx_output = OutputDisplay()
        layout.addWidget(self.cplx_output)
        return w

    # ── Slots ─────────────────────────────────────────────────────────────────
    def set_subject(self, subject_id: str, subject_config):
        self.subject_id = subject_id
        self.subject_cfg = subject_config

    def _lang_str(self, combo: QComboBox) -> str:
        return {"C++": "cpp", "C": "c", "Python": "python"}[combo.currentText()]

    def _on_generate(self):
        desc = self.gen_input.toPlainText().strip()
        if not desc:
            return
        lang = self._lang_str(self.gen_lang)
        self.gen_output.clear_output()
        self.gen_btn.setEnabled(False)
        self.gen_status.set_loading()

        from modules.code_generator import generate_code_stream
        self._worker = StreamWorker(generate_code_stream, desc, lang)
        self._worker.token.connect(self.gen_output.append_token)
        self._worker.error.connect(lambda e: self.gen_status.set_error(e))
        self._worker.finished.connect(lambda: (
            self.gen_btn.setEnabled(True), self.gen_status.set_done()
        ))
        self._thread = run_in_thread(self._worker)

    def _on_explain(self):
        code = self.exp_editor.get_code().strip()
        if not code:
            return
        lang = self._lang_str(self.exp_lang)
        self.exp_output.clear_output()
        self.exp_btn.setEnabled(False)
        self.exp_status.set_loading()

        from modules.code_explainer import explain_code_stream
        self._worker = StreamWorker(explain_code_stream, code, lang)
        self._worker.token.connect(self.exp_output.append_token)
        self._worker.error.connect(lambda e: self.exp_status.set_error(e))
        self._worker.finished.connect(lambda: (
            self.exp_btn.setEnabled(True), self.exp_status.set_done()
        ))
        self._thread = run_in_thread(self._worker)

    def _on_complexity(self):
        code = self.cplx_editor.get_code().strip()
        if not code:
            return
        self.cplx_output.clear_output()
        self.cplx_btn.setEnabled(False)
        self.cplx_status.set_loading()

        from modules.complexity_analyzer import analyze_complexity_stream
        self._worker = StreamWorker(analyze_complexity_stream, code, True)
        self._worker.token.connect(self.cplx_output.append_token)
        self._worker.error.connect(lambda e: self.cplx_status.set_error(e))
        self._worker.finished.connect(lambda: (
            self.cplx_btn.setEnabled(True), self.cplx_status.set_done()
        ))
        self._thread = run_in_thread(self._worker)
