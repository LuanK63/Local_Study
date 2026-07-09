"""
main.py — Entry point for Local Study RAG Agent (Desktop)
Run with: python main.py  OR  LocalStudyRAGAgent.exe
"""
import sys
import os

os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["POSTHOG_DISABLED"] = "1"

import types

# Đảm bảo thư mục gốc của dự án nằm trong sys.path để chạy được ứng dụng từ bất kỳ thư mục làm việc nào
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

# Reconfigure stdout/stderr to use UTF-8 on Windows to avoid UnicodeEncodeErrors
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# Tắt ChromaDB telemetry (analytics) — loại bỏ warning "Failed to send telemetry"
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("CHROMA_TELEMETRY", "False")

# ── Bypass native DLL issues for packages loaded by ChromaDB on Windows ────
# ChromaDB may try to import onnxruntime, tokenizers, transformers, or torch.
# We only need the backend client for delete/search operations, not model inference.
# Inject dummy modules TRƯỚC mọi import để chặn crash hoàn toàn.
class _DummyModule(types.ModuleType):
    def __getattr__(self, name: str):   # type: ignore[override]
        return _DummyModule(name)
    def __call__(self, *a, **kw):
        return self
    def __iter__(self):
        return iter([])

for _mod in ("onnxruntime", "tokenizers", "transformers", "torch"):
    if _mod not in sys.modules:
        sys.modules[_mod] = _DummyModule(_mod)
# ─────────────────────────────────────────────────────────────────────────────

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
    app.setFont(QFont("Inter", 12))
    
    # Always use light mode (theme toggle hidden in UI).
    from ui.theme_manager import apply_theme
    apply_theme("light", app)

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

    # ── Warm up BM25 index from ChromaDB ─────────────────────────────────────
    # BM25 is in-memory only; it must be rebuilt from ChromaDB on every startup.
    try:
        from utils.subject_loader import get_all_subjects
        from core.retrieval.hybrid_retriever import warm_up_bm25
        subject_ids = list(get_all_subjects().keys())
        warm_up_bm25(subject_ids)
    except Exception as e:
        print(f"[WARN] BM25 warm-up failed: {e}")

    # ── Main window ───────────────────────────────────────────────────────────
    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

# Block này không bao giờ chạy, nhưng buộc PyInstaller phải quét tĩnh và đóng gói đầy đủ các module
if False:
    import modules.algorithm_visualizer
    import modules.code_explainer
    import modules.code_generator
    import modules.code_grader
    import modules.code_sandbox
    import modules.complexity_analyzer
    import modules.concept_explainer
    import modules.flashcard_system
    import modules.learning_path
    import modules.practice_mode
    import modules.lesson_mode
    import modules.quiz_generator
    import modules.weakness_detector

