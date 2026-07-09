"""ui/theme_manager.py — Centralized Theme Manager for Light/Dark Mode
Manages QSettings, global stylesheet loading, visualizer canvas QColors, and dynamic widget re-styling.
"""
import os
from PyQt6.QtCore import QSettings, QObject
from PyQt6.QtWidgets import QApplication, QWidget, QTextEdit
from PyQt6.QtGui import QColor

# Palette definitions
PALETTES = {
    "dark": {
        "BG_MAIN": "#1a1b2e",
        "BG_SIDEBAR": "#14152a",
        "BG_WIDGET": "#2a2b3d",
        "COLOR_TEXT": "#cdd6f4",
        "COLOR_TEXT_MUTED": "#8a8daa",
        "COLOR_TEXT_DISABLED": "#4a4d64",
        "BORDER": "#3a3c52",
        "BORDER_HOVER": "#4e5068",
        "COLOR_ACCENT": "#cba6f7",
        "COLOR_ACCENT_HOVER": "#d4b5ff",
        "BG_HOVER": "#22243a",
        "BG_CHECKED": "#1f2038",
        "COLOR_BLUE": "#89b4fa",
        "COLOR_GREEN": "#a6e3a1",
        "COLOR_RED": "#f38ba8",
        "COLOR_YELLOW": "#f9e2af",
        "DIVIDER": "#3a3c52",
        "BG_CANVAS": "#1e1e2e",
        "VIS_BAR_DEFAULT": "#585b70",
        "BG_TERMINAL": "#14152a",
        "COLOR_TEXT_TERMINAL": "#cdd6f4",
        "BG_SCROLLBAR_TRACK": "transparent",
        "COLOR_SCROLLBAR_THUMB": "#3a3c52",
        "COLOR_SCROLLBAR_THUMB_HOVER": "#4e5068",
        "BORDER_INPUT": "#3a3c52",
        "BORDER_INPUT_FOCUS": "#cba6f7",
        "BORDER_CARD": "#3a3c52",
        "COLOR_TEXT_TITLE": "#cdd6f4" },
    "light": {
        "BG_MAIN": "#F6F8FC",
        "BG_SIDEBAR": "#F8FAFD",
        "BG_WIDGET": "#FFFFFF",
        "COLOR_TEXT": "#334155",
        "COLOR_TEXT_MUTED": "#64748B",
        "COLOR_TEXT_DISABLED": "#CBD5E1",
        "BORDER": "#E5E7EB",
        "BORDER_HOVER": "#94A3B8",
        "COLOR_ACCENT": "#2563EB",
        "COLOR_ACCENT_HOVER": "#1D4ED8",
        "BG_HOVER": "#EEF4FF",
        "BG_CHECKED": "#DCEBFF",
        "COLOR_BLUE": "#2563EB",
        "COLOR_GREEN": "#16A34A",
        "COLOR_RED": "#DC2626",
        "COLOR_YELLOW": "#F59E0B",
        "DIVIDER": "#E5E7EB",
        "BG_CANVAS": "#E2E8F0",
        "VIS_BAR_DEFAULT": "#5B8DEF",
        "BG_TERMINAL": "#FAFAFA",
        "COLOR_TEXT_TERMINAL": "#111827",
        "BG_SCROLLBAR_TRACK": "#F3F4F6",
        "COLOR_SCROLLBAR_THUMB": "#CBD5E1",
        "COLOR_SCROLLBAR_THUMB_HOVER": "#94A3B8",
        "BORDER_INPUT": "#D1D5DB",
        "BORDER_INPUT_FOCUS": "#3B82F6",
        "BORDER_CARD": "#E6EAF2",
        "COLOR_TEXT_TITLE": "#0F172A" }
}

# Syntax Highlighting Colors
SYNTAX_COLORS = {
    "dark": {
        "keyword": "#cba6f7",
        "string": "#a6e3a1",
        "number": "#fab387",
        "comment": "#5a5d78",
        "preprocessor": "#89dceb" },
    "light": {
        "keyword": "#8839ef",
        "string": "#40a02b",
        "number": "#df8e1d",
        "comment": "#8c8fa1",
        "preprocessor": "#04a5e5" }
}


def get_theme() -> str:
    settings = QSettings("LocalStudyRagAgent", "Settings")
    return settings.value("theme", "light")


