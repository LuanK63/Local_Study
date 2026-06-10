"""
ui/tabs/tab_path.py — M10 Learning Path Tab
Generate personalized learning roadmap based on subject topics + detected weaknesses.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.widgets import OutputDisplay, SectionHeader, StatusLabel
from ui.worker import StreamWorker, run_in_thread


class PathTab(QWidget):
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

        layout.addWidget(SectionHeader("🗺️ Learning Path"))
        
        desc = QLabel(
            "Lộ trình học tập được AI thiết kế riêng cho bạn dựa trên giáo trình của môn học "
            "và điểm yếu được phân tích từ lịch sử làm bài tập/trắc nghiệm của bạn."
        )
        desc.setWordWrap(True)
        desc.setFont(QFont("Inter", 10))
        layout.addWidget(desc)

        # Controls
        controls = QHBoxLayout()
        self.gen_btn = QPushButton("✨ Tạo Lộ Trình Học Tập")
        self.gen_btn.setFixedSize(200, 40)
        self.gen_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.gen_btn.clicked.connect(self._generate_path)
        controls.addWidget(self.gen_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.status = StatusLabel()
        layout.addWidget(self.status)

        # Output
        self.output = OutputDisplay()
        layout.addWidget(self.output)

    def set_subject(self, subject_id: str, subject_config):
        self.subject_id = subject_id
        self.subject_cfg = subject_config

    def _generate_path(self):
        if self._thread and self._thread.isRunning():
            return
            
        self.gen_btn.setEnabled(False)
        self.output.clear_output()
        self.status.set_loading("Đang phân tích dữ liệu học tập và tạo lộ trình...")

        def _stream():
            from modules.learning_path import generate_learning_path_stream
            return generate_learning_path_stream(self.subject_id)

        self._worker = StreamWorker(_stream)
        self._worker.token.connect(self.output.append_token)
        self._worker.error.connect(lambda e: self.status.set_error(e))
        self._worker.finished.connect(self._on_done)
        self._thread = run_in_thread(self._worker)

    def _on_done(self):
        self.gen_btn.setEnabled(True)
        self.status.set_done("Đã tạo xong lộ trình!")
