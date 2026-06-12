"""
modules/visualizer/render_engine.py — Thread-safe Render & Animation Engine
===========================================================================
Vai trò:
  - Cầu nối an toàn giữa Worker Thread (chạy thuật toán) và Main Thread (Qt UI).
  - Worker thread KHÔNG được gọi bất kỳ Qt widget nào trực tiếp.
    Thay vào đó nó gọi `RenderEngine.emit_frame(payload)` để gửi dữ liệu,
    và Main Thread sẽ vẽ lại khi nhận được signal.

Luồng dữ liệu:
  Worker Thread → RenderEngine.emit_frame() → Qt Signal (thread-safe)
                                              → Canvas.on_frame_received()
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable

from PyQt6.QtCore import QObject, pyqtSignal


# ── Frame payload type alias ──────────────────────────────────────────────────
# Mỗi frame là một dict tự do: canvas nhận và tự interpret theo mode của nó.
FramePayload = dict[str, Any]


class RenderEngine(QObject):
    """
    Singleton-per-visualizer: nhận frame từ worker thread và phát signal
    để Main Thread vẽ lại canvas.

    Sử dụng:
        engine = RenderEngine(speed_fn=lambda: slider.value())
        engine.frame_ready.connect(canvas.on_frame_received)
        engine.start(target=my_algo_function)
    """

    # Signal phát về Main Thread — LUÔN LUÔN an toàn giữa các luồng
    frame_ready   = pyqtSignal(dict)   # payload frame để vẽ
    algo_finished = pyqtSignal(str)    # thông báo kết thúc ("done" / "stopped" / lỗi)
    algo_started  = pyqtSignal()       # thông báo bắt đầu

    def __init__(self, speed_fn: Callable[[], int] | None = None, parent=None):
        """
        Args:
            speed_fn: Hàm không tham số trả về độ trễ tính bằng mili-giây.
                      Nếu None, dùng giá trị mặc định 500ms.
        """
        super().__init__(parent)
        self._speed_fn   = speed_fn or (lambda: 500)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()   # set → yêu cầu dừng
        self._pause_event = threading.Event()  # clear → pause, set → resume
        self._pause_event.set()                # mặc định: đang chạy (không pause)

    # ── Public API (gọi từ Main Thread) ──────────────────────────────────────

    def start(self, target: Callable[[], None]) -> None:
        """Khởi chạy `target` trong worker thread."""
        if self._thread and self._thread.is_alive():
            self.stop()  # dừng thread cũ nếu còn sống

        self._stop_event.clear()
        self._pause_event.set()

        self._thread = threading.Thread(
            target=self._run_wrapper,
            args=(target,),
            daemon=True,   # thread tự chết khi app đóng
            name="VisualizerWorker"
        )
        self._thread.start()
        self.algo_started.emit()

    def stop(self) -> None:
        """Yêu cầu dừng worker thread. Không block."""
        self._stop_event.set()
        self._pause_event.set()   # giải phóng nếu đang pause để thread thoát được

    def pause(self) -> None:
        """Tạm dừng hoạt ảnh."""
        self._pause_event.clear()

    def resume(self) -> None:
        """Tiếp tục hoạt ảnh."""
        self._pause_event.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    # ── API cho Worker Thread ─────────────────────────────────────────────────

    def emit_frame(self, payload: FramePayload) -> None:
        """
        Gửi một frame lên Main Thread để vẽ.
        Hàm này AN TOÀN để gọi từ bất kỳ thread nào.
        Sau khi emit, thread ngủ theo `speed_fn()` ms.
        Trong lúc ngủ, nếu bị pause thì tiếp tục chờ.
        """
        if self._stop_event.is_set():
            return

        # Phát signal → Qt tự marshal sang Main Thread
        self.frame_ready.emit(payload)

        # Chờ pause nếu cần, kiểm tra stop_event mỗi 50ms
        self._pause_event.wait()

        # Ngủ theo tốc độ (chia nhỏ để check stop_event thường xuyên hơn)
        delay_s = self._speed_fn() / 1000.0
        deadline = time.monotonic() + delay_s
        while time.monotonic() < deadline:
            if self._stop_event.is_set():
                return
            time.sleep(min(0.05, deadline - time.monotonic()))

        # Một lần nữa chờ nếu bị pause sau khi ngủ xong
        self._pause_event.wait()

    def should_stop(self) -> bool:
        """Worker thread gọi hàm này để biết có nên thoát sớm không."""
        return self._stop_event.is_set()

    # ── Private ───────────────────────────────────────────────────────────────

    def _run_wrapper(self, target: Callable[[], None]) -> None:
        """Wrapper chạy trong worker thread, bắt exception."""
        try:
            target()
            if not self._stop_event.is_set():
                self.algo_finished.emit("done")
        except Exception as exc:
            self.algo_finished.emit(f"error: {exc}")
