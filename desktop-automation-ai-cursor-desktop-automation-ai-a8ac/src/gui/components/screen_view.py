"""Screenshot preview with OCR / detection bounding boxes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QLabel


class ScreenView(QLabel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("screenView")
        self.setMinimumHeight(180)
        self.setAlignment(Qt.AlignCenter)
        self.setText("Screen understanding appears here after a command.")
        self.setWordWrap(True)
        self._pixmap: Optional[QPixmap] = None
        self._boxes: List[Dict[str, Any]] = []

    def set_frame(self, frame, boxes: Optional[List[Dict[str, Any]]] = None, path: str = "") -> None:
        self._boxes = list(boxes or [])
        pix = None
        if path:
            pix = QPixmap(path)
        if (pix is None or pix.isNull()) and frame is not None:
            try:
                import numpy as np

                arr = np.asarray(frame)
                h, w = arr.shape[:2]
                img = QImage(arr.data, w, h, 3 * w, QImage.Format_RGB888)
                pix = QPixmap.fromImage(img.copy())
            except Exception:
                pix = None
        if pix is None or pix.isNull():
            self.setText("No screenshot yet.")
            self._pixmap = None
            return
        self._pixmap = pix
        self._paint()

    def _paint(self) -> None:
        if self._pixmap is None:
            return
        scaled = self._pixmap.scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        canvas = QPixmap(scaled)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)
        sx = canvas.width() / max(1, self._pixmap.width())
        sy = canvas.height() / max(1, self._pixmap.height())
        painter.setPen(QPen(QColor("#4f46e5"), 2))
        for box in self._boxes[:30]:
            x = int(box.get("x", 0) * sx)
            y = int(box.get("y", 0) * sy)
            w = int(box.get("w", 8) * sx)
            h = int(box.get("h", 8) * sy)
            painter.drawRect(x, y, max(4, w), max(4, h))
            label = str(box.get("label") or "")
            if label:
                painter.fillRect(x, max(0, y - 16), min(canvas.width() - x, 120), 16, QColor("#4f46e5"))
                painter.setPen(QColor("#ffffff"))
                painter.drawText(x + 4, max(12, y - 4), label[:18])
                painter.setPen(QPen(QColor("#4f46e5"), 2))
        painter.end()
        self.setPixmap(canvas)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._pixmap is not None:
            self._paint()
