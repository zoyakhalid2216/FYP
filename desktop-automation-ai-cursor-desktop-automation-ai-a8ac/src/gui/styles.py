"""Professional Automate AI themes — clean spacing, no overlap."""

from __future__ import annotations

LIGHT_STYLE = """
QWidget {
    font-family: "Segoe UI", "IBM Plex Sans", "Noto Sans", sans-serif;
    font-size: 13px;
    color: #111827;
}
QMainWindow, QDialog {
    background: #f5f6f8;
}

/* Login */
#landingRoot { background: #f5f6f8; }
#brandPanel { background: #eef1f5; }
#formPanel { background: #ffffff; }
#brandLogo { font-size: 20px; font-weight: 700; color: #0f172a; }
#brandEyebrow {
    color: #64748b; font-size: 11px; font-weight: 700; letter-spacing: 1px;
}
#brandHeadline { font-size: 28px; font-weight: 700; color: #0f172a; }
#brandHeadlineAccent {
    font-size: 28px; font-weight: 500; font-style: italic; color: #64748b;
}
#brandBody { color: #475569; font-size: 13px; }
#featureCard {
    background: #0f172a; border-radius: 12px; color: #f8fafc; padding: 16px;
}
#featureCardTitle { color: #ffffff; font-size: 16px; font-weight: 700; }
#featureCardBody { color: #cbd5e1; font-size: 12px; }
#loginTitle { font-size: 22px; font-weight: 700; }
#loginSubtitle { color: #64748b; }

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
    background: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 8px 10px;
    min-height: 18px;
    selection-background-color: #dbeafe;
}
QComboBox {
    background: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 8px 28px 8px 10px;
    min-height: 18px;
    min-width: 120px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border: none;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #d1d5db;
    selection-background-color: #e5e7eb;
    outline: 0;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #4f46e5;
}

QPushButton {
    background: #4f46e5;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 600;
    min-height: 20px;
}
QPushButton:hover { background: #4338ca; }
QPushButton:pressed { background: #3730a3; }
QPushButton:disabled { background: #94a3b8; color: #f8fafc; }

QPushButton#btnGhost, QPushButton#btnSecondary {
    background: #ffffff;
    color: #0f172a;
    border: 1px solid #d1d5db;
}
QPushButton#btnGhost:hover, QPushButton#btnSecondary:hover {
    background: #f3f4f6;
}

QPushButton#btnNav {
    background: transparent;
    color: #334155;
    text-align: left;
    padding: 10px 12px;
    border-radius: 8px;
    font-weight: 600;
    border: none;
}
QPushButton#btnNav:hover { background: #eef2f7; }
QPushButton#btnNav[active="true"] {
    background: #eef2ff;
    color: #3730a3;
    font-weight: 700;
}

QPushButton#btnMicBig {
    background: #0f172a;
    color: #ffffff;
    border-radius: 28px;
    min-width: 96px;
    max-width: 120px;
    min-height: 56px;
    max-height: 56px;
    font-size: 14px;
    font-weight: 700;
    padding: 8px 12px;
}
QPushButton#btnMicBig:disabled { background: #94a3b8; }
QPushButton#btnDanger { background: #b91c1c; color: #ffffff; }
QPushButton#btnDanger:hover { background: #991b1b; }
QPushButton#btnPrimary {
    background: #4f46e5;
    color: #ffffff;
    padding: 10px 18px;
    font-weight: 700;
}

#sideBar {
    background: #ffffff;
    border-right: 1px solid #e5e7eb;
}
#sideBrand { font-size: 15px; font-weight: 700; color: #0f172a; }
#topBar {
    background: #ffffff;
    border-bottom: 1px solid #e5e7eb;
}
#pageTitle { font-size: 22px; font-weight: 700; color: #0f172a; }
#pageSubtitle { color: #64748b; font-size: 12px; }

#statusChip {
    background: #ecfdf5;
    color: #047857;
    border: 1px solid #a7f3d0;
    border-radius: 999px;
    padding: 5px 10px;
    font-weight: 600;
    font-size: 11px;
}

#metricCard, #panelCard, #workflowCard, #voicePanel {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
}
#metricCard {
    min-height: 100px;
}
#workflowCard {
    min-height: 140px;
    padding: 2px;
}
#metricLabel {
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.2px;
}
#metricValue {
    color: #0f172a;
    font-size: 24px;
    font-weight: 700;
    padding: 0;
    margin: 0;
    min-height: 28px;
}
#metricHint {
    color: #94a3b8;
    font-size: 11px;
    font-weight: 400;
}

QTableWidget {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    gridline-color: #f1f5f9;
    outline: 0;
    alternate-background-color: #f8fafc;
}
QTableWidget::item { padding: 8px 6px; }
QHeaderView::section {
    background: #f8fafc;
    border: none;
    border-bottom: 1px solid #e5e7eb;
    border-right: 1px solid #f1f5f9;
    padding: 10px 12px;
    font-weight: 600;
    color: #475569;
    min-height: 28px;
}
QListWidget {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 4px;
}
QListWidget::item { padding: 6px 8px; border-radius: 6px; }
QListWidget::item:selected { background: #e8eef6; color: #0f172a; }

QSlider::groove:horizontal {
    height: 6px;
    background: #e2e8f0;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
    background: #0f172a;
}
QCheckBox { spacing: 8px; color: #334155; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    background: #ffffff;
}
QCheckBox::indicator:checked {
    background: #0f172a;
    border-color: #0f172a;
}
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: transparent; width: 10px; margin: 0;
}
QScrollBar::handle:vertical {
    background: #cbd5e1; border-radius: 5px; min-height: 30px;
}
#footerLabel { color: #94a3b8; font-size: 11px; }
#daiOverlay {
    background: #0f172a;
    color: #f8fafc;
    border-radius: 14px;
    border: 1px solid #334155;
}
#daiTitle { font-size: 15px; font-weight: 800; color: #f8fafc; }
#daiLine { font-size: 12px; font-weight: 600; color: #e2e8f0; }
#daiHint { font-size: 10px; color: #94a3b8; }
#daiHide {
    background: #1e293b; color: #e2e8f0; border: none; border-radius: 6px;
    padding: 0; font-weight: 700;
}
#daiChip {
    background: #312e81; color: #e0e7ff; border: 1px solid #6366f1;
    border-radius: 8px; padding: 4px 8px; font-size: 11px; font-weight: 600;
    text-align: left;
}
#daiRetry {
    background: #1e293b; color: #e2e8f0; border: 1px solid #475569;
    border-radius: 8px; font-size: 11px;
}
#daiStop {
    background: #7f1d1d; color: #fecaca; border: 1px solid #ef4444;
    border-radius: 6px; padding: 0 8px; font-size: 10px; font-weight: 800;
}
#logFrame {
    border: 1px solid #1e293b;
    border-radius: 8px;
    background: #0f172a;
}
#sectionTitle {
    font-size: 14px;
    font-weight: 700;
    color: #0f172a;
}
"""

