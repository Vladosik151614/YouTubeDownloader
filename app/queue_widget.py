"""
queue_widget.py — виджет очереди загрузок с поддержкой отображения размера видео/плейлиста
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QProgressBar, QLabel, QPushButton, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import QSize, Qt, Signal, QUrl
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from app.icon_button import ActionIconButton
from app.logger import logger


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
    "Проверено":              "#4caf50",
}

COLUMNS = ["#", "Название", "Размер", "Статус", "Прогресс", "Скорость", "ETA", "Действия"]
THUMBNAIL_SIZE = QSize(64, 36)


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
        self._playlist_entries = {}  # item_id -> list[dict]
        self._playlist_expanded = set()
        self._playlist_child_rows = {}  # (item_id, playlist_index) -> row
        self._thumb_requests = {}  # reply -> (item_id, playlist_index | None)
        self._thumb_cache = {}  # thumbnail url -> fixed-size pixmap
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
        self.table.setColumnWidth(7, 132)  # Действия

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setIconSize(THUMBNAIL_SIZE)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.table)
        self._thumb_manager = QNetworkAccessManager(self)
        self._thumb_manager.finished.connect(self._on_thumbnail_loaded)

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

        self.table.setCellWidget(row, 7, self._action_widget(item_id))

        self.table.setRowHeight(row, 46)
        return row

    def _action_widget(self, item_id: str, paused: bool = False) -> QWidget:
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(4, 2, 4, 2)
        btn_layout.setSpacing(4)
        if item_id in self._playlist_entries:
            action = "collapse" if item_id in self._playlist_expanded else "expand"
            tip = "Свернуть список видео" if action == "collapse" else "Показать список видео"
            expand_btn = ActionIconButton(action, tip)
            expand_btn.clicked.connect(lambda _, iid=item_id: self.toggle_playlist(iid))
            btn_layout.addWidget(expand_btn)
        if paused:
            resume_btn = ActionIconButton("resume", "Продолжить")
            resume_btn.clicked.connect(lambda _, iid=item_id: self.resume_requested.emit(iid))
            btn_layout.addWidget(resume_btn)
        else:
            pause_btn = ActionIconButton("pause", "Пауза")
            pause_btn.clicked.connect(lambda _, iid=item_id: self.pause_requested.emit(iid))
            btn_layout.addWidget(pause_btn)
        cancel_btn = ActionIconButton("cancel", "Отменить")
        cancel_btn.clicked.connect(lambda _, iid=item_id: self.cancel_requested.emit(iid))
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        return btn_widget

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

    def set_item_thumbnail(self, item_id: str, thumbnail: str):
        self._request_thumbnail(item_id, None, thumbnail)

    def set_playlist_items(self, item_id: str, entries: list[dict]):
        if not entries:
            return
        normalized = []
        for pos, entry in enumerate(entries, start=1):
            try:
                index = int(entry.get("index") or pos)
            except Exception:
                index = pos
            normalized.append({
                "index": index,
                "title": entry.get("title") or f"Видео {index}",
                "url": entry.get("url", ""),
                "thumbnail": entry.get("thumbnail", ""),
                "status": "Ожидание",
                "percent": 0.0,
            })
        self._playlist_entries[item_id] = normalized
        self._set_playlist_parent_text(item_id)
        self._load_playlist_thumbnail(item_id)
        row = self._items.get(item_id)
        if row is not None:
            self.table.setCellWidget(row, 7, self._action_widget(item_id))
        if item_id in self._playlist_expanded:
            self._remove_playlist_children(item_id)
            self._insert_playlist_children(item_id)

    def _set_playlist_parent_text(self, item_id: str):
        row = self._items.get(item_id)
        item = self.table.item(row, 1) if row is not None else None
        if not item:
            return
        count = len(self._playlist_entries.get(item_id, []))
        title = item.toolTip() or item.text()
        item.setText(f"{title[:46]}{'...' if len(title) > 46 else ''}  ·  {count} видео")
        item.setToolTip(f"{title}\nВидео в плейлисте: {count}")

    def _load_playlist_thumbnail(self, item_id: str):
        entries = self._playlist_entries.get(item_id, [])
        thumb = next((entry.get("thumbnail") for entry in entries if entry.get("thumbnail")), "")
        if not thumb:
            return
        self._request_thumbnail(item_id, None, thumb)

    def _request_thumbnail(self, item_id: str, playlist_index: int | None, thumbnail: str):
        if not thumbnail:
            return
        if thumbnail in self._thumb_cache:
            self._apply_thumbnail(item_id, playlist_index, self._thumb_cache[thumbnail])
            return
        request = QNetworkRequest(QUrl(thumbnail))
        request.setRawHeader(b"User-Agent", b"Mozilla/5.0 YouTubeDownloader/0.1")
        reply = self._thumb_manager.get(request)
        self._thumb_requests[reply] = (item_id, playlist_index, thumbnail)

    def _on_thumbnail_loaded(self, reply):
        target = self._thumb_requests.pop(reply, None)
        if not target:
            reply.deleteLater()
            return
        if reply.error():
            logger.warning(f"Thumbnail load failed: {reply.errorString()}")
            reply.deleteLater()
            return
        pixmap = QPixmap()
        pixmap.loadFromData(reply.readAll())
        reply.deleteLater()
        if pixmap.isNull():
            return
        item_id, playlist_index, thumbnail = target
        fixed = self._thumbnail_icon(pixmap)
        self._thumb_cache[thumbnail] = fixed
        self._apply_thumbnail(item_id, playlist_index, fixed)

    def _apply_thumbnail(self, item_id: str, playlist_index: int | None, pixmap: QPixmap):
        row = self._items.get(item_id) if playlist_index is None else self._playlist_child_rows.get((item_id, playlist_index))
        item = self.table.item(row, 1) if row is not None else None
        if item:
            item.setIcon(QIcon(pixmap))

    def _thumbnail_icon(self, pixmap: QPixmap) -> QPixmap:
        canvas = QPixmap(THUMBNAIL_SIZE)
        canvas.fill(Qt.GlobalColor.transparent)
        scaled = pixmap.scaled(
            THUMBNAIL_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter = QPainter(canvas)
        x = (THUMBNAIL_SIZE.width() - scaled.width()) // 2
        y = (THUMBNAIL_SIZE.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()
        return canvas

    def toggle_playlist(self, item_id: str):
        if item_id not in self._playlist_entries:
            return
        if item_id in self._playlist_expanded:
            self._playlist_expanded.remove(item_id)
            self._remove_playlist_children(item_id)
        else:
            self._playlist_expanded.add(item_id)
            self._insert_playlist_children(item_id)
        row = self._items.get(item_id)
        if row is not None:
            self.table.setCellWidget(row, 7, self._action_widget(item_id))

    def _insert_playlist_children(self, item_id: str):
        parent_row = self._items.get(item_id)
        if parent_row is None:
            return
        for offset, entry in enumerate(self._playlist_entries.get(item_id, []), start=1):
            row = parent_row + offset
            self.table.insertRow(row)
            child_id = f"{item_id}:{entry['index']}"
            num_item = QTableWidgetItem(str(entry["index"]))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            num_item.setData(Qt.ItemDataRole.UserRole, child_id)
            num_item.setData(Qt.ItemDataRole.UserRole + 1, item_id)
            self.table.setItem(row, 0, num_item)

            title = str(entry.get("title", ""))
            title_item = QTableWidgetItem(f"   {title[:64]}{'...' if len(title) > 64 else ''}")
            title_item.setToolTip(title)
            title_item.setForeground(QColor("#bdbdbd"))
            self.table.setItem(row, 1, title_item)
            self._request_thumbnail(item_id, entry["index"], entry.get("thumbnail", ""))
            self.table.setItem(row, 2, QTableWidgetItem("—"))
            status_item = QTableWidgetItem(entry.get("status", "Ожидание"))
            status_item.setForeground(QColor(STATUS_COLORS.get(entry.get("status", ""), "#888888")))
            self.table.setItem(row, 3, status_item)
            progress_widget = QueueItemWidget()
            progress_widget.set_value(float(entry.get("percent", 0.0)))
            self.table.setCellWidget(row, 4, progress_widget)
            self.table.setItem(row, 5, QTableWidgetItem("—"))
            self.table.setItem(row, 6, QTableWidgetItem("—"))
            self.table.setCellWidget(row, 7, QWidget())
            self.table.setRowHeight(row, 40)
        self._reindex_rows()
        self.table.viewport().update()

    def _remove_playlist_children(self, item_id: str):
        rows = [
            row for (parent_id, _), row in self._playlist_child_rows.items()
            if parent_id == item_id
        ]
        for row in sorted(rows, reverse=True):
            self.table.removeRow(row)
        self._reindex_rows()
        self.table.viewport().update()

    def _reindex_rows(self):
        self._items.clear()
        self._playlist_child_rows.clear()
        display_index = 1
        for row in range(self.table.rowCount()):
            num_item = self.table.item(row, 0)
            if not num_item:
                continue
            item_id = num_item.data(Qt.ItemDataRole.UserRole)
            parent_id = num_item.data(Qt.ItemDataRole.UserRole + 1)
            if parent_id:
                try:
                    index = int(str(item_id).rsplit(":", 1)[1])
                except Exception:
                    index = row
                self._playlist_child_rows[(parent_id, index)] = row
            elif item_id:
                num_item.setText(str(display_index))
                display_index += 1
                self._items[item_id] = row

    def update_playlist_item(self, item_id: str, playlist_index: int, status: str, percent: float):
        entries = self._playlist_entries.get(item_id, [])
        for entry in entries:
            if entry.get("index") == playlist_index:
                entry["status"] = status
                entry["percent"] = max(float(entry.get("percent", 0.0)), float(percent))
                break
        row = self._playlist_child_rows.get((item_id, playlist_index))
        if row is None:
            return
        status_item = self.table.item(row, 3)
        if status_item:
            status_item.setText(status)
            status_item.setForeground(QColor(STATUS_COLORS.get(status, "#cccccc")))
        pw = self.table.cellWidget(row, 4)
        if pw:
            pw.set_value(percent)

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
        self.table.setCellWidget(row, 7, self._action_widget(item_id, paused=True))

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
        if success and item_id in self._playlist_entries:
            for entry in self._playlist_entries[item_id]:
                if entry.get("status") in ("Ожидание", "Загрузка...", "Обработка..."):
                    entry["status"] = "Проверено"
                    entry["percent"] = max(float(entry.get("percent", 0.0)), 100.0)
                    self.update_playlist_item(item_id, entry["index"], "Проверено", entry["percent"])
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
            open_btn = ActionIconButton("folder", "Открыть папку")
            open_btn.clicked.connect(lambda _, iid=item_id: self.open_requested.emit(iid))
            btn_layout.addWidget(open_btn)
            mark = QLabel("✓")
            mark.setStyleSheet("color: #4caf50; font-weight: bold;")
            mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn_layout.addWidget(mark)
        else:
            retry_btn = ActionIconButton("retry", "Повторить")
            retry_btn.clicked.connect(lambda _, iid=item_id: self.retry_requested.emit(iid))
            details_btn = ActionIconButton("details", "Показать ошибку")
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
            if item_id in self._playlist_expanded:
                self._remove_playlist_children(item_id)
            row = self._items.pop(item_id)
            self._paths.pop(item_id, None)
            self._errors.pop(item_id, None)
            self._playlist_entries.pop(item_id, None)
            self._playlist_expanded.discard(item_id)
            self.table.removeRow(row)
        self._reindex_rows()

    def remove_item(self, item_id: str):
        row = self._items.pop(item_id, None)
        if row is None:
            return
        if item_id in self._playlist_expanded:
            self._remove_playlist_children(item_id)
            row = self._items.get(item_id, row)
        self._paths.pop(item_id, None)
        self._errors.pop(item_id, None)
        self._playlist_entries.pop(item_id, None)
        self._playlist_expanded.discard(item_id)
        self.table.removeRow(row)
        self._reindex_rows()
