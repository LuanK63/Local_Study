"""
ui/tabs/tab_visualize.py — Algorithm & Data Structure Visualizer Tab
Wrapper nhẹ nhúng VisualizerController vào layout của app chính.
Toàn bộ logic nằm trong modules/visualizer/.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from modules.visualizer.visualizer_controller import VisualizerController


class VisualizeTab(QWidget):
    """Tab wrapper — chỉ chứa VisualizerController."""

    def __init__(self, subject_id: str, subject_config, parent=None):
        super().__init__(parent)
        self.subject_id  = subject_id
        self.subject_cfg = subject_config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._controller = VisualizerController(parent=self)
        layout.addWidget(self._controller)

        # Nếu app chính có sidebar nav thì có thể kết nối signal này
        # self._controller.return_requested.connect(...)

    def set_subject(self, subject_id: str, subject_config) -> None:
        """Gọi từ MainWindow khi người dùng đổi môn học."""
        self.subject_id  = subject_id
        self.subject_cfg = subject_config
