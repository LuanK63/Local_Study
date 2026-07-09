"""
ui/widgets.py — Shared UI widgets used across multiple tabs.
Redesigned: cleaner chat bubbles, numbered citation chips, compact source cards.
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
    QTextCursor, QDesktopServices, QTextFormat,
)


# ── Palette ───────────────────────────────────────────────────────────────────
SURFACE_0      = "#16161e"
SURFACE_1      = "#1e1e2e"
SURFACE_2      = "#252535"
BORDER         = "#2e2e45"
BORDER_STRONG  = "#3e3e5a"
TEXT_MAIN      = "#d4d4e8"
TEXT_MUTED     = "#5a5a7a"
TEXT_ACCENT    = "#7b8cde"
ACCENT_BG      = "#1a1f3a"
TEXT_SUCCESS   = "#6fcf97"
SUCCESS_BG     = "#0d2a1e"
TEXT_DANGER    = "#f38ba8"
DANGER_BG      = "#2a0e14"


# ── OutputDisplay (non-chat tabs) ─────────────────────────────────────────────
class OutputDisplay(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Inter", 10))
        self.setObjectName("OutputDisplay")
        self.apply_theme_styles()

    def apply_theme_styles(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            self.setStyleSheet(f"""
                QTextEdit#OutputDisplay {{
                    background: {tokens["BG_WIDGET"]};
                    border: 1px solid {tokens["BORDER"]};
                    border-radius: 10px;
                    padding: 16px;
                    color: {tokens["COLOR_TEXT"]};
                }}
            """)
        except Exception:
            pass

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


# ── CodeGenOutput (markdown + syntax-styled code blocks) ─────────────────────
class CodeGenOutput(QTextBrowser):
    """Hiển thị kết quả sinh code: stream plain text, finalize sang HTML đẹp."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenExternalLinks(True)
        self.setFont(QFont("Inter", 10))
        self.setObjectName("CodeGenOutput")
        self._raw_text = ""
        self.apply_theme_styles()

    def apply_theme_styles(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            self.setStyleSheet(f"""
                QTextBrowser#CodeGenOutput {{
                    background: {tokens["BG_WIDGET"]};
                    border: 1px solid {tokens["BORDER"]};
                    border-radius: 10px;
                    padding: 16px 18px;
                    color: {tokens["COLOR_TEXT"]};
                    selection-background-color: {tokens["BG_CHECKED"]};
                }}
            """)
            if self._raw_text.strip():
                self.setHtml(self._render_markdown(self._raw_text))
        except Exception:
            pass

    def begin_streaming(self):
        self._raw_text = ""
        self.clear()

    def append_token(self, token: str):
        self._raw_text += token
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(token)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def finalize(self):
        if self._raw_text.strip():
            self.setHtml(self._render_markdown(self._raw_text))

    def clear_output(self):
        self._raw_text = ""
        self.clear()

    @classmethod
    def _render_markdown(cls, md: str) -> str:
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
        except Exception:
            tokens = {
                "COLOR_TEXT": "#334155",
                "COLOR_TEXT_MUTED": "#64748B",
                "COLOR_ACCENT": "#2563EB",
                "BG_MAIN": "#F1F5F9",
                "BORDER": "#E5E7EB",
                "BG_TERMINAL": "#0F172A",
                "COLOR_TEXT_TERMINAL": "#E2E8F0",
            }

        html_parts = [
            f'<div style="font-family:Inter,Segoe UI,sans-serif;font-size:10.5pt;'
            f'line-height:1.7;color:{tokens["COLOR_TEXT"]};">'
        ]
        pos = 0
        fence = re.compile(r"```(\w*)\n?")

        while pos < len(md):
            m = fence.search(md, pos)
            if not m:
                html_parts.append(cls._render_prose(md[pos:], tokens))
                break
            if m.start() > pos:
                html_parts.append(cls._render_prose(md[pos:m.start()], tokens))
            lang = m.group(1) or ""
            code_start = m.end()
            end = md.find("```", code_start)
            if end == -1:
                html_parts.append(cls._render_prose(md[m.start():], tokens))
                break
            code = md[code_start:end].rstrip("\n")
            html_parts.append(cls._render_code_block(code, lang, tokens))
            pos = end + 3

        html_parts.append("</div>")
        return "".join(html_parts)

    @staticmethod
    def _esc(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    @classmethod
    def _render_prose(cls, text: str, tokens: dict) -> str:
        if not text.strip():
            return ""
        lines = text.split("\n")
        out: list[str] = []
        in_ul = False

        def close_ul():
            nonlocal in_ul
            if in_ul:
                out.append("</ul>")
                in_ul = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                close_ul()
                continue
            if stripped.startswith("### "):
                close_ul()
                out.append(
                    f'<div style="font-size:11pt;font-weight:700;color:{tokens["COLOR_ACCENT"]};'
                    f'margin:12px 0 4px;">{cls._inline_md(stripped[4:], tokens)}</div>'
                )
            elif stripped.startswith("## "):
                close_ul()
                out.append(
                    f'<div style="font-size:12pt;font-weight:700;color:{tokens["COLOR_ACCENT"]};'
                    f'margin:14px 0 6px;">{cls._inline_md(stripped[3:], tokens)}</div>'
                )
            elif stripped.startswith("# "):
                close_ul()
                out.append(
                    f'<div style="font-size:13pt;font-weight:700;color:{tokens["COLOR_TEXT"]};'
                    f'margin:0 0 8px;">{cls._inline_md(stripped[2:], tokens)}</div>'
                )
            elif stripped.startswith("- ") or stripped.startswith("* "):
                if not in_ul:
                    out.append(
                        f'<ul style="margin:6px 0;padding-left:20px;color:{tokens["COLOR_TEXT"]};">'
                    )
                    in_ul = True
                out.append(f"<li>{cls._inline_md(stripped[2:], tokens)}</li>")
            else:
                close_ul()
                out.append(
                    f'<p style="margin:4px 0;color:{tokens["COLOR_TEXT"]};">'
                    f'{cls._inline_md(stripped, tokens)}</p>'
                )
        close_ul()
        return "".join(out)

    @classmethod
    def _inline_md(cls, text: str, tokens: dict) -> str:
        s = cls._esc(text)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(
            r"`([^`]+)`",
            rf'<code style="background:{tokens["BG_MAIN"]};border:1px solid {tokens["BORDER"]};'
            rf'border-radius:4px;padding:1px 5px;font-family:Consolas,monospace;'
            rf'font-size:9.5pt;">\1</code>',
            s,
        )
        return s

    @classmethod
    def _render_code_block(cls, code: str, lang: str, tokens: dict) -> str:
        lang_lbl = lang.upper() if lang else "CODE"
        escaped = cls._esc(code)
        return (
            f'<div style="margin:10px 0 14px;">'
            f'<div style="font-size:8pt;font-weight:600;letter-spacing:0.05em;'
            f'color:{tokens["COLOR_TEXT_MUTED"]};margin-bottom:4px;">{lang_lbl}</div>'
            f'<pre style="margin:0;padding:14px 16px;'
            f'background:{tokens["BG_TERMINAL"]};color:{tokens["COLOR_TEXT_TERMINAL"]};'
            f'border:1px solid {tokens["BORDER"]};border-radius:8px;'
            f'font-family:Consolas,Monaco,monospace;font-size:10pt;'
            f'line-height:1.55;white-space:pre-wrap;overflow-x:auto;">'
            f'{escaped}</pre></div>'
        )


# ── CitationTextEdit ──────────────────────────────────────────────────────────
class CitationTextEdit(QTextBrowser):
    """
    Assistant bubble display.
    - Streams plain text during generation
    - Finalizes to HTML with numbered circle badges + source chips
    """
    citation_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenLinks(False)
        self.setFont(QFont("Inter", 10))
        self.setObjectName("CitationDisplay")
        self._raw_text: str = ""
        self._streaming: bool = False
        self._original_html: str = ""
        self.apply_theme_styles()
        self.anchorClicked.connect(self._on_anchor)

    def apply_theme_styles(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            theme = get_theme()
            tokens = PALETTES[theme]
            self.setStyleSheet(f"""
                QTextBrowser#CitationDisplay {{
                    background: transparent;
                    border: none;
                    color: {tokens["COLOR_TEXT"]};
                    padding: 0;
                    selection-background-color: {tokens["BG_CHECKED"]};
                }}
                QTextBrowser#CitationDisplay a {{
                    color: {tokens["COLOR_ACCENT"]};
                    text-decoration: none;
                }}
                QTextBrowser#CitationDisplay h1, QTextBrowser#CitationDisplay h2, QTextBrowser#CitationDisplay h3,
                QTextBrowser#CitationDisplay h4, QTextBrowser#CitationDisplay h5, QTextBrowser#CitationDisplay h6 {{
                    color: {tokens["COLOR_ACCENT"]};
                    font-weight: bold;
                    margin-top: 8px;
                    margin-bottom: 4px;
                }}
                QTextBrowser#CitationDisplay code {{
                    background-color: {tokens["BG_MAIN"]};
                    color: {tokens["COLOR_TEXT"]};
                    border: 1px solid {tokens["BORDER"]};
                    border-radius: 4px;
                    padding: 2px 4px;
                    font-family: Consolas, monospace;
                }}
                QTextBrowser#CitationDisplay hr {{
                    border: none;
                    border-top: 1px solid {tokens["BORDER"]};
                    margin: 10px 0;
                }}
                QTextBrowser#CitationDisplay th {{
                    background-color: {tokens["BG_CHECKED"]};
                    color: {tokens["COLOR_TEXT"]};
                    font-weight: bold;
                    border: 1px solid {tokens["BORDER"]};
                    padding: 4px 8px;
                }}
                QTextBrowser#CitationDisplay td {{
                    border: 1px solid {tokens["BORDER"]};
                    padding: 4px 8px;
                    color: {tokens["COLOR_TEXT"]};
                }}
                QTextBrowser#CitationDisplay blockquote {{
                    border-left: 3px solid {tokens["COLOR_ACCENT"]};
                    padding-left: 8px;
                    color: {tokens["COLOR_TEXT_MUTED"]};
                    margin: 8px 0;
                }}
                QTextBrowser#CitationDisplay ul, QTextBrowser#CitationDisplay ol {{
                    margin: 6px 0;
                    padding-left: 20px;
                }}
            """)
            
            if self._original_html:
                scrollbar = self.verticalScrollBar()
                old_scroll = scrollbar.value()
                
                cursor = self.textCursor()
                pos = cursor.position()
                anchor = cursor.anchor()
                
                from ui.theme_manager import translate_qss
                translated = translate_qss(self._original_html, theme)
                self.setHtml(translated)
                self.document().markContentsDirty(0, self.document().characterCount())
                
                cursor.setPosition(anchor)
                cursor.setPosition(pos, QTextCursor.MoveMode.KeepAnchor)
                self.setTextCursor(cursor)
                scrollbar.setValue(old_scroll)
        except Exception:
            pass

    def _on_anchor(self, url: QUrl):
        ref = url.toString()
        if ref.startswith("cite://"):
            try:
                self.citation_clicked.emit(int(ref.replace("cite://", "")))
            except ValueError:
                pass

    # ── badge helper ──────────────────────────────────────────────────────────
    @staticmethod
    def _badge(n: str) -> str:
        return (
            f'<a href="cite://{n}" style="'
            f'display:inline-flex;align-items:center;justify-content:center;'
            f'width:15px;height:15px;border-radius:50%;'
            f'font-size:8px;font-weight:700;'
            f'margin:0 2px;vertical-align:middle;text-decoration:none;'
            f'line-height:1;" title="Xem nguồn {n}">{n}</a>'
        )

    @staticmethod
    def _to_html(raw: str) -> str:
        s = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
        s = s.replace("\n", "<br>")
        s = re.sub(r'\[(\d+)\]', lambda m: CitationTextEdit._badge(m.group(1)), s)
        return s

    def set_text_with_citations(self, text: str):
        self._raw_text = text

        source_pattern = re.compile(
            r'\*\*Nguồn[^*]*:\*\*|\*\*Sources?[^*]*:\*\*|(?:^|\n)Nguồn tham khảo\s*(?:\n|$)',
            re.IGNORECASE,
        )
        m = source_pattern.search(text)

        from ui.theme_manager import get_theme, PALETTES
        theme = get_theme()
        tokens = PALETTES[theme]

        if m:
            answer_part = text[:m.start()].strip()
            answer_part = re.sub(r"(?:\n)?---\s*$", "", answer_part).strip()
            sources_raw = text[m.start():].strip()

            lines = [l.strip() for l in sources_raw.split('\n') if l.strip()]
            if lines and re.match(r'\*\*Nguồn', lines[0], re.IGNORECASE):
                lines = lines[1:]

            chips_html = ""
            for line in lines:
                m_line = re.match(r"^\[(\d+)\]\s*(.+)", line)
                if m_line:
                    chip_num = m_line.group(1)
                    clean = m_line.group(2).strip()
                else:
                    m_bare = re.match(r"^(\d+)([A-Za-zÀ-ỹ\u00C0-\u1EF9].+)", line)
                    if m_bare:
                        chip_num = m_bare.group(1)
                        clean = m_bare.group(2).strip()
                    else:
                        chip_num = "?"
                        clean = re.sub(r"^[-\d\.]+\s*", "", line).strip()
                clean = (clean.replace("&", "&amp;")
                              .replace("<", "&lt;")
                              .replace(">", "&gt;"))
                chips_html += (
                    f'<div style="display:flex;align-items:center;gap:7px;'
                    f'padding:5px 8px;margin:3px 0;'
                    f'background:{tokens["BG_WIDGET"]};border:1px solid {tokens["BORDER"]};'
                    f'border-radius:6px;">'
                    f'<span style="width:15px;height:15px;border-radius:50%;'
                    f'background:{tokens["BG_CHECKED"]};color:{tokens["COLOR_ACCENT"]};'
                    f'font-size:8px;font-weight:700;'
                    f'display:inline-flex;align-items:center;'
                    f'justify-content:center;flex-shrink:0;">{chip_num}</span>'
                    f'<span style="font-size:9pt;color:{tokens["COLOR_TEXT_MUTED"]};">{clean}</span>'
                    f'</div>'
                )

            body = (
                f'<div style="font-family:Inter,Segoe UI,sans-serif;'
                f'font-size:10pt;line-height:1.75;color:{tokens["COLOR_TEXT"]};">'
                f'{self._to_html(answer_part)}'
                f'<div style="border-top:1px solid {tokens["BORDER"]};margin:14px 0 10px;"></div>'
                f'<div style="font-size:8pt;font-weight:600;letter-spacing:0.06em;'
                f'color:{tokens["COLOR_TEXT_MUTED"]};text-transform:uppercase;margin-bottom:6px;">'
                f'Nguồn tham khảo</div>'
                f'{chips_html}</div>'
            )
        else:
            body = (
                f'<div style="font-family:Inter,Segoe UI,sans-serif;'
                f'font-size:10pt;line-height:1.75;color:{tokens["COLOR_TEXT"]};">'
                f'{self._to_html(text)}</div>'
            )

        self._original_html = body
        from ui.theme_manager import translate_qss
        self.setHtml(translate_qss(body, theme))

    def begin_streaming(self):
        self._streaming = True
        self._raw_text = ""
        self._original_html = ""
        self.clear()

    def append_token(self, token: str):
        self._raw_text += token
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(token)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def finalize(self):
        self._streaming = False
        if self._raw_text:
            from core.pipeline.answer_generator import rebuild_sources_in_answer
            self._raw_text = rebuild_sources_in_answer(self._raw_text)
            self.set_text_with_citations(self._raw_text)

    def clear_output(self):
        self.clear()
        self._raw_text = ""
        self._streaming = False

    def get_raw_text(self) -> str:
        return self._raw_text
class IngestProgressWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("IngestProgress")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        self._file_lbl = QLabel("Đang xử lý...")
        self._file_lbl.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        self._file_lbl.setWordWrap(True)
        layout.addWidget(self._file_lbl)

        self._status_lbl = QLabel("")
        self._status_lbl.setFont(QFont("Inter", 9))
        self._status_lbl.setWordWrap(True)
        layout.addWidget(self._status_lbl)
        self.apply_theme_styles()

    def apply_theme_styles(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            self.setStyleSheet(f"""
                QFrame#IngestProgress {{
                    background: {tokens["BG_SIDEBAR"]};
                    border-top: 1px solid {tokens["BORDER"]};
                }}
            """)
            self._file_lbl.setStyleSheet(f"color:{tokens['COLOR_ACCENT']}; background:transparent;")
            self._status_lbl.setStyleSheet(f"color:{tokens['COLOR_TEXT_MUTED']}; background:transparent;")
        except Exception:
            pass

    def set_file(self, name: str):
        self._file_lbl.setText(f"Đang xử lý tài liệu: {name}")
        self._status_lbl.setText("Đang chuẩn bị...")

    def update_stage(self, stage: str, done: int, total: int):
        stage_map = {"read": "Đọc tài liệu", "embed": "Vector hóa", "store": "Lưu trữ"}
        msg_map = {
            "read": f"Đọc tài liệu: Trang {done}/{total}",
            "embed": f"Vector hóa: Đoạn {done}/{total}",
            "store": f"Lưu trữ: Đoạn {done}/{total}"
        }
        self._status_lbl.setText(msg_map.get(stage, f"{stage_map.get(stage, stage)}: {done}/{total}"))

    def set_done(self, chunks: int):
        self._file_lbl.setText("Hoàn thành!")
        self._status_lbl.setText("Đã xử lý xong.")


# ── SourceFileCard ────────────────────────────────────────────────────────────
class SourceFileCard(QFrame):
    def __init__(self, file_path: str, doc_name: str, chunks: int, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setObjectName("SourceCard")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 8, 8)
        layout.setSpacing(8)

        icon = QLabel("")
        icon.setFont(QFont("Inter", 13))
        icon.setFixedWidth(0)
        icon.setStyleSheet("background:transparent; border:none;")
        layout.addWidget(icon)

        col = QVBoxLayout()
        col.setSpacing(1)
        name_lbl = QLabel(doc_name)
        name_lbl.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        name_lbl.setWordWrap(True)
        col.addWidget(name_lbl)

        self._info_lbl = QLabel("")
        self._info_lbl.setFont(QFont("Inter", 8))
        col.addWidget(self._info_lbl)
        layout.addLayout(col)
        layout.addStretch()

        self.apply_theme_styles()

    def apply_theme_styles(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            self.setStyleSheet(f"""
                QFrame#SourceCard {{
                    background: {tokens["BG_SIDEBAR"]};
                    border: 1px solid {tokens["BORDER"]};
                    border-radius: 8px;
                }}
                QFrame#SourceCard:hover {{
                    border-color: {tokens["BORDER_HOVER"]};
                    background: {tokens["BG_HOVER"]};
                }}
            """)
            self.findChild(QLabel, "").setStyleSheet("background:transparent; border:none;")
            for lbl in self.findChildren(QLabel):
                if lbl.text() != "":
                    lbl.setStyleSheet(f"color:{tokens['COLOR_TEXT']}; background:transparent; border:none;")
            self._info_lbl.setStyleSheet(f"color:{tokens['COLOR_TEXT_MUTED']}; background:transparent; border:none;")
        except Exception:
            pass

    def update_chunks(self, chunks: int):
        self._info_lbl.setText("")


# ── SourcesPanel ──────────────────────────────────────────────────────────────
class SourcesPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SourcesPanel")
        self.setMinimumWidth(200)
        self.setMaximumWidth(560)
        
        self._cards: dict[str, SourceFileCard] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        self.header = QFrame()
        self.header.setFixedHeight(44)
        hlay = QHBoxLayout(self.header)
        hlay.setContentsMargins(14, 0, 14, 0)
        self.title_lbl = QLabel("Nguồn tài liệu")
        self.title_lbl.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        hlay.addWidget(self.title_lbl)
        hlay.addStretch()
        self.count_lbl = QLabel("0 nguồn")
        self.count_lbl.setFont(QFont("Inter", 8))
        hlay.addWidget(self.count_lbl)
        outer.addWidget(self.header)

        # Scroll
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        container = QWidget()
        container.setStyleSheet("background:transparent;")
        self._cards_layout = QVBoxLayout(container)
        self._cards_layout.setContentsMargins(10, 10, 10, 10)
        self._cards_layout.setSpacing(6)
        self._cards_layout.addStretch()
        self.scroll.setWidget(container)
        outer.addWidget(self.scroll)
        
        self.apply_theme_styles()

    def apply_theme_styles(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            self.setStyleSheet(f"""
                QWidget#SourcesPanel {{
                    background: {tokens["BG_MAIN"]};
                    border-right: 1px solid {tokens["BORDER"]};
                }}
            """)
            self.header.setStyleSheet(f"background:{tokens['BG_SIDEBAR']}; border-bottom:1px solid {tokens['BORDER']};")
            self.title_lbl.setStyleSheet(f"color:{tokens['COLOR_TEXT']}; background:transparent; border:none;")
            self.count_lbl.setStyleSheet(
                f"color:{tokens['COLOR_TEXT_MUTED']}; background:{tokens['BG_CHECKED']};"
                f"border:1px solid {tokens['BORDER']}; border-radius:10px; padding:1px 7px;"
            )
            self.scroll.setStyleSheet("QScrollArea{background:transparent; border:none;}")
        except Exception:
            pass

    def add_card(self, file_path: str, doc_name: str, chunks: int):
        if file_path in self._cards:
            self._cards[file_path].update_chunks(chunks)
            return
        card = SourceFileCard(file_path, doc_name, chunks)
        self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)
        self._cards[file_path] = card
        self._update_count()

    def _update_count(self):
        self.count_lbl.setText(f"{len(self._cards)} nguồn")

    def get_source_names(self) -> list[str]:
        return [c.doc_name for c in self._cards.values()]


# ── CitationPopup ─────────────────────────────────────────────────────────────
class CitationPopup(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CitationPopup")
        self.setWindowFlags(Qt.WindowType.ToolTip)
        self.setMinimumWidth(340)
        self.setMaximumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        self._num_badge = QLabel("1")
        self._num_badge.setFixedSize(22, 22)
        self._num_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._num_badge.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        header_row.addWidget(self._num_badge)

        self._file_lbl = QLabel()
        self._file_lbl.setFont(QFont("Inter", 9))
        self._file_lbl.setWordWrap(True)
        header_row.addWidget(self._file_lbl, 1)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.hide)
        header_row.addWidget(self.close_btn)
        layout.addLayout(header_row)

        self._page_lbl = QLabel()
        self._page_lbl.setFont(QFont("Inter", 8))
        self._page_lbl.setFixedHeight(18)
        layout.addWidget(self._page_lbl)

        self.div = QFrame()
        self.div.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(self.div)

        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setMaximumHeight(160)
        self._text_edit.setFont(QFont("Inter", 9))
        layout.addWidget(self._text_edit)
        
        self.apply_theme_styles()

    def apply_theme_styles(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            
            # Keep geometry
            geom = self.geometry()
            
            self.setStyleSheet(f"""
                QFrame#CitationPopup {{
                    background: {tokens["BG_SIDEBAR"]};
                    border: 2px solid {tokens["COLOR_ACCENT"]};
                    border-radius: 10px;
                }}
            """)
            
            self._num_badge.setStyleSheet(f"""
                background: {tokens["BG_CHECKED"]};
                color: {tokens["COLOR_ACCENT"]};
                border: 1px solid {tokens["COLOR_ACCENT"]};
                border-radius: 11px;
            """)
            
            self._file_lbl.setStyleSheet(f"color: {tokens['COLOR_TEXT']}; background: transparent;")
            
            self.close_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {tokens["COLOR_TEXT_MUTED"]};
                    border: none;
                    font-size: 9pt;
                    padding: 0;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    color: {tokens["COLOR_RED"]};
                    background: {tokens["BG_HOVER"]};
                }}
            """)
            
            self._page_lbl.setStyleSheet(f"""
                color: {tokens["COLOR_ACCENT"]};
                background: {tokens["BG_CHECKED"]};
                border: 1px solid {tokens["COLOR_ACCENT"]};
                border-radius: 4px;
                padding: 1px 7px;
            """)
            
            self.div.setStyleSheet(f"background: {tokens['BORDER']}; max-height: 1px;")
            
            # Save scroll/selection/cursor for _text_edit
            scrollbar = self._text_edit.verticalScrollBar()
            old_scroll = scrollbar.value()
            cursor = self._text_edit.textCursor()
            pos = cursor.position()
            anchor = cursor.anchor()
            
            self._text_edit.setStyleSheet(f"""
                QTextEdit {{
                    background: {tokens["BG_MAIN"]};
                    border: 1px solid {tokens["BORDER"]};
                    border-radius: 6px;
                    color: {tokens["COLOR_TEXT"]};
                    padding: 8px 10px;
                }}
            """)
            
            cursor.setPosition(anchor)
            cursor.setPosition(pos, QTextCursor.MoveMode.KeepAnchor)
            self._text_edit.setTextCursor(cursor)
            scrollbar.setValue(old_scroll)
            
            # Restore geometry
            self.setGeometry(geom)
        except Exception:
            pass

    def show_citation(self, num: int, chunk: dict):
        self._num_badge.setText(str(num))
        self._file_lbl.setText(f"📄 {chunk.get('doc_name', '')}")
        self._page_lbl.setText(f"Trang {chunk.get('page_num', '?')}")
        text = chunk.get('text', '')
        self._text_edit.setPlainText(text[:700] + ("…" if len(text) > 700 else ""))
        self.adjustSize()
        self.show()
        self.raise_()


# ── ChatBubble ────────────────────────────────────────────────────────────────
class ChatBubble(QFrame):
    """
    User bubble  → right-aligned, compact, no border radius top-right
    Asst bubble  → full-width, with citation support, no border radius top-left
    """
    citation_clicked = pyqtSignal(int)

    def __init__(self, role: str, parent=None):
        super().__init__(parent)
        self.role = role
        self.setObjectName("ChatBubble")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 2, 0, 2)
        outer.setSpacing(4)

        # Role label
        role_row = QHBoxLayout()
        role_row.setContentsMargins(0, 0, 0, 0)

        if role == "user":
            self.role_lbl = QLabel("◎  Bạn")
            role_row.addStretch()
            role_row.addWidget(self.role_lbl)
        else:
            self.role_lbl = QLabel("◈  Trợ lý")
            role_row.addWidget(self.role_lbl)
            role_row.addStretch()

        self.role_lbl.setFont(QFont("Inter", 8, QFont.Weight.Bold))
        outer.addLayout(role_row)

        # Bubble frame
        bubble_row = QHBoxLayout()
        bubble_row.setContentsMargins(0, 0, 0, 0)

        self._bubble_frame = QFrame()

        if role == "assistant":
            self._bubble_frame.setObjectName("AssistantBubble")
            inner = QVBoxLayout(self._bubble_frame)
            inner.setContentsMargins(14, 12, 14, 12)
            inner.setSpacing(0)

            self._display = CitationTextEdit()
            self._display.citation_clicked.connect(self.citation_clicked)
            self._display.setMinimumHeight(36)
            self._display.document().contentsChanged.connect(self._resize_display)
            inner.addWidget(self._display)

            bubble_row.addWidget(self._bubble_frame)

        else:
            self._bubble_frame.setObjectName("UserBubble")
            inner = QVBoxLayout(self._bubble_frame)
            inner.setContentsMargins(12, 9, 12, 9)
            inner.setSpacing(0)

            self._display = QTextEdit()
            self._display.setReadOnly(True)
            self._display.setFont(QFont("Inter", 10))
            self._display.setMaximumHeight(200)
            self._display.setMaximumWidth(520)
            inner.addWidget(self._display)

            bubble_row.addStretch()
            bubble_row.addWidget(self._bubble_frame)

        outer.addLayout(bubble_row)
        self.apply_theme_styles()

    def apply_theme_styles(self):
        self.refresh_colors()
        self.refresh_html()

    def refresh_colors(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            theme = get_theme()
            tokens = PALETTES[theme]

            if self.role == "user":
                self.role_lbl.setStyleSheet(f"color:{tokens['COLOR_ACCENT']}; background:transparent;")
                self._bubble_frame.setStyleSheet(f"""
                    QFrame#UserBubble {{
                        background: {tokens['BG_CHECKED']};
                        border: 1px solid {tokens['BORDER']};
                        border-radius: 10px;
                        border-top-right-radius: 2px;
                    }}
                """)
                self._display.setStyleSheet(f"""
                    QTextEdit {{
                        background: transparent;
                        border: none;
                        color: {tokens['COLOR_TEXT']};
                        padding: 0;
                    }}
                """)
            else:
                self.role_lbl.setStyleSheet(f"color:{tokens['COLOR_GREEN']}; background:transparent;")
                self._bubble_frame.setStyleSheet(f"""
                    QFrame#AssistantBubble {{
                        background: {tokens['BG_MAIN']};
                        border: 1px solid {tokens['BORDER']};
                        border-radius: 10px;
                        border-top-left-radius: 2px;
                    }}
                """)
            self.update()
        except Exception:
            pass

    def refresh_html(self):
        try:
            if self.role == "assistant" and hasattr(self._display, "apply_theme_styles"):
                self._display.apply_theme_styles()
        except Exception:
            pass

    def _resize_display(self):
        doc_h = int(self._display.document().size().height())
        self._display.setMinimumHeight(min(max(doc_h + 20, 36), 640))

    def set_text(self, text: str):
        if self.role == "assistant":
            self._display.set_text_with_citations(text)
        else:
            self._display.setPlainText(text)

    def begin_streaming(self):
        if self.role == "assistant":
            self._display.begin_streaming()

    def append_token(self, token: str):
        if self.role == "assistant":
            self._display.append_token(token)

    def finalize(self):
        if self.role == "assistant":
            self._display.finalize()

    def get_display(self):
        return self._display


# ── CppHighlighter ────────────────────────────────────────────────────────────
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
        self.update_colors()

    def update_colors(self):
        self._rules = []
        from ui.theme_manager import get_theme, SYNTAX_COLORS
        theme = get_theme()
        colors = SYNTAX_COLORS[theme]

        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor(colors["keyword"]))
        kw_fmt.setFontWeight(700)
        for kw in self.KEYWORDS:
            self._rules.append((re.compile(r'\b' + kw + r'\b'), kw_fmt))

        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor(colors["string"]))
        self._rules += [
            (re.compile(r'"[^"\\]*"'), str_fmt),
            (re.compile(r"'[^'\\]*'"), str_fmt),
        ]

        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor(colors["number"]))
        self._rules.append((re.compile(r'\b\d+\.?\d*\b'), num_fmt))

        cmt_fmt = QTextCharFormat()
        cmt_fmt.setForeground(QColor(colors["comment"]))
        cmt_fmt.setFontItalic(True)
        self._rules += [
            (re.compile(r'//[^\n]*'), cmt_fmt),
            (re.compile(r'#[^\n]*'), cmt_fmt),
        ]

        pre_fmt = QTextCharFormat()
        pre_fmt.setForeground(QColor(colors["preprocessor"]))
        self._rules.append((re.compile(r'#\w+'), pre_fmt))

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


# ── CodeEditor ────────────────────────────────────────────────────────────────
class CodeEditor(QPlainTextEdit):
    def __init__(self, language: str = "cpp", parent=None):
        super().__init__(parent)
        self.setFont(QFont("Consolas", 11))
        self.setObjectName("CodeEditor")
        self.language = language
        self._highlighter = None
        if language in ("c", "cpp"):
            self._highlighter = CppHighlighter(self.document())
        self.apply_theme_styles()
        self.setTabStopDistance(28)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.highlight_current_line()

    def apply_theme_styles(self):
        from ui.theme_manager import get_theme, PALETTES
        theme = get_theme()
        tokens = PALETTES[theme]
        bg = "#FCFCFD" if theme == "light" else tokens["BG_SIDEBAR"]
        selection_bg = "#DBEAFE" if theme == "light" else tokens["COLOR_ACCENT"]
        selection_fg = "#1E293B" if theme == "light" else tokens["BG_MAIN"]
        
        self.setStyleSheet(f"""
            QPlainTextEdit#CodeEditor {{
                background: {bg};
                border: 1px solid {tokens["BORDER"]};
                border-radius: 8px;
                color: {tokens["COLOR_TEXT"]};
                padding: 12px;
                selection-background-color: {selection_bg};
                selection-color: {selection_fg};
            }}
            QPlainTextEdit#CodeEditor:focus {{ border-color: {tokens["COLOR_ACCENT"]}; }}
        """)
        if self._highlighter:
            self._highlighter.update_colors()
            self._highlighter.rehighlight()
        self.highlight_current_line()

    def highlight_current_line(self):
        from ui.theme_manager import get_theme
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor("#F1F5F9") if get_theme() == "light" else QColor("#22243a")
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    def get_code(self) -> str:
        return self.toPlainText()

    def set_code(self, code: str):
        self.setPlainText(code)

    def set_language(self, language: str):
        self.language = language
        if language in ("c", "cpp"):
            if not self._highlighter:
                self._highlighter = CppHighlighter(self.document())
            self._highlighter.rehighlight()
        elif self._highlighter:
            self._highlighter.setDocument(None)
            self._highlighter = None


# ── SourcesWidget (legacy badge row, kept for other tabs) ─────────────────────
class SourcesWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 4, 0, 4)
        self._layout.setSpacing(6)
        self._layout.addStretch()

    def set_sources(self, sources: list[dict]):
        for i in reversed(range(self._layout.count())):
            w = self._layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        for s in sources:
            badge = QLabel(f"📄 {s['doc_name']} p.{s['page_num']}")
            badge.setFont(QFont("Inter", 9))
            badge.setObjectName("SourcesWidgetBadge")
            self._layout.addWidget(badge)
        self._layout.addStretch()
        self.apply_theme_styles()

    def apply_theme_styles(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            for i in range(self._layout.count()):
                w = self._layout.itemAt(i).widget()
                if isinstance(w, QLabel) and w.objectName() == "SourcesWidgetBadge":
                    w.setStyleSheet(f"""
                        background: {tokens["BG_WIDGET"]};
                        color: {tokens["COLOR_ACCENT"]};
                        border: 1px solid {tokens["BORDER"]};
                        border-radius: 6px;
                        padding: 4px 10px;
                    """)
        except Exception:
            pass


# ── SectionHeader ─────────────────────────────────────────────────────────────
class SectionHeader(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Inter", 13, QFont.Weight.DemiBold))
        self.setObjectName("SectionHeader")
        self.apply_theme_styles()

    def apply_theme_styles(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            self.setStyleSheet(f"color: {tokens['COLOR_ACCENT']}; padding: 4px 0 8px 0;")
        except Exception:
            pass


# ── StatusLabel ───────────────────────────────────────────────────────────────
class StatusLabel(QLabel):
    """
    Thin bar below the chat header. Visible only while there's a message.
    """
    _BASE = "font-size:9pt; padding:4px 16px; border-bottom:1px solid {b};"

    def __init__(self, parent=None):
        super().__init__("", parent)
        self.setFont(QFont("Inter", 9))
        self.setObjectName("StatusLabel")
        self.setVisible(False)
        self._last_state = None

    def apply_theme_styles(self):
        if self._last_state == "loading":
            self.set_loading(self.text())
        elif self._last_state == "done":
            self.set_done(self.text())
        elif self._last_state == "error":
            self.set_error(self.text())

    def set_loading(self, msg: str = "Đang xử lý..."):
        self._last_state = "loading"
        self.setText(msg)
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            self.setStyleSheet(
                self._BASE.format(b=tokens["BORDER"]) +
                f"color:{tokens['COLOR_ACCENT']}; background:{tokens['BG_CHECKED']};"
            )
        except Exception:
            pass
        self.setVisible(True)

    def set_done(self, msg: str = "Hoàn thành"):
        self._last_state = "done"
        self.setText(msg)
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            self.setStyleSheet(
                self._BASE.format(b=tokens["BORDER"]) +
                f"color:{tokens['COLOR_GREEN']}; background:{tokens['BG_CHECKED']};"
            )
        except Exception:
            pass
        self.setVisible(True)

    def set_error(self, msg: str):
        self._last_state = "error"
        self.setText(msg)
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            self.setStyleSheet(
                self._BASE.format(b=tokens["BORDER"]) +
                f"color:{tokens['COLOR_RED']}; background:{tokens['BG_CHECKED']};"
            )
        except Exception:
            pass
        self.setVisible(True)

    def clear_status(self):
        self._last_state = None
        self.setText("")
        self.setVisible(False)