"""
ui/tabs/tab_practice.py — M7 Lesson/Practice Mode Tab
Duolingo-style Lesson Mode with instant local grading and learning analytics.
"""
import time
import random
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel,
    QScrollArea, QFrame, QLineEdit, QListWidget, QAbstractItemView,
    QProgressBar, QSizePolicy, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QSize
from PyQt6.QtGui import QFont, QColor

from ui.widgets import SectionHeader, StatusLabel
from ui.worker import LLMWorker, run_in_thread


def _theme_tokens() -> dict:
    try:
        from ui.theme_manager import get_theme, PALETTES
        return PALETTES[get_theme()]
    except Exception:
        return {
            "COLOR_TEXT": "#334155",
            "COLOR_TEXT_MUTED": "#64748B",
            "COLOR_TEXT_TITLE": "#0F172A",
            "BORDER": "#E5E7EB",
            "BORDER_HOVER": "#94A3B8",
            "BG_WIDGET": "#FFFFFF",
            "BG_SIDEBAR": "#F8FAFD",
            "BG_MAIN": "#F6F8FC",
            "BG_HOVER": "#EEF4FF",
            "BG_CHECKED": "#DCEBFF",
            "COLOR_ACCENT": "#2563EB",
            "COLOR_ACCENT_HOVER": "#1D4ED8",
            "COLOR_GREEN": "#16A34A",
            "COLOR_RED": "#DC2626",
            "COLOR_YELLOW": "#F59E0B",
            "BG_TERMINAL": "#0F172A",
            "COLOR_TEXT_TERMINAL": "#E2E8F0",
        }


_QTYPE_LABELS = {
    "multiple_choice": "Trắc nghiệm",
    "true_false": "Đúng / Sai",
    "fill_blank": "Điền khuyết",
    "matching": "Nối cặp",
    "ordering": "Sắp xếp",
    "output_prediction": "Dự đoán output",
}


