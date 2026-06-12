"""
ui/widgets.py — Shared UI widgets used across multiple tabs.
"""
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPlainTextEdit, QPushButton, QFrame,
    QSizePolicy, QScrollArea, QTextBrowser, QProgressBar,
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import (
    QFont, QSyntaxHighlighter, QTextCharFormat, QColor,
    QTextCursor, QDesktopServices,
)


# ── Markdown/Text Display ─────────────────────────────────────────────────────
class OutputDisplay(QTextEdit):
    """Read-only display that auto-scrolls. Used to show LLM output."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Inter", 10))
        self.setObjectName("OutputDisplay")
        self.setStyleSheet("""
            QTextEdit#OutputDisplay {
                background-color: #14152a;
                border: 1px solid #2a2b3d;
                border-radius: 10px;
                padding: 16px;
                color: #cdd6f4;
            }
        """)

    def append_token(self, token: str):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(token)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def set_markdown(self, md: str):
        self.setPlainText(md)

    def clear_output(self):
        self.clear()


# ── Citation-aware Text Browser ───────────────────────────────────────────────
class CitationTextEdit(QTextBrowser):
    """
    Read-only display that renders [1],[2],... as clickable blue links.
    Emits citation_clicked(int) when user clicks a number.
    """
    citation_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenLinks(False)
        self.setFont(QFont("Inter", 10))
        self.setObjectName("CitationDisplay")
        self.setStyleSheet("""
            QTextBrowser#CitationDisplay {
                background-color: #1a1b2e;
                border: none;
                color: #cdd6f4;
                padding: 8px 4px;
                selection-background-color: #3a3c52;
                line-height: 1.6;
            }
            QTextBrowser#CitationDisplay a {
                color: #89b4fa;
                text-decoration: none;
                font-weight: bold;
            }
        """)
        self.anchorClicked.connect(self._on_anchor)
        self._raw_text: str = ""          # accumulate streaming tokens here
        self._streaming: bool = False     # True while tokens are coming in

    def _on_anchor(self, url: QUrl):
        ref = url.toString()
        if ref.startswith("cite://"):
            try:
                num = int(ref.replace("cite://", ""))
                self.citation_clicked.emit(num)
            except ValueError:
                pass

    def set_text_with_citations(self, text: str):
        """
        Convert raw LLM output to styled HTML:
        - **bold** → <b>
        - [N] → clickable blue badge
        - **Nguồn:** section → distinct styling with separator
        """
        self._raw_text = text

        def _to_html(raw: str) -> str:
            """Render a block of plain text to HTML."""
            s = (raw
                 .replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;"))
            # Bold markers
            s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
            # Newlines
            s = s.replace("\n", "<br>")
            # Citation badges [N] → clickable blue pill
            def _badge(m):
                n = m.group(1)
                return (
                    f'<a href="cite://{n}" style="'
                    f'display:inline-block;color:#1a1b2e;background:#89b4fa;'
                    f'border-radius:4px;padding:0px 6px;font-weight:bold;'
                    f'font-size:8pt;text-decoration:none;margin:0 1px;">'
                    f'[{n}]</a>'
                )
            s = re.sub(r'\[(\d+)\]', _badge, s)
            return s

        # Split on raw markers BEFORE rendering (avoids regex conflict)
        source_pattern = re.compile(
            r'\*\*Nguồn[^*]*:\*\*|\*\*Sources?[^*]*:\*\*',
            re.IGNORECASE,
        )
        m = source_pattern.search(text)

        if m:
            answer_part = text[:m.start()].strip()
            sources_part = text[m.start():].strip()
            body = (
                f'<div style="font-family:Inter,Segoe UI;font-size:10pt;'
                f'line-height:1.8;color:#cdd6f4;">'
                f'{_to_html(answer_part)}'
                f'<hr style="border:none;border-top:1px solid #2a2b3d;margin:14px 0 8px 0;">'
                f'<div style="color:#8a8daa;font-size:9pt;line-height:1.9;">'
                f'{_to_html(sources_part)}'
                f'</div></div>'
            )
        else:
            body = (
                f'<div style="font-family:Inter,Segoe UI;font-size:10pt;'
                f'line-height:1.8;color:#cdd6f4;">'
                f'{_to_html(text)}</div>'
            )

        self.setHtml(body)

    def begin_streaming(self):
        """Call before first token — switches to fast plain-text mode."""
        self._streaming = True
        self._raw_text = ""
        self.clear()

    def append_token(self, token: str):
        """
        Streaming mode: append token as plain text directly to cursor.
        Much faster than re-rendering HTML on every token.
        """
        self._raw_text += token
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(token)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def finalize(self):
        """
        Call after streaming is done.
        Re-renders accumulated text as styled HTML with clickable [N] citations.
        """
        self._streaming = False
        if self._raw_text:
            self.set_text_with_citations(self._raw_text)

    def clear_output(self):
        self.clear()
        self._raw_text = ""
        self._streaming = False

    def get_raw_text(self) -> str:
        return self._raw_text


# ── Ingest Progress Widget ────────────────────────────────────────────────────
class IngestProgressWidget(QFrame):
    """
    Shows real-time progress during document ingestion (3 stages).
    Embed in SourcesPanel footer during upload.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("IngestProgress")
        self.setStyleSheet("""
            QFrame#IngestProgress {
                background: #0e0f1e;
                border-top: 1px solid #2a2b3d;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 12)
        layout.setSpacing(6)

        self._file_lbl = QLabel("Đang xử lý...")
        self._file_lbl.setFont(QFont("Inter", 8, QFont.Weight.Bold))
        self._file_lbl.setStyleSheet("color:#cba6f7; background:transparent;")
        self._file_lbl.setWordWrap(True)
        layout.addWidget(self._file_lbl)

        # 3 stage bars
        for stage, color in [
            ("read",  "#89b4fa"),
            ("embed", "#a6e3a1"),
            ("store", "#fab387"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel({"read": "📄 Đọc", "embed": "🔢 Embed", "store": "💾 Lưu"}[stage])
            lbl.setFont(QFont("Inter", 8))
            lbl.setFixedWidth(64)
            lbl.setStyleSheet("color:#8a8daa; background:transparent;")
            row.addWidget(lbl)

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setFixedHeight(6)
            bar.setTextVisible(False)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    background: #2a2b3d; border: none; border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background: {color}; border-radius: 3px;
                }}
            """)
            row.addWidget(bar)

            pct_lbl = QLabel("0%")
            pct_lbl.setFont(QFont("Inter", 8))
            pct_lbl.setFixedWidth(32)
            pct_lbl.setStyleSheet("color:#5a5d78; background:transparent;")
            row.addWidget(pct_lbl)

            layout.addLayout(row)
            setattr(self, f"_{stage}_bar", bar)
            setattr(self, f"_{stage}_pct", pct_lbl)

        self._pages_lbl = QLabel("")
        self._pages_lbl.setFont(QFont("Inter", 8))
        self._pages_lbl.setStyleSheet("color:#5a5d78; background:transparent;")
        layout.addWidget(self._pages_lbl)

    def set_file(self, name: str):
        self._file_lbl.setText(f"⏳ {name}")
        for stage in ("read", "embed", "store"):
            getattr(self, f"_{stage}_bar").setValue(0)
            getattr(self, f"_{stage}_pct").setText("0%")
        self._pages_lbl.setText("")

    def update_stage(self, stage: str, done: int, total: int):
        if total <= 0:
            return
        pct = int(done / total * 100)
        bar = getattr(self, f"_{stage}_bar", None)
        pct_lbl = getattr(self, f"_{stage}_pct", None)
        if bar:
            bar.setValue(pct)
        if pct_lbl:
            pct_lbl.setText(f"{pct}%")
        if stage == "read":
            self._pages_lbl.setText(f"Trang {done}/{total}")
        elif stage == "embed":
            self._pages_lbl.setText(f"Đoạn embed {done}/{total}")
        elif stage == "store":
            self._pages_lbl.setText(f"Lưu {done}/{total} chunks")

    def set_done(self, chunks: int):
        for stage in ("read", "embed", "store"):
            getattr(self, f"_{stage}_bar").setValue(100)
            getattr(self, f"_{stage}_pct").setText("100%")
        self._file_lbl.setText(f"✅ Hoàn thành — {chunks} đoạn")
        self._pages_lbl.setText("")


