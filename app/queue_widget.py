"""
queue_widget.py — виджет очереди загрузок с поддержкой отображения размера видео/плейлиста
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QProgressBar, QLabel, QPushButton, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor


class QueueItemWidget(QWidget):
    """Виджет прогресс-бара для ячейки таблицы."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(True)
        self.bar.setFixedHeight(18)
        layout.addWidget(self.bar)

    def set_value(self, v: float):
        self.bar.setValue(int(v))
        self.bar.setFormat(f"{v:.1f}%")


STATUS_COLORS = {
    "Ожидание":               "#888888",
    "Получение информации...": "#6ab0f5",
    "Загрузка...":            "#6ab0f5",
    "Обработка...":           "#f5c542",
    "Конвертация...":          "#f5a742",
    "Пауза":                   "#f5c542",
    "Завершено":              "#4caf50",
    "Ошибка":                 "#f44336",
    "Отменено":               "#999999",
}

COLUMNS = ["#", "Название", "Размер", "Статус", "Прогресс", "Скорость", "ETA", "Действия"]


class QueueWidget(QWidget):
    cancel_requested = Signal(str)   # item_id
    pause_requested = Signal(str)    # item_id
    resume_requested = Signal(str)   # item_id
    open_requested = Signal(str)     # item_id
    retry_requested = Signal(str)    # item_id
    details_requested = Signal(str)  # item_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = {}   # item_id -> row index
        self._paths = {}   # item_id -> downloaded file/folder
        self._errors = {}  # item_id -> last error text
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 118)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 34)
        self.table.setColumnWidth(2, 72)   # Размер
        self.table.setColumnWidth(3, 108)  # Статус
        self.table.setColumnWidth(5, 78)   # Скорость
        self.table.setColumnWidth(6, 52)   # ETA
        self.table.setColumnWidth(7, 118)  # Действия

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.table)

    def add_item(self, item_id: str, url: str) -> int:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._items[item_id] = row

        num_item = QTableWidgetItem(str(row + 1))
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        num_item.setData(Qt.ItemDataRole.UserRole, item_id)
        self.table.setItem(row, 0, num_item)

        title_item = QTableWidgetItem(url[:60] + ("..." if len(url) > 60 else ""))
        self.table.setItem(row, 1, title_item)

        size_item = QTableWidgetItem("—")
        size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 2, size_item)

        status_item = QTableWidgetItem("Ожидание")
        status_item.setForeground(QColor("#888"))
        self.table.setItem(row, 3, status_item)

        progress_widget = QueueItemWidget()
        self.table.setCellWidget(row, 4, progress_widget)

        self.table.setItem(row, 5, QTableWidgetItem("—"))
        self.table.setItem(row, 6, QTableWidgetItem("—"))

        pause_btn = QPushButton("⏸")
        pause_btn.setFixedSize(28, 22)
        pause_btn.setToolTip("Пауза")
        pause_btn.clicked.connect(lambda _, iid=item_id: self.pause_requested.emit(iid))

        cancel_btn = QPushButton("✕")
        cancel_btn.setFixedSize(28, 22)
        cancel_btn.setToolTip("Отменить")
        cancel_btn.clicked.connect(lambda _, iid=item_id: self.cancel_requested.emit(iid))
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(4, 2, 4, 2)
        btn_layout.setSpacing(4)
        btn_layout.addWidget(pause_btn)
        btn_layout.addWidget(cancel_btn)
        self.table.setCellWidget(row, 7, btn_widget)

        self.table.setRowHeight(row, 34)
        return row

    def update_info(self, item_id: str, title: str, size_str: str):
        row = self._items.get(item_id)
        if row is None:
            return
        title_item = self.table.item(row, 1)
        if title_item:
            short = title[:60] + ("..." if len(title) > 60 else "")
            title_item.setText(short)
            title_item.setToolTip(title)

        size_item = self.table.item(row, 2)
        if size_item:
            size_item.setText(size_str)

    def update_status(self, item_id: str, status: str):
        row = self._items.get(item_id)
        if row is None:
            return
        item = self.table.item(row, 3)
        if item:
            item.setText(status)
            color = STATUS_COLORS.get(status, "#cccccc")
            item.setForeground(QColor(color))
        if status == "Пауза":
            self.set_paused(item_id)

    def set_paused(self, item_id: str):
        row = self._items.get(item_id)
        if row is None:
            return
        self.table.removeCellWidget(row, 7)
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(4, 2, 4, 2)
        btn_layout.setSpacing(4)
        resume_btn = QPushButton("▶")
        resume_btn.setFixedSize(28, 22)
        resume_btn.setToolTip("Продолжить")
        resume_btn.clicked.connect(lambda _, iid=item_id: self.resume_requested.emit(iid))
        cancel_btn = QPushButton("✕")
        cancel_btn.setFixedSize(28, 22)
        cancel_btn.setToolTip("Удалить из очереди")
        cancel_btn.clicked.connect(lambda _, iid=item_id: self.cancel_requested.emit(iid))
        btn_layout.addWidget(resume_btn)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        self.table.setCellWidget(row, 7, btn_widget)

    def update_progress(self, item_id: str, percent: float, speed: str, eta: str):
        row = self._items.get(item_id)
        if row is None:
            return
        pw = self.table.cellWidget(row, 4)
        if pw:
            pw.set_value(percent)
        speed_item = self.table.item(row, 5)
        if speed_item:
            speed_item.setText(speed)
        eta_item = self.table.item(row, 6)
        if eta_item:
            eta_item.setText(eta)

    def set_finished(self, item_id: str, success: bool):
        row = self._items.get(item_id)
        if row is None:
            return
        pw = self.table.cellWidget(row, 4)
        if pw and success:
            pw.set_value(100)
        self.table.removeCellWidget(row, 7)
        self.table.takeItem(row, 7)
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(4, 2, 4, 2)
        btn_layout.setSpacing(4)

        if success:
            open_btn = QPushButton("📂")
            open_btn.setFixedSize(30, 22)
            open_btn.setToolTip("Открыть папку")
            open_btn.clicked.connect(lambda _, iid=item_id: self.open_requested.emit(iid))
            btn_layout.addWidget(open_btn)
            mark = QLabel("✓")
            mark.setStyleSheet("color: #4caf50; font-weight: bold;")
            mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn_layout.addWidget(mark)
        else:
            retry_btn = QPushButton("↻")
            retry_btn.setFixedSize(30, 22)
            retry_btn.setToolTip("Повторить")
            retry_btn.clicked.connect(lambda _, iid=item_id: self.retry_requested.emit(iid))
            details_btn = QPushButton("!")
            details_btn.setFixedSize(30, 22)
            details_btn.setToolTip("Показать ошибку")
            details_btn.clicked.connect(lambda _, iid=item_id: self.details_requested.emit(iid))
            btn_layout.addWidget(retry_btn)
            btn_layout.addWidget(details_btn)

        btn_layout.addStretch()
        self.table.setCellWidget(row, 7, btn_widget)

    def set_result(self, item_id: str, filepath: str = "", error_msg: str = ""):
        if filepath:
            self._paths[item_id] = filepath
        if error_msg:
            self._errors[item_id] = error_msg

    def result_path(self, item_id: str) -> str:
        return self._paths.get(item_id, "")

    def error_text(self, item_id: str) -> str:
        return self._errors.get(item_id, "")

    def title_text(self, item_id: str) -> str:
        row = self._items.get(item_id)
        if row is None:
            return ""
        item = self.table.item(row, 1)
        return item.toolTip() or item.text() if item else ""

    def clear_finished(self):
        rows_to_remove = []
        for item_id, row in self._items.items():
            status_item = self.table.item(row, 3)
            if status_item and status_item.text() in ("Завершено", "Ошибка", "Отменено"):
                rows_to_remove.append((item_id, row))
        for item_id, _ in sorted(rows_to_remove, key=lambda x: x[1], reverse=True):
            row = self._items.pop(item_id)
            self._paths.pop(item_id, None)
            self._errors.pop(item_id, None)
            self.table.removeRow(row)
        self._items.clear()
        for row in range(self.table.rowCount()):
            num_item = self.table.item(row, 0)
            if not num_item:
                continue
            item_id = num_item.data(Qt.ItemDataRole.UserRole)
            if item_id:
                num_item.setText(str(row + 1))
                self._items[item_id] = row

    def remove_item(self, item_id: str):
        row = self._items.pop(item_id, None)
        if row is None:
            return
        self._paths.pop(item_id, None)
        self._errors.pop(item_id, None)
        self.table.removeRow(row)
        self._items.clear()
        for index in range(self.table.rowCount()):
            num_item = self.table.item(index, 0)
            if not num_item:
                continue
            current_id = num_item.data(Qt.ItemDataRole.UserRole)
            if current_id:
                num_item.setText(str(index + 1))
                self._items[current_id] = index
