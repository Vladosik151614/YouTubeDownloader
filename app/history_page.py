"""
history_page.py - download history view.
"""
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.history_store import clear_history, load_history
from app.logger import logger


COLUMNS = ["Дата", "Источник", "Название", "Статус", "Действия"]


class HistoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._records: list[dict] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(11)

        header = QHBoxLayout()
        title = QLabel("История загрузок")
        title.setObjectName("section_title")
        title.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)

        clear_btn = QPushButton("Очистить")
        clear_btn.clicked.connect(self._clear)
        header.addWidget(clear_btn)
        layout.addLayout(header)

        hint = QLabel("Локальная история хранится в AppData и не попадает в GitHub.")
        hint.setObjectName("subtle")
        layout.addWidget(hint)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(0, 142)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(3, 90)
        self.table.setColumnWidth(4, 116)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

    def refresh(self):
        self._records = load_history()
        self.table.setRowCount(0)
        for row, record in enumerate(self._records):
            self.table.insertRow(row)
            self._set_item(row, 0, record.get("created_at", ""))
            self._set_item(row, 1, record.get("source", ""))
            title = record.get("title") or record.get("url") or ""
            self._set_item(row, 2, title, title)
            status = "Готово" if record.get("status") == "success" else "Ошибка"
            status_item = self._set_item(row, 3, status)
            status_item.setForeground(QColor("#4caf50" if record.get("status") == "success" else "#f44336"))
            self._add_actions(row, record)
            self.table.setRowHeight(row, 34)

    def _set_item(self, row: int, col: int, value: str, tooltip: str = "") -> QTableWidgetItem:
        item = QTableWidgetItem(value)
        item.setToolTip(tooltip or value)
        if col in (0, 1, 3):
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, col, item)
        return item

    def _add_actions(self, row: int, record: dict):
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        open_btn = QPushButton("📂")
        open_btn.setFixedSize(30, 24)
        open_btn.setToolTip("Открыть папку")
        open_btn.clicked.connect(lambda _, path=record.get("path", ""): self._open_path(path))
        layout.addWidget(open_btn)

        details_btn = QPushButton("!")
        details_btn.setFixedSize(28, 24)
        details_btn.setToolTip("Показать детали")
        details_btn.clicked.connect(lambda _, rec=record: self._show_details(rec))
        layout.addWidget(details_btn)
        layout.addStretch()
        self.table.setCellWidget(row, 4, box)

    def _open_path(self, path: str):
        if not path:
            QMessageBox.information(self, "История", "Путь к файлу не сохранён.")
            return
        target = path if os.path.isdir(path) else os.path.dirname(path)
        if not target or not os.path.exists(target):
            QMessageBox.warning(self, "История", "Папка больше не найдена.")
            return
        try:
            os.startfile(os.path.abspath(target))
        except Exception as exc:
            logger.error(f"Cannot open history path: {exc}")
            QMessageBox.critical(self, "История", f"Не удалось открыть папку:\n{exc}")

    def _show_details(self, record: dict):
        QMessageBox.information(
            self,
            "Детали истории",
            "Название:\n{title}\n\nСсылка:\n{url}\n\nПуть:\n{path}\n\nОшибка:\n{error}".format(
                title=record.get("title", ""),
                url=record.get("url", ""),
                path=record.get("path", ""),
                error=record.get("error", "") or "—",
            ),
        )

    def _clear(self):
        clear_history()
        self.refresh()
