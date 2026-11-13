"""Live vision feed with detected target overlays."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame


class FeedWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel("Screen recognition")
        title.setStyleSheet("font-weight: 700; color: #0f3d4c; font-size: 14px;")
        hint = QLabel("Latest desktop capture with detected UI targets")
        hint.setObjectName("sectionHint")

        self.frame = QFrame()
        self.frame.setObjectName("feedFrame")
        self.frame.setMinimumHeight(280)
        frame_layout = QVBoxLayout(self.frame)
        self.image_label = QLabel("Capture preview will appear here")
        self.image_label.setObjectName("feedLabel")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(320, 240)
        frame_layout.addWidget(self.image_label)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(self.frame, stretch=1)

        self._boxes: List[Dict[str, Any]] = []

    def show_frame(self, frame: Optional[np.ndarray], boxes: Optional[List[Dict[str, Any]]] = None) -> None:
        if frame is None:
            return
        self._boxes = boxes or []
        rgb = np.ascontiguousarray(frame)
        if rgb.dtype != np.uint8:
            rgb = rgb.astype(np.uint8)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
        pix = QPixmap.fromImage(qimg)
        if self._boxes:
            painter = QPainter(pix)
            pen = QPen(QColor(20, 180, 120))
            pen.setWidth(max(2, pix.width() // 400))
            painter.setPen(pen)
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            for box in self._boxes[:40]:
                x, y, bw, bh = int(box["x"]), int(box["y"]), int(box["w"]), int(box["h"])
                painter.drawRect(x, y, bw, bh)
                label = str(box.get("label", ""))[:28]
                if label:
                    painter.drawText(x + 2, max(14, y - 4), label)
            painter.end()
        scaled = pix.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        pm = self.image_label.pixmap()
        if pm and not pm.isNull():
            self.image_label.setPixmap(
                pm.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
