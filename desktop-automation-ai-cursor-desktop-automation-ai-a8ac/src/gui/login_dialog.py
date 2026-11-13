"""Login / Landing screen matching Automate AI wireframe."""

from __future__ import annotations

from typing import Any, Dict, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QMessageBox,
    QFrame,
    QScrollArea,
    QApplication,
)

from src.db.repositories import UserRepository, UserConfRepository
from src.gui.window_fit import apply_standard_window_chrome, fit_to_screen


class LoginDialog(QDialog):
    def __init__(
        self,
        users: UserRepository,
        conf_repo: Optional[UserConfRepository] = None,
        app_name: str = "Automate AI",
        product_name: str = "AI Desktop Automation",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.users = users
        self.conf_repo = conf_repo
        self.user: Optional[Dict[str, Any]] = None
        self.setWindowTitle(f"Login — {app_name}")
        apply_standard_window_chrome(self)
        fit_to_screen(self, preferred_w=920, preferred_h=580, min_w=720, min_h=480, margin=40)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        host = QWidget()
        root = QHBoxLayout(host)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left brand panel
        brand = QWidget()
        brand.setObjectName("brandPanel")
        brand.setMinimumWidth(280)
        bl = QVBoxLayout(brand)
        bl.setContentsMargins(28, 28, 28, 24)
        bl.setSpacing(10)

        logo_row = QHBoxLayout()
        logo_mark = QLabel("⌁")
        logo_mark.setStyleSheet(
            "background:#111827;color:white;border-radius:8px;padding:6px 10px;font-size:16px;font-weight:800;"
        )
        logo_text = QLabel(app_name)
        logo_text.setObjectName("brandLogo")
        logo_row.addWidget(logo_mark)
        logo_row.addWidget(logo_text)
        logo_row.addStretch()

        eyebrow = QLabel("AI-POWERED DESKTOP AUTOMATION")
        eyebrow.setObjectName("brandEyebrow")
        h1 = QLabel("Control your <u>desktop</u>")
        h1.setObjectName("brandHeadline")
        h1.setTextFormat(Qt.RichText)
        h2 = QLabel("Your desktop. Your commands. Automated.")
        h2.setObjectName("brandHeadlineAccent")
        body_txt = QLabel(
            "Use natural language to open applications, files, folders, and automate desktop tasks."
        )
        body_txt.setObjectName("brandBody")
        body_txt.setWordWrap(True)

        feature = QFrame()
        feature.setObjectName("featureCard")
        fl = QVBoxLayout(feature)
        ft = QLabel("AI desktop agent")
        ft.setObjectName("featureCardTitle")
        fb = QLabel(
            "Understands a goal, builds an action plan, finds on-screen elements, "
            "acts safely, and verifies the result."
        )
        fb.setObjectName("featureCardBody")
        fb.setWordWrap(True)
        fl.addWidget(ft)
        fl.addWidget(fb)

        feats = QLabel("🎙 Voice commands    🖥 Computer Vision    ⚡ Task Automation    🛡 Secure Execution")
        feats.setObjectName("brandBody")

        bl.addLayout(logo_row)
        bl.addSpacing(12)
        bl.addWidget(eyebrow)
        bl.addWidget(h1)
        bl.addWidget(h2)
        bl.addWidget(body_txt)
        bl.addSpacing(6)
        bl.addWidget(feature)
        bl.addStretch()
        bl.addWidget(feats)

        # Right form panel
        form = QWidget()
        form.setObjectName("formPanel")
        fr = QVBoxLayout(form)
        fr.setContentsMargins(28, 32, 28, 24)
        fr.setSpacing(10)

        title = QLabel(product_name)
        title.setObjectName("loginTitle")
        subtitle = QLabel("Log in to your workspace to continue.")
        subtitle.setObjectName("loginSubtitle")

        email_lbl = QLabel("Email / Username")
        self.email = QLineEdit()
        self.email.setPlaceholderText("name@company.com")

        pass_row = QHBoxLayout()
        pass_lbl = QLabel("Password")
        forgot = QLabel('<a href="#">Forgot password?</a>')
        forgot.setOpenExternalLinks(False)
        pass_row.addWidget(pass_lbl)
        pass_row.addStretch()
        pass_row.addWidget(forgot)

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Create or enter your password")
        self.password.returnPressed.connect(self._try_login)

        self.keep = QCheckBox("Keep me signed in for 30 days")
        self.btn_login = QPushButton("Sign In  →")
        self.btn_login.clicked.connect(self._try_login)

        divider = QLabel("NEW HERE? CREATE YOUR ACCOUNT")
        divider.setAlignment(Qt.AlignCenter)
        divider.setObjectName("loginSubtitle")
        self.btn_signup = QPushButton("Sign Up Now")
        self.btn_signup.setObjectName("btnSecondary")
        self.btn_signup.clicked.connect(self._signup)

        links = QLabel("Privacy Policy   ·   Terms of Service   ·   Help Center")
        links.setObjectName("footerLabel")
        links.setAlignment(Qt.AlignCenter)

        fr.addWidget(title)
        fr.addWidget(subtitle)
        fr.addSpacing(10)
        fr.addWidget(email_lbl)
        fr.addWidget(self.email)
        fr.addLayout(pass_row)
        fr.addWidget(self.password)
        fr.addWidget(self.keep)
        fr.addSpacing(6)
        fr.addWidget(self.btn_login)
        fr.addSpacing(8)
        fr.addWidget(divider)
        fr.addWidget(self.btn_signup)
        fr.addStretch()
        fr.addWidget(links)

        root.addWidget(brand, 5)
        root.addWidget(form, 4)
        scroll.setWidget(host)
        outer.addWidget(scroll)

        from PyQt5.QtCore import QTimer

        QTimer.singleShot(
            0, lambda: fit_to_screen(self, 920, 580, min_w=720, min_h=480, margin=40)
        )
    def _try_login(self) -> None:
        user = self.users.authenticate(self.email.text().strip(), self.password.text())
        if not user:
            QMessageBox.warning(self, "Sign in failed", "Invalid email/username or password.")
            return
        self.user = user
        self.accept()

    def _signup(self) -> None:
        email = self.email.text().strip()
        password = self.password.text()
        if not email or not password:
            QMessageBox.information(
                self,
                "Sign up",
                "Enter your email/username and a password, then click Sign Up Now.",
            )
            return
        if len(password) < 6:
            QMessageBox.warning(self, "Sign up", "Password must be at least 6 characters.")
            return
        username = email.split("@")[0] if "@" in email else email
        try:
            uid = self.users.create(
                username=username,
                email=email if "@" in email else f"{email}@automate.ai",
                password=password,
            )
            # Seed personal settings + starter workflows (live automation by default)
            from src.config import load_config
            from src.db.database import get_database

            db = get_database()
            db.seed_user_workspace(uid, load_config())
            user = self.users.get_by_id(uid)
            if not user:
                raise RuntimeError("Account created but could not load profile.")
            self.user = user
            QMessageBox.information(
                self,
                "Welcome",
                f"Account ready for {username}. You’re signed in.",
            )
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, "Sign up failed", str(exc))
