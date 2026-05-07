"""
ui/tabs/tab_document.py — Document Upload Tab
Allows users to add new PDF/DOCX files into the RAG knowledge base.
"""
import shutil
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.widgets import SectionHeader, StatusLabel
from ui.worker import LLMWorker, run_in_thread


class DocumentTab(QWidget):
    def __init__(self, subject_id: str, subject_config, parent=None):
        super().__init__(parent)
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._thread = None
        self._worker = None
        self._selected_file = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(SectionHeader("📁 Document Upload (Thêm Tài Liệu)"))
        
        desc = QLabel(
            "Tải lên giáo trình, bài tập hoặc tài liệu tham khảo (PDF, DOCX). "
            "AI sẽ đọc, phân tích và học thuộc tài liệu này để trả lời các câu hỏi của bạn."
        )
        desc.setWordWrap(True)
        desc.setFont(QFont("Segoe UI", 10))
        layout.addWidget(desc)

        # Upload Box
        self.box = QFrame()
        self.box.setStyleSheet(
            "QFrame { background:#1e1e2e; border:2px dashed #45475a; border-radius:12px; }"
        )
        self.box.setMinimumHeight(200)
        box_layout = QVBoxLayout(self.box)
        box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.file_label = QLabel("Chưa chọn file nào")
        self.file_label.setFont(QFont("Segoe UI", 11))
        self.file_label.setStyleSheet("color:#a6adc8; border: none;")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_layout.addWidget(self.file_label)

        btn_row = QHBoxLayout()
        self.select_btn = QPushButton("📂 Chọn File")
        self.select_btn.setFixedSize(130, 40)
        self.select_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.select_btn.clicked.connect(self._select_file)
        btn_row.addWidget(self.select_btn)

        self.upload_btn = QPushButton("🚀 Tải Lên & Xử Lý")
        self.upload_btn.setFixedSize(160, 40)
        self.upload_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.upload_btn.setStyleSheet("background:#89b4fa; color:#1e1e2e;")
        self.upload_btn.clicked.connect(self._upload_file)
        self.upload_btn.setEnabled(False)
        btn_row.addWidget(self.upload_btn)
        
        box_layout.addLayout(btn_row)
        layout.addWidget(self.box)

        self.status = StatusLabel()
        layout.addWidget(self.status)

        layout.addStretch()

    def set_subject(self, subject_id: str, subject_config):
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._selected_file = None
        self.file_label.setText("Chưa chọn file nào")
        self.upload_btn.setEnabled(False)

    def _select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn tài liệu", "", "Documents (*.pdf *.docx *.txt)"
        )
        if file_path:
            self._selected_file = file_path
            self.file_label.setText(f"📄 {Path(file_path).name}")
            self.file_label.setStyleSheet("color:#a6e3a1; border: none; font-weight: bold;")
            self.upload_btn.setEnabled(True)

    def _upload_file(self):
        if not self._selected_file:
            return
            
        if self._thread and self._thread.isRunning():
            return
            
        self.upload_btn.setEnabled(False)
        self.select_btn.setEnabled(False)
        self.status.set_loading("Đang đọc, chia nhỏ và học tài liệu (có thể mất vài phút)...")

        def _process():
            # 1. Copy file to subjects/<id>/documents/
            doc_dir = Path(self.subject_cfg.documents_dir)
            doc_dir.mkdir(parents=True, exist_ok=True)
            
            src_path = Path(self._selected_file)
            dest_path = doc_dir / src_path.name
            
            if src_path != dest_path:
                shutil.copy2(src_path, dest_path)
            
            # 2. Ingest into ChromaDB
            from core.retrieval.hybrid_retriever import ingest_document
            chunks_added = ingest_document(dest_path, self.subject_id)
            return chunks_added

        self._worker = LLMWorker(_process)
        self._worker.result.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(lambda: self.select_btn.setEnabled(True))
        self._thread = run_in_thread(self._worker)

    def _on_done(self, chunks: int):
        self.status.set_done(f"Thành công! Đã trích xuất và học được {chunks} đoạn kiến thức mới.")
        self._selected_file = None
        self.file_label.setText("Chưa chọn file nào")
        self.file_label.setStyleSheet("color:#a6adc8; border: none;")
        
    def _on_error(self, err: str):
        self.status.set_error(f"Lỗi: {err}")
        self.upload_btn.setEnabled(True)
