"""
ui/tabs/tab_explain.py — NotebookLM-style Q&A Tab
Layout: Left = Sources panel | Right = Chat conversation
"""
from pathlib import Path

DEFAULT_TOP_K = 5

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLineEdit, QPushButton, QLabel, QFrame, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSlot, QPoint, QObject
from PyQt6.QtCore import pyqtSignal as Signal
from PyQt6.QtGui import QFont

from ui.widgets import (
    SourcesPanel, ChatBubble, CitationPopup, StatusLabel,
    SURFACE_0, SURFACE_1, SURFACE_2,
    BORDER, BORDER_STRONG,
    TEXT_MAIN, TEXT_MUTED, TEXT_ACCENT, TEXT_SUCCESS, TEXT_DANGER,
    ACCENT_BG,
)
from ui.worker import StreamWorker, run_in_thread


class ExplainTab(QWidget):
    def __init__(self, subject_id: str, subject_config, parent=None):
        super().__init__(parent)
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._thread = None
        self._worker = None
        self._current_chunks: list[dict] = []
        self._chat_bubbles: list[ChatBubble] = []
        self._citation_popup = CitationPopup(self)
        self._citation_popup.hide()
        self._current_assistant_bubble: ChatBubble | None = None
        self._setup_ui()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        self._splitter = splitter
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {BORDER}; }}")

        # ── Left: Sources panel ───────────────────────────────────────────
        self.sources_panel = SourcesPanel()
        splitter.addWidget(self.sources_panel)

        # ── Right: Chat area ──────────────────────────────────────────────
        self.chat_widget = QWidget()
        chat_layout = QVBoxLayout(self.chat_widget)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        # Top bar
        top_bar = QFrame()
        top_bar.setObjectName("ChatTopBar")
        self.top_bar = top_bar
        top_bar.setFixedHeight(44)
        top_row = QHBoxLayout(top_bar)
        top_row.setContentsMargins(16, 0, 12, 0)
        top_row.setSpacing(10)

        self.title_lbl = QLabel("Cuộc trò chuyện")
        self.title_lbl.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.title_lbl.setObjectName("ChatTitle")
        top_row.addWidget(self.title_lbl)
        top_row.addStretch()

        self.clear_btn = QPushButton("Xóa chat")
        self.clear_btn.setObjectName("ClearChatBtn")
        self.clear_btn.setFixedHeight(30)
        self.clear_btn.setMinimumWidth(76)
        self.clear_btn.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setToolTip("Xóa toàn bộ cuộc trò chuyện")
        self.clear_btn.clicked.connect(self._clear_chat)
        top_row.addWidget(self.clear_btn)
        chat_layout.addWidget(top_bar)

        # Status bar (hidden when idle)
        self.status = StatusLabel()
        chat_layout.addWidget(self.status)

        # Chat scroll area
        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)

        self._chat_container = QWidget()
        self._chat_vbox = QVBoxLayout(self._chat_container)
        self._chat_vbox.setContentsMargins(20, 20, 20, 20)
        self._chat_vbox.setSpacing(16)
        self._chat_vbox.addStretch()

        self._chat_scroll.setWidget(self._chat_container)
        chat_layout.addWidget(self._chat_scroll, 1)

        # ── Input area ────────────────────────────────────────────────────
        input_frame = QFrame()
        self.input_frame = input_frame
        self.input_frame.setObjectName("InputFrame")
        self.input_frame.setFixedHeight(60)
        inp_row = QHBoxLayout(self.input_frame)
        inp_row.setContentsMargins(12, 10, 12, 10)
        inp_row.setSpacing(0)

        # Inner container (input + send button)
        input_container = QFrame()
        self.input_container = input_container
        self.input_container.setObjectName("InputContainer")
        c_layout = QHBoxLayout(self.input_container)
        c_layout.setContentsMargins(4, 4, 4, 4)
        c_layout.setSpacing(6)

        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Đặt câu hỏi về tài liệu của bạn...")
        self.query_input.setFont(QFont("Inter", 10))
        self.query_input.setFixedHeight(32)
        self.query_input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                color: {TEXT_MAIN};
                padding: 0 10px;
            }}
            QLineEdit:focus {{ border: none; outline: none; }}
        """)
        self.query_input.returnPressed.connect(self._on_ask)
        c_layout.addWidget(self.query_input)

        self.ask_btn = QPushButton("Gửi")
        self.ask_btn.setFixedSize(48, 32)
        self.ask_btn.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        self.ask_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ask_btn.setStyleSheet(f"""
            QPushButton {{
                background: {TEXT_ACCENT};
                color: {SURFACE_0};
                border: none;
                border-radius: 8px;
                text-align: center;
                padding: 0;
            }}
            QPushButton:hover {{ background: #8fa0f0; }}
            QPushButton:pressed {{ background: #6a7bce; }}
            QPushButton:disabled {{ background: {SURFACE_2}; color: {TEXT_MUTED}; }}
        """)
        self.ask_btn.clicked.connect(self._on_ask)
        c_layout.addWidget(self.ask_btn)

        inp_row.addWidget(self.input_container)
        chat_layout.addWidget(self.input_frame)

        splitter.addWidget(self.chat_widget)
        splitter.setSizes([240, 860])
        root.addWidget(splitter)
        self.apply_theme_styles()
        self._load_existing_sources()

    def apply_theme_styles(self):
        """Update all inline-styled widgets in ExplainTab to current theme."""
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]

            self._splitter.setStyleSheet(
                f"QSplitter::handle {{ background: {tokens['BORDER']}; }}"
            )
            self.chat_widget.setStyleSheet(
                f"background: {tokens['BG_SIDEBAR']};"
            )
            self.top_bar.setStyleSheet(f"""
                QFrame#ChatTopBar {{
                    background: {tokens['BG_MAIN']};
                    border-bottom: 1px solid {tokens['BORDER']};
                }}
            """)
            self.title_lbl.setStyleSheet(
                f"color:{tokens['COLOR_TEXT']}; background:transparent; border:none;"
            )
            self.clear_btn.setStyleSheet(f"""
                QPushButton#ClearChatBtn {{
                    background: {tokens['BG_WIDGET']};
                    border: 1px solid {tokens['BORDER']};
                    border-radius: 8px;
                    color: {tokens['COLOR_TEXT']};
                    padding: 0 12px;
                }}
                QPushButton#ClearChatBtn:hover {{
                    background: {tokens['BG_HOVER']};
                    color: {tokens['COLOR_RED']};
                    border-color: {tokens['COLOR_RED']};
                }}
                QPushButton#ClearChatBtn:pressed {{
                    background: {tokens['BG_CHECKED']};
                }}
            """)
            self._chat_scroll.setStyleSheet(
                f"QScrollArea{{background:{tokens['BG_SIDEBAR']};border:none;}}"
            )
            self._chat_container.setStyleSheet(
                f"background:{tokens['BG_SIDEBAR']};"
            )
            self.input_frame.setStyleSheet(f"""
                QFrame#InputFrame {{
                    background: {tokens['BG_MAIN']};
                    border-top: 1px solid {tokens['BORDER']};
                }}
            """)
            self.input_container.setStyleSheet(f"""
                QFrame#InputContainer {{
                    background: {tokens['BG_SIDEBAR']};
                    border: 1px solid {tokens['BORDER']};
                    border-radius: 10px;
                }}
                QFrame#InputContainer:focus-within {{
                    border-color: {tokens['COLOR_ACCENT']};
                }}
            """)
            self.query_input.setStyleSheet(f"""
                QLineEdit {{
                    background: transparent;
                    border: none;
                    color: {tokens['COLOR_TEXT']};
                    padding: 0 10px;
                }}
                QLineEdit:focus {{ border: none; outline: none; }}
            """)
            # ask_btn: accent hover adapts to theme
            accent = tokens['COLOR_ACCENT']
            accent_hover = tokens['COLOR_ACCENT_HOVER']
            self.ask_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {accent};
                    color: {tokens['BG_MAIN']};
                    border: none;
                    border-radius: 8px;
                    text-align: center;
                    padding: 0;
                }}
                QPushButton:hover {{ background: {accent_hover}; }}
                QPushButton:pressed {{ background: {tokens['BG_CHECKED']}; color: {accent}; }}
                QPushButton:disabled {{ background: {tokens['BG_WIDGET']}; color: {tokens['COLOR_TEXT_MUTED']}; }}
            """)
        except Exception:
            pass

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _load_existing_sources(self):
        try:
            self.sources_panel._cards.clear()
            for i in reversed(range(self.sources_panel._cards_layout.count() - 1)):
                w = self.sources_panel._cards_layout.itemAt(i).widget()
                if w:
                    w.deleteLater()
            self.sources_panel._update_count()

            doc_dir = Path(self.subject_cfg.documents_dir)
            if not doc_dir.exists():
                return
            for f in doc_dir.iterdir():
                if f.suffix.lower() in (".pdf", ".docx", ".doc", ".txt"):
                    self.sources_panel.add_card(str(f), f.name, 0)
        except Exception:
            pass

    def _scroll_to_bottom(self):
        bar = self._chat_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _add_bubble(self, role: str) -> ChatBubble:
        bubble = ChatBubble(role)
        bubble.citation_clicked.connect(self._on_citation_clicked)
        idx = self._chat_vbox.count() - 1
        self._chat_vbox.insertWidget(idx, bubble)
        self._chat_bubbles.append(bubble)
        return bubble

    # ── Ask ───────────────────────────────────────────────────────────────────
    def _on_ask(self):
        query = self.query_input.text().strip()
        if not query or (self._thread and self._thread.isRunning()):
            return

        self.ask_btn.setEnabled(False)
        self.query_input.setEnabled(False)
        self.query_input.clear()
        self._citation_popup.hide()

        user_bubble = self._add_bubble("user")
        user_bubble.set_text(query)
        self._scroll_to_bottom()

        asst_bubble = self._add_bubble("assistant")
        asst_bubble.begin_streaming()
        self._current_assistant_bubble = asst_bubble
        self._scroll_to_bottom()

        class _StatusBridge(QObject):
            status_changed  = Signal(str)
            chunks_received = Signal(object)

        self._status_bridge = _StatusBridge()
        self._status_bridge.status_changed.connect(self.status.set_loading)
        self._status_bridge.chunks_received.connect(self._on_chunks_received)

        def _stream():
            from core.pipeline.advanced_rag import generate_rag_response
            return generate_rag_response(
                query,
                self.subject_id,
                self.subject_cfg,
                status_cb=self._status_bridge.status_changed.emit,
                chunks_cb=self._status_bridge.chunks_received.emit,
                search_mode="hybrid",
            )

        self._worker = StreamWorker(_stream)
        self._worker.token.connect(asst_bubble.append_token)
        self._worker.token.connect(lambda _: self._scroll_to_bottom())
        self._worker.error.connect(lambda e: self.status.set_error(e))
        self._worker.finished.connect(self._on_done)
        self._thread = run_in_thread(self._worker)

    def _on_done(self):
        self.ask_btn.setEnabled(True)
        self.query_input.setEnabled(True)
        self.query_input.setFocus()
        if self._current_assistant_bubble:
            self._current_assistant_bubble.finalize()

        self.status.set_done("Tìm thấy nguồn liên quan")
        self._scroll_to_bottom()

    @pyqtSlot(object)
    def _on_chunks_received(self, chunks):
        self._current_chunks = chunks

    # ── Clear chat ────────────────────────────────────────────────────────────
    def _clear_chat(self):
        for bubble in self._chat_bubbles:
            self._chat_vbox.removeWidget(bubble)
            bubble.deleteLater()
        self._chat_bubbles.clear()
        self._current_chunks = []
        self._current_assistant_bubble = None
        self._citation_popup.hide()

        # Khôi phục lại toàn bộ tài liệu của môn học ở panel trái
        self._load_existing_sources()

        self.status.clear_status()

    # ── Citation clicked ──────────────────────────────────────────────────────
    @pyqtSlot(int)
    def _on_citation_clicked(self, num: int):
        idx = num - 1
        if 0 <= idx < len(self._current_chunks):
            chunk = self._current_chunks[idx]
            pos = self.mapToGlobal(QPoint(
                self.width() // 2 - 200,
                self.height() // 2 - 150,
            ))
            self._citation_popup.move(pos)
            self._citation_popup.show_citation(num, chunk)


    # ── Subject switch ────────────────────────────────────────────────────────
    def set_subject(self, subject_id: str, subject_config):
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._clear_chat()