def save_theme(theme_name: str):
    settings = QSettings("LocalStudyRagAgent", "Settings")
    settings.setValue("theme", theme_name)


def translate_qss(qss_text: str, theme_name: str) -> str:
    if not qss_text or not isinstance(qss_text, str):
        return qss_text

    base_colors = [
        ("#1a1b2e", "BG_MAIN"),
        ("#14152a", "BG_SIDEBAR"),
        ("#2a2b3d", "BG_WIDGET"),
        ("#cdd6f4", "COLOR_TEXT"),
        ("#8a8daa", "COLOR_TEXT_MUTED"),
        ("#4a4d64", "COLOR_TEXT_DISABLED"),
        ("#3a3c52", "BORDER"),
        ("#2e2e45", "BORDER"),
        ("#3e3e5a", "BORDER_HOVER"),
        ("#4e5068", "BORDER_HOVER"),
        ("#cba6f7", "COLOR_ACCENT"),
        ("#d4b5ff", "COLOR_ACCENT_HOVER"),
        ("#89b4fa", "COLOR_BLUE"),
        ("#22243a", "BG_HOVER"),
        ("#1f2038", "BG_CHECKED"),
        ("#252535", "BG_HOVER"),
        ("#d4d4e8", "COLOR_TEXT"),
        ("#5a5a7a", "COLOR_TEXT_MUTED"),
        ("#f38ba8", "COLOR_RED"),
        ("#a6e3a1", "COLOR_GREEN"),
        ("#16161e", "BG_SIDEBAR"),
        ("#1e1e2e", "BG_MAIN"),
        ("#7b8cde", "COLOR_ACCENT"),
        ("#1a1f3a", "BG_CHECKED"),
        ("#6fcf97", "COLOR_GREEN"),
        ("#0d2a1e", "BG_MAIN"),
        ("#2a0e14", "BG_MAIN"),
        ("#b0b4cc", "COLOR_TEXT_MUTED"),
        ("#5a5d78", "COLOR_TEXT_MUTED"),
        ("#3a3b52", "COLOR_TEXT_DISABLED"),
        ("#181825", "BG_SIDEBAR"),
        
        # Visualizer and custom button/layout colors
        ("#313244", "BG_SIDEBAR"),
        ("#45475a", "BORDER"),
        ("#11111b", "BG_SIDEBAR"),
        ("#6c7086", "COLOR_TEXT_MUTED"),
        ("#a6adc8", "COLOR_TEXT_MUTED"),
        ("#fab387", "COLOR_YELLOW"),
        ("#585b70", "BORDER_HOVER"),
        ("#f5a8b8", "COLOR_ACCENT_HOVER"),
        ("#b4f4af", "COLOR_GREEN"),
        ("#2a2c44", "BG_CHECKED"),
        ("#9d8abf", "COLOR_ACCENT_HOVER"),
        ("#2e2f44", "BG_MAIN"),
        ("#1e2038", "BG_HOVER"),
        ("#191a30", "BG_HOVER"),
        
        # New terminal and canvas theme mappings
        ("#1d1d2b", "BG_CANVAS"),
        ("#14152b", "BG_TERMINAL"),
        ("#cdd6f5", "COLOR_TEXT_TERMINAL"),
        ("#E6EAF2", "BORDER_CARD"),
        ("#cdd6f6", "COLOR_TEXT_TITLE"),
    ]

    tokens = PALETTES[theme_name]
    for hex_code, token_name in base_colors:
        val = tokens[token_name]
        qss_text = qss_text.replace(hex_code, val)
        qss_text = qss_text.replace(hex_code.upper(), val)
    return qss_text


IS_SWITCHING_THEME = False

# Monkeypatch QWidget.setStyleSheet to automatically translate hex colors
_original_set_stylesheet = QWidget.setStyleSheet

def new_set_stylesheet(self, qss_text):
    if isinstance(qss_text, str):
        if hasattr(self, "apply_theme_styles"):
            _original_set_stylesheet(self, qss_text)
            return

        global IS_SWITCHING_THEME
        if not IS_SWITCHING_THEME:
            self._original_qss = qss_text
        theme = get_theme()
        original = getattr(self, "_original_qss", qss_text)
        qss_text = translate_qss(original, theme)
    _original_set_stylesheet(self, qss_text)