DARK_STYLE = """
QWidget {
    font-family: "Segoe UI", "IBM Plex Sans", "Noto Sans", sans-serif;
    font-size: 13px;
    color: #e2e8f0;
}
QMainWindow, QDialog { background: #0b1220; }

#landingRoot { background: #0b1220; }
#brandPanel { background: #111827; }
#formPanel { background: #1e293b; }
#brandLogo { font-size: 20px; font-weight: 700; color: #f8fafc; }
#brandEyebrow {
    color: #94a3b8; font-size: 11px; font-weight: 700; letter-spacing: 1px;
}
#brandHeadline { font-size: 28px; font-weight: 700; color: #f8fafc; }
#brandHeadlineAccent {
    font-size: 28px; font-weight: 500; font-style: italic; color: #94a3b8;
}
#brandBody { color: #cbd5e1; font-size: 13px; }
#featureCard {
    background: #020617; border-radius: 12px; color: #f8fafc; padding: 16px;
}
#featureCardTitle { color: #ffffff; font-size: 16px; font-weight: 700; }
#featureCardBody { color: #94a3b8; font-size: 12px; }
#loginTitle { font-size: 22px; font-weight: 700; color: #f8fafc; }
#loginSubtitle { color: #94a3b8; }

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 10px;
    color: #e2e8f0;
    min-height: 18px;
}
QComboBox {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 28px 8px 10px;
    color: #e2e8f0;
    min-height: 18px;
    min-width: 120px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border: none;
}
QComboBox QAbstractItemView {
    background: #0f172a;
    border: 1px solid #334155;
    selection-background-color: #1e293b;
    color: #e2e8f0;
    outline: 0;
}

QPushButton {
    background: #6366f1;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 700;
    min-height: 20px;
}
QPushButton:hover { background: #818cf8; }
QPushButton:disabled { background: #475569; color: #cbd5e1; }
QPushButton#btnGhost, QPushButton#btnSecondary {
    background: #1e293b; color: #e2e8f0; border: 1px solid #334155;
}
QPushButton#btnGhost:hover, QPushButton#btnSecondary:hover { background: #334155; }
QPushButton#btnNav {
    background: transparent; color: #cbd5e1; text-align: left;
    padding: 10px 12px; border-radius: 8px; font-weight: 600; border: none;
}
QPushButton#btnNav:hover { background: #1e293b; }
QPushButton#btnNav[active="true"] {
    background: #1e293b; color: #f8fafc; font-weight: 700;
}
QPushButton#btnMicBig {
    background: #6366f1; color: #ffffff; border-radius: 28px;
    min-width: 96px; max-width: 120px; min-height: 56px; max-height: 56px;
    font-size: 14px; font-weight: 700;
}
QPushButton#btnDanger { background: #ef4444; color: #ffffff; }
QPushButton#btnPrimary {
    background: #6366f1; color: #ffffff; padding: 10px 18px; font-weight: 700;
}

#sideBar { background: #111827; border-right: 1px solid #1e293b; }
#sideBrand { font-size: 15px; font-weight: 700; color: #f8fafc; }
#topBar { background: #111827; border-bottom: 1px solid #1e293b; }
#pageTitle { font-size: 22px; font-weight: 700; color: #f8fafc; }
#pageSubtitle { color: #94a3b8; font-size: 12px; }
#statusChip {
    background: #064e3b; color: #6ee7b7; border: 1px solid #065f46;
    border-radius: 999px; padding: 5px 10px; font-weight: 600; font-size: 11px;
}
#metricCard, #panelCard, #workflowCard, #voicePanel {
    background: #1e293b; border: 1px solid #334155; border-radius: 12px;
}
#metricCard { min-height: 100px; }
#workflowCard { min-height: 140px; }
#metricLabel { color: #94a3b8; font-size: 11px; font-weight: 600; }
#metricValue { color: #f8fafc; font-size: 24px; font-weight: 700; min-height: 28px; }
#metricHint { color: #64748b; font-size: 11px; }

QTableWidget {
    background: #0f172a; border: 1px solid #334155; border-radius: 8px;
    gridline-color: #1e293b; color: #e2e8f0; outline: 0;
}
QHeaderView::section {
    background: #1e293b; border: none; border-bottom: 1px solid #334155;
    padding: 8px 10px; font-weight: 600; color: #94a3b8;
}
QListWidget {
    background: #0f172a; border: 1px solid #334155; border-radius: 8px; color: #e2e8f0;
}
QSlider::groove:horizontal { height: 6px; background: #334155; border-radius: 3px; }
QSlider::handle:horizontal {
    width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; background: #38bdf8;
}
QCheckBox { spacing: 8px; color: #e2e8f0; }
QScrollArea { border: none; background: transparent; }
#footerLabel { color: #64748b; font-size: 11px; }
#daiOverlay {
    background: #020617;
    color: #e2e8f0;
    border-radius: 14px;
    border: 1px solid #334155;
}
#daiTitle { font-size: 15px; font-weight: 800; color: #f8fafc; }
#daiLine { font-size: 12px; font-weight: 600; color: #e2e8f0; }
#daiHint { font-size: 10px; color: #94a3b8; }
#daiHide { background: #1e293b; color: #e2e8f0; border: none; border-radius: 6px; }
#daiChip {
    background: #312e81; color: #e0e7ff; border: 1px solid #6366f1;
    border-radius: 8px; padding: 4px 8px; font-size: 11px; font-weight: 600;
    text-align: left;
}
#daiRetry {
    background: #1e293b; color: #e2e8f0; border: 1px solid #475569;
    border-radius: 8px; font-size: 11px;
}
#daiStop {
    background: #7f1d1d; color: #fecaca; border: 1px solid #ef4444;
    border-radius: 6px; padding: 0 8px; font-size: 10px; font-weight: 800;
}
#logFrame { border: 1px solid #334155; border-radius: 8px; background: #020617; }
#sectionTitle { font-size: 14px; font-weight: 700; color: #f8fafc; }
"""

APP_STYLE = LIGHT_STYLE


def get_app_style(theme: str = "light") -> str:
    return DARK_STYLE if str(theme).lower() in ("dark", "night") else LIGHT_STYLE
