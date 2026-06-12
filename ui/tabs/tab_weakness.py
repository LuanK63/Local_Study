"""
ui/tabs/tab_weakness.py — M8 Weakness Detection Tab
Analyze quiz/practice history to find weak topics and suggest review.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from ui.widgets import OutputDisplay, SectionHeader, StatusLabel
from ui.worker import LLMWorker, run_in_thread


class WeaknessTab(QWidget):
    def __init__(self, subject_id: str, subject_config, parent=None):
        super().__init__(parent)
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._thread = None
        self._worker = None
        self._weak_topics = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(SectionHeader("⚠️ Weakness Detection"))
        
        desc = QLabel(
            "Phân tích dữ liệu từ quá trình làm bài Quiz và Practice của bạn "
            "để tìm ra các chủ đề còn yếu."
        )
        desc.setWordWrap(True)
        desc.setFont(QFont("Inter", 10))
        layout.addWidget(desc)

        # Controls
        controls = QHBoxLayout()
        self.scan_btn = QPushButton("🔍 Quét Lịch Sử Học Tập")
        self.scan_btn.setFixedSize(200, 40)
        self.scan_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.scan_btn.clicked.connect(self._scan_weaknesses)
        controls.addWidget(self.scan_btn)
        
        self.plan_btn = QPushButton("💡 Đề xuất Kế Hoạch Ôn Tập")
        self.plan_btn.setFixedSize(220, 40)
        self.plan_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.plan_btn.clicked.connect(self._generate_plan)
        self.plan_btn.setEnabled(False)
        controls.addWidget(self.plan_btn)
        
        controls.addStretch()
        layout.addLayout(controls)

        self.status = StatusLabel()
        layout.addWidget(self.status)

        # Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Chủ đề", "Số lần thử", "Số lần sai", "Tỷ lệ sai"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet(
            "QTableWidget { background:#1a1b2e; color:#cdd6f4; gridline-color:#3a3c52; border: 1px solid #3a3c52; border-radius: 6px; }"
            "QHeaderView::section { background:#2a2b3d; color:#cdd6f4; padding:4px; font-weight:bold; border: 1px solid #3a3c52; }"
        )
        layout.addWidget(self.table)

        # Output Plan
        self.output = OutputDisplay()
        layout.addWidget(self.output)

    def set_subject(self, subject_id: str, subject_config):
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._scan_weaknesses() # Auto scan on load

    def _scan_weaknesses(self):
        from modules.weakness_detector import get_weak_topics
        self.status.set_loading("Đang phân tích cơ sở dữ liệu...")
        self.scan_btn.setEnabled(False)
        self.table.setRowCount(0)
        
        try:
            self._weak_topics = get_weak_topics(self.subject_id)
            self._populate_table()
            self.status.set_done(f"Đã tìm thấy {len(self._weak_topics)} chủ đề có dữ liệu.")
            self.plan_btn.setEnabled(len(self._weak_topics) > 0)
        except Exception as e:
            self.status.set_error(str(e))
        finally:
            self.scan_btn.setEnabled(True)

    def _populate_table(self):
        self.table.setRowCount(len(self._weak_topics))
        for row, data in enumerate(self._weak_topics):
            # Translate topic_id to name if possible
            topic_name = data['topic_id']
            for t in self.subject_cfg.topics:
                if t['id'] == topic_name:
                    topic_name = t['name']
                    break
                    
            item_name = QTableWidgetItem(topic_name)
            item_att = QTableWidgetItem(str(data['attempts']))
            item_wrong = QTableWidgetItem(str(data['wrong']))
            
            rate = data['wrong_rate']
            item_rate = QTableWidgetItem(f"{rate*100:.0f}%")
            
            # Color coding
            if rate > 0.5:
                color = QColor("#f38ba8") # Red
            elif rate > 0.3:
                color = QColor("#f9e2af") # Yellow
            else:
                color = QColor("#a6e3a1") # Green
                
            item_rate.setForeground(color)
            
            # Center alignment
            item_att.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_wrong.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_rate.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_att)
            self.table.setItem(row, 2, item_wrong)
            self.table.setItem(row, 3, item_rate)

    def _generate_plan(self):
        if not self._weak_topics:
            return
            
        if self._thread and self._thread.isRunning():
            return
            
        self.plan_btn.setEnabled(False)
        self.output.clear_output()
        self.status.set_loading("Đang nhờ AI phân tích và lên kế hoạch ôn tập...")

        def _gen():
            from modules.weakness_detector import generate_review_plan
            return generate_review_plan(self._weak_topics, self.subject_id)

        self._worker = LLMWorker(_gen)
        self._worker.result.connect(self._on_plan_ready)
        self._worker.error.connect(lambda e: self.status.set_error(e))
        self._worker.finished.connect(lambda: self.plan_btn.setEnabled(True))
        self._thread = run_in_thread(self._worker)

    def _on_plan_ready(self, plan: str):
        self.output.clear_output()
        self.output.append_token(plan) # Non-streaming, just dump all
        self.status.set_done("Đã lập kế hoạch ôn tập.")