QWidget.setStyleSheet = new_set_stylesheet


# Monkeypatch QTextEdit.setHtml to automatically translate hex colors inside HTML
_original_set_html = QTextEdit.setHtml

def new_set_html(self, html_text):
    if isinstance(html_text, str):
        global IS_SWITCHING_THEME
        if not IS_SWITCHING_THEME:
            self._original_html = html_text
        theme = get_theme()
        original = getattr(self, "_original_html", html_text)
        html_text = translate_qss(original, theme)
    _original_set_html(self, html_text)

QTextEdit.setHtml = new_set_html


def apply_theme(theme_name: str, app: QApplication = None):
    if not app:
        app = QApplication.instance()
    if not app:
        return

    # 1. Update active theme setting
    save_theme(theme_name)

    # 2. Update global variables in ui.widgets
    import ui.widgets as w
    tokens = PALETTES[theme_name]
    w.SURFACE_0 = tokens["BG_SIDEBAR"]
    w.SURFACE_1 = tokens["BG_MAIN"]
    w.SURFACE_2 = tokens["BG_WIDGET"]
    w.BORDER = tokens["BORDER"]
    w.BORDER_STRONG = tokens["BORDER_HOVER"]
    w.TEXT_MAIN = tokens["COLOR_TEXT"]
    w.TEXT_MUTED = tokens["COLOR_TEXT_MUTED"]
    w.TEXT_ACCENT = tokens["COLOR_ACCENT"]
    w.ACCENT_BG = tokens["BG_CHECKED"]
    w.TEXT_SUCCESS = tokens["COLOR_GREEN"]
    w.TEXT_DANGER = tokens["COLOR_RED"]

    # 3. Apply global style template
    qss_dir = os.path.dirname(__file__)
    template_path = os.path.join(qss_dir, "style_template.qss")

    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            qss_content = f.read()

        # Interpolate variables
        for k, v in tokens.items():
            qss_content = qss_content.replace(f"{{{k}}}", v)

        # Set stylesheet
        app.setStyleSheet(qss_content)

    # 4. Update visualizer colors
    update_visualizer_colors(theme_name)

    # 5. Re-apply stylesheets and HTML to all existing widgets via tree traversal
    global IS_SWITCHING_THEME
    IS_SWITCHING_THEME = True
    try:
        top_levels = app.topLevelWidgets()
        all_widgets = []
        for tl in top_levels:
            if tl.isVisible() or tl.objectName() == "MainWindow":
                all_widgets.append(tl)
                all_widgets.extend(tl.findChildren(QWidget))

        seen = set()
        unique_widgets = []
        for w in all_widgets:
            if w not in seen:
                seen.add(w)
                unique_widgets.append(w)

        from PyQt6.QtGui import QTextCursor
        for widget in unique_widgets:
            if hasattr(widget, "_original_qss"):
                widget.setStyleSheet(widget._original_qss)

            if hasattr(widget, "_original_html"):
                scrollbar = widget.verticalScrollBar()
                old_scroll = scrollbar.value()
                cursor = widget.textCursor()
                pos = cursor.position()
                anchor = cursor.anchor()

                widget.setHtml(widget._original_html)
                if widget.document():
                    widget.document().markContentsDirty(0, widget.document().characterCount())

                cursor.setPosition(anchor)
                cursor.setPosition(pos, QTextCursor.MoveMode.KeepAnchor)
                widget.setTextCursor(cursor)
                scrollbar.setValue(old_scroll)

            if hasattr(widget, "apply_theme_styles"):
                try:
                    # Dynamic theme update
                    widget.apply_theme_styles()
                except Exception:
                    pass

            # Invalidate cached brushes and pens if present on the widget/canvas
            if hasattr(widget, "_cached_pen"):
                widget._cached_pen = None
            if hasattr(widget, "_cached_brush"):
                widget._cached_brush = None
            if hasattr(widget, "canvas"):
                cv = widget.canvas
                if cv:
                    if hasattr(cv, "_cached_pen"):
                        cv._cached_pen = None
                    if hasattr(cv, "_cached_brush"):
                        cv._cached_brush = None

            if hasattr(widget, "viewport") and widget.viewport():
                widget.viewport().update()

        # Update syntax highlighters (rehighlight without recreating)
        for widget in unique_widgets:
            if hasattr(widget, "_highlighter") and widget._highlighter:
                try:
                    widget._highlighter.rehighlight()
                except Exception:
                    pass

        # Trigger redraw for all widgets
        for widget in unique_widgets:
            widget.update()

        app.processEvents()
    finally:
        IS_SWITCHING_THEME = False


