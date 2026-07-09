"""
ui/tabs/tab_sandbox.py — Interactive Code Sandbox + Grader
Supports interactive Terminal/Console running in real-time.
"""
import os
import sys
import time
import shutil
import tempfile
import threading
import subprocess
import ctypes
import codecs
import psutil

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QComboBox, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPlainTextEdit, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QObject, QTimer
from PyQt6.QtGui import QFont, QColor, QTextCursor, QKeyEvent

from ui.widgets import CodeEditor, StatusLabel, SectionHeader
from ui.worker import LLMWorker, run_in_thread


class TerminalWidget(QPlainTextEdit):
    input_submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(False)
        self.setFont(QFont("Consolas", 10))
        self._input_start_pos = 0
        self.apply_theme_styles()
        self.clear_console()

    def apply_theme_styles(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            self.setStyleSheet(f"""
                QPlainTextEdit {{
                    background: {tokens["BG_TERMINAL"]};
                    border: 1px solid {tokens["BORDER_INPUT"]};
                    border-radius: 8px;
                    color: {tokens["COLOR_TEXT_TERMINAL"]};
                    padding: 10px;
                }}
            """)
        except Exception:
            pass

    def append_html(self, html: str):
        bar = self.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 15

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)

        cursor.insertHtml(html)

        self._input_start_pos = self.toPlainText().__len__()
        if at_bottom:
            bar.setValue(bar.maximum())

    def clear_console(self):
        self.clear()
        self._input_start_pos = 0

    def append_output(self, text: str):
        bar = self.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 15

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)

        self.insertPlainText(text)

        self._input_start_pos = self.toPlainText().__len__()

        if at_bottom:
            bar.setValue(bar.maximum())

    def keyPressEvent(self, event: QKeyEvent):
        cursor = self.textCursor()

        if cursor.position() < self._input_start_pos:
            if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down,
                               Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
                super().keyPressEvent(event)
                return
            else:
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.setTextCursor(cursor)

        if event.key() == Qt.Key.Key_Backspace:
            if cursor.position() <= self._input_start_pos:
                event.accept()
                return

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            full_text = self.toPlainText()
            user_input = full_text[self._input_start_pos:]

            self.input_submitted.emit(user_input + "\n")

            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(cursor)
            self.insertPlainText("\n")

            self._input_start_pos = self.toPlainText().__len__()

            bar = self.verticalScrollBar()
            bar.setValue(bar.maximum())
            event.accept()
            return

        super().keyPressEvent(event)