# ── Sources Panel (left side, NotebookLM style) ───────────────────────────────
class SourceFileCard(QFrame):
    """A card for a single uploaded source file."""
    remove_requested = pyqtSignal(str)   # emits file_path

    def __init__(self, file_path: str, doc_name: str, chunks: int, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.doc_name = doc_name
        self.setObjectName("SourceCard")
        self.setStyleSheet("""
            QFrame#SourceCard {
                background: #14152a;
                border: 1px solid #2a2b3d;
                border-radius: 10px;
                padding: 2px;
            }
            QFrame#SourceCard:hover {
                border-color: #4e5068;
                background: #191a30;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 10, 10)
        layout.setSpacing(10)

        icon = QLabel("📄")
        icon.setFont(QFont("Inter", 14))
        icon.setFixedWidth(24)
        icon.setStyleSheet("background:transparent; border:none;")
        layout.addWidget(icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        name_lbl = QLabel(doc_name)
        name_lbl.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color:#cdd6f4; background:transparent; border:none;")
        name_lbl.setWordWrap(True)
        text_col.addWidget(name_lbl)

        info_lbl = QLabel(f"{chunks} đoạn văn bản")
        info_lbl.setFont(QFont("Inter", 8))
        info_lbl.setStyleSheet("color:#5a5d78; background:transparent; border:none;")
        text_col.addWidget(info_lbl)
        layout.addLayout(text_col)
        layout.addStretch()

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(24, 24)
        del_btn.setFont(QFont("Inter", 9))
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setToolTip("Xóa tài liệu này")
        del_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#5a5d78;border:none;border-radius:6px;padding:0;}"
            "QPushButton:hover{background:#2a2b3d;color:#f38ba8;}"
        )
        del_btn.clicked.connect(lambda: self.remove_requested.emit(self.file_path))
        layout.addWidget(del_btn)


class SourcesPanel(QWidget):
    """Left panel: list of uploaded sources + Add button."""
    add_source_clicked = pyqtSignal()
    remove_source_requested = pyqtSignal(str)   # emits file_path to delete

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SourcesPanel")
        self.setMinimumWidth(220)
        self.setMaximumWidth(600)
        self.setStyleSheet("""
            QWidget#SourcesPanel {
                background: #14152a;
                border-right: 1px solid #2a2b3d;
            }
        """)
        self._cards: dict[str, SourceFileCard] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet("background:#0e0f1e; border-bottom:1px solid #2a2b3d;")
        header.setFixedHeight(48)
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(16, 0, 16, 0)
        title = QLabel("📚 Nguồn tài liệu")
        title.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        title.setStyleSheet("color:#cba6f7; background:transparent; border:none;")
        hlay.addWidget(title)
        hlay.addStretch()
        self.count_lbl = QLabel("0 nguồn")
        self.count_lbl.setFont(QFont("Inter", 8))
        self.count_lbl.setStyleSheet("color:#5a5d78; background:transparent; border:none;")
        hlay.addWidget(self.count_lbl)
        outer.addWidget(header)

        # Scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        container = QWidget()
        container.setStyleSheet("background:transparent;")
        self._cards_layout = QVBoxLayout(container)
        self._cards_layout.setContentsMargins(12, 12, 12, 12)
        self._cards_layout.setSpacing(8)
        self._cards_layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

        # Add source button
        footer = QFrame()
        footer.setStyleSheet("background:#0e0f1e; border-top:1px solid #2a2b3d;")
        footer.setFixedHeight(56)
        flay = QHBoxLayout(footer)
        flay.setContentsMargins(12, 8, 12, 8)
        add_btn = QPushButton("＋  Thêm tài liệu")
        add_btn.setFixedHeight(38)
        add_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton {
                background: #2a2b3d;
                color: #cba6f7;
                border: 1px dashed #3a3c52;
                border-radius: 10px;
                text-align: center;
                padding: 0;
            }
            QPushButton:hover {
                background: #363850;
                border-color: #cba6f7;
                border-style: solid;
            }
            QPushButton:pressed { background: #22243a; }
        """)
        add_btn.clicked.connect(self.add_source_clicked.emit)
        flay.addWidget(add_btn)
        outer.addWidget(footer)

    def add_card(self, file_path: str, doc_name: str, chunks: int):
        if file_path in self._cards:
            return
        card = SourceFileCard(file_path, doc_name, chunks)
        # Forward card's remove signal up to the panel's own signal
        card.remove_requested.connect(self.remove_source_requested)
        card.remove_requested.connect(self._remove_card)
        # Insert before the stretch
        idx = self._cards_layout.count() - 1
        self._cards_layout.insertWidget(idx, card)
        self._cards[file_path] = card
        self._update_count()

    def _remove_card(self, file_path: str):
        card = self._cards.pop(file_path, None)
        if card:
            self._cards_layout.removeWidget(card)
            card.deleteLater()
        self._update_count()

    def _update_count(self):
        n = len(self._cards)
        self.count_lbl.setText(f"{n} nguồn")

    def get_source_names(self) -> list[str]:
        return [c.doc_name for c in self._cards.values()]

    # ── Ingestion progress controls ───────────────────────────────────────────
    def show_progress(self, file_name: str):
        """Show the ingest progress widget above the add-button footer."""
        if not hasattr(self, "_progress_widget"):
            self._progress_widget = IngestProgressWidget()
            # Insert before the footer (last item)
            outer_layout = self.layout()
            outer_layout.insertWidget(outer_layout.count() - 1, self._progress_widget)
        self._progress_widget.set_file(file_name)
        self._progress_widget.show()

    def update_progress(self, stage: str, done: int, total: int):
        if hasattr(self, "_progress_widget"):
            self._progress_widget.update_stage(stage, done, total)

    def finish_progress(self, chunks: int):
        if hasattr(self, "_progress_widget"):
            self._progress_widget.set_done(chunks)

    def hide_progress(self):
        if hasattr(self, "_progress_widget"):
            self._progress_widget.hide()


