"""
tray_controller.py - Windows tray integration and user notifications.
"""
import os

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from app.binary_manager import get_resource_path


class TrayController:
    def __init__(self, window):
        self.window = window
        self.icon = None
        self.allow_close = False
        self._setup()

    def _setup(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon_path = get_resource_path("youtube.ico")
        icon = QIcon(icon_path) if os.path.isfile(icon_path) else self.window.windowIcon()
        self.icon = QSystemTrayIcon(icon, self.window)
        menu = QMenu()
        show_action = QAction("Открыть", self.window)
        quit_action = QAction("Выход", self.window)
        show_action.triggered.connect(self.restore)
        quit_action.triggered.connect(self.quit)
        menu.addAction(show_action)
        menu.addAction(quit_action)
        self.icon.setContextMenu(menu)
        self.icon.activated.connect(self._activated)
        self.icon.show()

    def _activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.restore()

    def restore(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def quit(self):
        self.allow_close = True
        QApplication.quit()

    def notify(self, title: str, message: str):
        if not self.window.settings.get("show_in_notification_center", True):
            return
        if self.icon and self.icon.isVisible():
            self.icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 5000)
        if self.window.settings.get("play_notification_sound", False):
            QApplication.beep()

    def handle_close_event(self, event):
        if self.allow_close:
            event.accept()
            return
        active = bool(self.window._active_download_ids)
        if active and self.window.settings.get("confirm_exit_with_active_downloads", True):
            reply = QMessageBox.question(
                self.window,
                "Активные загрузки",
                "Есть незавершенные загрузки. Закрыть приложение?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        if self.window.settings.get("background_on_close", False) and self.icon:
            event.ignore()
            self.window.hide()
            self.notify("YouTube Downloader", "Приложение продолжает работать в фоне.")
            return
        event.accept()
