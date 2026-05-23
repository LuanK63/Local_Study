"""
modules/visualizer/algorithms/dijkstra.py — Dijkstra Pathfinding Visualizer
============================================================================
Triển khai đầy đủ thuật toán Dijkstra trên lưới 2D (grid).

Cách dùng:
    from modules.visualizer.algorithms.dijkstra import DijkstraVisualizer

    engine = RenderEngine(speed_fn=...)
    viz    = DijkstraVisualizer(engine, rows=15, cols=25)
    viz.set_start(0, 0)
    viz.set_end(14, 24)
    engine.start(viz.run)          # chạy trong worker thread

Mỗi frame phát ra payload có dạng:
    {
        "mode":    "dijkstra",
        "grid":    list[list[CellState]],   # "empty"|"wall"|"start"|"end"
        "dist":    list[list[float]],        # khoảng cách hiện tại (inf nếu chưa thăm)
        "visited": set of (row, col),
        "frontier":set of (row, col),
        "path":    list of (row, col) | None,
        "current": (row, col) | None,
        "message": str,
    }
"""
from __future__ import annotations

import heapq
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.visualizer.render_engine import RenderEngine

# Trạng thái của từng ô trong lưới
EMPTY = "empty"
WALL  = "wall"
START = "start"
END   = "end"


class DijkstraVisualizer:
    """
    Controller cho thuật toán Dijkstra trực quan hóa trên lưới 2D.
    Thread-safe: mọi cập nhật UI đều đi qua RenderEngine.
    """

    def __init__(self, engine: "RenderEngine", rows: int = 15, cols: int = 25):
        self._engine = engine
        self.rows = rows
        self.cols = cols

        # ── Trạng thái lưới ─────────────────────────────────────────────────
        # grid[r][c] = EMPTY | WALL | START | END
        self.grid: list[list[str]] = [
            [EMPTY] * cols for _ in range(rows)
        ]

        # Điểm bắt đầu & kết thúc mặc định
        self._start: tuple[int, int] = (0, 0)
        self._end:   tuple[int, int] = (rows - 1, cols - 1)
        self.grid[self._start[0]][self._start[1]] = START
        self.grid[self._end[0]][self._end[1]]     = END

    # ── Public setters (gọi từ Main Thread) ──────────────────────────────────

    def set_start(self, row: int, col: int) -> None:
        """Đặt ô bắt đầu."""
        old_r, old_c = self._start
        if self.grid[old_r][old_c] == START:
            self.grid[old_r][old_c] = EMPTY
        self._start = (row, col)
        self.grid[row][col] = START

    def set_end(self, row: int, col: int) -> None:
        """Đặt ô kết thúc."""
        old_r, old_c = self._end
        if self.grid[old_r][old_c] == END:
            self.grid[old_r][old_c] = EMPTY
        self._end = (row, col)
        self.grid[row][col] = END

    def toggle_wall(self, row: int, col: int) -> None:
        """Bật/tắt tường tại ô (row, col)."""
        if self.grid[row][col] == EMPTY:
            self.grid[row][col] = WALL
        elif self.grid[row][col] == WALL:
            self.grid[row][col] = EMPTY

    def clear(self) -> None:
        """Xóa toàn bộ tường, giữ nguyên start/end."""
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == WALL:
                    self.grid[r][c] = EMPTY

    # ── Thuật toán Dijkstra (chạy trong Worker Thread) ───────────────────────

    def run(self) -> None:
        """
        Hàm này chạy trong Worker Thread.
        Mỗi bước phát một frame lên Main Thread qua engine.emit_frame().
        """
        engine = self._engine

        # Khởi tạo cấu trúc dữ liệu Dijkstra
        INF = math.inf
        dist: list[list[float]] = [
            [INF] * self.cols for _ in range(self.rows)
        ]
        prev: dict[tuple, tuple | None] = {}   # lưu node trước để truy vết đường đi

        sr, sc = self._start
        er, ec = self._end

        dist[sr][sc] = 0.0
        # Min-heap: (khoảng cách, row, col)
        heap: list[tuple[float, int, int]] = [(0.0, sr, sc)]

        visited: set[tuple[int, int]]  = set()
        frontier: set[tuple[int, int]] = {(sr, sc)}

        # ── Phát frame khởi tạo ─────────────────────────────────────────────
        self._emit(engine, dist, visited, frontier, current=None,
                   path=None, message="Khởi tạo: đặt khoảng cách start = 0")

        # ── Vòng lặp chính ──────────────────────────────────────────────────
        while heap:
            if engine.should_stop():
                return

            cur_dist, r, c = heapq.heappop(heap)

            # Bỏ qua nếu đã thăm (stale entry trong heap)
            if (r, c) in visited:
                continue

            visited.add((r, c))
            frontier.discard((r, c))

            # Phát frame: đang xử lý node (r, c)
            self._emit(engine, dist, visited, frontier, current=(r, c),
                       path=None,
                       message=f"Đang xử lý ô ({r},{c}) — dist={cur_dist:.0f}")

            # Kiểm tra đến đích chưa
            if (r, c) == (er, ec):
                path = self._reconstruct_path(prev, sr, sc, er, ec)
                self._emit(engine, dist, visited, frontier, current=(r, c),
                           path=path, message="✅ Tìm thấy đường đi ngắn nhất!")
                return

            # Duyệt 4 láng giềng (lên, xuống, trái, phải)
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                    continue
                if self.grid[nr][nc] == WALL:
                    continue
                if (nr, nc) in visited:
                    continue

                new_dist = cur_dist + 1.0   # trọng số mỗi bước = 1
                if new_dist < dist[nr][nc]:
                    dist[nr][nc] = new_dist
                    prev[(nr, nc)] = (r, c)
                    heapq.heappush(heap, (new_dist, nr, nc))
                    frontier.add((nr, nc))

            # Phát frame sau khi cập nhật láng giềng
            self._emit(engine, dist, visited, frontier, current=(r, c),
                       path=None, message=f"Đã cập nhật láng giềng của ({r},{c})")

        # Nếu heap rỗng mà chưa đến đích → không có đường đi
        self._emit(engine, dist, visited, frontier, current=None,
                   path=None, message="❌ Không tìm thấy đường đi!")

    # ── Private helpers ───────────────────────────────────────────────────────

    def _reconstruct_path(
        self,
        prev: dict,
        sr: int, sc: int,
        er: int, ec: int
    ) -> list[tuple[int, int]]:
        """Truy vết từ đích về start để lấy đường đi."""
        path: list[tuple[int, int]] = []
        node: tuple[int, int] | None = (er, ec)
        while node is not None:
            path.append(node)
            node = prev.get(node)
        path.reverse()
        return path

    def _emit(
        self,
        engine: "RenderEngine",
        dist: list[list[float]],
        visited: set,
        frontier: set,
        current: tuple | None,
        path: list | None,
        message: str,
    ) -> None:
        """Đóng gói và gửi frame lên Main Thread."""
        engine.emit_frame({
            "mode":     "dijkstra",
            "grid":     [row[:] for row in self.grid],   # deep copy để tránh race condition
            "dist":     [row[:] for row in dist],
            "visited":  set(visited),
            "frontier": set(frontier),
            "path":     list(path) if path else None,
            "current":  current,
            "message":  message,
        })