# ── Citation Detail Popup ─────────────────────────────────────────────────────
class CitationPopup(QFrame):
    """
    Floating card showing the exact chunk text for a citation [N].
    Shown below/beside the chat when user clicks a [N] badge.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CitationPopup")
        self.setWindowFlags(Qt.WindowType.ToolTip)
        self.setStyleSheet("""
            QFrame#CitationPopup {
                background: #1e2038;
                border: 1px solid #89b4fa;
                border-radius: 12px;
            }
        """)
        self.setMinimumWidth(360)
        self.setMaximumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        # Header row
        header_row = QHBoxLayout()
        self._num_lbl = QLabel("[1]")
        self._num_lbl.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self._num_lbl.setStyleSheet("color:#89b4fa; background:transparent;")
        header_row.addWidget(self._num_lbl)

        self._file_lbl = QLabel()
        self._file_lbl.setFont(QFont("Inter", 9))
        self._file_lbl.setStyleSheet("color:#8a8daa; background:transparent;")
        self._file_lbl.setWordWrap(True)
        header_row.addWidget(self._file_lbl, 1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#5a5d78;border:none;font-size:9pt;padding:0;border-radius:4px;}"
            "QPushButton:hover{color:#f38ba8;background:#2a2b3d;}"
        )
        close_btn.clicked.connect(self.hide)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("background:#2a2b3d; max-height:1px;")
        layout.addWidget(div)

        # Page info
        self._page_lbl = QLabel()
        self._page_lbl.setFont(QFont("Inter", 8))
        self._page_lbl.setStyleSheet("color:#5a5d78; background:transparent;")
        layout.addWidget(self._page_lbl)

        # Text excerpt
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setMaximumHeight(180)
        self._text_edit.setFont(QFont("Inter", 9))
        self._text_edit.setStyleSheet("""
            QTextEdit {
                background:#14152a;
                border:1px solid #2a2b3d;
                border-radius:8px;
                color:#cdd6f4;
                padding:10px;
            }
        """)
        layout.addWidget(self._text_edit)

    def show_citation(self, num: int, chunk: dict):
        self._num_lbl.setText(f"[{num}]")
        self._file_lbl.setText(f"📄 {chunk.get('doc_name', '')}")
        page = chunk.get('page_num', '?')
        self._page_lbl.setText(f"Trang {page}")
        text = chunk.get('text', '')
        self._text_edit.setPlainText(text[:800] + ("..." if len(text) > 800 else ""))
        self.adjustSize()
        self.show()
        self.raise_()


# ── Chat Message Bubble ───────────────────────────────────────────────────────
class ChatBubble(QFrame):
    """A single chat message (user or assistant)."""
    citation_clicked = pyqtSignal(int)

    def __init__(self, role: str, parent=None):
        """role: 'user' or 'assistant'"""
        super().__init__(parent)
        self.role = role
        self.setObjectName("ChatBubble")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(6)

        # Role header
        role_lbl = QLabel("🧑 Bạn" if role == "user" else "🤖 Trợ lý")
        role_lbl.setFont(QFont("Inter", 8, QFont.Weight.Bold))
        role_lbl.setStyleSheet(
            f"color:{'#89b4fa' if role == 'user' else '#a6e3a1'}; background:transparent;"
        )
        layout.addWidget(role_lbl)

        if role == "assistant":
            self._display = CitationTextEdit()
            self._display.citation_clicked.connect(self.citation_clicked)
            self._display.setMinimumHeight(40)
            # Auto-shrink height based on content
            self._display.document().contentsChanged.connect(self._resize_display)
        else:
            self._display = QTextEdit()
            self._display.setReadOnly(True)
            self._display.setFont(QFont("Inter", 10))
            self._display.setMaximumHeight(200)
            self._display.setStyleSheet("""
                QTextEdit {
                    background: #2a2b3d;
                    border: none;
                    border-radius: 10px;
                    color: #cdd6f4;
                    padding: 12px 16px;
                }
            """)

        layout.addWidget(self._display)

    def _resize_display(self):
        doc_h = int(self._display.document().size().height())
        self._display.setMinimumHeight(min(max(doc_h + 24, 40), 600))

    def set_text(self, text: str):
        if self.role == "assistant":
            self._display.set_text_with_citations(text)
        else:
            self._display.setPlainText(text)

    def begin_streaming(self):
        """Prepare display for incoming tokens."""
        if self.role == "assistant":
            self._display.begin_streaming()

    def append_token(self, token: str):
        if self.role == "assistant":
            self._display.append_token(token)

    def finalize(self):
        """Re-render with clickable citation links after streaming ends."""
        if self.role == "assistant":
            self._display.finalize()

    def get_display(self):
        return self._display


# ── C/C++ Syntax Highlighter ─────────────────────────────────────────────────
class CppHighlighter(QSyntaxHighlighter):
    KEYWORDS = [
        "auto","break","case","char","const","continue","default","do",
        "double","else","enum","extern","float","for","goto","if","inline",
        "int","long","register","return","short","signed","sizeof","static",
        "struct","switch","typedef","union","unsigned","void","volatile","while",
        "class","namespace","template","typename","public","private","protected",
        "new","delete","try","catch","throw","bool","true","false","nullptr",
        "include","define","pragma",
    ]

    def __init__(self, document):
        super().__init__(document)
        self._rules = []

        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#cba6f7"))
        kw_fmt.setFontWeight(700)
        for kw in self.KEYWORDS:
            self._rules.append((re.compile(r'\b' + kw + r'\b'), kw_fmt))

        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#a6e3a1"))
        self._rules.append((re.compile(r'"[^"\\]*"'), str_fmt))
        self._rules.append((re.compile(r"'[^'\\]*'"), str_fmt))

        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#fab387"))
        self._rules.append((re.compile(r'\b\d+\.?\d*\b'), num_fmt))

        self._comment_fmt = QTextCharFormat()
        self._comment_fmt.setForeground(QColor("#5a5d78"))
        self._comment_fmt.setFontItalic(True)
        self._rules.append((re.compile(r'//[^\n]*'), self._comment_fmt))
        self._rules.append((re.compile(r'#[^\n]*'), self._comment_fmt))

        pre_fmt = QTextCharFormat()
        pre_fmt.setForeground(QColor("#89dceb"))
        self._rules.append((re.compile(r'#\w+'), pre_fmt))

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


# ── Code Editor ───────────────────────────────────────────────────────────────
class CodeEditor(QPlainTextEdit):
    """Code editor with C/C++ syntax highlighting."""
    def __init__(self, language: str = "cpp", parent=None):
        super().__init__(parent)
        self.setFont(QFont("Consolas", 11))
        self.setObjectName("CodeEditor")
        self.setStyleSheet("""
            QPlainTextEdit#CodeEditor {
                background-color: #14152a;
                border: 1px solid #3a3c52;
                border-radius: 8px;
                color: #cdd6f4;
                padding: 12px;
                selection-background-color: #3a3c52;
            }
            QPlainTextEdit#CodeEditor:focus {
                border-color: #89b4fa;
            }
        """)
        if language in ("c", "cpp"):
            self._highlighter = CppHighlighter(self.document())
        self.setTabStopDistance(28)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def get_code(self) -> str:
        return self.toPlainText()

    def set_code(self, code: str):
        self.setPlainText(code)


# ── Source Citation Badge (legacy, kept for other tabs) ───────────────────────
class SourcesWidget(QWidget):
    """Display source citation chips (used in non-explain tabs)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 4, 0, 4)
        self._layout.setSpacing(8)
        self._layout.addStretch()

    def set_sources(self, sources: list[dict]):
        for i in reversed(range(self._layout.count())):
            w = self._layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        for s in sources:
            badge = QLabel(f"📄 {s['doc_name']} p.{s['page_num']}")
            badge.setFont(QFont("Inter", 8))
            badge.setStyleSheet(
                "background:#2a2b3d; color:#cba6f7; border-radius:6px; padding:4px 10px;"
            )
            self._layout.addWidget(badge)
        self._layout.addStretch()


# ── Section Header ────────────────────────────────────────────────────────────
class SectionHeader(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        self.setObjectName("SectionHeader")
        self.setStyleSheet("color: #cba6f7; padding: 4px 0 8px 0;")


# ── Loading Spinner Label ─────────────────────────────────────────────────────
class StatusLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__("", parent)
        self.setFont(QFont("Inter", 9))
        self.setObjectName("PlaceholderInfo")

    def set_loading(self, msg: str = "Đang xử lý..."):
        self.setText(f"⏳ {msg}")

    def set_done(self, msg: str = "Hoàn thành"):
        self.setText(f"✅ {msg}")

    def set_error(self, msg: str):
        self.setText(f"❌ {msg}")
        self.setStyleSheet("color: #f38ba8;")

    def clear_status(self):
        self.setText("")
        self.setStyleSheet("")
