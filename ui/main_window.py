"""
ui/main_window.py — Main application window (QMainWindow)
Layout: Left sidebar (subject + nav) | Right content (stacked pages)
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QComboBox, QStackedWidget,
    QFrame, QSizePolicy, QScrollArea,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QIcon

from utils.subject_loader import get_all_subjects
from ui.tabs.tab_explain import ExplainTab
from ui.tabs.tab_code import CodeTab
from ui.tabs.tab_sandbox import SandboxTab
from ui.tabs.tab_quiz import QuizTab
from ui.tabs.tab_practice import PracticeTab
from ui.tabs.tab_flashcard import FlashcardTab
from ui.tabs.tab_path import PathTab
from ui.tabs.tab_weakness import WeaknessTab
from ui.tabs.tab_document import DocumentTab
from ui.tabs.tab_visualize import VisualizeTab

# ── Nav button IDs ────────────────────────────────────────────────────────────
NAV_ITEMS = [
    ("📖", "Giải thích",   "explain"),
    ("📁", "Tài liệu",     "document"),
    ("🌳", "Visualizer",   "visualize"),   # shown only if has_visualizer
    ("💻", "Code",         "code"),
    ("▶️", "Sandbox",      "sandbox"),
    ("📝", "Quiz",         "quiz"),
    ("🎯", "Luyện tập",    "practice"),
    ("🃏", "Flashcard",    "flashcard"),
    ("🗺️", "Lộ trình",    "path"),
    ("⚠️", "Điểm yếu",    "weakness"),
]


class NavButton(QPushButton):
    def __init__(self, icon_text: str, label: str, page_id: str, parent=None):
        super().__init__(parent)
        self.page_id = page_id
        self.setText(f"  {icon_text}  {label}")
        self.setCheckable(True)
        self.setFixedHeight(40)
        self.setFont(QFont("Inter", 10))
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class Sidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self.setObjectName("Sidebar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 16)
        layout.setSpacing(4)

        # App title
        title = QLabel("🎓 Study Agent")
        title.setFont(QFont("Inter", 16, QFont.Weight.Bold))
        title.setObjectName("AppTitle")
        layout.addWidget(title)

        # Subject selector
        layout.addSpacing(16)
        sub_label = QLabel("📚 MÔN HỌC")
        sub_label.setFont(QFont("Inter", 10))
        sub_label.setObjectName("SectionLabel")
        layout.addWidget(sub_label)

        layout.addSpacing(4)
        self.subject_combo = QComboBox()
        self.subject_combo.setFont(QFont("Inter", 10))
        self.subject_combo.setFixedHeight(36)
        layout.addWidget(self.subject_combo)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("Divider")
        layout.addSpacing(12)
        layout.addWidget(line)
        layout.addSpacing(8)

        # Nav buttons container
        self.nav_buttons: dict[str, NavButton] = {}
        self.nav_layout = QVBoxLayout()
        self.nav_layout.setSpacing(4)
        layout.addLayout(self.nav_layout)

        layout.addStretch()

        # Footer separator
        footer_line = QFrame()
        footer_line.setFrameShape(QFrame.Shape.HLine)
        footer_line.setObjectName("Divider")
        layout.addWidget(footer_line)
        layout.addSpacing(8)

        # Footer info
        self.info_label = QLabel()
        self.info_label.setFont(QFont("Inter", 8))
        self.info_label.setObjectName("FooterLabel")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

    def rebuild_nav(self, has_visualizer: bool):
        """Rebuild nav buttons based on subject capabilities."""
        # Clear old buttons
        for btn in self.nav_buttons.values():
            self.nav_layout.removeWidget(btn)
            btn.deleteLater()
        self.nav_buttons.clear()

        for icon_text, label, page_id in NAV_ITEMS:
            if page_id == "visualize" and not has_visualizer:
                continue
            btn = NavButton(icon_text, label, page_id)
            self.nav_buttons[page_id] = btn
            self.nav_layout.addWidget(btn)

        # Select first button by default
        if self.nav_buttons:
            first = next(iter(self.nav_buttons.values()))
            first.setChecked(True)


class ContentPlaceholder(QWidget):
    """Temporary placeholder shown while a module is not yet implemented."""
    def __init__(self, title: str, sprint: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("🚧")
        icon.setFont(QFont("Inter", 48))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        lbl = QLabel(f"<b>{title}</b>")
        lbl.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        info = QLabel(f"Module đang được xây dựng — {sprint}")
        info.setFont(QFont("Inter", 11))
        info.setObjectName("PlaceholderInfo")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Local Study RAG Agent")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        self.subjects = get_all_subjects()
        self._setup_ui()
        self._connect_signals()
        self._load_subject(next(iter(self.subjects)))  # load first subject

    # ── UI setup ──────────────────────────────────────────────────────────────
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        root.addWidget(self.sidebar)

        # Vertical separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setObjectName("VDivider")
        root.addWidget(sep)

        # Stacked content area
        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        first_subject_id = next(iter(self.subjects))
        first_subject = self.subjects[first_subject_id]

        def safe_tab(tab_class, name):
            try:
                return tab_class(first_subject_id, first_subject)
            except Exception as e:
                return ContentPlaceholder(name, "Tính năng đang ở nhánh khác")

        # Build placeholder pages
        self.pages: dict[str, QWidget] = {
            "explain":   safe_tab(ExplainTab, "Giải thích"),
            "document":  safe_tab(DocumentTab, "Tài liệu"),
            "visualize": safe_tab(VisualizeTab, "Visualizer"),
            "code":      safe_tab(CodeTab, "Code"),
            "sandbox":   safe_tab(SandboxTab, "Sandbox"),
            "quiz":      safe_tab(QuizTab, "Quiz"),
            "practice":  safe_tab(PracticeTab, "Luyện tập"),
            "flashcard": safe_tab(FlashcardTab, "Flashcard"),
            "path":      safe_tab(PathTab, "Lộ trình"),
            "weakness":  safe_tab(WeaknessTab, "Điểm yếu"),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        # Populate subject combo
        for sid, cfg in self.subjects.items():
            self.sidebar.subject_combo.addItem(cfg.display_name, sid)

    # ── Signals ───────────────────────────────────────────────────────────────
    def _connect_signals(self):
        self.sidebar.subject_combo.currentIndexChanged.connect(
            lambda _: self._load_subject(self.sidebar.subject_combo.currentData())
        )

    def _load_subject(self, subject_id: str):
        subject = self.subjects[subject_id]
        self.sidebar.rebuild_nav(subject.has_visualizer)
        self.sidebar.info_label.setText(
            f"Collection  {subject.chroma_collection}\n"
            f"Sandbox  {'C/C++' if subject.code_language == 'c_cpp' else 'Python'}\n"
            f"Lang  {', '.join(subject.languages).upper()}"
        )

        # Update subject in all pages that support it
        for page in self.pages.values():
            if hasattr(page, "set_subject"):
                try:
                    page.set_subject(subject_id, subject)
                except Exception:
                    pass

        # Connect nav buttons → stack pages
        for page_id, btn in self.sidebar.nav_buttons.items():
            btn.clicked.connect(lambda checked, pid=page_id: self._navigate(pid))

        # Show first page
        first_id = next(iter(self.sidebar.nav_buttons))
        self._navigate(first_id)

    def _navigate(self, page_id: str):
        # Update button states
        for pid, btn in self.sidebar.nav_buttons.items():
            btn.setChecked(pid == page_id)

        # Switch page
        if page_id in self.pages:
            self.stack.setCurrentWidget(self.pages[page_id])
