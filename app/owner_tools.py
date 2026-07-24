"""
owner_tools.py - local-only maintainer publishing controls.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.settings_manager import APP_DATA_DIR


OWNER_LOGIN = "Vladosik151614"
REPO_FULL_NAME = "Vladosik151614/YouTubeDownloader"
LOCAL_OWNER_FLAG = Path(APP_DATA_DIR) / "owner_tools.enabled"
ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str], *, timeout: int = 120) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        return result.returncode, output
    except Exception as exc:
        return 1, str(exc)


def _gh_login() -> str:
    code, output = _run(["gh", "api", "user", "-q", ".login"], timeout=30)
    return output.strip() if code == 0 else ""


def owner_tools_available() -> bool:
    return LOCAL_OWNER_FLAG.exists() and _gh_login().lower() == OWNER_LOGIN.lower()


class GitHubPublishWorker(QThread):
    log = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, message: str, parent=None):
        super().__init__(parent)
        self.message = message.strip() or "Prepare release 0.1.0"

    def _step(self, command: list[str], label: str, *, timeout: int = 120) -> bool:
        self.log.emit(f"\n> {label}")
        self.log.emit("  " + " ".join(command))
        code, output = _run(command, timeout=timeout)
        if output:
            self.log.emit(output[-5000:])
        if code != 0:
            self.finished.emit(False, f"Остановлено на шаге: {label}")
            return False
        return True

    def run(self):
        login = _gh_login()
        if login.lower() != OWNER_LOGIN.lower():
            self.finished.emit(False, "GitHub CLI авторизован не под аккаунтом владельца.")
            return
        if not LOCAL_OWNER_FLAG.exists():
            self.finished.emit(False, "Локальный флаг владельца не найден.")
            return

        checks = [
            ([sys.executable, "tools\\privacy_check.py"], "Проверка приватности"),
            ([sys.executable, "tools\\quality_check.py"], "Проверка качества"),
        ]
        for command, label in checks:
            if not self._step(command, label, timeout=180):
                return

        if not (ROOT / ".git").exists():
            if not self._step(["git", "init"], "Инициализация git"):
                return
            self._step(["git", "branch", "-M", "main"], "Основная ветка")

        code, remotes = _run(["git", "remote"])
        if code != 0:
            self.finished.emit(False, "Не удалось прочитать git remote.")
            return
        if "origin" not in remotes.split():
            url = f"https://github.com/{REPO_FULL_NAME}.git"
            if not self._step(["git", "remote", "add", "origin", url], "Подключение origin"):
                return

        if not self._step(["git", "add", "-A"], "Подготовка файлов"):
            return
        code, status = _run(["git", "status", "--porcelain"])
        if code != 0:
            self.finished.emit(False, "Не удалось проверить git status.")
            return
        if status.strip():
            if not self._step(["git", "commit", "-m", self.message], "Коммит"):
                return
        else:
            self.log.emit("\nНет новых изменений для коммита.")

        if not self._step(["git", "push", "-u", "origin", "main"], "Push main", timeout=240):
            return
        self.finished.emit(True, "Код отправлен на GitHub.")


class OwnerToolsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(12)

        title = QLabel("Owner Tools")
        title.setObjectName("section_title")
        layout.addWidget(title)

        group = QGroupBox("GitHub release workflow")
        group_layout = QVBoxLayout(group)
        info = QLabel(
            "Эта панель доступна только на компьютере владельца. "
            "Перед push автоматически выполняются проверки приватности и качества."
        )
        info.setWordWrap(True)
        group_layout.addWidget(info)

        row = QHBoxLayout()
        self.check_btn = QPushButton("Проверить безопасность")
        self.check_btn.clicked.connect(self._run_checks)
        self.push_btn = QPushButton("Push на GitHub")
        self.push_btn.setObjectName("primary_btn")
        self.push_btn.clicked.connect(self._push)
        row.addWidget(self.check_btn)
        row.addWidget(self.push_btn)
        row.addStretch()
        group_layout.addLayout(row)
        layout.addWidget(group)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Здесь появится результат проверок и push.")
        layout.addWidget(self.log_box, 1)

    def _append(self, text: str):
        self.log_box.appendPlainText(text)

    def _run_checks(self):
        self._start_worker("Owner safety check")

    def _push(self):
        reply = QMessageBox.question(
            self,
            "Push на GitHub",
            "Запустить проверки, создать коммит при наличии изменений и отправить main на GitHub?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._start_worker("Release 0.1.0")

    def _start_worker(self, message: str):
        self.check_btn.setEnabled(False)
        self.push_btn.setEnabled(False)
        self.log_box.clear()
        self._worker = GitHubPublishWorker(message, self)
        self._worker.log.connect(self._append)
        self._worker.finished.connect(self._done)
        self._worker.start()

    def _done(self, ok: bool, message: str):
        self.check_btn.setEnabled(True)
        self.push_btn.setEnabled(True)
        self._append("\n" + message)
        (QMessageBox.information if ok else QMessageBox.warning)(self, "Owner Tools", message)
