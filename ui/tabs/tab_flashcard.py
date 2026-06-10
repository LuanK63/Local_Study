"""
ui/tabs/tab_flashcard.py — M8 Flashcard System Tab
Generate Anki-style flashcards.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel,
    QScrollArea, QFrame, QSpinBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.widgets import SectionHeader, StatusLabel
from ui.worker import LLMWorker, run_in_thread


class FlashcardTab(QWidget):
    def __init__(self, subject_id: str, subject_config, parent=None):
        super().__init__(parent)
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._thread = None
        self._worker = None
        self._flashcards = []
        self._current_idx = 0
        self._showing_answer = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(SectionHeader("🃏 Flashcard System"))

        # Config row
        cfg = QHBoxLayout()
        cfg.addWidget(QLabel("Chủ đề:"))
        self.topic_combo = QComboBox()
        self.topic_combo.setMinimumWidth(200)
        self.topic_combo.setFixedHeight(36)
        cfg.addWidget(self.topic_combo)

        cfg.addWidget(QLabel("Số lượng:"))
        self.num_spin = QSpinBox()
        self.num_spin.setRange(3, 20)
        self.num_spin.setValue(5)
        self.num_spin.setFixedSize(60, 36)
        cfg.addWidget(self.num_spin)

        cfg.addStretch()
        self.gen_btn = QPushButton("✨ Tạo Flashcard")
        self.gen_btn.setFixedSize(130, 36)
        self.gen_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.gen_btn.clicked.connect(self._generate_flashcards)
        cfg.addWidget(self.gen_btn)
        layout.addLayout(cfg)

        self.status = StatusLabel()
        layout.addWidget(self.status)

        # Card Area
        self.card_area = QWidget()
        card_layout = QVBoxLayout(self.card_area)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress_label = QLabel("")
        self.progress_label.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.progress_label)

        # The Card
        self.card_frame = QFrame()
        self.card_frame.setStyleSheet(
            "QFrame { background:#2a2b3d; border-radius:12px; border:2px solid #3a3c52; }"
        )
        self.card_frame.setFixedSize(500, 300)
        card_inner = QVBoxLayout(self.card_frame)
        card_inner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.card_text = QLabel("Mặt trước")
        self.card_text.setFont(QFont("Inter", 14))
        self.card_text.setWordWrap(True)
        self.card_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_text.setStyleSheet("color:#cdd6f4; border: none;")
        card_inner.addWidget(self.card_text)

        card_layout.addWidget(self.card_frame, alignment=Qt.AlignmentFlag.AlignCenter)

        # Controls
        controls = QHBoxLayout()
        controls.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.prev_btn = QPushButton("◀ Trước")
        self.prev_btn.setFixedSize(100, 40)
        self.prev_btn.clicked.connect(self._prev_card)
        controls.addWidget(self.prev_btn)

        self.flip_btn = QPushButton("🔄 Lật thẻ")
        self.flip_btn.setFixedSize(120, 40)
        self.flip_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.flip_btn.clicked.connect(self._flip_card)
        controls.addWidget(self.flip_btn)

        self.next_btn = QPushButton("Sau ▶")
        self.next_btn.setFixedSize(100, 40)
        self.next_btn.clicked.connect(self._next_card)
        controls.addWidget(self.next_btn)

        card_layout.addLayout(controls)

        # Export
        export_layout = QHBoxLayout()
        export_layout.addStretch()
        self.export_btn = QPushButton("💾 Xuất file Anki (.apkg)")
        self.export_btn.setFixedSize(180, 36)
        self.export_btn.clicked.connect(self._export_anki)
        export_layout.addWidget(self.export_btn)
        card_layout.addLayout(export_layout)

        self.card_area.hide()
        layout.addWidget(self.card_area)
        layout.addStretch()

    def set_subject(self, subject_id: str, subject_config):
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._populate_topics()

    def _populate_topics(self):
        self.topic_combo.clear()
        for t in self.subject_cfg.topics:
            self.topic_combo.addItem(t["name"], t["id"])

    def _generate_flashcards(self):
        topic_name = self.topic_combo.currentText()
        n = self.num_spin.value()

        self.gen_btn.setEnabled(False)
        self.card_area.hide()
        self.status.set_loading(f"Đang sinh {n} flashcard...")

        def _gen():
            from modules.flashcard_system import generate_flashcards
            return generate_flashcards(topic_name, self.subject_id, n)

        self._worker = LLMWorker(_gen)
        self._worker.result.connect(self._on_cards_ready)
        self._worker.error.connect(lambda e: self.status.set_error(e))
        self._worker.finished.connect(lambda: self.gen_btn.setEnabled(True))
        self._thread = run_in_thread(self._worker)

    def _on_cards_ready(self, cards: list):
        if not cards:
            self.status.set_error("Không tạo được flashcard.")
            return
        self._flashcards = cards
        self._current_idx = 0
        self.status.set_done(f"Tạo thành công {len(cards)} flashcard.")
        self.card_area.show()
        self._show_card()

    def _show_card(self):
        if not self._flashcards:
            return
        self._showing_answer = False
        card = self._flashcards[self._current_idx]
        total = len(self._flashcards)
        
        self.progress_label.setText(f"Thẻ {self._current_idx + 1} / {total}")
        self.card_text.setText(card.get("front", ""))
        self.card_frame.setStyleSheet(
            "QFrame { background:#2a2b3d; border-radius:12px; border:2px solid #3a3c52; }"
        )

        self.prev_btn.setEnabled(self._current_idx > 0)
        self.next_btn.setEnabled(self._current_idx < total - 1)

    def _flip_card(self):
        if not self._flashcards:
            return
        card = self._flashcards[self._current_idx]
        self._showing_answer = not self._showing_answer
        
        if self._showing_answer:
            self.card_text.setText(card.get("back", ""))
            self.card_frame.setStyleSheet(
                "QFrame { background:#1a1b2e; border-radius:12px; border:2px solid #a6e3a1; }"
            )
        else:
            self.card_text.setText(card.get("front", ""))
            self.card_frame.setStyleSheet(
                "QFrame { background:#2a2b3d; border-radius:12px; border:2px solid #3a3c52; }"
            )

    def _prev_card(self):
        if self._current_idx > 0:
            self._current_idx -= 1
            self._show_card()

    def _next_card(self):
        if self._current_idx < len(self._flashcards) - 1:
            self._current_idx += 1
            self._show_card()

    def _export_anki(self):
        if not self._flashcards:
            return
        self.status.set_loading("Đang xuất file Anki...")
        
        def _export():
            from modules.flashcard_system import export_to_anki
            topic_name = self.topic_combo.currentText()
            return export_to_anki(self._flashcards, f"{self.subject_id}_{topic_name}")

        self._worker = LLMWorker(_export)
        self._worker.result.connect(lambda p: self.status.set_done(f"Đã lưu tại: {p}"))
        self._worker.error.connect(lambda e: self.status.set_error(e))
        self._thread = run_in_thread(self._worker)
