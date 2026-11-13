"""Fit windows to the visible screen and keep system min/max/close buttons."""

from __future__ import annotations

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QApplication, QWidget


def apply_standard_window_chrome(widget: QWidget) -> None:
    """Ensure minimize / maximize / close are available (native OS chrome)."""
    widget.setWindowFlags(
        Qt.Window
        | Qt.WindowTitleHint
        | Qt.WindowSystemMenuHint
        | Qt.WindowMinMaxButtonsHint
        | Qt.WindowCloseButtonHint
    )


def fit_to_screen(
    widget: QWidget,
    preferred_w: int = 1100,
    preferred_h: int = 700,
    *,
    min_w: int = 860,
    min_h: int = 560,
    margin: int = 48,
) -> None:
    """Resize and center a window so it fits the available desktop area."""
    screen = QApplication.primaryScreen()
    if screen is None:
        widget.resize(preferred_w, preferred_h)
        return
    geo = screen.availableGeometry()
    max_w = max(640, geo.width() - margin)
    max_h = max(480, geo.height() - margin)
    w = min(preferred_w, max_w)
    h = min(preferred_h, max_h)
    widget.setMinimumSize(QSize(min(min_w, max_w), min(min_h, max_h)))
    widget.resize(w, h)
    x = geo.x() + (geo.width() - w) // 2
    y = geo.y() + (geo.height() - h) // 2
    widget.move(max(geo.x(), x), max(geo.y(), y))
