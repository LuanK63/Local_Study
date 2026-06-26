"""
ui/setup_wizard.py
First-run setup dialog: installs Ollama and pulls required models automatically.
Shows a step-by-step progress UI. Only shown once (tracked in global_config or a flag file).
"""
import subprocess
import sys
import os
import shutil
import urllib.request
import threading
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTextEdit, QWidget,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont

OLLAMA_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"
OLLAMA_INSTALLER_PATH = Path("data/OllamaSetup.exe")
REQUIRED_MODELS = [
    ("qwen2.5-coder:7b",  "LLM chính (~4.7 GB)"),
    ("nomic-embed-text",  "Embedding model (~300 MB)"),
]


# ── Worker thread ─────────────────────────────────────────────────────────────
class SetupWorker(QObject):
    step_changed  = pyqtSignal(str)        # step description
    log           = pyqtSignal(str)        # log line
    progress      = pyqtSignal(int, int)   # current, total bytes (for download)
    finished      = pyqtSignal(bool, str)  # success, error_message

    def run(self):
        try:
            # ── Step 1: Ollama ────────────────────────────────────────────────
            if not self._ollama_installed():
                self.step_changed.emit("⬇️  Đang tải Ollama (~100 MB)...")
                self._download_ollama()
                self.step_changed.emit("⚙️  Đang cài đặt Ollama...")
                self._install_ollama()

            # ── Step 2: Start Ollama service ──────────────────────────────────
            self.step_changed.emit("🚀  Đang khởi động Ollama service...")
            self._start_ollama()

            # ── Step 3: Pull models ───────────────────────────────────────────
            for model_id, model_desc in REQUIRED_MODELS:
                if not self._model_exists(model_id):
                    self.step_changed.emit(f"📥  Đang tải {model_desc}...")
                    self.log.emit(f"[ollama pull {model_id}]")
                    self._pull_model(model_id)
                else:
                    self.log.emit(f"✓ {model_id} đã có sẵn")

            self.finished.emit(True, "")

        except Exception as e:
            self.finished.emit(False, str(e))

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _ollama_installed(self) -> bool:
        return shutil.which("ollama") is not None

    def _download_ollama(self):
        OLLAMA_INSTALLER_PATH.parent.mkdir(parents=True, exist_ok=True)
        total = [0]

        def reporthook(count, block_size, total_size):
            total[0] = total_size
            downloaded = count * block_size
            self.progress.emit(downloaded, total_size)

        urllib.request.urlretrieve(
            OLLAMA_INSTALLER_URL,
            str(OLLAMA_INSTALLER_PATH),
            reporthook=reporthook,
        )
        self.log.emit("✓ Tải Ollama xong")

    def _install_ollama(self):
        # Silent install
        result = subprocess.run(
            [str(OLLAMA_INSTALLER_PATH), "/S"],
            capture_output=True, timeout=120
        )
        if result.returncode not in (0, 3010):  # 3010 = restart required
            raise RuntimeError(f"Cài Ollama thất bại (code {result.returncode})")
        self.log.emit("✓ Cài Ollama thành công")
        # Clean up installer
        try:
            OLLAMA_INSTALLER_PATH.unlink()
        except Exception:
            pass

    def _start_ollama(self):
        # Start server in background if not running
        try:
            subprocess.run(["ollama", "list"], capture_output=True, timeout=5)
            self.log.emit("✓ Ollama service đang chạy")
            return
        except Exception:
            pass
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        import time
        for _ in range(10):
            time.sleep(1)
            try:
                subprocess.run(["ollama", "list"], capture_output=True, timeout=3)
                self.log.emit("✓ Ollama service đã khởi động")
                return
            except Exception:
                pass
        raise RuntimeError("Không thể kết nối Ollama service")

    def _model_exists(self, model_id: str) -> bool:
        try:
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=10
            )
            return model_id.split(":")[0] in result.stdout
        except Exception:
            return False

    def _pull_model(self, model_id: str):
        process = subprocess.Popen(
            ["ollama", "pull", model_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            if line:
                self.log.emit(line)
        process.wait()
        if process.returncode != 0:
            raise RuntimeError(f"Pull model {model_id} thất bại")
        self.log.emit(f"✓ {model_id} đã tải xong")


# ── Dialog ────────────────────────────────────────────────────────────────────
class SetupWizard(QDialog):
    setup_complete = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Thiết lập ban đầu — Local Study RAG Agent")
        self.setFixedSize(560, 420)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint
        )
        self._build_ui()
        self._start_setup()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        # Title
        title = QLabel("🚀 Chào mừng đến với Local Study RAG Agent")
        title.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Đang thiết lập môi trường lần đầu. Vui lòng chờ...")
        subtitle.setFont(QFont("Inter", 10))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setObjectName("PlaceholderInfo")
        layout.addWidget(subtitle)

        # Current step label
        self.step_label = QLabel("Đang kiểm tra hệ thống...")
        self.step_label.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        layout.addWidget(self.step_label)

        # Download progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 0)   # indeterminate by default
        layout.addWidget(self.progress_bar)

        # Log area
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Consolas", 9))
        self.log_area.setFixedHeight(180)
        layout.addWidget(self.log_area)

        # Note
        note = QLabel(
            "⚠️  Lần đầu tiên sẽ cần tải ~5 GB dữ liệu (model AI).\n"
            "Từ lần sau sẽ khởi động ngay lập tức."
        )
        note.setFont(QFont("Inter", 10))
        note.setObjectName("PlaceholderInfo")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(note)

        # Continue button (hidden until done)
        self.btn_continue = QPushButton("✅  Bắt đầu sử dụng")
        self.btn_continue.setFixedHeight(40)
        self.btn_continue.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        self.btn_continue.setVisible(False)
        self.btn_continue.clicked.connect(self._on_continue)
        layout.addWidget(self.btn_continue)

    def _start_setup(self):
        self._thread = QThread()
        self._worker = SetupWorker()
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.step_changed.connect(self.step_label.setText)
        self._worker.log.connect(self._append_log)
        self._worker.progress.connect(self._update_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)

        self._thread.start()

    def _append_log(self, text: str):
        self.log_area.append(text)
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )

    def _update_progress(self, current: int, total: int):
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)

    def _on_finished(self, success: bool, error: str):
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        if success:
            self.step_label.setText("✅  Thiết lập hoàn tất!")
            self._append_log("\n🎉 Sẵn sàng sử dụng!")
            self.btn_continue.setVisible(True)
        else:
            self.step_label.setText(f"❌  Lỗi: {error}")
            self._append_log(f"\n[LỖI] {error}")
            # Allow retry or exit
            self.btn_continue.setText("❌  Đóng")
            self.btn_continue.setVisible(True)

    def _on_continue(self):
        self.setup_complete.emit()
        self.accept()


# ── Helper: check if setup is needed ─────────────────────────────────────────
FLAG_FILE = Path("data/.setup_done")

def needs_setup() -> bool:
    """Return True if first-run setup has not been completed."""
    if FLAG_FILE.exists():
        return False
    # Also check directly
    import shutil
    if shutil.which("ollama") is None:
        return True
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5
        )
        for model_id, _ in REQUIRED_MODELS:
            if model_id.split(":")[0] not in result.stdout:
                return True
        # All good — write flag
        FLAG_FILE.parent.mkdir(parents=True, exist_ok=True)
        FLAG_FILE.touch()
        return False
    except Exception:
        return True

def mark_setup_done():
    FLAG_FILE.parent.mkdir(parents=True, exist_ok=True)
    FLAG_FILE.touch()
