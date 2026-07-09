"""
ui/tabs/tab_weakness.py — M8 Weakness Detection Tab
Analyze quiz/practice history to find weak topics and suggest review.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from ui.widgets import SectionHeader, StatusLabel


class WeaknessTab(QWidget):
    def __init__(self, subject_id: str, subject_config, parent=None):
        super().__init__(parent)
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._weak_topics = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(SectionHeader("Weakness Detection"))
        
        desc = QLabel(
            "Phân tích dữ liệu từ quá trình làm bài Quiz và Practice của bạn "
            "để tìm ra các chủ đề còn yếu."
        )
        desc.setWordWrap(True)
        desc.setFont(QFont("Inter", 10))
        layout.addWidget(desc)

        # Controls
        controls = QHBoxLayout()
        self.scan_btn = QPushButton("Quét lịch sử học tập")
        self.scan_btn.setFixedSize(200, 40)
        self.scan_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.scan_btn.clicked.connect(self._scan_weaknesses)
        controls.addWidget(self.scan_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.status = StatusLabel()
        layout.addWidget(self.status)

        # Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Chủ đề", "Số lần thử", "Số lần sai", "Tỷ lệ sai"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.apply_theme_styles()

    def apply_theme_styles(self):
        """Update all inline-styled widgets to current theme."""
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            self.table.setStyleSheet(
                f"QTableWidget {{ background:{tokens['BG_MAIN']}; color:{tokens['COLOR_TEXT']};"
                f" gridline-color:{tokens['BORDER']}; border:1px solid {tokens['BORDER']}; border-radius:6px; }}"
                f"QHeaderView::section {{ background:{tokens['BG_WIDGET']}; color:{tokens['COLOR_TEXT']};"
                f" padding:4px; font-weight:bold; border:1px solid {tokens['BORDER']}; }}"
            )
        except Exception:
            pass

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
            
            # Color coding with theme-aware colors
            try:
                from ui.theme_manager import get_theme, PALETTES
                tokens = PALETTES[get_theme()]
                if rate > 0.5:
                    color = QColor(tokens["COLOR_RED"])
                elif rate > 0.3:
                    color = QColor(tokens["COLOR_YELLOW"])
                else:
                    color = QColor(tokens["COLOR_GREEN"])
            except Exception:
                if rate > 0.5:
                    color = QColor("#f38ba8")
                elif rate > 0.3:
                    color = QColor("#f9e2af")
                else:
                    color = QColor("#a6e3a1")
                
            item_rate.setForeground(color)
            
            # Center alignment
            item_att.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_wrong.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_rate.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_att)
            self.table.setItem(row, 2, item_wrong)
            self.table.setItem(row, 3, item_rate)
