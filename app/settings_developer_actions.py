"""
settings_developer_actions.py - functional developer settings actions.
"""
from __future__ import annotations

import os
import subprocess

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from app.error_reporter import build_support_report
from app.logger import LOGS_DIR
from app.process_utils import hidden_subprocess_kwargs
from app.settings_manager import APP_DATA_DIR


def _open_folder_path(self, path: str):
    os.makedirs(path, exist_ok=True)
    if os.name == "nt":
        os.startfile(path)
    else:
        subprocess.Popen(["xdg-open", path], **hidden_subprocess_kwargs())


def _developer_open_logs(self):
    self._open_folder_path(LOGS_DIR)


def _developer_open_app_data(self):
    self._open_folder_path(APP_DATA_DIR)


def _developer_open_download_folder(self):
    folder = self.folder_edit.text() or self.settings.get("download_folder", os.path.expanduser("~"))
    self._open_folder_path(folder)


def _developer_open_format_tab(self):
    self.tabs.setCurrentIndex(1)


def _developer_open_connection_tab(self):
    self.tabs.setCurrentIndex(3)


def _developer_open_access_tab(self):
    self.tabs.setCurrentIndex(5)


def _developer_refresh_encoders(self):
    self._load_codecs()
    self._update_encoder_status()
    QMessageBox.information(self, "Разработчик", f"Доступно: {self.encoder_status_label.text()}")


def _developer_check_write_access(self):
    folder = self.folder_edit.text() or self.settings.get("download_folder", os.path.expanduser("~"))
    try:
        os.makedirs(folder, exist_ok=True)
        probe = os.path.join(folder, ".ytd_write_test.tmp")
        with open(probe, "w", encoding="utf-8") as file:
            file.write("ok")
        os.remove(probe)
    except Exception as exc:
        QMessageBox.warning(self, "Права записи", f"Нет доступа к папке:\n{exc}")
        return
    QMessageBox.information(self, "Права записи", "Папка доступна для записи.")


def _developer_latest_log_text(self) -> str:
    try:
        files = sorted(
            (os.path.join(LOGS_DIR, name) for name in os.listdir(LOGS_DIR) if name.endswith(".log")),
            key=os.path.getmtime,
            reverse=True,
        )
        if not files:
            return "Логи пока не созданы."
        with open(files[0], "r", encoding="utf-8", errors="replace") as file:
            return file.read()[-5000:]
    except Exception as exc:
        return f"Не удалось прочитать лог: {exc}"


def _developer_support_report(self) -> str:
    return build_support_report(
        service="diagnostics",
        url="",
        error_category="manual_report",
        user_message="Manual support report from Developer settings.",
        settings=self.settings,
        raw_error=self._developer_latest_log_text(),
        developer_mode=True,
    )


def _developer_show_latest_log(self):
    QMessageBox.information(self, "Последний лог", self._developer_latest_log_text()[-3000:])


def _developer_show_support_report(self):
    QMessageBox.information(self, "Support-пакет", self._developer_support_report()[:3500])


def _developer_copy_support_report(self):
    QApplication.clipboard().setText(self._developer_support_report())
    QMessageBox.information(self, "Support-пакет", "Безопасный отчёт скопирован.")


def _developer_save_support_report(self):
    path, _ = QFileDialog.getSaveFileName(self, "Сохранить support TXT", "support-report.txt", "Text Files (*.txt)")
    if not path:
        return
    with open(path, "w", encoding="utf-8") as file:
        file.write(self._developer_support_report())
    QMessageBox.information(self, "Support-пакет", f"Отчёт сохранён:\n{path}")


def install_developer_actions(cls):
    for name, value in globals().items():
        if name.startswith("_developer_") or name == "_open_folder_path":
            setattr(cls, name, value)
