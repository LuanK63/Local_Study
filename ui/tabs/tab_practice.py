"""
ui/tabs/tab_practice.py — M7 Practice Mode Tab
Interactive practice: AI asks → user answers → AI grades + explains.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel,
    QTextEdit, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.widgets import SectionHeader, StatusLabel
from ui.worker import LLMWorker, run_in_thread


class PracticeTab(QWidget):
    def __init__(self, subject_id: str, subject_config, parent=None):
        super().__init__(parent)
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._thread = None
        self._worker = None
        self._current_question = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(SectionHeader("🎯 Practice Mode"))

        # Config row
        cfg = QHBoxLayout()
        cfg.addWidget(QLabel("Chủ đề:"))
        self.topic_combo = QComboBox()
        self.topic_combo.setMinimumWidth(200)
        self.topic_combo.setFixedHeight(36)
        cfg.addWidget(self.topic_combo)

        cfg.addWidget(QLabel("Độ khó:"))
        self.diff_combo = QComboBox()
        self.diff_combo.addItems(["Dễ", "Trung bình", "Khó"])
        self.diff_combo.setCurrentIndex(1)
        self.diff_combo.setFixedHeight(36)
        cfg.addWidget(self.diff_combo)

        cfg.addWidget(QLabel("Loại bài:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Viết Code", "Lý thuyết/Giải thích"])
        self.type_combo.setFixedHeight(36)
        cfg.addWidget(self.type_combo)

        cfg.addStretch()
        self.gen_btn = QPushButton("📝 Ra đề")
        self.gen_btn.setFixedSize(110, 36)
        self.gen_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.gen_btn.clicked.connect(self._generate_question)
        cfg.addWidget(self.gen_btn)
        layout.addLayout(cfg)

        self.status = StatusLabel()
        layout.addWidget(self.status)

        # Main Practice Area
        self.practice_area = QWidget()
        prac_layout = QVBoxLayout(self.practice_area)
        prac_layout.setContentsMargins(0, 0, 0, 0)

        # Question Label
        self.question_label = QLabel("Đề bài sẽ hiện ở đây...")
        self.question_label.setFont(QFont("Inter", 11))
        self.question_label.setWordWrap(True)
        self.question_label.setStyleSheet(
            "background:#2a2b3d; border-radius:8px; padding:12px; color:#cdd6f4;"
        )
        self.question_label.setMinimumHeight(80)
        prac_layout.addWidget(self.question_label)

        # Answer Input
        prac_layout.addWidget(QLabel("Bài làm của bạn:"))
        self.answer_input = QTextEdit()
        self.answer_input.setFont(QFont("Consolas", 11))
        self.answer_input.setStyleSheet(
            "background:#1a1b2e; border:1px solid #3a3c52; border-radius:6px; "
            "color:#cdd6f4; padding:8px;"
        )
        prac_layout.addWidget(self.answer_input)

        # Submit / Feedback area
        nav = QHBoxLayout()
        self.submit_btn = QPushButton("✅ Nộp bài")
        self.submit_btn.setFixedSize(120, 36)
        self.submit_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.submit_btn.clicked.connect(self._submit_answer)
        nav.addWidget(self.submit_btn)
        
        self.score_label = QLabel("")
        self.score_label.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        self.score_label.setStyleSheet("color:#cba6f7;")
        nav.addWidget(self.score_label)
        nav.addStretch()
        prac_layout.addLayout(nav)

        self.feedback_label = QLabel()
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setFont(QFont("Inter", 10))
        self.feedback_label.setStyleSheet(
            "background:#14152a; border-radius:6px; padding:12px; color:#a6e3a1; border: 1px solid #a6e3a1;"
        )
        self.feedback_label.hide()
        prac_layout.addWidget(self.feedback_label)

        self.practice_area.hide()
        layout.addWidget(self.practice_area)
        layout.addStretch()

    def set_subject(self, subject_id: str, subject_config):
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._populate_topics()

    def _populate_topics(self):
        self.topic_combo.clear()
        for t in self.subject_cfg.topics:
            self.topic_combo.addItem(t["name"], t["id"])

    def _diff_str(self) -> str:
        return ["easy", "medium", "hard"][self.diff_combo.currentIndex()]

    def _type_str(self) -> str:
        return "code" if self.type_combo.currentIndex() == 0 else "text"

    def _generate_question(self):
        topic_name = self.topic_combo.currentText()
        diff = self._diff_str()
        q_type = self._type_str()

        self.gen_btn.setEnabled(False)
        self.practice_area.hide()
        self.feedback_label.hide()
        self.score_label.setText("")
        self.answer_input.clear()
        self.status.set_loading("Đang suy nghĩ và ra đề...")

        def _gen():
            from modules.practice_mode import generate_question
            return generate_question(topic_name, self.subject_id, diff, q_type)

        self._worker = LLMWorker(_gen)
        self._worker.result.connect(self._on_question_ready)
        self._worker.error.connect(lambda e: self.status.set_error(e))
        self._worker.finished.connect(lambda: self.gen_btn.setEnabled(True))
        self._thread = run_in_thread(self._worker)

    def _on_question_ready(self, question: str):
        if not question:
            self.status.set_error("Lỗi khi tạo đề bài. Thử lại!")
            return
        
        self._current_question = question
        self.question_label.setText(question)
        self.practice_area.show()
        self.submit_btn.setEnabled(True)
        self.status.set_done("Đã tạo đề bài thành công.")

    def _submit_answer(self):
        answer = self.answer_input.toPlainText().strip()
        if not answer:
            return

        topic_id = self.topic_combo.currentData()
        q_type = self._type_str()

        self.submit_btn.setEnabled(False)
        self.status.set_loading("Đang chấm bài...")
        self.feedback_label.hide()

        def _grade():
            from modules.practice_mode import grade_answer
            return grade_answer(self._current_question, answer, topic_id, self.subject_id, q_type)

        self._worker = LLMWorker(_grade)
        self._worker.result.connect(self._on_graded)
        self._worker.error.connect(lambda e: self.status.set_error(e))
        self._worker.finished.connect(lambda: self.submit_btn.setEnabled(True))
        self._thread = run_in_thread(self._worker)

    def _on_graded(self, result: tuple[float, str]):
        score, feedback = result
        self.status.set_done("Chấm bài hoàn tất.")
        
        color = "#a6e3a1" if score >= 8 else "#f9e2af" if score >= 5 else "#f38ba8"
        self.score_label.setText(f"Điểm: {score}/10")
        self.score_label.setStyleSheet(f"color: {color};")
        
        self.feedback_label.setText(feedback)
        self.feedback_label.setStyleSheet(
            f"background:#14152a; border-radius:6px; padding:12px; color:#cdd6f4; border: 1px solid {color};"
        )
        self.feedback_label.show()
