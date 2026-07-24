"""
support_dialog.py - user-safe error dialog with optional support report.
"""
import webbrowser

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox, QPushButton

from app.error_reporter import build_support_report, github_issue_url


class SupportErrorDialog(QDialog):
    def __init__(self, parent, url: str, path: str, error: str, settings: dict):
        super().__init__(parent)
        self.setWindowTitle("Ошибка загрузки")
        self.setMinimumSize(560, 420)
        self._report = build_support_report(
            service="auto",
            url=url,
            error_category="download",
            user_message=error,
            settings=settings,
            raw_error=error,
            developer_mode=bool(settings.get("developer_mode", False)),
        )

        layout = QVBoxLayout(self)
        message = QLabel("Не удалось завершить загрузку. Можно повторить позже, проверить вход в аккаунт или отправить отчет разработчику.")
        message.setWordWrap(True)
        layout.addWidget(message)

        summary = QTextEdit()
        summary.setReadOnly(True)
        summary.setPlainText(f"Ссылка:\n{url or '-'}\n\nПуть:\n{path or '-'}\n\nОшибка:\n{error or '-'}")
        layout.addWidget(summary, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        copy_btn = QPushButton("Скопировать отчет")
        issue_btn = QPushButton("Открыть GitHub")
        if not github_issue_url(self._report):
            issue_btn.setEnabled(False)
            issue_btn.setToolTip("Ссылка на GitHub не настроена")
        buttons.addButton(copy_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(issue_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        copy_btn.clicked.connect(self._copy_report)
        issue_btn.clicked.connect(self._open_issue)
        layout.addWidget(buttons)

    def _copy_report(self):
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self._report)

    def _open_issue(self):
        url = github_issue_url(self._report, "Download error report")
        if url:
            webbrowser.open(url)