def update_visualizer_colors(theme_name: str):
    try:
        import modules.visualizer.canvas as canvas
        import modules.visualizer.tracers as tracers

        tokens = PALETTES[theme_name]
        bg = tokens["BG_CANVAS"]
        surface = tokens.get("VIS_BAR_DEFAULT", tokens["COLOR_BLUE"])
        border = tokens["BORDER"]
        text = tokens["COLOR_TEXT"]
        subtext = tokens["COLOR_TEXT_MUTED"]
        red = tokens["COLOR_RED"]
        yellow = tokens["COLOR_YELLOW"]
        green = tokens["COLOR_GREEN"]
        blue = tokens["COLOR_BLUE"]
        purple = tokens["COLOR_ACCENT"]

        if theme_name == "light":
            teal = "#179287"
            pink = "#ea76cb"
            orange = "#F59E0B"
            mauve = "#8839ef"
        else:
            teal = "#94e2d5"
            pink = "#f5c2e7"
            orange = "#fab387"
            mauve = "#cba6f7"

        # Update canvas QColor objects in-place
        canvas.C_BG.setNamedColor(bg)
        canvas.C_SURFACE.setNamedColor(surface)
        canvas.C_BORDER.setNamedColor(border)
        canvas.C_TEXT.setNamedColor(text)
        canvas.C_SUBTEXT.setNamedColor(subtext)
        canvas.C_RED.setNamedColor(red)
        canvas.C_YELLOW.setNamedColor(yellow)
        canvas.C_GREEN.setNamedColor(green)
        canvas.C_BLUE.setNamedColor(blue)
        canvas.C_PURPLE.setNamedColor(purple)
        canvas.C_TEAL.setNamedColor(teal)
        canvas.C_PINK.setNamedColor(pink)

        # Update tracers.C dict in-place (module-level palette, NOT COLORS)
        if hasattr(tracers, "C") and isinstance(tracers.C, dict):
            tracers.C["bg"].setNamedColor(bg)
            tracers.C["surface"].setNamedColor(surface)
            tracers.C["border"].setNamedColor(border)
            tracers.C["text"].setNamedColor(text)
            tracers.C["subtext"].setNamedColor(subtext)
            tracers.C["red"].setNamedColor(red)
            tracers.C["yellow"].setNamedColor(yellow)
            tracers.C["green"].setNamedColor(green)
            tracers.C["blue"].setNamedColor(blue)
            tracers.C["purple"].setNamedColor(purple)
            tracers.C["teal"].setNamedColor(teal)
            tracers.C["pink"].setNamedColor(pink)
            tracers.C["orange"].setNamedColor(orange)
            tracers.C["mauve"].setNamedColor(mauve)

        # Update pathfinding canvas colors in GridTracerCanvas class
        if hasattr(tracers, "GridTracerCanvas") and hasattr(tracers.GridTracerCanvas, "COLORS"):
            gc = tracers.GridTracerCanvas.COLORS
            if theme_name == "light":
                gc["empty"].setNamedColor(tokens["BG_WIDGET"])
                gc["wall"].setNamedColor("#94A3B8")
                gc["start"].setNamedColor("#16A34A")
                gc["end"].setNamedColor("#DC2626")
                gc["visited"].setNamedColor("#93C5FD")
                gc["frontier"].setNamedColor("#F59E0B")
                gc["current"].setNamedColor("#EAB308")
                gc["path"].setNamedColor("#22C55E")
            else:
                gc["empty"].setNamedColor("#313244")
                gc["wall"].setNamedColor("#45475a")
                gc["start"].setNamedColor("#2e7d32")
                gc["end"].setNamedColor("#d32f2f")
                gc["visited"].setNamedColor("#b4befe")
                gc["frontier"].setNamedColor("#fab387")
                gc["current"].setNamedColor("#f9e2af")
                gc["path"].setNamedColor("#a6e3a1")
    except Exception as e:
        print(f"[WARN] Failed to update visualizer colors: {e}")

