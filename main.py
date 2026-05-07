"""
main.py — Entry point for Local Study RAG Agent (Desktop)
Run with: python main.py  OR  LocalStudyRAGAgent.exe
"""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from utils.db_schema import init_db


def load_stylesheet(app: QApplication):
    try:
        import os
        qss_path = os.path.join(os.path.dirname(__file__), "ui", "style.qss")
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        pass


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Local Study RAG Agent")
    app.setApplicationVersion("1.0.0")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    load_stylesheet(app)

    # ── First-run setup ───────────────────────────────────────────────────────
    from ui.setup_wizard import needs_setup, mark_setup_done, SetupWizard

    if needs_setup():
        wizard = SetupWizard()
        wizard.setup_complete.connect(mark_setup_done)
        result = wizard.exec()
        if result != wizard.DialogCode.Accepted:
            sys.exit(0)  # User closed wizard before completion

    # ── Init DB ───────────────────────────────────────────────────────────────
    init_db()

    # ── Main window ───────────────────────────────────────────────────────────
    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
