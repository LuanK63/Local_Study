"""
ui/tabs/tab_code.py — Tab sinh code từ mô tả tự nhiên.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QTextEdit,
)
from PyQt6.QtGui import QFont

from ui.widgets import CodeGenOutput, SectionHeader, StatusLabel
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
        layout.setSpacing(12)

        layout.addWidget(SectionHeader("Sinh mã"))

        hint = QLabel("Mô tả thuật toán hoặc bài toán cần viết code:")
        hint.setFont(QFont("Inter", 10))
        hint.setObjectName("CodeGenHint")
        layout.addWidget(hint)

        self.gen_input = QTextEdit()
        self.gen_input.setPlaceholderText(
            "Ví dụ: Viết thuật toán QuickSort bằng C++, có hàm main và in mảng sau khi sắp xếp"
        )
        self.gen_input.setFont(QFont("Inter", 10))
        self.gen_input.setFixedHeight(88)
        self.gen_input.setObjectName("CodeGenInput")
        layout.addWidget(self.gen_input)

        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)

        lang_lbl = QLabel("Ngôn ngữ")
        lang_lbl.setFont(QFont("Inter", 9))
        lang_lbl.setObjectName("CodeGenLangLabel")
        ctrl.addWidget(lang_lbl)

        self.gen_lang = QComboBox()
        self.gen_lang.addItems(["C++", "C", "Python"])
        self.gen_lang.setFixedHeight(34)
        self.gen_lang.setObjectName("CodeGenLangCombo")
        ctrl.addWidget(self.gen_lang)

        ctrl.addStretch()

        self.gen_btn = QPushButton("Tạo code")
        self.gen_btn.setObjectName("PrimaryBtn")
        self.gen_btn.setFixedSize(120, 34)
        self.gen_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.gen_btn.clicked.connect(self._on_generate)
        ctrl.addWidget(self.gen_btn)

        self.copy_btn = QPushButton("Sao chép")
        self.copy_btn.setFixedSize(100, 34)
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self._on_copy)
        ctrl.addWidget(self.copy_btn)

        layout.addLayout(ctrl)

        self.gen_status = StatusLabel()
        layout.addWidget(self.gen_status)

        out_lbl = QLabel("Kết quả")
        out_lbl.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        out_lbl.setObjectName("CodeGenOutLabel")
        layout.addWidget(out_lbl)

        self.gen_output = CodeGenOutput()
        layout.addWidget(self.gen_output, stretch=1)

        self.apply_theme_styles()

    def apply_theme_styles(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            for lbl in (self.findChild(QLabel, "CodeGenHint"),
                        self.findChild(QLabel, "CodeGenLangLabel"),
                        self.findChild(QLabel, "CodeGenOutLabel")):
                if lbl:
                    lbl.setStyleSheet(
                        f"color: {tokens['COLOR_TEXT_MUTED']}; background: transparent;"
                    )
            self.gen_input.setStyleSheet(f"""
                QTextEdit#CodeGenInput {{
                    background: {tokens["BG_WIDGET"]};
                    border: 1px solid {tokens["BORDER"]};
                    border-radius: 8px;
                    color: {tokens["COLOR_TEXT"]};
                    padding: 10px 12px;
                }}
                QTextEdit#CodeGenInput:focus {{
                    border-color: {tokens["COLOR_ACCENT"]};
                }}
            """)
            self.gen_lang.setStyleSheet(f"""
                QComboBox#CodeGenLangCombo {{
                    background: {tokens["BG_WIDGET"]};
                    border: 1px solid {tokens["BORDER"]};
                    border-radius: 6px;
                    padding: 4px 10px;
                    color: {tokens["COLOR_TEXT"]};
                    min-width: 90px;
                }}
            """)
            if hasattr(self.gen_output, "apply_theme_styles"):
                self.gen_output.apply_theme_styles()
        except Exception:
            pass

    def set_subject(self, subject_id: str, subject_config):
        self.subject_id = subject_id
        self.subject_cfg = subject_config

    def _lang_str(self) -> str:
        return {"C++": "cpp", "C": "c", "Python": "python"}[self.gen_lang.currentText()]

    def _on_generate(self):
        desc = self.gen_input.toPlainText().strip()
        if not desc:
            self.gen_status.set_error("Vui lòng nhập mô tả.")
            return

        lang = self._lang_str()
        self.gen_output.begin_streaming()
        self.gen_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.gen_status.set_loading()

        from modules.code_generator import generate_code_stream
        self._worker = StreamWorker(generate_code_stream, desc, lang)
        self._worker.token.connect(self.gen_output.append_token)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_finished)
        self._thread = run_in_thread(self._worker)

    def _on_error(self, err: str):
        self.gen_status.set_error(err)

    def _on_finished(self):
        self.gen_btn.setEnabled(True)
        self.gen_output.finalize()
        self.copy_btn.setEnabled(bool(self.gen_output._raw_text.strip()))
        self.gen_status.set_done()

    def _on_copy(self):
        from PyQt6.QtWidgets import QApplication
        text = self.gen_output._raw_text.strip()
        if text:
            QApplication.clipboard().setText(text)