class TopicCard(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, topic_id: str, topic_name: str, progress: dict, is_weak: bool, parent=None):
        super().__init__(parent)
        self.setObjectName("TopicCard")
        self.topic_id = topic_id
        self.topic_name = topic_name
        self.progress = progress
        self.is_weak = is_weak
        self._selected = False
        self._setup_ui()

    def _setup_ui(self):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(108)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(10)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self.title_lbl = QLabel(self.topic_name)
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        text_col.addWidget(self.title_lbl)

        self.status_lbl = QLabel()
        self.status_lbl.setFont(QFont("Inter", 8))
        text_col.addWidget(self.status_lbl)
        top.addLayout(text_col, stretch=1)
        layout.addLayout(top)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        self.score_lbl = QLabel()
        self.score_lbl.setFont(QFont("Inter", 8, QFont.Weight.Bold))
        self.score_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.score_lbl)

        self.update_style()

    def set_selected(self, selected: bool):
        self._selected = selected
        self.update_style()

    def update_style(self):
        tokens = _theme_tokens()
        max_score = self.progress.get("max_score")

        if self.is_weak:
            status = "Cần ôn lại"
            accent = tokens["COLOR_RED"]
            bar = tokens["COLOR_RED"]
        elif max_score is not None:
            if max_score >= 7.0:
                status = "Đã thành thạo"
                accent = tokens["COLOR_GREEN"]
                bar = tokens["COLOR_GREEN"]
            else:
                status = "Đang luyện tập"
                accent = tokens["COLOR_YELLOW"]
                bar = tokens["COLOR_YELLOW"]
        else:
            status = "Chưa bắt đầu"
            accent = tokens["COLOR_TEXT_MUTED"]
            bar = tokens["BORDER"]

        pct = int((max_score or 0) * 10) if max_score is not None else 0
        self.status_lbl.setText(status)
        self.status_lbl.setStyleSheet(f"color:{accent}; border:none; background:transparent;")
        self.title_lbl.setStyleSheet(
            f"color:{tokens['COLOR_TEXT_TITLE']}; border:none; background:transparent;"
        )
        self.progress_bar.setValue(pct)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background:{tokens['BORDER']}; border:none; border-radius:3px;
            }}
            QProgressBar::chunk {{
                background:{bar}; border-radius:3px;
            }}
        """)
        if max_score is not None:
            self.score_lbl.setText(f"{max_score}/10")
            self.score_lbl.setStyleSheet(f"color:{accent}; border:none; background:transparent;")
        else:
            self.score_lbl.setText("")
            self.score_lbl.setStyleSheet("border:none; background:transparent;")

        border = tokens["COLOR_ACCENT"] if self._selected else tokens["BORDER"]
        bg = tokens["BG_HOVER"] if self._selected else tokens["BG_WIDGET"]
        width = "2px" if self._selected else "1px"
        self.setStyleSheet(f"""
            QFrame#TopicCard {{
                border:{width} solid {border};
                border-radius:12px;
                background:{bg};
            }}
            QFrame#TopicCard:hover {{
                border-color:{tokens['COLOR_ACCENT']};
                background:{tokens['BG_HOVER']};
            }}
        """)

    def mousePressEvent(self, event):
        self.clicked.emit(self.topic_id)
        super().mousePressEvent(event)


class LessonTab(QWidget):
    def __init__(self, subject_id: str, subject_config, parent=None):
        super().__init__(parent)
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._thread = None
        self._worker = None
        self._cards = []
        
        # State variables
        self._questions: list[dict] = []
        self._current_idx = 0
        self._correct_count = 0
        self._duration_start = 0
        
        # Details of current question
        self._question_start_time = 0
        self._answers_details: list[dict] = []  # To save in DB
        self._mistakes: list[dict] = []          # For review mistakes
        
        # Active question variables
        self._selected_mc_option = None
        self._selected_tf_option = None
        self._selected_matching_left = None
        self._selected_matching_right = None
        self._matched_pairs = {}
        
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 20, 24, 20)
        self.layout.setSpacing(12)

        self.layout.addWidget(SectionHeader("Luyện tập"))

        self.config_area = QWidget()
        cfg_layout = QVBoxLayout(self.config_area)
        cfg_layout.setContentsMargins(0, 0, 0, 0)
        cfg_layout.setSpacing(14)

        # Hero banner — tổng quan tiến độ
        self.hero_frame = QFrame()
        self.hero_frame.setObjectName("PracticeHero")
        hero_layout = QVBoxLayout(self.hero_frame)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_layout.setSpacing(12)

        hero_top = QHBoxLayout()
        hero_text = QVBoxLayout()
        hero_text.setSpacing(4)
        self.hero_title = QLabel("Lộ trình học của bạn")
        self.hero_title.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        self.hero_subtitle = QLabel("Chọn chủ đề, luyện tập và theo dõi tiến độ từng phần.")
        self.hero_subtitle.setFont(QFont("Inter", 9))
        self.hero_subtitle.setWordWrap(True)
        hero_text.addWidget(self.hero_title)
        hero_text.addWidget(self.hero_subtitle)
        hero_top.addLayout(hero_text, stretch=1)
        hero_layout.addLayout(hero_top)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        self.stat_total = self._make_stat_chip("Tổng chủ đề", "0")
        self.stat_done = self._make_stat_chip("Đã thành thạo", "0")
        self.stat_weak = self._make_stat_chip("Cần ôn", "0")
        for chip in (self.stat_total, self.stat_done, self.stat_weak):
            stats_row.addWidget(chip)
        stats_row.addStretch()
        hero_layout.addLayout(stats_row)
        cfg_layout.addWidget(self.hero_frame)

        self.path_scroll = QScrollArea()
        self.path_scroll.setWidgetResizable(True)
        self.path_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.path_widget = QWidget()
        self.path_layout = QVBoxLayout(self.path_widget)
        self.path_layout.setContentsMargins(4, 4, 4, 4)
        self.path_layout.setSpacing(16)

        self.path_scroll.setWidget(self.path_widget)
        cfg_layout.addWidget(self.path_scroll, 1)

        self.detail_panel = QFrame()
        self.detail_panel.setObjectName("PracticeDetail")
        self.detail_layout = QVBoxLayout(self.detail_panel)
        self.detail_layout.setContentsMargins(18, 16, 18, 16)
        self.detail_layout.setSpacing(12)

        self.detail_title = QLabel("Chọn một chủ đề để bắt đầu")
        self.detail_title.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        self.detail_title.setWordWrap(True)
        self.detail_layout.addWidget(self.detail_title)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)
        self.detail_stats_score = self._make_detail_chip("Điểm cao nhất", "—")
        self.detail_stats_status = self._make_detail_chip("Trạng thái", "—")
        self.detail_stats_attempts = self._make_detail_chip("Lần học", "0")
        for chip in (
            self.detail_stats_score,
            self.detail_stats_status,
            self.detail_stats_attempts,
        ):
            chips_row.addWidget(chip)
        chips_row.addStretch()
        self.detail_layout.addLayout(chips_row)

        diff_lbl = QLabel("Chọn độ khó")
        diff_lbl.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        self.detail_layout.addWidget(diff_lbl)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.diff_btns = []
        self._selected_difficulty = "medium"
        for label, val in [("Dễ", "easy"), ("Trung bình", "medium"), ("Khó", "hard")]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(34)
            btn.setMinimumWidth(96)
            btn.setProperty("diff_val", val)
            btn.clicked.connect(self._on_diff_btn_clicked)
            self.diff_btns.append(btn)
            action_row.addWidget(btn)
        action_row.addStretch()

        self.start_btn = QPushButton("Bắt đầu luyện tập")
        self.start_btn.setObjectName("PracticeStartBtn")
        self.start_btn.setFixedSize(168, 40)
        self.start_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.clicked.connect(self._start_lesson)
        action_row.addWidget(self.start_btn)
        self.detail_layout.addLayout(action_row)

        cfg_layout.addWidget(self.detail_panel)
        self.detail_panel.hide()

        self.layout.addWidget(self.config_area)

        # Status Label for loading/error
        self.status = StatusLabel()
        self.layout.addWidget(self.status)

        self.lesson_area = QWidget()
        self.lesson_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lesson_outer = QVBoxLayout(self.lesson_area)
        lesson_outer.setContentsMargins(0, 0, 0, 0)

        self.lesson_card = QFrame()
        self.lesson_card.setObjectName("LessonCard")
        self.lesson_layout = QVBoxLayout(self.lesson_card)
        self.lesson_layout.setContentsMargins(22, 20, 22, 20)
        self.lesson_layout.setSpacing(14)

        prog_row = QHBoxLayout()
        prog_col = QVBoxLayout()
        prog_col.setSpacing(6)
        prog_header = QHBoxLayout()
        self.lesson_topic_lbl = QLabel("")
        self.lesson_topic_lbl.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        prog_header.addWidget(self.lesson_topic_lbl)
        prog_header.addStretch()
        self.streak_lbl = QLabel("")
        self.streak_lbl.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        prog_header.addWidget(self.streak_lbl)
        prog_col.addLayout(prog_header)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        prog_col.addWidget(self.progress_bar)
        prog_row.addLayout(prog_col, stretch=1)

        self.prog_lbl = QLabel("")
        self.prog_lbl.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.prog_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        prog_row.addWidget(self.prog_lbl)
        self.lesson_layout.addLayout(prog_row)

        self.q_type_badge = QLabel("")
        self.q_type_badge.setObjectName("QuestionTypeBadge")
        self.q_type_badge.setFont(QFont("Inter", 8, QFont.Weight.Bold))
        self.q_type_badge.setContentsMargins(10, 4, 10, 4)
        self.lesson_layout.addWidget(self.q_type_badge, alignment=Qt.AlignmentFlag.AlignLeft)

        self.question_frame = QFrame()
        self.question_frame.setObjectName("QuestionFrame")
        q_inner = QVBoxLayout(self.question_frame)
        q_inner.setContentsMargins(16, 14, 16, 14)
        self.question_title = QLabel("")
        self.question_title.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        self.question_title.setWordWrap(True)
        q_inner.addWidget(self.question_title)
        self.lesson_layout.addWidget(self.question_frame)

        self.option_container = QWidget()
        self.option_layout = QVBoxLayout(self.option_container)
        self.option_layout.setContentsMargins(0, 0, 0, 0)
        self.option_layout.setSpacing(10)
        self.lesson_layout.addWidget(self.option_container)

        self.submit_btn = QPushButton("Kiểm tra đáp án")
        self.submit_btn.setObjectName("PracticeSubmitBtn")
        self.submit_btn.setFixedHeight(48)
        self.submit_btn.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_btn.clicked.connect(self._on_submit_clicked)
        self.lesson_layout.addWidget(self.submit_btn)

        self.feedback_frame = QFrame()
        self.feedback_frame.setObjectName("FeedbackFrame")
        self.feedback_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.feedback_layout = QVBoxLayout(self.feedback_frame)
        self.feedback_layout.setContentsMargins(18, 16, 18, 16)
        self.feedback_layout.setSpacing(10)

        self.feedback_title = QLabel("")
        self.feedback_title.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        self.feedback_layout.addWidget(self.feedback_title)

        self.feedback_text = QLabel("")
        self.feedback_text.setWordWrap(True)
        self.feedback_text.setFont(QFont("Inter", 10))
        self.feedback_layout.addWidget(self.feedback_text)

        self.continue_btn = QPushButton("Tiếp tục")
        self.continue_btn.setObjectName("PracticeContinueBtn")
        self.continue_btn.setFixedHeight(46)
        self.continue_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.continue_btn.clicked.connect(self._on_continue_clicked)
        self.feedback_layout.addWidget(self.continue_btn)

        self.lesson_layout.addWidget(self.feedback_frame)
        self.feedback_frame.hide()

        lesson_outer.addWidget(self.lesson_card)
        self.lesson_area.hide()
        self.layout.addWidget(self.lesson_area, stretch=1)

        self.summary_area = QWidget()
        self.summary_layout = QVBoxLayout(self.summary_area)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        self.summary_layout.setSpacing(16)

        self.summary_card = QFrame()
        self.summary_card.setObjectName("SummaryCard")
        sc_layout = QVBoxLayout(self.summary_card)
        sc_layout.setContentsMargins(28, 28, 28, 28)
        sc_layout.setSpacing(14)
        sc_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.summary_title = QLabel("Hoàn thành bài luyện!")
        self.summary_title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        self.summary_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sc_layout.addWidget(self.summary_title)

        self.score_ring = QLabel("0.0")
        self.score_ring.setObjectName("ScoreRing")
        self.score_ring.setFont(QFont("Inter", 36, QFont.Weight.Bold))
        self.score_ring.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sc_layout.addWidget(self.score_ring)

        self.stars_lbl = QLabel("")
        self.stars_lbl.setFont(QFont("Segoe UI Emoji", 20))
        self.stars_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sc_layout.addWidget(self.stars_lbl)

        self.summary_stats = QLabel("")
        self.summary_stats.setFont(QFont("Inter", 10))
        self.summary_stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary_stats.setWordWrap(True)
        sc_layout.addWidget(self.summary_stats)
        self.summary_layout.addWidget(self.summary_card)
        
        # Scrollable area for Review Mistakes
        self.mistakes_scroll = QScrollArea()
        self.mistakes_scroll.setWidgetResizable(True)
        self.mistakes_scroll.setFixedHeight(240)
        self.mistakes_content = QWidget()
        self.mistakes_layout = QVBoxLayout(self.mistakes_content)
        self.mistakes_layout.setContentsMargins(8, 8, 8, 8)
        self.mistakes_layout.setSpacing(10)
        self.mistakes_layout.addStretch()
        self.mistakes_scroll.setWidget(self.mistakes_content)
        self.summary_layout.addWidget(self.mistakes_scroll)
        self.mistakes_scroll.hide()
        
        summary_nav = QHBoxLayout()
        summary_nav.setAlignment(Qt.AlignmentFlag.AlignCenter)
        summary_nav.setSpacing(12)
        self.review_btn = QPushButton("Xem câu sai")
        self.review_btn.setFixedSize(140, 40)
        self.review_btn.clicked.connect(self._show_mistakes_review)
        summary_nav.addWidget(self.review_btn)

        self.close_btn = QPushButton("Về lộ trình")
        self.close_btn.setFixedSize(140, 40)
        self.close_btn.clicked.connect(self._exit_summary)
        summary_nav.addWidget(self.close_btn)
        self.summary_layout.addLayout(summary_nav)

        self.summary_area.hide()
        self.layout.addWidget(self.summary_area)

        self.apply_theme_styles()

    def _make_stat_chip(self, label: str, value: str) -> QFrame:
        chip = QFrame()
        chip.setObjectName("PracticeStatChip")
        lay = QVBoxLayout(chip)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(2)
        val_lbl = QLabel(value)
        val_lbl.setObjectName("chip_value")
        val_lbl.setFont(QFont("Inter", 16, QFont.Weight.Bold))
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        key_lbl = QLabel(label)
        key_lbl.setObjectName("chip_key")
        key_lbl.setFont(QFont("Inter", 8))
        key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(val_lbl)
        lay.addWidget(key_lbl)
        chip._value_lbl = val_lbl
        return chip

    def _make_detail_chip(self, label: str, value: str) -> QFrame:
        chip = QFrame()
        chip.setObjectName("PracticeDetailChip")
        lay = QVBoxLayout(chip)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(2)
        key_lbl = QLabel(label)
        key_lbl.setFont(QFont("Inter", 8))
        val_lbl = QLabel(value)
        val_lbl.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        val_lbl.setWordWrap(True)
        lay.addWidget(key_lbl)
        lay.addWidget(val_lbl)
        chip._key_lbl = key_lbl
        chip._value_lbl = val_lbl
        return chip

    def _option_btn_style(self, tokens: dict) -> str:
        return f"""
            QPushButton {{
                text-align: left;
                padding: 12px 16px;
                background: {tokens['BG_WIDGET']};
                color: {tokens['COLOR_TEXT']};
                border: 1px solid {tokens['BORDER']};
                border-radius: 10px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background: {tokens['BG_HOVER']};
                border-color: {tokens['COLOR_ACCENT']};
            }}
            QPushButton:checked {{
                background: {tokens['BG_CHECKED']};
                border: 2px solid {tokens['COLOR_ACCENT']};
                font-weight: bold;
            }}
        """

    def _update_hero_stats(self, progress: dict, weak_ids: list, total_topics: int):
        done = 0
        for prog in progress.values():
            if prog.get("max_score", 0) >= 7.0:
                done += 1
        weak = len(weak_ids)
        self.stat_total._value_lbl.setText(str(total_topics))
        self.stat_done._value_lbl.setText(str(done))
        self.stat_weak._value_lbl.setText(str(weak))

    def apply_theme_styles(self):
        try:
            tokens = _theme_tokens()

            self.progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    background: {tokens['BORDER']};
                    border: none;
                    border-radius: 6px;
                }}
                QProgressBar::chunk {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {tokens['COLOR_ACCENT']}, stop:1 {tokens['COLOR_GREEN']});
                    border-radius: 6px;
                }}
            """)
            self.prog_lbl.setStyleSheet(f"color: {tokens['COLOR_TEXT_MUTED']}; min-width: 64px;")
            self.lesson_topic_lbl.setStyleSheet(f"color: {tokens['COLOR_TEXT_MUTED']};")
            self.streak_lbl.setStyleSheet(f"color: {tokens['COLOR_GREEN']};")
            self.q_type_badge.setStyleSheet(f"""
                QLabel#QuestionTypeBadge {{
                    background: {tokens['BG_CHECKED']};
                    color: {tokens['COLOR_ACCENT']};
                    border-radius: 10px;
                    padding: 4px 10px;
                }}
            """)
            self.question_frame.setStyleSheet(f"""
                QFrame#QuestionFrame {{
                    background: {tokens['BG_SIDEBAR']};
                    border: 1px solid {tokens['BORDER']};
                    border-radius: 12px;
                }}
            """)
            self.question_title.setStyleSheet(f"color: {tokens['COLOR_TEXT_TITLE']}; border: none; background: transparent;")
            self.lesson_card.setStyleSheet(f"""
                QFrame#LessonCard {{
                    background: {tokens['BG_WIDGET']};
                    border: 1px solid {tokens['BORDER']};
                    border-radius: 16px;
                }}
            """)

            self.hero_frame.setStyleSheet(f"""
                QFrame#PracticeHero {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 {tokens['BG_CHECKED']}, stop:1 {tokens['BG_WIDGET']});
                    border: 1px solid {tokens['BORDER']};
                    border-radius: 14px;
                }}
            """)
            self.hero_title.setStyleSheet(f"color: {tokens['COLOR_TEXT_TITLE']}; background: transparent;")
            self.hero_subtitle.setStyleSheet(f"color: {tokens['COLOR_TEXT_MUTED']}; background: transparent;")

            for chip in (self.stat_total, self.stat_done, self.stat_weak):
                chip.setStyleSheet(f"""
                    QFrame#PracticeStatChip {{
                        background: {tokens['BG_WIDGET']};
                        border: 1px solid {tokens['BORDER']};
                        border-radius: 10px;
                        min-width: 96px;
                    }}
                """)
                for lbl in chip.findChildren(QLabel):
                    if lbl.objectName() == "chip_value":
                        lbl.setStyleSheet(f"color: {tokens['COLOR_ACCENT']}; border: none; background: transparent;")
                    elif lbl.objectName() == "chip_key":
                        lbl.setStyleSheet(f"color: {tokens['COLOR_TEXT_MUTED']}; border: none; background: transparent;")

            self.summary_card.setStyleSheet(f"""
                QFrame#SummaryCard {{
                    background: {tokens['BG_WIDGET']};
                    border: 1px solid {tokens['BORDER']};
                    border-radius: 16px;
                }}
            """)
            self.summary_title.setStyleSheet(f"color: {tokens['COLOR_TEXT_TITLE']}; background: transparent;")
            self.score_ring.setStyleSheet(f"color: {tokens['COLOR_ACCENT']}; background: transparent;")
            self.summary_stats.setStyleSheet(f"color: {tokens['COLOR_TEXT']}; background: transparent;")

            self.mistakes_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: {tokens['BG_SIDEBAR']};
                    border: 1px solid {tokens['BORDER']};
                    border-radius: 10px;
                }}
            """)
            self.mistakes_content.setStyleSheet("background: transparent;")

            btn_style = f"""
                QPushButton {{
                    background: {tokens['COLOR_ACCENT']};
                    color: #FFFFFF;
                    border: none;
                    border-radius: 10px;
                    padding: 0 16px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {tokens['COLOR_ACCENT_HOVER']};
                }}
                QPushButton:disabled {{
                    background: {tokens['BG_SIDEBAR']};
                    color: {tokens['COLOR_TEXT_MUTED']};
                    border: 1px solid {tokens['BORDER']};
                }}
            """
            for btn in (self.start_btn, self.submit_btn, self.review_btn, self.close_btn, self.continue_btn):
                btn.setStyleSheet(btn_style)

            self.detail_panel.setStyleSheet(f"""
                QFrame#PracticeDetail {{
                    background: {tokens['BG_WIDGET']};
                    border: 2px solid {tokens['COLOR_ACCENT']};
                    border-radius: 14px;
                }}
            """)
            self.detail_title.setStyleSheet(
                f"color: {tokens['COLOR_TEXT_TITLE']}; font-weight: bold; border: none; background: transparent;"
            )
            for chip in (
                self.detail_stats_score,
                self.detail_stats_status,
                self.detail_stats_attempts,
            ):
                chip.setStyleSheet(f"""
                    QFrame#PracticeDetailChip {{
                        background: {tokens['BG_SIDEBAR']};
                        border: 1px solid {tokens['BORDER']};
                        border-radius: 8px;
                        min-width: 88px;
                    }}
                """)
                for lbl in chip.findChildren(QLabel):
                    if lbl is chip._key_lbl:
                        lbl.setStyleSheet(f"color: {tokens['COLOR_TEXT_MUTED']}; border: none; background: transparent;")
                    else:
                        lbl.setStyleSheet(f"color: {tokens['COLOR_TEXT']}; border: none; background: transparent;")

            self.update_difficulty_buttons()
            self.path_scroll.setStyleSheet("background: transparent; border: none;")
            self.path_widget.setStyleSheet("background: transparent;")

            if hasattr(self, "_cards") and self._cards:
                for card in self._cards:
                    card.set_selected(
                        hasattr(self, "_selected_topic_id")
                        and card.topic_id == self._selected_topic_id
                    )
        except Exception:
            pass

    def set_subject(self, subject_id: str, subject_config):
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._selected_topic_id = None
        self.detail_panel.hide()
        self._populate_topics()

    def _populate_topics(self):
        # 1. Clear previous layout items
        for i in reversed(range(self.path_layout.count())):
            item = self.path_layout.itemAt(i)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
            else:
                lay = item.layout()
                if lay:
                    for j in reversed(range(lay.count())):
                        sw = lay.itemAt(j).widget()
                        if sw:
                            sw.setParent(None)
                            sw.deleteLater()
                    self.path_layout.removeItem(lay)

        self._cards = []

        # 2. Group topics by phase
        phases = {}
        for t in self.subject_cfg.topics:
            phase_id = t.get("phase", 1)
            phase_name = t.get("phase_name", "Chương")
            if phase_id not in phases:
                phases[phase_id] = {
                    "name": phase_name,
                    "topics": []
                }
            phases[phase_id]["topics"].append(t)

        # 3. Fetch progress & weaknesses
        from modules.lesson_mode import get_topics_progress
        progress = get_topics_progress(self.subject_id)
        
        weak_topic_ids = []
        try:
            from modules.weakness_detector import get_weak_topics
            weak_topic_ids = [w["topic_id"] for w in get_weak_topics(self.subject_id)]
        except Exception as e:
            print(f"[ERROR] get_weak_topics failed: {e}")

        total_topics = len(self.subject_cfg.topics)
        self._update_hero_stats(progress, weak_topic_ids, total_topics)

        tokens = _theme_tokens()

        for phase_id in sorted(phases.keys()):
            p_data = phases[phase_id]

            p_header = QFrame()
            p_header.setObjectName("PhaseHeader")
            p_header.setStyleSheet(f"""
                QFrame#PhaseHeader {{
                    background: transparent;
                    border-left: 4px solid {tokens['COLOR_ACCENT']};
                    border-radius: 0;
                }}
            """)
            p_header_layout = QHBoxLayout(p_header)
            p_header_layout.setContentsMargins(12, 4, 12, 4)

            p_lbl = QLabel(f"Phần {phase_id} · {p_data['name']}")
            p_lbl.setFont(QFont("Inter", 11, QFont.Weight.Bold))
            p_lbl.setStyleSheet(f"color: {tokens['COLOR_TEXT_TITLE']}; border: none; background: transparent;")
            p_header_layout.addWidget(p_lbl)
            self.path_layout.addWidget(p_header)

            grid = QGridLayout()
            grid.setSpacing(12)
            
            for idx, t in enumerate(p_data["topics"]):
                tid = t["id"]
                tname = t["name"]
                is_weak = tid in weak_topic_ids
                
                t_prog = progress.get(tid, {})
                card = TopicCard(tid, tname, t_prog, is_weak)
                card.clicked.connect(self._on_topic_clicked)
                self._cards.append(card)
                
                row = idx // 2
                col = idx % 2
                grid.addWidget(card, row, col)
                
            self.path_layout.addLayout(grid)
            
        self.path_layout.addStretch()

    def _on_topic_clicked(self, topic_id: str):
        self._selected_topic_id = topic_id
        
        # Find topic name
        topic_name = ""
        for t in self.subject_cfg.topics:
            if t["id"] == topic_id:
                topic_name = t["name"]
                break
                
        # Fetch stats
        from modules.lesson_mode import get_topics_progress
        progress = get_topics_progress(self.subject_id).get(topic_id, {})
        max_score = progress.get("max_score", "Chưa học")
        attempts = progress.get("attempts", 0)
        
        # Check weakness
        is_weak = False
        try:
            from modules.weakness_detector import get_weak_topics
            is_weak = topic_id in [w["topic_id"] for w in get_weak_topics(self.subject_id)]
        except Exception:
            pass
            
        tokens = _theme_tokens()

        if is_weak:
            status_str = "Cần ôn lại"
            status_color = tokens["COLOR_RED"]
        elif max_score != "Chưa học":
            status_str = "Đã thành thạo" if float(max_score) >= 7.0 else "Đang luyện"
            status_color = tokens["COLOR_GREEN"] if float(max_score) >= 7.0 else tokens["COLOR_YELLOW"]
        else:
            status_str = "Chưa bắt đầu"
            status_color = tokens["COLOR_TEXT_MUTED"]

        self.detail_title.setText(topic_name)
        self.detail_stats_score._value_lbl.setText(
            str(max_score) if max_score != "Chưa học" else "—"
        )
        self.detail_stats_status._value_lbl.setText(status_str)
        self.detail_stats_status._value_lbl.setStyleSheet(
            f"color: {status_color}; font-weight: bold; border: none; background: transparent;"
        )
        self.detail_stats_attempts._value_lbl.setText(str(attempts))

        for card in self._cards:
            card.set_selected(card.topic_id == topic_id)
                
        self.detail_panel.show()

    def _on_diff_btn_clicked(self):
        sender = self.sender()
        self._selected_difficulty = sender.property("diff_val")
        self.update_difficulty_buttons()

    def update_difficulty_buttons(self):
        tokens = _theme_tokens()
        diff_colors = {
            "easy": tokens["COLOR_GREEN"],
            "medium": tokens["COLOR_YELLOW"],
            "hard": tokens["COLOR_RED"],
        }
        for btn in self.diff_btns:
            val = btn.property("diff_val")
            accent = diff_colors.get(val, tokens["COLOR_ACCENT"])
            if val == self._selected_difficulty:
                btn.setChecked(True)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {accent};
                        color: #FFFFFF;
                        border: none;
                        border-radius: 8px;
                        font-weight: bold;
                    }}
                """)
            else:
                btn.setChecked(False)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {tokens['BG_SIDEBAR']};
                        color: {tokens['COLOR_TEXT']};
                        border: 1px solid {tokens['BORDER']};
                        border-radius: 8px;
                    }}
                    QPushButton:hover {{
                        border-color: {accent};
                        background: {tokens['BG_HOVER']};
                    }}
                """)

    # ── LESSON FLOW CONTROLLER ──
    
    def _start_lesson(self):
        if not hasattr(self, "_selected_topic_id") or not self._selected_topic_id:
            self.status.set_error("Vui lòng chọn một chủ đề học tập từ lộ trình trước!")
            return
            
        topic_id = self._selected_topic_id
        diff = self._selected_difficulty
        
        # Get topic name
        topic_name = ""
        for t in self.subject_cfg.topics:
            if t["id"] == topic_id:
                topic_name = t["name"]
                break
                
        self.config_area.hide()
        self.summary_area.hide()
        self.lesson_area.hide()
        self.status.set_loading("Đang kết nối tài liệu RAG và xây dựng bài học tương tác...")
        
        def _gen():
            from modules.lesson_mode import generate_lesson
            return generate_lesson(topic_name, self.subject_id, diff)

        self._worker = LLMWorker(_gen)
        self._worker.result.connect(self._on_lesson_ready)
        self._worker.error.connect(lambda e: self._on_generation_error(e))
        self._thread = run_in_thread(self._worker)

    def _on_generation_error(self, err: str):
        self.status.set_error(f"Lỗi tạo bài học: {err}")
        self.config_area.show()

    def _on_lesson_ready(self, questions: list):
        if not questions:
            self.status.set_error("Không thể tạo câu hỏi. Vui lòng thử lại!")
            self.config_area.show()
            return
            
        self._questions = questions
        self._current_idx = 0
        self._correct_count = 0
        self._duration_start = time.time()
        self._answers_details.clear()
        self._mistakes.clear()
        
        self.status.clear_status()
        self.lesson_area.show()
        topic_name = ""
        for t in self.subject_cfg.topics:
            if t["id"] == self._selected_topic_id:
                topic_name = t["name"]
                break
        self.lesson_topic_lbl.setText(topic_name)
        self._show_question()

    def _show_question(self):
        # Reset local widgets
        self.feedback_frame.hide()
        self.submit_btn.show()
        self.submit_btn.setEnabled(True)
        
        # Clear option container
        for i in reversed(range(self.option_layout.count())):
            w = self.option_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
                
        q = self._questions[self._current_idx]
        total = len(self._questions)
        
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(self._current_idx)
        self.prog_lbl.setText(f"{self._current_idx + 1}/{total}")
        self.streak_lbl.setText(f"Đúng: {self._correct_count}")

        q_type = q.get("type", "multiple_choice")
        self.q_type_badge.setText(_QTYPE_LABELS.get(q_type, "Câu hỏi"))
        self.question_title.setText(q.get("question", "Đề bài"))

        tokens = _theme_tokens()
        opt_style = self._option_btn_style(tokens)

        if q_type == "multiple_choice":
            self._selected_mc_option = None
            options = q.get("options", [])
            for opt in options:
                btn = QPushButton(opt)
                btn.setMinimumHeight(48)
                btn.setCheckable(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(opt_style)
                btn.clicked.connect(lambda checked, b=btn: self._select_mc(b))
                self.option_layout.addWidget(btn)

        elif q_type == "true_false":
            self._selected_tf_option = None
            row = QHBoxLayout()
            row.setSpacing(10)
            for opt in ["Đúng", "Sai"]:
                btn = QPushButton(opt)
                btn.setMinimumHeight(48)
                btn.setCheckable(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(opt_style)
                btn.clicked.connect(lambda checked, b=btn: self._select_tf(b))
                row.addWidget(btn)
            widget = QWidget()
            widget.setLayout(row)
            self.option_layout.addWidget(widget)

        elif q_type == "fill_blank":
            self.fill_input = QLineEdit()
            self.fill_input.setPlaceholderText("Nhập đáp án của bạn...")
            self.fill_input.setFixedHeight(48)
            self.fill_input.setStyleSheet(f"""
                QLineEdit {{
                    background: {tokens['BG_WIDGET']};
                    color: {tokens['COLOR_TEXT']};
                    border: 1px solid {tokens['BORDER']};
                    border-radius: 10px;
                    padding: 0 14px;
                    font-size: 11pt;
                }}
                QLineEdit:focus {{
                    border: 2px solid {tokens['COLOR_ACCENT']};
                }}
            """)
            self.option_layout.addWidget(self.fill_input)

        elif q_type == "matching":
            self._selected_matching_left = None
            self._selected_matching_right = None
            self._matched_pairs.clear()
            
            grid = QGridLayout()
            left_items = q.get("left_items", [])
            right_items = q.get("right_items", [])
            
            # Shuffle columns for game difficulty
            shuffled_left = list(left_items)
            shuffled_right = list(right_items)
            random.seed(int(time.time()))
            random.shuffle(shuffled_left)
            random.shuffle(shuffled_right)
            
            self._matching_left_btns = []
            self._matching_right_btns = []
            
            for idx, item in enumerate(shuffled_left):
                btn = QPushButton(item)
                btn.setMinimumHeight(44)
                btn.setCheckable(True)
                btn.setStyleSheet(opt_style)
                btn.clicked.connect(lambda checked, b=btn: self._matching_left_clicked(b))
                grid.addWidget(btn, idx, 0)
                self._matching_left_btns.append(btn)

            for idx, item in enumerate(shuffled_right):
                btn = QPushButton(item)
                btn.setMinimumHeight(44)
                btn.setCheckable(True)
                btn.setStyleSheet(opt_style)
                btn.clicked.connect(lambda checked, b=btn: self._matching_right_clicked(b))
                grid.addWidget(btn, idx, 1)
                self._matching_right_btns.append(btn)
                
            widget = QWidget()
            widget.setLayout(grid)
            self.option_layout.addWidget(widget)

        elif q_type == "ordering":
            # Native list widget with drag & drop
            self.order_list = QListWidget()
            self.order_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
            self.order_list.setFixedHeight(120)
            self.order_list.setStyleSheet(f"""
                QListWidget {{
                    background: {tokens['BG_WIDGET']};
                    color: {tokens['COLOR_TEXT']};
                    border: 1px solid {tokens['BORDER']};
                    border-radius: 8px;
                    padding: 4px;
                }}
            """)
            
            items = list(q.get("items", []))
            # Shuffle items initially
            shuffled_items = list(items)
            random.seed(int(time.time()))
            random.shuffle(shuffled_items)
            
            for item in shuffled_items:
                self.order_list.addItem(item)
            self.option_layout.addWidget(self.order_list)

        elif q_type == "output_prediction":
            code_view = QLabel(q.get("code", ""))
            code_view.setFont(QFont("Consolas", 10))
            code_view.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            code_view.setStyleSheet(f"""
                QLabel {{
                    background: {tokens['BG_TERMINAL'] if 'BG_TERMINAL' in tokens else tokens['BG_SIDEBAR']};
                    border: 1px solid {tokens['BORDER']};
                    border-radius: 10px;
                    padding: 14px;
                    color: {tokens.get('COLOR_TEXT_TERMINAL', tokens['COLOR_TEXT'])};
                    font-family: Consolas, monospace;
                }}
            """)
            self.option_layout.addWidget(code_view)

            self.predict_input = QLineEdit()
            self.predict_input.setPlaceholderText("Nhập kết quả in ra màn hình...")
            self.predict_input.setFixedHeight(48)
            self.predict_input.setStyleSheet(f"""
                QLineEdit {{
                    background: {tokens['BG_WIDGET']};
                    color: {tokens['COLOR_TEXT']};
                    border: 1px solid {tokens['BORDER']};
                    border-radius: 10px;
                    padding: 0 14px;
                }}
                QLineEdit:focus {{
                    border: 2px solid {tokens['COLOR_ACCENT']};
                }}
            """)
            self.option_layout.addWidget(self.predict_input)
            
        self._question_start_time = time.time()

    # Helpers for selection
    def _select_mc(self, active_btn):
        # Uncheck others
        for i in range(self.option_layout.count()):
            w = self.option_layout.itemAt(i).widget()
            if isinstance(w, QPushButton) and w != active_btn:
                w.setChecked(False)
        self._selected_mc_option = active_btn.text() if active_btn.isChecked() else None

    def _select_tf(self, active_btn):
        # TF is in horizontal widget
        container = self.option_layout.itemAt(0).widget()
        if container:
            for btn in container.findChildren(QPushButton):
                if btn != active_btn:
                    btn.setChecked(False)
        self._selected_tf_option = active_btn.text() if active_btn.isChecked() else None

    def _matching_left_clicked(self, active_btn):
        for btn in self._matching_left_btns:
            if btn != active_btn:
                btn.setChecked(False)
        self._selected_matching_left = active_btn.text() if active_btn.isChecked() else None
        self._check_matching_pair()

    def _matching_right_clicked(self, active_btn):
        for btn in self._matching_right_btns:
            if btn != active_btn:
                btn.setChecked(False)
        self._selected_matching_right = active_btn.text() if active_btn.isChecked() else None
        self._check_matching_pair()

    def _check_matching_pair(self):
        if self._selected_matching_left and self._selected_matching_right:
            q = self._questions[self._current_idx]
            correct_pairs = q.get("correct_pairs", {})
            
            # Check correctness
            expected_right = correct_pairs.get(self._selected_matching_left)
            
            try:
                from ui.theme_manager import get_theme, PALETTES
                tokens = PALETTES[get_theme()]
                c_accent = tokens['COLOR_ACCENT']
                c_success = tokens['COLOR_GREEN']
                c_danger = tokens['COLOR_RED']
            except Exception:
                c_accent = "#5555ff"
                c_success = "#a6e3a1"
                c_danger = "#f38ba8"

            left_btn = next(b for b in self._matching_left_btns if b.text() == self._selected_matching_left)
            right_btn = next(b for b in self._matching_right_btns if b.text() == self._selected_matching_right)
            
            if expected_right == self._selected_matching_right:
                # Correct Pair
                self._matched_pairs[self._selected_matching_left] = self._selected_matching_right
                
                left_btn.setChecked(False)
                right_btn.setChecked(False)
                left_btn.setEnabled(False)
                right_btn.setEnabled(False)
                left_btn.setStyleSheet(f"background: {c_success}; color: #11111b; border: none; border-radius: 8px;")
                right_btn.setStyleSheet(f"background: {c_success}; color: #11111b; border: none; border-radius: 8px;")
            else:
                # Incorrect Pair: blink red and reset selection
                left_btn.setStyleSheet(f"background: {c_danger}; color: #11111b; border: none; border-radius: 8px;")
                right_btn.setStyleSheet(f"background: {c_danger}; color: #11111b; border: none; border-radius: 8px;")
                
                # Tiny delay simulation or immediate reset
                left_btn.setChecked(False)
                right_btn.setChecked(False)
                
            self._selected_matching_left = None
            self._selected_matching_right = None

    # ── GRADING LOGIC (LOCAL) ──
    
    def _on_submit_clicked(self):
        q = self._questions[self._current_idx]
        q_type = q.get("type", "multiple_choice")
        
        is_correct = False
        user_ans = ""
        correct_ans = ""
        
        if q_type == "multiple_choice":
            if not self._selected_mc_option:
                return  # Must select
            user_ans = self._selected_mc_option
            # Extract option prefix (A, B, C, D)
            prefix = user_ans.strip().split(".")[0].strip().upper()
            correct_ans = q.get("correct", "A").strip().upper()
            is_correct = (prefix == correct_ans)
            
        elif q_type == "true_false":
            if not self._selected_tf_option:
                return
            user_ans = self._selected_tf_option
            correct_ans = q.get("correct", "Đúng")
            is_correct = (user_ans == correct_ans)
            
        elif q_type == "fill_blank":
            user_ans = self.fill_input.text().strip()
            if not user_ans:
                return
            correct_ans = q.get("correct", "").strip()
            is_correct = (user_ans.lower() == correct_ans.lower())
            
        elif q_type == "matching":
            correct_pairs = q.get("correct_pairs", {})
            # Verify if all correct pairs are matched
            is_correct = (len(self._matched_pairs) == len(correct_pairs))
            user_ans = str(self._matched_pairs)
            correct_ans = str(correct_pairs)
            
        elif q_type == "ordering":
            # Read current order of list widget
            current_order = []
            for i in range(self.order_list.count()):
                current_order.append(self.order_list.item(i).text())
                
            original_items = q.get("items", [])
            correct_indices = q.get("correct_order", [])
            correct_order = [original_items[idx] for idx in correct_indices]
            
            is_correct = (current_order == correct_order)
            user_ans = " -> ".join(current_order)
            correct_ans = " -> ".join(correct_order)
            
        elif q_type == "output_prediction":
            user_ans = self.predict_input.text().strip()
            if not user_ans:
                return
            correct_ans = q.get("correct", "").strip()
            is_correct = (user_ans.lower() == correct_ans.lower())

        # Grade details recording
        time_spent = int(time.time() - self._question_start_time)
        self._answers_details.append({
            "question_type": q_type,
            "difficulty": q.get("difficulty", "medium"),
            "user_answer": user_ans,
            "correct_answer": correct_ans,
            "is_correct": 1 if is_correct else 0,
            "time_spent": time_spent
        })

        if is_correct:
            self._correct_count += 1
            self.streak_lbl.setText(f"Đúng: {self._correct_count}")
            self.feedback_title.setText("Chính xác!")
            tokens = _theme_tokens()
            self.feedback_title.setStyleSheet(f"color: {tokens['COLOR_GREEN']}; border: none; background: transparent;")
            self.feedback_text.setStyleSheet(f"color: {tokens['COLOR_TEXT']}; border: none; background: transparent;")
            self.feedback_frame.setStyleSheet(f"""
                QFrame#FeedbackFrame {{
                    background: {tokens['BG_SIDEBAR']};
                    border: 2px solid {tokens['COLOR_GREEN']};
                    border-radius: 12px;
                }}
            """)
            self.continue_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens['COLOR_GREEN']};
                    color: #FFFFFF;
                    border: none;
                    border-radius: 10px;
                    font-weight: bold;
                }}
            """)
        else:
            self.feedback_title.setText("Chưa đúng — cố gắng lên!")
            tokens = _theme_tokens()
            self.feedback_title.setStyleSheet(f"color: {tokens['COLOR_RED']}; border: none; background: transparent;")
            self.feedback_text.setStyleSheet(f"color: {tokens['COLOR_TEXT']}; border: none; background: transparent;")
            self.feedback_frame.setStyleSheet(f"""
                QFrame#FeedbackFrame {{
                    background: {tokens['BG_SIDEBAR']};
                    border: 2px solid {tokens['COLOR_RED']};
                    border-radius: 12px;
                }}
            """)
            self.continue_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens['COLOR_RED']};
                    color: #FFFFFF;
                    border: none;
                    border-radius: 10px;
                    font-weight: bold;
                }}
            """)
                
            # Log mistake for review summary later
            self._mistakes.append({
                "question": q.get("question", ""),
                "user_ans": user_ans,
                "correct_ans": correct_ans,
                "explanation": q.get("explanation", "Không có giải thích.")
            })

        self.feedback_text.setText(q.get("explanation", ""))
        self.submit_btn.hide()
        self.feedback_frame.show()

    def _on_continue_clicked(self):
        self._current_idx += 1
        if self._current_idx >= len(self._questions):
            self._finish_lesson()
        else:
            self._show_question()

    # ── END LESSON SUMMARY ──
    
    def _finish_lesson(self):
        self.lesson_area.hide()
        
        # Calculate summary metrics
        total = len(self._questions)
        accuracy = (self._correct_count / total) * 100 if total > 0 else 0
        score = round((self._correct_count / total) * 10, 1) if total > 0 else 0.0
        duration = int(time.time() - self._duration_start)
        
        # Determine weak topic based on local answers
        # If score is low (e.g. < 7.0), current topic is marked as weak
        topic_id = self._selected_topic_id
        topic_name = ""
        for t in self.subject_cfg.topics:
            if t["id"] == topic_id:
                topic_name = t["name"]
                break
        
        weak_topic_msg = ""
        if score < 7.0:
            weak_topic_msg = f"Chủ đề <b>{topic_name}</b> cần ôn thêm."
            self.summary_title.setText("Cố gắng thêm nhé!")
            rating = f"{max(1, int(score / 2))}/5"
        else:
            weak_topic_msg = f"Bạn đã nắm tốt chủ đề <b>{topic_name}</b>!"
            self.summary_title.setText("Xuất sắc!")
            rating = f"{min(5, max(3, int(score / 2)))}/5"

        self.score_ring.setText(f"{score}")
        self.stars_lbl.setText(rating)
        self.summary_stats.setText(
            f"Chính xác <b>{self._correct_count}/{total}</b> câu "
            f"({accuracy:.0f}%) · Thời gian <b>{duration}s</b><br><br>{weak_topic_msg}"
        )
        self.apply_theme_styles()
        
        # Show/Hide review mistakes list
        if self._mistakes:
            self.review_btn.show()
        else:
            self.review_btn.hide()
        self.mistakes_scroll.hide()
        
        self.summary_area.show()
        
        # Database persistence asynchronously
        def _save_to_db():
            from modules.lesson_mode import save_lesson_session, save_lesson_answer
            session_id = save_lesson_session(
                self.subject_id,
                topic_id,
                score,
                total,
                self._correct_count,
                duration
            )
            for idx, ans in enumerate(self._answers_details):
                save_lesson_answer(
                    session_id,
                    idx,
                    ans["question_type"],
                    topic_id,
                    ans["difficulty"],
                    ans["user_answer"],
                    ans["correct_answer"],
                    ans["is_correct"],
                    ans["time_spent"]
                )
            return True

        self._worker = LLMWorker(_save_to_db)
        self._thread = run_in_thread(self._worker)

    def _show_mistakes_review(self):
        # Clear previous mistakes widgets
        for i in reversed(range(self.mistakes_layout.count())):
            w = self.mistakes_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
                
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
        except Exception:
            tokens = {"COLOR_TEXT": "#ffffff", "COLOR_TEXT_MUTED": "#888899", "COLOR_RED": "#ff5555", "COLOR_GREEN": "#55ff55", "BORDER": "#444455"}

        for idx, m in enumerate(self._mistakes, 1):
            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            frame.setStyleSheet(f"QFrame {{ border: 1px solid {tokens['BORDER']}; border-radius: 6px; padding: 8px; }}")
            
            box = QVBoxLayout(frame)
            box.setContentsMargins(6, 6, 6, 6)
            box.setSpacing(4)
            
            lbl_q = QLabel(f"<b>Câu {idx}:</b> {m['question']}")
            lbl_q.setWordWrap(True)
            lbl_q.setStyleSheet(f"color: {tokens['COLOR_TEXT']}; border: none;")
            box.addWidget(lbl_q)
            
            lbl_user = QLabel(f"• Đáp án đã chọn: <font color='{tokens['COLOR_RED']}'>{m['user_ans']}</font>")
            lbl_user.setWordWrap(True)
            lbl_user.setStyleSheet("border: none;")
            box.addWidget(lbl_user)
            
            lbl_correct = QLabel(f"• Đáp án đúng: <font color='{tokens['COLOR_GREEN']}'>{m['correct_ans']}</font>")
            lbl_correct.setWordWrap(True)
            lbl_correct.setStyleSheet("border: none;")
            box.addWidget(lbl_correct)
            
            lbl_exp = QLabel(f"<i>Giải thích:</i> {m['explanation']}")
            lbl_exp.setWordWrap(True)
            lbl_exp.setStyleSheet(f"color: {tokens['COLOR_TEXT_MUTED']}; border: none;")
            box.addWidget(lbl_exp)
            
            self.mistakes_layout.insertWidget(self.mistakes_layout.count() - 1, frame)
            
        self.mistakes_scroll.show()
        self.review_btn.hide()

    def _exit_summary(self):
        self.summary_area.hide()
        self.config_area.show()
        self._populate_topics()


# Alias for backward compatibility with main_window.py
PracticeTab = LessonTab