class InteractiveProcessWorker(QObject):
    output_received = pyqtSignal(str)
    process_finished = pyqtSignal(int, float)
    error_occurred = pyqtSignal(str)

    def __init__(self, cmd: list[str], cwd: str, env: dict = None):
        super().__init__()
        self.cmd = cmd
        self.cwd = cwd
        self.env = env
        self.process = None
        self._thread_stdout = None
        self._thread_stderr = None
        self._running = False
        self._start_time = 0.0

    def start(self):
        try:
            self._start_time = time.perf_counter()
            self.process = subprocess.Popen(
                self.cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                cwd=self.cwd,
                env=self.env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            self._running = True

            self._thread_stdout = threading.Thread(target=self._read_pipe, args=(self.process.stdout,), daemon=True)
            self._thread_stderr = threading.Thread(target=self._read_pipe, args=(self.process.stderr,), daemon=True)
            self._thread_stdout.start()
            self._thread_stderr.start()

            self._thread_wait = threading.Thread(target=self._wait_for_exit, daemon=True)
            self._thread_wait.start()

            self.start_watchdog()
        except Exception as e:
            self.error_occurred.emit(str(e))

    def write_input(self, text: str):
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write(text.encode('utf-8'))
                self.process.stdin.flush()
            except Exception as e:
                self.output_received.emit(f"\n[Lỗi gửi input: {e}]\n")

    def _join_reader_threads(self, timeout: float = 5.0):
        if self._thread_stdout and self._thread_stdout.is_alive():
            self._thread_stdout.join(timeout=timeout)
        if self._thread_stderr and self._thread_stderr.is_alive():
            self._thread_stderr.join(timeout=timeout)

    def stop(self):
        self._running = False
        if hasattr(self, "_watchdog_timer"):
            self._watchdog_timer.stop()

        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                try:
                    self.process.kill()
                    self.process.wait(timeout=1.0)
                except Exception:
                    pass
            except Exception:
                pass

        self._join_reader_threads()

        if self.process:
            try:
                self.process.stdin.close()
            except Exception:
                pass
            try:
                self.process.stdout.close()
            except Exception:
                pass
            try:
                self.process.stderr.close()
            except Exception:
                pass
            self.process = None

    def _emit_decoded(self, decoder, chunk_bytes: bytes):
        if not chunk_bytes:
            return
        text = decoder.decode(chunk_bytes)
        if text:
            self.output_received.emit(text)

    def _read_pipe(self, pipe):
        handle = None
        if sys.platform == "win32":
            try:
                import msvcrt
                fd = pipe.fileno()
                handle = msvcrt.get_osfhandle(fd)
            except Exception:
                handle = None

        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        while self._running:
            try:
                avail = ctypes.c_ulong(0)
                if handle:
                    success = ctypes.windll.kernel32.PeekNamedPipe(
                        handle, None, 0, None, ctypes.byref(avail), None
                    )
                    if not success:
                        break
                else:
                    avail.value = 1

                if avail.value > 0:
                    chunk_bytes = pipe.read(avail.value)
                    if not chunk_bytes:
                        break
                    self._emit_decoded(decoder, chunk_bytes)
                else:
                    chunk_bytes = pipe.read(1)
                    if not chunk_bytes:
                        break
                    self._emit_decoded(decoder, chunk_bytes)
            except Exception:
                break

        try:
            while True:
                chunk_bytes = pipe.read(4096)
                if not chunk_bytes:
                    break
                self._emit_decoded(decoder, chunk_bytes)
        except Exception:
            pass

        try:
            text = decoder.decode(b"", final=True)
            if text:
                self.output_received.emit(text)
        except Exception:
            pass

    def _wait_for_exit(self):
        if self.process:
            exit_code = self.process.wait()
            elapsed = (time.perf_counter() - self._start_time) * 1000
            self._running = False
            if hasattr(self, "_watchdog_timer"):
                self._watchdog_timer.stop()
            self._join_reader_threads()
            self.process_finished.emit(exit_code, round(elapsed, 2))

    def start_watchdog(self):
        self._watchdog_timer = QTimer()
        self._watchdog_timer.setInterval(500)
        self._watchdog_timer.timeout.connect(self._check_watchdog)
        self._watchdog_timer.start()

    def _check_watchdog(self):
        if not self._running or not self.process:
            self._watchdog_timer.stop()
            return

        try:
            p = psutil.Process(self.process.pid)
            cpu_times = p.cpu_times()
            cpu_time = cpu_times.user + cpu_times.system

            if cpu_time > 30.0:
                self._watchdog_timer.stop()
                self.output_received.emit("\nProgram terminated (Timeout)\nExit Code: -1\n")
                self.stop()
                self.process_finished.emit(-1, 30000.0)
        except psutil.NoSuchProcess:
            self._watchdog_timer.stop()
        except Exception:
            pass


class SandboxTab(QWidget):
    def __init__(self, subject_id: str, subject_config, parent=None):
        super().__init__(parent)
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self._thread = None
        self._worker = None
        self._process_worker = None
        self._temp_dir_path = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        title = SectionHeader("Code Sandbox")
        top_bar.addWidget(title)
        top_bar.addStretch()

        lang_lbl = QLabel("Ngôn ngữ:")
        lang_lbl.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        top_bar.addWidget(lang_lbl)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["C++", "C", "Python"])
        self.lang_combo.setFixedHeight(34)
        self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        top_bar.addWidget(self.lang_combo)

        self.run_btn = QPushButton("Chạy")
        self.run_btn.setFixedSize(90, 34)
        self.run_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.run_btn.clicked.connect(self._on_run_clicked)
        top_bar.addWidget(self.run_btn)

        self.grade_btn = QPushButton("Chấm bài")
        self.grade_btn.setFixedSize(100, 34)
        self.grade_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.grade_btn.clicked.connect(self._on_grade)
        top_bar.addWidget(self.grade_btn)

        layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setSpacing(0)
        ll.setContentsMargins(0, 0, 0, 0)

        editor_card = QFrame()
        editor_card.setObjectName("SandboxCard")

        editor_layout = QVBoxLayout(editor_card)
        editor_layout.setContentsMargins(12, 12, 12, 12)
        editor_layout.setSpacing(0)

        self.editor = CodeEditor("cpp")
        self.editor.setMinimumHeight(450)
        self.editor.set_code(self._default_code("cpp"))
        self.editor.setStyleSheet(
            "QPlainTextEdit#CodeEditor { border: none; background: transparent; padding: 0; }"
        )

        editor_layout.addWidget(self.editor)
        ll.addWidget(editor_card)
        splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setSpacing(12)
        rl.setContentsMargins(0, 0, 0, 0)

        term_card = QFrame()
        term_card.setObjectName("SandboxCard")
        term_layout = QVBoxLayout(term_card)
        term_layout.setContentsMargins(12, 12, 12, 12)
        term_layout.setSpacing(8)

        term_header = QHBoxLayout()
        term_header.setContentsMargins(0, 0, 0, 0)
        term_title = QLabel("Terminal Console")
        term_title.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        term_title.setObjectName("SandboxTermTitle")
        term_header.addWidget(term_title)
        term_header.addStretch()

        self.status = StatusLabel()
        term_header.addWidget(self.status)
        term_layout.addLayout(term_header)

        self.terminal = TerminalWidget()
        self.terminal.setFixedHeight(200)
        self.terminal.input_submitted.connect(self._on_terminal_input)
        term_layout.addWidget(self.terminal)
        rl.addWidget(term_card)

        tc_card = QFrame()
        tc_card.setObjectName("SandboxCard")
        tc_layout = QVBoxLayout(tc_card)
        tc_layout.setContentsMargins(12, 12, 12, 12)
        tc_layout.setSpacing(8)

        tc_title = QLabel("Test Cases")
        tc_title.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        tc_layout.addWidget(tc_title)

        self._build_test_table(tc_layout)

        add_title = QLabel("Thêm Test Case mới:")
        add_title.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        tc_layout.addWidget(add_title)

        add_layout = QVBoxLayout()
        add_layout.setSpacing(4)
        add_layout.setContentsMargins(0, 0, 0, 0)

        add_layout.addWidget(QLabel("Input:"))
        self.tc_stdin = QLineEdit()
        self.tc_stdin.setPlaceholderText("stdin...")
        self.tc_stdin.setFixedHeight(30)
        add_layout.addWidget(self.tc_stdin)

        add_layout.addWidget(QLabel("Expected Output:"))
        self.tc_expected = QLineEdit()
        self.tc_expected.setPlaceholderText("Expected output...")
        self.tc_expected.setFixedHeight(30)
        add_layout.addWidget(self.tc_expected)

        add_layout.addSpacing(4)

        self.add_tc_btn = QPushButton("+ Add Test Case")
        self.add_tc_btn.setFixedHeight(32)
        self.add_tc_btn.clicked.connect(self._add_test_case)
        add_layout.addWidget(self.add_tc_btn)

        tc_layout.addLayout(add_layout)
        rl.addWidget(tc_card)

        splitter.addWidget(right)
        splitter.setSizes([600, 400])
        layout.addWidget(splitter)
        self.apply_theme_styles()

    def apply_theme_styles(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            self.run_btn.setStyleSheet(
                f"background:{tokens['COLOR_GREEN']}; color:{tokens['BG_MAIN']}; border-radius:6px;"
            )
            self.grade_btn.setStyleSheet(
                f"background:{tokens['COLOR_ACCENT']}; color:{tokens['BG_MAIN']}; border-radius:6px;"
            )
            self.tc_table.setStyleSheet(
                f"QTableWidget {{ background:{tokens['BG_WIDGET']}; color:{tokens['COLOR_TEXT']};"
                f" border:1px solid {tokens['BORDER']}; }}"
                f"QHeaderView::section {{ background:{tokens['BG_CHECKED']}; color:{tokens['COLOR_ACCENT']};"
                f" padding:6px; font-weight:bold; border:1px solid {tokens['BORDER']}; }}"
            )
            if hasattr(self, "terminal"):
                self.terminal.apply_theme_styles()
        except Exception:
            pass

    def _restore_run_btn(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            self.run_btn.setStyleSheet(
                f"background:{tokens['COLOR_GREEN']}; color:{tokens['BG_MAIN']}; border-radius:6px;"
            )
        except Exception:
            self.run_btn.setStyleSheet("background:#a6e3a1; color:#1a1b2e; border-radius:6px;")
        self.run_btn.setText("Chạy")

    def _set_run_btn_stop(self):
        try:
            from ui.theme_manager import get_theme, PALETTES
            tokens = PALETTES[get_theme()]
            self.run_btn.setStyleSheet(
                f"background:{tokens['COLOR_RED']}; color:{tokens['BG_MAIN']}; border-radius:6px;"
            )
        except Exception:
            self.run_btn.setStyleSheet("background:#f38ba8; color:#1a1b2e; border-radius:6px;")
        self.run_btn.setText("Dừng")

    def _build_test_table(self, layout):
        self.tc_table = QTableWidget(0, 4)
        self.tc_table.setHorizontalHeaderLabels(["Input", "Expected", "Actual", "✓"])
        self.tc_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tc_table.setFixedHeight(140)
        self.tc_table.setFont(QFont("Consolas", 9))
        self.tc_table.verticalHeader().setDefaultSectionSize(28)
        layout.addWidget(self.tc_table)

    def _lang_str(self) -> str:
        return {"C++": "cpp", "C": "c", "Python": "python"}[self.lang_combo.currentText()]

    def _on_lang_changed(self):
        lang = self._lang_str()
        if hasattr(self.editor, "set_language"):
            self.editor.set_language("python" if lang == "python" else "cpp")
        self.editor.set_code(self._default_code(lang))

    def _default_code(self, lang: str) -> str:
        if lang == "cpp":
            return """#include <iostream>
using namespace std;

int main() {
    int n;
    cout << "Enter n: ";
    cin >> n;
    cout << "Result: " << n * 2 << endl;
    return 0;
}"""
        elif lang == "c":
            return """#include <stdio.h>

int main() {
    int n;
    printf("Enter n: ");
    fflush(stdout);
    if (scanf("%d", &n) == 1) {
        printf("Result: %d\\n", n * 2);
    }
    return 0;
}"""
        else:
            return """n = int(input("Enter n: "))
print(f"Result: {n * 2}")
"""

    def set_subject(self, subject_id: str, subject_config):
        self._stop_running_process()
        self.subject_id = subject_id
        self.subject_cfg = subject_config
        self.terminal.clear_console()
        self.status.clear_status()

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

        status_item = QTableWidgetItem("...")
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tc_table.setItem(row, 3, status_item)
        self.tc_stdin.clear()
        self.tc_expected.clear()

    def _on_run_clicked(self):
        if self._process_worker:
            self._stop_running_process()
            return

        self.terminal.clear_console()
        code = self.editor.get_code()
        lang = self._lang_str()

        self._set_controls_enabled(False)
        self._set_run_btn_stop()

        self.status.set_loading("Đang biên dịch/chuẩn bị...")

        def _compile_and_prepare():
            if lang in ("c", "cpp"):
                from modules.code_sandbox import compile_c
                return compile_c(code, lang)
            else:
                from modules.code_sandbox import prepare_python
                return prepare_python(code)

        self._worker = LLMWorker(_compile_and_prepare)
        self._worker.result.connect(lambda res: self._on_prepare_done(res, lang))
        self._worker.error.connect(self._on_prepare_error)
        self._thread = run_in_thread(self._worker)

    def _on_prepare_done(self, result: tuple[str, str, str], lang: str):
        target_path, tmpdir_path, err = result
        if err:
            self.terminal.append_output(f"Lỗi: {err}\n")
            self.status.set_error("Biên dịch thất bại.")
            self._set_controls_enabled(True)
            self._restore_run_btn()
            return

        self._temp_dir_path = tmpdir_path
        self.status.set_loading("Đang chạy...")

        if lang in ("c", "cpp"):
            cmd = [target_path]
            env = os.environ.copy()
        else:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONUNBUFFERED"] = "1"
            cmd = [sys.executable or "python", "-u", target_path]

        self._process_worker = InteractiveProcessWorker(cmd, cwd=tmpdir_path, env=env)
        self._process_worker.output_received.connect(self.terminal.append_output)
        self._process_worker.process_finished.connect(self._on_process_finished)
        self._process_worker.error_occurred.connect(self._on_process_error)
        self._process_worker.start()

    def _on_prepare_error(self, err: str):
        self.terminal.append_output(f"Lỗi hệ thống: {err}\n")
        self.status.set_error("Lỗi chuẩn bị.")
        self._set_controls_enabled(True)
        self._restore_run_btn()

    def _on_terminal_input(self, text: str):
        if self._process_worker:
            self._process_worker.write_input(text)

    def _on_process_finished(self, exit_code: int, elapsed_ms: float):
        if exit_code == -1 and elapsed_ms >= 30000.0:
            self.status.set_error("Quá thời gian thực thi (Timeout 30s CPU)")
        else:
            from ui.theme_manager import get_theme, translate_qss
            msg = (
                f'<br/><span style="color:#6c7086; font-family:Consolas; font-size:10pt;">'
                f'Program exited with code {exit_code}<br/>'
                f'Runtime: {elapsed_ms:.0f} ms</span><br/>'
            )
            self.terminal.append_html(translate_qss(msg, get_theme()))
            self.status.set_done("Chương trình kết thúc.")

        self._cleanup_process_and_files()
        self._set_controls_enabled(True)
        self._restore_run_btn()

    def _on_process_error(self, err: str):
        self.terminal.append_output(f"\n[Lỗi chạy tiến trình: {err}]\n")
        self.status.set_error("Lỗi tiến trình.")
        self._cleanup_process_and_files()
        self._set_controls_enabled(True)
        self._restore_run_btn()

    def _stop_running_process(self):
        if self._process_worker:
            self._process_worker.stop()
            self.terminal.append_output("\nProgram terminated (Stop)\nExit Code: -1\n")
            self.status.set_error("Đã dừng tiến trình.")
            self._cleanup_process_and_files()

        self._set_controls_enabled(True)
        self._restore_run_btn()

    def _cleanup_process_and_files(self):
        if self._process_worker:
            try:
                self._process_worker.stop()
            except Exception:
                pass
            self._process_worker = None

        if self._temp_dir_path and os.path.exists(self._temp_dir_path):
            try:
                shutil.rmtree(self._temp_dir_path, ignore_errors=True)
            except Exception:
                pass
            self._temp_dir_path = None

    def _set_controls_enabled(self, enabled: bool):
        self.editor.setReadOnly(not enabled)
        self.lang_combo.setEnabled(enabled)
        self.grade_btn.setEnabled(enabled)
        self.add_tc_btn.setEnabled(enabled)
        self.tc_table.setEnabled(enabled)

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
        from ui.theme_manager import get_theme, PALETTES
        theme = get_theme()
        tokens = PALETTES[theme]
        green_color = QColor(tokens["COLOR_GREEN"])
        red_color = QColor(tokens["COLOR_RED"])

        for i, detail in enumerate(result.details):
            if i >= self.tc_table.rowCount():
                break
            self.tc_table.setItem(i, 2, QTableWidgetItem(detail["actual"]))
            status_item = QTableWidgetItem("Đạt" if detail["passed"] else "Lỗi")
            status_item.setForeground(green_color if detail["passed"] else red_color)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tc_table.setItem(i, 3, status_item)

        self.status.set_done(
            f"Kết quả: {result.passed}/{result.total} test cases — {result.score:.1f}%"
        )

    def closeEvent(self, event):
        self._stop_running_process()
        super().closeEvent(event)

    def __del__(self):
        try:
            self._stop_running_process()
        except Exception:
            pass
