"""
ui/worker.py — Background worker threads for LLM calls.
Prevents UI from freezing during long operations.
"""
from PyQt6.QtCore import QThread, pyqtSignal, QObject
from typing import Callable


class LLMWorker(QObject):
    """Generic worker: runs a callable in a background thread, emits result."""
    result   = pyqtSignal(object)   # finished result
    error    = pyqtSignal(str)      # error message
    finished = pyqtSignal()

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.result.emit(result)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class StreamWorker(QObject):
    """Worker for streaming LLM output — emits tokens one by one."""
    token    = pyqtSignal(str)
    error    = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            for chunk in self._fn(*self._args, **self._kwargs):
                self.token.emit(chunk)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


def run_in_thread(worker: LLMWorker | StreamWorker) -> QThread:
    """Convenience: create thread, move worker, connect, start. Returns thread."""
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    thread.start()
    return thread
