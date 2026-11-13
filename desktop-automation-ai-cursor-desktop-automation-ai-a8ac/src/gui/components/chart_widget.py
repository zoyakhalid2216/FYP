"""Lightweight painted charts (no matplotlib dependency)."""

from __future__ import annotations

from typing import List, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QWidget


class LineChartWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._points: List[Tuple[str, float]] = []
        self.setMinimumHeight(160)

    def set_series(self, points: List[Tuple[str, float]]) -> None:
        self._points = list(points)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor("#f8fafc"))
        painter.setPen(QPen(QColor("#e5e7eb")))
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 8, 8)
        if not self._points:
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Run commands to populate trend data.")
            return
        values = [p[1] for p in self._points]
        vmax = max(values) or 1
        left, right, top, bottom = 36, w - 16, 16, h - 28
        plot_w = max(1, right - left)
        plot_h = max(1, bottom - top)
        # grid
        painter.setPen(QPen(QColor("#e2e8f0"), 1, Qt.DashLine))
        for i in range(4):
            y = top + int(plot_h * i / 3)
            painter.drawLine(left, y, right, y)
        xs = []
        ys = []
        n = len(self._points)
        for i, (_lab, val) in enumerate(self._points):
            x = left + int(plot_w * (i / max(1, n - 1))) if n > 1 else left + plot_w // 2
            y = bottom - int(plot_h * (val / vmax))
            xs.append(x)
            ys.append(y)
        painter.setPen(QPen(QColor("#4f46e5"), 2.4))
        for i in range(1, n):
            painter.drawLine(xs[i - 1], ys[i - 1], xs[i], ys[i])
        painter.setBrush(QColor("#4f46e5"))
        for x, y in zip(xs, ys):
            painter.drawEllipse(x - 4, y - 4, 8, 8)
        painter.setPen(QColor("#64748b"))
        for i, (lab, val) in enumerate(self._points):
            painter.drawText(xs[i] - 16, h - 8, 40, 16, Qt.AlignCenter, lab[-3:])


class BarRatioWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.success = 0
        self.failed = 0
        self.setMinimumHeight(72)

    def set_counts(self, success: int, failed: int) -> None:
        self.success = int(success)
        self.failed = int(failed)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        total = max(1, self.success + self.failed)
        ok_pct = self.success / total
        fail_pct = self.failed / total
        painter.setPen(Qt.NoPen)
        y = 8
        painter.setBrush(QColor("#10b981"))
        painter.drawRoundedRect(8, y, max(8, int((self.width() - 16) * ok_pct)), 16, 4, 4)
        painter.setBrush(QColor("#ef4444"))
        painter.drawRoundedRect(8, y + 28, max(8, int((self.width() - 16) * fail_pct)), 16, 4, 4)
        painter.setPen(QColor("#334155"))
        painter.drawText(12, y + 13, f"SUCCESS  {int(ok_pct * 100)}%")
        painter.drawText(12, y + 41, f"FAILED   {int(fail_pct * 100)}%")
