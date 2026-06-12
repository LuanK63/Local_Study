"""
ui/tabs/tab_quiz.py — M6 Quiz Generator Tab
Generate MCQ, show options, record answers, give score.
"""
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel,
    QRadioButton, QButtonGroup, QFrame,
    QScrollArea, QSpinBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from ui.widgets import OutputDisplay, SectionHeader, StatusLabel
from ui.worker import LLMWorker, run_in_thread


class QuizTab(QWidget):
    def __init__(self, subject_id: str, subject_config, parent=None):
        super().__init__(parent)
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._questions: list[dict] = []
        self._current_idx = 0
        self._score = 0
        self._thread = None
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(SectionHeader("📝 Quiz Generator"))

        # Config row
        cfg = QHBoxLayout()
        cfg.addWidget(QLabel("Chủ đề:"))
        self.topic_combo = QComboBox()
        self.topic_combo.setMinimumWidth(200)
        self.topic_combo.setFixedHeight(36)
        cfg.addWidget(self.topic_combo)

        cfg.addWidget(QLabel("Số câu:"))
        self.num_spin = QSpinBox()
        self.num_spin.setRange(3, 20)
        self.num_spin.setValue(5)
        self.num_spin.setFixedSize(60, 36)
        cfg.addWidget(self.num_spin)

        cfg.addWidget(QLabel("Độ khó:"))
        self.diff_combo = QComboBox()
        self.diff_combo.addItems(["Dễ", "Trung bình", "Khó"])
        self.diff_combo.setCurrentIndex(1)
        self.diff_combo.setFixedHeight(36)
        cfg.addWidget(self.diff_combo)

        cfg.addStretch()
        self.gen_btn = QPushButton("🎲 Tạo Quiz")
        self.gen_btn.setFixedSize(110, 36)
        self.gen_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.gen_btn.clicked.connect(self._generate_quiz)
        cfg.addWidget(self.gen_btn)
        layout.addLayout(cfg)

        self.status = StatusLabel()
        layout.addWidget(self.status)

        # Quiz area (hidden until generated)
        self.quiz_area = QWidget()
        quiz_layout = QVBoxLayout(self.quiz_area)

        # Progress
        self.progress_label = QLabel("")
        self.progress_label.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        quiz_layout.addWidget(self.progress_label)

        # Question
        self.question_label = QLabel("")
        self.question_label.setFont(QFont("Inter", 12))
        self.question_label.setWordWrap(True)
        self.question_label.setStyleSheet(
            "background:#2a2b3d; border-radius:8px; padding:12px 16px; color:#cdd6f4;"
        )
        quiz_layout.addWidget(self.question_label)

        # Options
        self.btn_group = QButtonGroup()
        self.option_btns: list[QRadioButton] = []
        for i in range(4):
            rb = QRadioButton("")
            rb.setFont(QFont("Inter", 11))
            rb.setStyleSheet("color:#cdd6f4; padding:6px;")
            self.option_btns.append(rb)
            self.btn_group.addButton(rb, i)
            quiz_layout.addWidget(rb)

        # Feedback
        self.feedback_label = QLabel("")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setFont(QFont("Inter", 10))
        self.feedback_label.setStyleSheet(
            "background:#1a1b2e; border-radius:6px; padding:10px; color:#a6e3a1;"
        )
        self.feedback_label.hide()
        quiz_layout.addWidget(self.feedback_label)

        # Nav buttons
        nav = QHBoxLayout()
        self.submit_btn = QPushButton("✅ Trả lời")
        self.submit_btn.setFixedSize(120, 36)
        self.submit_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.submit_btn.clicked.connect(self._submit_answer)
        nav.addWidget(self.submit_btn)

        self.next_btn = QPushButton("▶ Câu tiếp")
        self.next_btn.setFixedSize(120, 36)
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self._next_question)
        nav.addWidget(self.next_btn)
        nav.addStretch()

        self.score_label = QLabel("")
        self.score_label.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        self.score_label.setStyleSheet("color:#cba6f7;")
        nav.addWidget(self.score_label)
        quiz_layout.addLayout(nav)

        self.quiz_area.hide()
        layout.addWidget(self.quiz_area)
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

    def _generate_quiz(self):
        topic_name = self.topic_combo.currentText()
        topic_id = self.topic_combo.currentData()
        n = self.num_spin.value()
        diff = self._diff_str()

        self.gen_btn.setEnabled(False)
        self.quiz_area.hide()
        self.status.set_loading("Đang tạo câu hỏi...")

        def _gen():
            from modules.quiz_generator import generate_quiz
            return generate_quiz(topic_name, self.subject_id, n, diff)

        self._worker = LLMWorker(_gen)
        self._worker.result.connect(self._on_quiz_ready)
        self._worker.error.connect(lambda e: self.status.set_error(e))
        self._worker.finished.connect(lambda: self.gen_btn.setEnabled(True))
        self._thread = run_in_thread(self._worker)

    def _on_quiz_ready(self, questions: list):
        if not questions:
            self.status.set_error("Không tạo được câu hỏi. Thử lại!")
            return
        self._questions = questions
        self._current_idx = 0
        self._score = 0
        self.quiz_area.show()
        self.status.set_done(f"Đã tạo {len(questions)} câu hỏi")
        self._show_question()

    def _show_question(self):
        q = self._questions[self._current_idx]
        total = len(self._questions)
        self.progress_label.setText(f"Câu {self._current_idx + 1}/{total}")
        self.question_label.setText(q["question"])
        self.feedback_label.hide()
        self.next_btn.setEnabled(False)
        self.submit_btn.setEnabled(True)

        for i, btn in enumerate(self.option_btns):
            options = q.get("options", [])
            if i < len(options):
                btn.setText(options[i])
                btn.setChecked(False)
                btn.setEnabled(True)
                btn.setStyleSheet("color:#cdd6f4; padding:6px;")
                btn.show()
            else:
                btn.hide()

    def _submit_answer(self):
        checked_id = self.btn_group.checkedId()
        if checked_id < 0:
            return
        q = self._questions[self._current_idx]
        letters = ["A", "B", "C", "D"]
        user_ans = letters[checked_id]
        correct = q.get("correct", "A").upper()
        is_correct = user_ans == correct

        if is_correct:
            self._score += 1
            self.feedback_label.setStyleSheet(
                "background:#1a1b2e; border-radius:6px; padding:10px; color:#a6e3a1;"
            )
            self.feedback_label.setText(f"✅ Đúng! {q.get('explanation', '')}")
        else:
            self.feedback_label.setStyleSheet(
                "background:#1a1b2e; border-radius:6px; padding:10px; color:#f38ba8;"
            )
            self.feedback_label.setText(
                f"❌ Sai! Đáp án đúng: {correct}\n{q.get('explanation', '')}"
            )

        self.feedback_label.show()
        self.submit_btn.setEnabled(False)
        self.next_btn.setEnabled(True)
        self.score_label.setText(f"Điểm: {self._score}/{self._current_idx + 1}")

        # Save to DB
        from modules.quiz_generator import save_quiz_result
        options = q.get("options", [])
        save_quiz_result(
            q["question"], options, correct, user_ans,
            q.get("explanation", ""),
            self.topic_combo.currentData(),
            self.subject_id,
        )

    def _next_question(self):
        self._current_idx += 1
        if self._current_idx >= len(self._questions):
            total = len(self._questions)
            self.question_label.setText(
                f"🎉 Hoàn thành!\n\nKết quả: {self._score}/{total} "
                f"({self._score/total*100:.0f}%)"
            )
            for btn in self.option_btns:
                btn.hide()
            self.submit_btn.hide()
            self.next_btn.setEnabled(False)
        else:
            self._show_question()
