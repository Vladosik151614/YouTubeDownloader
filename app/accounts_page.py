"""
accounts_page.py - account access controls for supported services.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.auth_manager import (
    SERVICE_HOSTS,
    clear_service_auth,
    cookie_status,
    export_service_cookies,
    open_login_browser,
)


SERVICE_LABELS = {
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "twitch": "Twitch",
    "soundcloud": "SoundCloud",
}

SERVICE_BADGES = {
    "youtube": ("▶", "#ff3b3b"),
    "tiktok": ("♪", "#22d3ee"),
    "twitch": ("T", "#9146ff"),
    "soundcloud": ("S", "#ff7a1a"),
}


class AccountsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._status_labels: dict[str, QLabel] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(12)

        title = QLabel("Аккаунты и доступ")
        title.setObjectName("section_title")
        title.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        layout.addWidget(title)

        hint = QLabel(
            "Публичные материалы скачиваются без входа. Аккаунт нужен только для контента, который сам сервис ограничивает."
        )
        hint.setObjectName("subtle")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        for service in SERVICE_LABELS:
            layout.addWidget(self._service_card(service))
        layout.addStretch()

    def _service_card(self, service: str) -> QWidget:
        card = QFrame()
        card.setObjectName("tool_band")
        grid = QGridLayout(card)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        badge_text, badge_color = SERVICE_BADGES[service]
        badge = QLabel(badge_text)
        badge.setFixedSize(34, 34)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: {badge_color}; color: white; border-radius: 17px; font-weight: 800; font-size: 16px;"
        )
        grid.addWidget(badge, 0, 0, 2, 1)

        name = QLabel(SERVICE_LABELS[service])
        name.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        grid.addWidget(name, 0, 1)

        hosts = QLabel(", ".join(SERVICE_HOSTS[service]))
        hosts.setObjectName("subtle")
        grid.addWidget(hosts, 1, 1)

        status = QLabel("Проверка...")
        status.setObjectName("subtle")
        self._status_labels[service] = status
        grid.addWidget(status, 0, 2, 2, 1)

        buttons = QHBoxLayout()
        login_btn = QPushButton("Войти")
        login_btn.clicked.connect(lambda _, s=service: self._open_login(s))
        buttons.addWidget(login_btn)

        check_btn = QPushButton("Проверить")
        check_btn.clicked.connect(lambda _, s=service: self._show_status(s))
        buttons.addWidget(check_btn)

        logout_btn = QPushButton("Выйти")
        logout_btn.clicked.connect(lambda _, s=service: self._clear(s))
        buttons.addWidget(logout_btn)
        grid.addLayout(buttons, 0, 3, 2, 1)
        grid.setColumnStretch(2, 1)
        return card

    def refresh(self):
        for service in SERVICE_LABELS:
            ok, count, _ = cookie_status(service)
            text = f"Активно, данные доступа: {count}" if ok else "Не подключено"
            self._status_labels[service].setText(text)

    def _open_login(self, service: str):
        try:
            open_login_browser(service)
            QMessageBox.information(
                self,
                "Вход",
                "Открылось отдельное окно Chrome.\n\n"
                "Войдите в аккаунт выбранного сервиса. После этого приложение будет обновлять доступ автоматически, когда это потребуется.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Вход", str(exc))

    def _show_status(self, service: str):
        if not cookie_status(service)[0]:
            export_service_cookies(service)
            self.refresh()
        ok, count, path = cookie_status(service)
        state = "подключён" if ok else "не подключён"
        QMessageBox.information(
            self,
            "Статус аккаунта",
            f"{SERVICE_LABELS[service]}: {state}\nДанные доступа: {count}",
        )

    def _clear(self, service: str):
        reply = QMessageBox.question(
            self,
            "Выйти",
            f"Удалить локальный профиль и данные доступа для {SERVICE_LABELS[service]}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            clear_service_auth(service)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Выйти", str(exc))
