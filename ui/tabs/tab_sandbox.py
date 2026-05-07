"""
ui/tabs/tab_sandbox.py — M4b Code Sandbox + Grader
Code editor + run/compile + test case grading.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QComboBox, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QTextEdit, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from ui.widgets import CodeEditor, StatusLabel, SectionHeader
from ui.worker import LLMWorker, run_in_thread


class SandboxTab(QWidget):
    def __init__(self, subject_id: str, subject_config, parent=None):
        super().__init__(parent)
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._thread = None
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        layout.addWidget(SectionHeader("▶️ Code Sandbox"))

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: Editor + Controls ───────────────────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setSpacing(8)

        ctrl = QHBoxLayout()
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["C++", "C", "Python"])
        self.lang_combo.setFixedHeight(34)
        ctrl.addWidget(QLabel("Ngôn ngữ:"))
        ctrl.addWidget(self.lang_combo)
        ctrl.addStretch()

        self.run_btn = QPushButton("▶ Chạy")
        self.run_btn.setFixedSize(90, 34)
        self.run_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.run_btn.setStyleSheet("background:#a6e3a1; color:#1e1e2e; border-radius:6px;")
        self.run_btn.clicked.connect(self._on_run)
        ctrl.addWidget(self.run_btn)

        self.grade_btn = QPushButton("🏆 Chấm bài")
        self.grade_btn.setFixedSize(100, 34)
        self.grade_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.grade_btn.setStyleSheet("background:#cba6f7; color:#1e1e2e; border-radius:6px;")
        self.grade_btn.clicked.connect(self._on_grade)
        ctrl.addWidget(self.grade_btn)
        ll.addLayout(ctrl)

        self.editor = CodeEditor("cpp")
        self.editor.setMinimumHeight(280)
        self.editor.set_code(self._default_code())
        ll.addWidget(self.editor)

        # Stdin input
        ll.addWidget(QLabel("📥 Input (stdin):"))
        self.stdin_input = QTextEdit()
        self.stdin_input.setFont(QFont("Consolas", 10))
        self.stdin_input.setFixedHeight(60)
        self.stdin_input.setStyleSheet(
            "background:#181825; border:1px solid #45475a; border-radius:6px; "
            "color:#cdd6f4; padding:4px;"
        )
        ll.addWidget(self.stdin_input)

        splitter.addWidget(left)

        # ── Right: Output + Test Cases ─────────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setSpacing(8)

        # Output
        rl.addWidget(QLabel("📤 Output:"))
        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)
        self.output_display.setFont(QFont("Consolas", 10))
        self.output_display.setFixedHeight(160)
        self.output_display.setStyleSheet(
            "background:#181825; border:1px solid #313244; border-radius:6px; "
            "color:#cdd6f4; padding:8px;"
        )
        rl.addWidget(self.output_display)

        self.status = StatusLabel()
        rl.addWidget(self.status)

        # Test cases
        rl.addWidget(QLabel("🧪 Test Cases:"))
        self._build_test_table(rl)

        # Add test case row
        add_row = QHBoxLayout()
        self.tc_stdin = QLineEdit()
        self.tc_stdin.setPlaceholderText("Input...")
        self.tc_stdin.setFixedHeight(30)
        add_row.addWidget(QLabel("In:"))
        add_row.addWidget(self.tc_stdin)
        self.tc_expected = QLineEdit()
        self.tc_expected.setPlaceholderText("Expected output...")
        self.tc_expected.setFixedHeight(30)
        add_row.addWidget(QLabel("Out:"))
        add_row.addWidget(self.tc_expected)
        add_tc_btn = QPushButton("+")
        add_tc_btn.setFixedSize(30, 30)
        add_tc_btn.clicked.connect(self._add_test_case)
        add_row.addWidget(add_tc_btn)
        rl.addLayout(add_row)

        splitter.addWidget(right)
        splitter.setSizes([500, 400])
        layout.addWidget(splitter)

    def _build_test_table(self, layout):
        self.tc_table = QTableWidget(0, 4)
        self.tc_table.setHorizontalHeaderLabels(["Input", "Expected", "Actual", "✓"])
        self.tc_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tc_table.setFixedHeight(160)
        self.tc_table.setFont(QFont("Consolas", 9))
        self.tc_table.setStyleSheet(
            "QTableWidget { background:#181825; color:#cdd6f4; border:1px solid #313244; }"
            "QHeaderView::section { background:#313244; color:#cba6f7; padding:4px; }"
        )
        layout.addWidget(self.tc_table)

    def _default_code(self) -> str:
        return """#include <iostream>
