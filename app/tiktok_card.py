"""Reusable TikTok video card and responsive four-column grid."""
from __future__ import annotations

from PySide6.QtCore import QBuffer, QEvent, QIODevice, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QFont, QMovie, QPixmap
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QStackedLayout,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class TikTokVideoCard(QFrame):
    """One selectable video with an inline muted-preview surface."""

    hover_started = Signal(object)
    hover_ended = Signal(object)
    download_requested = Signal(str)
    selected_changed = Signal()

    def __init__(self, entry: dict, size_mode: str = "medium", parent=None):
        super().__init__(parent)
        self.entry = entry
        self._cover_pixmap = QPixmap()
        self._quality_loading_base = ""
        self._quality_loading_step = 0
        self._quality_loading_timer = QTimer(self)
        self._quality_loading_timer.setInterval(450)
        self._quality_loading_timer.timeout.connect(self._animate_quality_loading)
        self.setObjectName("tiktok_card")
        self.setMouseTracking(True)
        self._build_ui()
        self.set_size_mode(size_mode)

    @property
    def video_url(self) -> str:
        return str(self.entry.get("url") or "")

    @property
    def checked(self) -> bool:
        return self.checkbox.isChecked()

    def set_checked(self, checked: bool):
        self.checkbox.setChecked(checked)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 9)
        root.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(5)
        self.checkbox = QCheckBox()
        self.checkbox.setAccessibleName(
            f"Выбрать видео {self.entry.get('index', '')}"
        )
        self.checkbox.toggled.connect(lambda _checked: self.selected_changed.emit())
        top.addWidget(self.checkbox)
        number = QLabel(f"#{self.entry.get('index', '')}")
        number.setObjectName("subtle")
        top.addWidget(number)
        top.addStretch()
        duration = int(self.entry.get("duration") or 0)
        self.duration_label = QLabel(
            f"{duration // 60}:{duration % 60:02d}" if duration else ""
        )
        self.duration_label.setObjectName("subtle")
        top.addWidget(self.duration_label)
        root.addLayout(top)

        self.cover_host = QFrame()
        self.cover_host.setObjectName("tiktok_cover")
        self.cover_stack = QStackedLayout(self.cover_host)
        self.cover_stack.setContentsMargins(0, 0, 0, 0)
        self.cover_label = QLabel()
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet("background: #111318; border-radius: 7px;")
        self.animation_label = QLabel()
        self.animation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.animation_label.setStyleSheet(
            "background: #111318; border-radius: 7px;"
        )
        self.video_widget = QVideoWidget()
        self.cover_stack.addWidget(self.cover_label)
        self.cover_stack.addWidget(self.animation_label)
        self.cover_stack.addWidget(self.video_widget)
        root.addWidget(self.cover_host, 0, Qt.AlignmentFlag.AlignHCenter)

        for target in (
            self.cover_host, self.cover_label, self.animation_label,
            self.video_widget,
        ):
            target.setMouseTracking(True)
            target.installEventFilter(self)

        self.preview_hint = QLabel("Наведите для предпросмотра без звука")
        self.preview_hint.setObjectName("subtle")
        self.preview_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_hint.setWordWrap(True)
        self.preview_hint.setStyleSheet("font-size: 10px;")
        root.addWidget(self.preview_hint)

        self.quality_label = QLabel()
        self.quality_label.setObjectName("source_quality")
        self.quality_label.setWordWrap(True)
        self.quality_label.setStyleSheet("font-size: 10px; font-weight: 600;")
        root.addWidget(self.quality_label)
        self.set_source_quality(self.entry.get("source_quality") or {})

        self.title_label = QLabel(str(self.entry.get("title") or "Видео TikTok"))
        self.title_label.setWordWrap(True)
        self.title_label.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self.title_label.setToolTip(self.title_label.text())
        self.title_label.setMaximumHeight(42)
        root.addWidget(self.title_label)

        self.download_button = QToolButton()
        self.download_button.setText("Скачать")
        self.download_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.download_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.download_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.download_button.clicked.connect(
            lambda: self.download_requested.emit(self.video_url)
        )
        menu = QMenu(self.download_button)
        active_profile = QAction("Скачать по активному профилю", menu)
        active_profile.triggered.connect(
            lambda: self.download_requested.emit(self.video_url)
        )
        mark = QAction("✓ Выбрать это видео", menu)
        mark.triggered.connect(lambda: self.set_checked(True))
        menu.addAction(active_profile)
        menu.addAction(mark)
        self.download_button.setMenu(menu)
        root.addWidget(self.download_button)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Enter:
            self.hover_started.emit(self)
        elif event.type() == QEvent.Type.Leave:
            QTimer.singleShot(0, self._emit_leave_if_outside)
        return super().eventFilter(watched, event)

    def _emit_leave_if_outside(self):
        if not self.cover_host.rect().contains(
            self.cover_host.mapFromGlobal(self.cursor().pos())
        ):
            self.hover_ended.emit(self)

    def set_cover(self, pixmap: QPixmap):
        if pixmap.isNull():
            return
        self._cover_pixmap = pixmap
        self._render_cover()

    @property
    def has_animated_preview(self) -> bool:
        return bool(getattr(self, "_preview_movie", None))

    def set_animated_preview(self, data: bytes) -> bool:
        self._preview_buffer = QBuffer(self)
        self._preview_buffer.setData(data)
        self._preview_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        movie = QMovie(self._preview_buffer, b"webp", self)
        movie.setCacheMode(QMovie.CacheMode.CacheAll)
        movie.setScaledSize(self.animation_label.size())
        if not movie.isValid():
            return False
        self._preview_movie = movie
        self.animation_label.setMovie(movie)
        return True

    def start_animated_preview(self):
        if not self.has_animated_preview:
            return
        self.cover_stack.setCurrentWidget(self.animation_label)
        self._preview_movie.start()
        self.preview_hint.setText("Предпросмотр без звука")

    def stop_animated_preview(self):
        if self.has_animated_preview:
            self._preview_movie.stop()

    def _render_cover(self):
        if self._cover_pixmap.isNull():
            return
        self.cover_label.setPixmap(
            self._cover_pixmap.scaled(
                self.cover_label.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        if self.has_animated_preview:
            self._preview_movie.setScaledSize(self.animation_label.size())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_cover()

    def set_size_mode(self, mode: str):
        large = mode == "large"
        card_width = 230 if large else 196
        cover_width = 212 if large else 180
        cover_height = 283 if large else 240
        self.setFixedWidth(card_width)
        self.cover_host.setFixedSize(cover_width, cover_height)

    def set_source_quality(self, quality: dict):
        self.entry["source_quality"] = dict(quality or {})
        label = str((quality or {}).get("label") or "")
        confidence = str((quality or {}).get("confidence") or "")
        self._stop_quality_loading()
        if (quality or {}).get("probe_failed"):
            text = (
                f"Не удалось подтвердить HD · предварительно: {label}"
                if label else "Качество не подтверждено"
            )
            self.quality_label.setText(text)
            return
        if (quality or {}).get("checking") or confidence == "reported":
            self._start_quality_loading(label)
            return
        if label:
            prefix = "Доступно" if confidence == "limited" else "Макс. доступно"
            suffix = " · HD не подтверждён" if confidence == "limited" else ""
            self.quality_label.setText(f"{prefix}: {label}{suffix}")
        else:
            self._start_quality_loading("")

    def _start_quality_loading(self, label: str):
        self._quality_loading_base = (
            f"Проверяем реальное качество · пока видно: {label}"
            if label else "Проверяем реальное качество"
        )
        self._quality_loading_step = 0
        self._animate_quality_loading()
        self._quality_loading_timer.start()

    def _stop_quality_loading(self):
        if getattr(self, "_quality_loading_timer", None):
            self._quality_loading_timer.stop()

    def _animate_quality_loading(self):
        dots = "." * (self._quality_loading_step % 4)
        self._quality_loading_step += 1
        self.quality_label.setText(f"{self._quality_loading_base}{dots}")

    def mark_quality_loading(self):
        current = dict(self.entry.get("source_quality") or {})
        current["checking"] = True
        current.pop("probe_failed", None)
        self.set_source_quality(current)

    def mark_quality_probe_failed(self):
        current = dict(self.entry.get("source_quality") or {})
        current.pop("checking", None)
        current["probe_failed"] = True
        self.set_source_quality(current)

    def apply_resolved_quality(self, quality: dict):
        if (quality or {}).get("probe_failed"):
            self.mark_quality_probe_failed()
        else:
            self.set_source_quality(quality)

    def show_preview(self, message: str = "Предпросмотр без звука"):
        self.cover_stack.setCurrentWidget(self.video_widget)
        self.preview_hint.setText(message)

    def show_cover(self, message: str = "Наведите для предпросмотра без звука"):
        self.stop_animated_preview()
        self.cover_stack.setCurrentWidget(self.cover_label)
        self.preview_hint.setText(message)

class TikTokCardGrid(QWidget):
    """Responsive grid capped at four cards per row."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards: list[TikTokVideoCard] = []
        self.size_mode = "medium"
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(2, 2, 10, 8)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._reflow_timer = QTimer(self)
        self._reflow_timer.setSingleShot(True)
        self._reflow_timer.timeout.connect(self.reflow)

    def add_card(self, card: TikTokVideoCard):
        self.cards.append(card)
        self.reflow()

    def set_size_mode(self, mode: str):
        self.size_mode = mode
        for card in self.cards:
            card.set_size_mode(mode)
        self.reflow()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow_timer.start(0)

    def reflow(self):
        while self.grid.count():
            self.grid.takeAt(0)
        card_width = 230 if self.size_mode == "large" else 196
        available = max(card_width, self.width() - 12)
        max_columns = int(getattr(self, "max_columns", 5) or 5)
        columns = max(1, min(max_columns, available // (card_width + 12)))
        for index, card in enumerate(self.cards):
            self.grid.addWidget(card, index // columns, index % columns)
