"""ui/tabs/tab_document.py — Document Upload Tab"""
import os
import shutil
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QFrame, QScrollArea,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont

from ui.widgets import SectionHeader, StatusLabel, IngestProgressWidget
from ui.worker import LLMWorker, run_in_thread


class _DocumentCard(QFrame):
    remove_requested = pyqtSignal(str)

    def __init__(self, file_path: str, doc_name: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setObjectName("DocumentCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 10, 10)
        layout.setSpacing(10)

        self._name_lbl = QLabel(doc_name)
        self._name_lbl.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self._name_lbl.setWordWrap(True)
        layout.addWidget(self._name_lbl, 1)

        self.del_btn = QPushButton("Xóa")
        self.del_btn.setFixedSize(52, 28)
        self.del_btn.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self.del_btn)

        self.apply_theme_styles()

    def _on_delete_clicked(self):
        self.remove_requested.emit(self.file_path)

    def set_busy(self, busy: bool):
        self.del_btn.setEnabled(not busy)

    def apply_theme_styles(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            self.setStyleSheet(f"""
                QFrame#DocumentCard {{
                    background: {tokens["BG_WIDGET"]};
                    border: 1px solid {tokens["BORDER"]};
                    border-radius: 8px;
                }}
            """)
            self._name_lbl.setStyleSheet(
                f"color:{tokens['COLOR_TEXT']}; background:transparent; border:none;"
            )
            self.del_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens["BG_SIDEBAR"]};
                    color: {tokens["COLOR_RED"]};
                    border: 1px solid {tokens["BORDER"]};
                    border-radius: 6px;
                }}
                QPushButton:hover:enabled {{
                    background: {tokens["BG_HOVER"]};
                    border-color: {tokens["COLOR_RED"]};
                }}
                QPushButton:disabled {{
                    color: {tokens["COLOR_TEXT_DISABLED"]};
                }}
            """)
        except Exception:
            pass


class DocumentTab(QWidget):
    document_changed = pyqtSignal()

    def __init__(self, subject_id: str, subject_config, parent=None):
        super().__init__(parent)
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._thread = None
        self._worker = None
        self._busy = False
        self._selected_file = None
        self._doc_cards: list[_DocumentCard] = []
        self._setup_ui()
        self._refresh_document_list()

    def _storage_id(self) -> str:
        return self.subject_cfg.chroma_collection or self.subject_id

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.select_btn.setEnabled(not busy)
        self.upload_btn.setEnabled(not busy and bool(self._selected_file))
        for card in self._doc_cards:
            card.set_busy(busy)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(SectionHeader("Document Upload"))

        self.box = QFrame()
        self.box.setObjectName("UploadBox")
        self.box.setMinimumHeight(160)
        box_layout = QVBoxLayout(self.box)
        box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.file_label = QLabel("Chưa chọn file nào")
        self.file_label.setFont(QFont("Inter", 11))
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_layout.addWidget(self.file_label)

        btn_row = QHBoxLayout()
        self.select_btn = QPushButton("Chọn File")
        self.select_btn.setFixedSize(130, 40)
        self.select_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_btn.clicked.connect(self._select_file)
        btn_row.addWidget(self.select_btn)

        self.upload_btn = QPushButton("Tải Lên & Xử Lý")
        self.upload_btn.setFixedSize(160, 40)
        self.upload_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.upload_btn.clicked.connect(self._upload_file)
        self.upload_btn.setEnabled(False)
        btn_row.addWidget(self.upload_btn)

        box_layout.addLayout(btn_row)
        layout.addWidget(self.box)

        self.progress = IngestProgressWidget()
        self.progress.hide()
        layout.addWidget(self.progress)

        self.status = StatusLabel()
        layout.addWidget(self.status)

        layout.addWidget(SectionHeader("Tài liệu trong môn học"))

        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 4, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch()
        self.list_scroll.setWidget(self._list_container)
        layout.addWidget(self.list_scroll, 1)

        self._empty_lbl = QLabel("Chưa có tài liệu nào.")
        self._empty_lbl.setFont(QFont("Inter", 10))
        self._empty_lbl.setWordWrap(True)
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_lbl)

        self.apply_theme_styles()

    def apply_theme_styles(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]

            self.box.setStyleSheet(f"""
                QFrame#UploadBox {{
                    background: {tokens["BG_SIDEBAR"]};
                    border: 2px dashed {tokens["BORDER"]};
                    border-radius: 14px;
                }}
            """)
            self.file_label.setStyleSheet(
                f"color:{tokens['COLOR_TEXT_MUTED']}; border: none; background: transparent;"
            )
            self.select_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens["BG_WIDGET"]};
                    color: {tokens["COLOR_TEXT"]};
                    border: 1px solid {tokens["BORDER"]};
                    border-radius: 8px;
                }}
                QPushButton:hover:enabled {{
                    background: {tokens["BG_HOVER"]};
                    border-color: {tokens["BORDER_HOVER"]};
                }}
                QPushButton:disabled {{
                    color: {tokens["COLOR_TEXT_DISABLED"]};
                }}
            """)
            self.upload_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens["COLOR_BLUE"]};
                    color: #FFFFFF;
                    border-radius: 8px;
                    border: none;
                }}
                QPushButton:hover:enabled {{
                    background: {tokens["COLOR_ACCENT_HOVER"]};
                }}
                QPushButton:disabled {{
                    background: {tokens["BG_WIDGET"]};
                    color: {tokens["COLOR_TEXT_DISABLED"]};
                }}
            """)
            self.list_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
            self._empty_lbl.setStyleSheet(
                f"color:{tokens['COLOR_TEXT_MUTED']}; background:transparent; padding: 24px;"
            )
            for card in self._doc_cards:
                card.apply_theme_styles()
            self.progress.apply_theme_styles()
        except Exception:
            pass

    def set_subject(self, subject_id: str, subject_config):
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._selected_file = None
        self.file_label.setText("Chưa chọn file nào")
        self.upload_btn.setEnabled(False)
        self.apply_theme_styles()
        self._refresh_document_list()

    def _refresh_document_list(self):
        for card in self._doc_cards:
            self._list_layout.removeWidget(card)
            card.deleteLater()
        self._doc_cards.clear()

        doc_dir = Path(self.subject_cfg.documents_dir)
        files = []
        if doc_dir.exists():
            files = sorted(
                f.resolve() for f in doc_dir.iterdir()
                if f.suffix.lower() in (".pdf", ".docx", ".doc")
            )

        self._empty_lbl.setVisible(not files)
        self.list_scroll.setVisible(bool(files))

        for f in files:
            card = _DocumentCard(str(f), f.name)
            card.remove_requested.connect(self._delete_document)
            idx = self._list_layout.count() - 1
            self._list_layout.insertWidget(idx, card)
            self._doc_cards.append(card)

        if self._busy:
            for card in self._doc_cards:
                card.set_busy(True)

    def _select_file(self):
        if self._busy:
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn tài liệu", "", "Documents (*.pdf *.docx)"
        )
        if file_path:
            self._selected_file = file_path
            self.file_label.setText(Path(file_path).name)
            try:
                from ui.theme_manager import get_theme, PALETTES
                tokens = PALETTES[get_theme()]
                self.file_label.setStyleSheet(
                    f"color:{tokens['COLOR_GREEN']}; border: none; font-weight: bold; background:transparent;"
                )
            except Exception:
                pass
            self.upload_btn.setEnabled(True)

    def _run_worker(self, fn, on_result, on_error=None):
        if self._busy:
            self.status.set_error("Đang xử lý, vui lòng đợi...")
            return

        self._set_busy(True)
        self._worker = LLMWorker(fn)
        self._worker.result.connect(on_result)
        if on_error:
            self._worker.error.connect(on_error)
        else:
            self._worker.error.connect(self._on_worker_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._thread = run_in_thread(self._worker)

    def _on_worker_finished(self):
        self._set_busy(False)

    def _on_worker_error(self, err: str):
        self.progress.hide()
        self.status.set_error(f"Lỗi: {err}")

    def _upload_file(self):
        if not self._selected_file:
            return

        src = Path(self._selected_file)
        self.progress.show()
        self.progress.set_file(src.name)
        self.status.set_loading(f"Đang nạp '{src.name}'...")

        class _ProgressBridge(QObject):
            progress = pyqtSignal(str, int, int)

        bridge = _ProgressBridge()
        bridge.progress.connect(self.progress.update_stage)
        storage_id = self._storage_id()

        def _process():
            doc_dir = Path(self.subject_cfg.documents_dir)
            doc_dir.mkdir(parents=True, exist_ok=True)
            dest = (doc_dir / src.name).resolve()
            if src.resolve() != dest:
                shutil.copy2(src, dest)

            def _cb(stage, done, total):
                bridge.progress.emit(stage, done, total)

            from core.retrieval.hybrid_retriever import ingest_document
            chunks_added = ingest_document(dest, storage_id, progress_cb=_cb)
            return str(dest), src.name, chunks_added

        self._run_worker(_process, self._on_upload_done)

    @pyqtSlot(object)
    def _on_upload_done(self, result):
        _dest_path, name, chunks = result
        self.progress.set_done(chunks)
        self.status.set_done(f"Thành công! Đã thêm '{name}' — {chunks} đoạn kiến thức.")
        self._selected_file = None
        self.file_label.setText("Chưa chọn file nào")
        self.apply_theme_styles()
        self._refresh_document_list()
        self.document_changed.emit()

    def _delete_document(self, file_path: str):
        path = Path(file_path).resolve()
        if not path.exists():
            self.status.set_error("File không tồn tại.")
            self._refresh_document_list()
            return

        name = path.name
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa tài liệu",
            f"Bạn có chắc muốn xóa '{name}'?\n"
            "File và dữ liệu đã index sẽ bị xóa vĩnh viễn.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.status.set_loading(f"Đang xóa '{name}'...")
        storage_id = self._storage_id()
        path_str = str(path)

        def _delete():
            from core.retrieval.hybrid_retriever import delete_document
            removed = delete_document(path_str, storage_id)
            try:
                os.remove(path_str)
            except FileNotFoundError:
                pass
            return name, removed

        self._run_worker(_delete, self._on_delete_done, on_error=self._on_delete_error)

    def _on_delete_error(self, err: str):
        self.status.set_error(f"Lỗi xóa: {err}")

    @pyqtSlot(object)
    def _on_delete_done(self, result):
        name, removed = result
        self.status.set_done(f"Đã xóa '{name}' ({removed} đoạn index).")
        self._refresh_document_list()
        self.document_changed.emit()
