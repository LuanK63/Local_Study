"""
ui/tabs/tab_explain.py — NotebookLM-style Q&A Tab
Layout: Left = Sources panel | Right = Chat conversation
Features:
  - Citation [1],[2],... clickable in answers
  - Citation popup shows exact source chunk
  - Sources panel with file upload management
"""
import shutil
from pathlib import Path
DEFAULT_TOP_K = 5   # number of chunks retrieved per query

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLineEdit, QPushButton, QLabel, QComboBox,
    QFrame, QScrollArea, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSlot, QPoint, QObject
from PyQt6.QtCore import pyqtSignal as Signal
from PyQt6.QtGui import QFont

from ui.widgets import (
    SourcesPanel, ChatBubble, CitationPopup, StatusLabel, IngestProgressWidget,
)
from ui.worker import StreamWorker, run_in_thread


class ExplainTab(QWidget):
    def __init__(self, subject_id: str, subject_config, parent=None):
        super().__init__(parent)
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._thread = None
        self._worker = None
        self._current_chunks: list[dict] = []   # retrieved chunks for last query
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
        splitter.setStyleSheet("QSplitter::handle { background: #2a2b3d; }")

        # ── Left: Sources panel ──────────────────────────────────────────
        self.sources_panel = SourcesPanel()
        self.sources_panel.add_source_clicked.connect(self._add_source)
        self.sources_panel.remove_source_requested.connect(self._on_remove_source)
        splitter.addWidget(self.sources_panel)

        # ── Right: Chat area ─────────────────────────────────────────────
        chat_widget = QWidget()
        chat_widget.setStyleSheet("background: #1a1b2e;")
        chat_layout = QVBoxLayout(chat_widget)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        # Top bar
        top_bar = QFrame()
        top_bar.setObjectName("ChatTopBar")
        top_bar.setFixedHeight(48)
        top_bar.setStyleSheet("""
            QFrame#ChatTopBar {
                background: #0e0f1e;
                border-bottom: 1px solid #2a2b3d;
            }
        """)
        top_row = QHBoxLayout(top_bar)
        top_row.setContentsMargins(20, 0, 20, 0)
        top_row.setSpacing(12)

        title_lbl = QLabel("💬 Cuộc trò chuyện")
        title_lbl.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color:#cba6f7; background:transparent;")
        top_row.addWidget(title_lbl)
        top_row.addStretch()


        # Clear chat button — icon only, clean
        clear_btn = QPushButton("🗑")
        clear_btn.setFixedSize(32, 32)
        clear_btn.setFont(QFont("Inter", 12))
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setToolTip("Xóa cuộc trò chuyện")
        clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #3a3c52;
                border-radius: 8px;
                padding: 0;
                color: #5a5d78;
            }
            QPushButton:hover {
                background: #2a2b3d;
                color: #f38ba8;
                border-color: #f38ba8;
            }
        """)
        clear_btn.clicked.connect(self._clear_chat)
        top_row.addWidget(clear_btn)
        chat_layout.addWidget(top_bar)

        # Status bar
        self.status = StatusLabel()
        self.status.setContentsMargins(20, 6, 20, 0)
        chat_layout.addWidget(self.status)

        # Chat scroll area
        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setStyleSheet(
            "QScrollArea{background:#1a1b2e;border:none;}"
        )

        self._chat_container = QWidget()
        self._chat_container.setStyleSheet("background:#1a1b2e;")
        self._chat_vbox = QVBoxLayout(self._chat_container)
        self._chat_vbox.setContentsMargins(24, 20, 24, 20)
        self._chat_vbox.setSpacing(20)
        self._chat_vbox.addStretch()

        self._chat_scroll.setWidget(self._chat_container)
        chat_layout.addWidget(self._chat_scroll, 1)

        # ── Input area (full-width, send button inside) ──────────────────
        input_frame = QFrame()
        input_frame.setObjectName("InputFrame")
        input_frame.setStyleSheet("""
            QFrame#InputFrame {
                background: #0e0f1e;
                border-top: 1px solid #2a2b3d;
            }
        """)
        input_frame.setFixedHeight(64)
        inp_row = QHBoxLayout(input_frame)
        inp_row.setContentsMargins(16, 10, 16, 10)
        inp_row.setSpacing(0)

        # Container for input + send button overlay
        input_container = QFrame()
        input_container.setStyleSheet("""
            QFrame {
                background: #2a2b3d;
                border: 1.5px solid #3a3c52;
                border-radius: 14px;
            }
            QFrame:focus-within {
                border-color: #89b4fa;
            }
        """)
        container_layout = QHBoxLayout(input_container)
        container_layout.setContentsMargins(4, 4, 4, 4)
        container_layout.setSpacing(8)

        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Đặt câu hỏi về tài liệu của bạn...")
        self.query_input.setFont(QFont("Inter", 10))
        self.query_input.setFixedHeight(36)
        self.query_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #cdd6f4;
                padding: 4px 12px;
            }
            QLineEdit:focus {
                border: none;
                background: transparent;
            }
        """)
        self.query_input.returnPressed.connect(self._on_ask)
        container_layout.addWidget(self.query_input)

        self.ask_btn = QPushButton("↑")
        self.ask_btn.setFixedSize(36, 36)
        self.ask_btn.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        self.ask_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ask_btn.setStyleSheet("""
            QPushButton {
                background: #cba6f7;
                color: #1a1b2e;
                border: none;
                border-radius: 12px;
                text-align: center;
                padding: 0;
            }
            QPushButton:hover { background: #d4b5ff; }
            QPushButton:pressed { background: #b09ae0; }
            QPushButton:disabled { background: #3a3c52; color: #5a5d78; }
        """)
        self.ask_btn.clicked.connect(self._on_ask)
        container_layout.addWidget(self.ask_btn)

        inp_row.addWidget(input_container)
        chat_layout.addWidget(input_frame)

        splitter.addWidget(chat_widget)
        splitter.setSizes([260, 900])
        root.addWidget(splitter)

        # Load existing sources on startup
        self._load_existing_sources()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _load_existing_sources(self):
        """Scan the subject's documents dir and show existing files."""
        try:
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
        # Insert before the trailing stretch
        idx = self._chat_vbox.count() - 1
        self._chat_vbox.insertWidget(idx, bubble)
        self._chat_bubbles.append(bubble)
        return bubble

    # ── Add source (file upload) ──────────────────────────────────────────────
    def _add_source(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn tài liệu", "", "Documents (*.pdf *.docx *.txt)"
        )
        if not file_path:
            return
        if self._thread and self._thread.isRunning():
            self.status.set_error("Đang xử lý, vui lòng đợi...")
            return

        src = Path(file_path)

        # Show progress widget
        self.sources_panel.show_progress(src.name)
        self.status.set_loading(f"Đang nạp '{src.name}'...")

        # Thread-safe bridge: background thread sends (stage,done,total)
        # to main thread via a QObject signal
        class _ProgressBridge(QObject):
            progress = Signal(str, int, int)  # stage, done, total

        bridge = _ProgressBridge()
        bridge.progress.connect(self.sources_panel.update_progress)

        def _process():
            doc_dir = Path(self.subject_cfg.documents_dir)
            doc_dir.mkdir(parents=True, exist_ok=True)
            dest = doc_dir / src.name
            if src != dest:
                shutil.copy2(src, dest)

            def _cb(stage, done, total):
                bridge.progress.emit(stage, done, total)

            from core.retrieval.hybrid_retriever import ingest_document
            chunks_added = ingest_document(dest, self.subject_id, progress_cb=_cb)
            return str(dest), src.name, chunks_added

        from ui.worker import LLMWorker
        self._worker = LLMWorker(_process)
        self._worker.result.connect(self._on_source_added)
        self._worker.error.connect(self._on_source_error)
        self._thread = run_in_thread(self._worker)

    @pyqtSlot(object)
    def _on_source_added(self, result):
        dest_path, name, chunks = result
        self.sources_panel.finish_progress(chunks)
        self.sources_panel.add_card(dest_path, name, chunks)
        self.status.set_done(f"Đã thêm '{name}' — {chunks} đoạn")

    @pyqtSlot(str)
    def _on_source_error(self, err: str):
        self.sources_panel.hide_progress()
        self.status.set_error(f"Lỗi: {err}")

    # ── Remove source ─────────────────────────────────────────────────────────
    @pyqtSlot(str)
    def _on_remove_source(self, file_path: str):
        from PyQt6.QtWidgets import QMessageBox
        from pathlib import Path
        name = Path(file_path).name
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa tài liệu",
            f"Bạn có chắc muốn xóa '{name}' khỏi cơ sở tri thức?\n"
            f"Thao tác này sẽ xóa file và toàn bộ dữ liệu liên quan.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if self._thread and self._thread.isRunning():
            self.status.set_error("Đang xử lý, vui lòng đợi...")
            return

        self.status.set_loading(f"Đang xóa '{name}'...")

        def _delete():
            import os
            from core.retrieval.hybrid_retriever import delete_document
            # 1. Remove from ChromaDB + BM25
            removed = delete_document(file_path, self.subject_id)
            # 2. Delete physical file
            try:
                os.remove(file_path)
            except FileNotFoundError:
                pass
            return name, removed

        from ui.worker import LLMWorker
        self._worker = LLMWorker(_delete)
        self._worker.result.connect(self._on_source_removed)
        self._worker.error.connect(lambda e: self.status.set_error(f"Lỗi xóa: {e}"))
        self._thread = run_in_thread(self._worker)

    @pyqtSlot(object)
    def _on_source_removed(self, result):
        name, removed = result
        self.status.set_done(f"Đã xóa '{name}' — {removed} đoạn bị loại bỏ")

    # ── Ask question ──────────────────────────────────────────────────────────
    def _on_ask(self):
        query = self.query_input.text().strip()
        if not query:
            return
        if self._thread and self._thread.isRunning():
            return

        top_k = DEFAULT_TOP_K
        self.ask_btn.setEnabled(False)
        self.query_input.setEnabled(False)
        self.query_input.clear()
        self._citation_popup.hide()

        # Add user bubble
        user_bubble = self._add_bubble("user")
        user_bubble.set_text(query)
        self._scroll_to_bottom()

        # Add assistant bubble (empty, will be filled by stream)
        asst_bubble = self._add_bubble("assistant")
        asst_bubble.begin_streaming()           # ← prepare for incoming tokens
        self._current_assistant_bubble = asst_bubble
        self._scroll_to_bottom()

        # Thread-safe status and chunk updates via a PyQt bridge QObject
        class _StatusBridge(QObject):
            status_changed = Signal(str)
            chunks_received = Signal(object)

        self._status_bridge = _StatusBridge()
        self._status_bridge.status_changed.connect(self.status.set_loading)
        self._status_bridge.chunks_received.connect(self._on_chunks_received)

        # Stream answer via Agentic RAG (forcing hybrid search)
        selected_mode = "hybrid"

        def _stream():
            from core.pipeline.agentic_rag import generate_agentic_response
            return generate_agentic_response(
                query,
                self.subject_id,
                self.subject_cfg,
                status_cb=self._status_bridge.status_changed.emit,
                chunks_cb=self._status_bridge.chunks_received.emit,
                search_mode=selected_mode,
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
        # Re-render plain text → HTML with clickable [N] citations
        if self._current_assistant_bubble:
            self._current_assistant_bubble.finalize()  # ← key fix
        self.status.set_done(
            f"Tìm thấy {len(self._current_chunks)} đoạn liên quan"
        )
        self._scroll_to_bottom()

    @pyqtSlot(object)
    def _on_chunks_received(self, chunks):
        print(f"[DEBUG UI] Chunks received in PyQt slot: {len(chunks)}")
        self._current_chunks = chunks

    # ── Citation clicked ──────────────────────────────────────────────────────
    @pyqtSlot(int)
    def _on_citation_clicked(self, num: int):
        idx = num - 1
        if 0 <= idx < len(self._current_chunks):
            chunk = self._current_chunks[idx]
            # Position popup relative to window
            pos = self.mapToGlobal(QPoint(
                self.width() // 2 - 200,
                self.height() // 2 - 150,
            ))
            self._citation_popup.move(pos)
            self._citation_popup.show_citation(num, chunk)

    # ── Clear chat ────────────────────────────────────────────────────────────
    def _clear_chat(self):
        for bubble in self._chat_bubbles:
            self._chat_vbox.removeWidget(bubble)
            bubble.deleteLater()
        self._chat_bubbles.clear()
        self._current_chunks = []
        self._current_assistant_bubble = None
        self._citation_popup.hide()
        self.status.clear_status()

    # ── Subject switch ────────────────────────────────────────────────────────
    def set_subject(self, subject_id: str, subject_config):
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._clear_chat()
        # Refresh source panel - clear and reload
        self.sources_panel._cards.clear()
        for i in reversed(range(self.sources_panel._cards_layout.count() - 1)):
            w = self.sources_panel._cards_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        self.sources_panel._update_count()
        self._load_existing_sources()