using namespace std;

int main() {
    int n;
    cin >> n;
    cout << "Hello, n = " << n << endl;
    return 0;
}"""

    def _lang_str(self) -> str:
        return {"C++": "cpp", "C": "c", "Python": "python"}[self.lang_combo.currentText()]

    def set_subject(self, subject_id: str, subject_config):
        self.subject_id = subject_id
        self.subject_cfg = subject_config

    def _add_test_case(self):
        tc_in = self.tc_stdin.text()
        tc_out = self.tc_expected.text()
        if not tc_out:
            return
        row = self.tc_table.rowCount()
        self.tc_table.insertRow(row)
        self.tc_table.setItem(row, 0, QTableWidgetItem(tc_in))
        self.tc_table.setItem(row, 1, QTableWidgetItem(tc_out))
        self.tc_table.setItem(row, 2, QTableWidgetItem(""))
        self.tc_table.setItem(row, 3, QTableWidgetItem("⏳"))
        self.tc_stdin.clear()
        self.tc_expected.clear()

    def _on_run(self):
        code = self.editor.get_code()
        lang = self._lang_str()
        stdin = self.stdin_input.toPlainText()
        self.run_btn.setEnabled(False)
        self.status.set_loading("Đang biên dịch và chạy...")

        def _run():
            if lang in ("c", "cpp"):
                from modules.code_sandbox import run_c
                return run_c(code, stdin=stdin, lang=lang)
            else:
                from modules.code_sandbox import run_python
                return run_python(code, stdin=stdin)

        self._worker = LLMWorker(_run)
        self._worker.result.connect(self._on_run_result)
        self._worker.error.connect(lambda e: self.status.set_error(e))
        self._worker.finished.connect(lambda: self.run_btn.setEnabled(True))
        self._thread = run_in_thread(self._worker)

    def _on_run_result(self, result):
        if result.success:
            self.output_display.setPlainText(result.stdout)
            self.status.set_done(f"✅ Chạy xong — {result.elapsed_ms:.1f}ms")
        else:
            self.output_display.setPlainText(
                result.stderr or result.stdout or "Lỗi không xác định"
            )
            self.status.set_error(f"Lỗi biên dịch/chạy — {result.elapsed_ms:.1f}ms")

    def _on_grade(self):
        code = self.editor.get_code()
        lang = self._lang_str()
        rows = self.tc_table.rowCount()
        if rows == 0:
            self.status.set_error("Chưa có test case nào!")
            return

        from modules.code_grader import TestCase
        test_cases = []
        for i in range(rows):
            tc_in = self.tc_table.item(i, 0).text() if self.tc_table.item(i, 0) else ""
            tc_exp = self.tc_table.item(i, 1).text() if self.tc_table.item(i, 1) else ""
            test_cases.append(TestCase(stdin=tc_in, expected_stdout=tc_exp, description=f"TC{i+1}"))

        self.grade_btn.setEnabled(False)
        self.status.set_loading("Đang chấm bài...")

        def _grade():
            from modules.code_grader import grade
            return grade(code, test_cases, lang=lang, subject_id=self.subject_id)

        self._worker = LLMWorker(_grade)
        self._worker.result.connect(self._on_grade_result)
        self._worker.error.connect(lambda e: self.status.set_error(e))
        self._worker.finished.connect(lambda: self.grade_btn.setEnabled(True))
        self._thread = run_in_thread(self._worker)

    def _on_grade_result(self, result):
        for i, detail in enumerate(result.details):
            if i >= self.tc_table.rowCount():
                break
            self.tc_table.setItem(i, 2, QTableWidgetItem(detail["actual"]))
            status_item = QTableWidgetItem("✅" if detail["passed"] else "❌")
            status_item.setForeground(
                QColor("#a6e3a1") if detail["passed"] else QColor("#f38ba8")
            )
            self.tc_table.setItem(i, 3, status_item)

        self.status.set_done(
            f"Kết quả: {result.passed}/{result.total} test cases — {result.score:.1f}%"
        )
