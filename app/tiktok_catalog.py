"""Inline TikTok catalog UI with muted preview inside the hovered card."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)

from app.logger import logger
from app.error_messages import classify_download_error
from app.tiktok_card import TikTokCardGrid, TikTokVideoCard
from app.tiktok_metadata import TikTokCatalogWorker, TikTokPreviewWorker, is_tiktok_collection_url, normalize_catalog_entries, select_preview_format
from app.tiktok_preview import TikTokPreviewProxy


CARD_WIDTH = 196
CARD_GAP = 12
GRID_SIDE_MARGINS = 12
SCROLL_FRAME_AND_BAR_WIDTH = 22
FIVE_CARD_SCROLL_WIDTH = GRID_SIDE_MARGINS + CARD_WIDTH * 5 + CARD_GAP * 4 + SCROLL_FRAME_AND_BAR_WIDTH
FOUR_CARD_SCROLL_WIDTH = GRID_SIDE_MARGINS + CARD_WIDTH * 4 + CARD_GAP * 3 + SCROLL_FRAME_AND_BAR_WIDTH


class TikTokCatalogWidget(QWidget):
    closed = Signal()
    download_requested = Signal(str, str, list, str)

    def __init__(self, url: str, settings: dict, parent=None, *, auto_load=True):
        super().__init__(parent)
        self.url = url
        self.settings = dict(settings)
        self.entries: list[dict] = []
        self.cards_by_url: dict[str, TikTokVideoCard] = {}
        self._thumb_requests = {}
        self._thumb_queue = []
        self._preview_worker = None
        self._pending_card = None
        self._active_card = None
        self._queue_section = None
        self.playlists: list[dict] = []
        self._preview_proxy = TikTokPreviewProxy()
        self._build_ui()
        if auto_load:
            self._load_catalog()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 4)
        root.setSpacing(8)
        header = QHBoxLayout()
        title = QLabel("TikTok — ролики профиля или плейлиста")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        header.addWidget(title)
        self.status_label = QLabel("Читаю профиль или плейлист…")
        self.status_label.setObjectName("subtle")
        header.addWidget(self.status_label, 1)
        root.addLayout(header)

        controls = QHBoxLayout()
        self.select_all_btn = QPushButton("Выбрать всё")
        self.select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        controls.addWidget(self.select_all_btn)
        self.clear_btn = QPushButton("Снять выбор")
        self.clear_btn.clicked.connect(lambda: self._set_all_checked(False))
        controls.addWidget(self.clear_btn)
        self.queue_toggle = QToolButton()
        self.queue_toggle.setText("Скачивание ▾")
        self.queue_toggle.setToolTip("Показать или скрыть компактную очередь скачивания")
        self.queue_toggle.setCheckable(True)
        self.queue_toggle.setVisible(False)
        self.queue_toggle.clicked.connect(self._toggle_queue_section)
        controls.addWidget(self.queue_toggle)
        controls.addStretch()
        self.selected_btn = QPushButton("Скачать выбранное")
        self.selected_btn.clicked.connect(self._accept_selected)
        controls.addWidget(self.selected_btn)
        self.all_btn = QPushButton("Скачать весь профиль")
        self.all_btn.clicked.connect(self._accept_all)
        controls.addWidget(self.all_btn)
        self.playlist_btn = QPushButton("Скачать плейлист")
        self.playlist_btn.setToolTip("Если у профиля есть плейлисты, выберите плейлист справа или нажмите эту кнопку для текущего плейлиста")
        self.playlist_btn.clicked.connect(self._accept_playlist)
        controls.addWidget(self.playlist_btn)
        root.addLayout(controls)

        self.queue_slot = QVBoxLayout()
        self.queue_slot.setContentsMargins(0, 0, 0, 0)
        self.queue_slot.setSpacing(0)
        root.addLayout(self.queue_slot)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFixedWidth(FIVE_CARD_SCROLL_WIDTH)
        self.scroll.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.card_grid = TikTokCardGrid()
        self.card_grid.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.scroll.setWidget(self.card_grid)
        body = QHBoxLayout()
        body.setSpacing(8)
        body.addWidget(self.scroll, 0)
        self.playlists_panel = QFrame()
        self.playlists_panel.setObjectName("tiktok_playlists_panel")
        self.playlists_panel.setFixedWidth(196)
        self.playlists_layout = QVBoxLayout(self.playlists_panel)
        self.playlists_layout.setContentsMargins(8, 8, 8, 8)
        self.playlists_layout.setSpacing(8)
        self.playlists_panel.hide()
        body.addWidget(self.playlists_panel)
        root.addLayout(body, 1)

        self.audio_output = QAudioOutput(self)
        self.audio_output.setMuted(True)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.errorOccurred.connect(self._on_player_error)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self._start_pending_preview)
        self._set_actions_enabled(False)

    def _load_catalog(self):
        self.worker = TikTokCatalogWorker(self.url, self.settings, self)
        self.worker.loaded.connect(self._on_loaded)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_loaded(self, title: str, entries: list[dict], playlists: list[dict] | None = None):
        self.entries = entries
        self.status_label.setText(f"{title} · найдено: {len(entries)}")
        size_mode = "medium"
        for entry in entries:
            card = TikTokVideoCard(entry, size_mode, self.card_grid)
            card.hover_started.connect(self._schedule_preview)
            card.hover_ended.connect(self._stop_preview)
            card.download_requested.connect(self._download_one)
            card.selected_changed.connect(self._refresh_selection_actions)
            self.cards_by_url[card.video_url] = card
            self.card_grid.add_card(card)
            self._request_thumbnail(card, entry.get("thumbnail", ""), "cover")
            self._request_thumbnail(
                card, entry.get("animated_thumbnail", ""), "animated"
            )
        self._render_playlists(playlists or [])
        self._set_actions_enabled(True)
        self._refresh_selection_actions()

    def _render_playlists(self, playlists: list[dict]):
        self.playlists = playlists
        while self.playlists_layout.count():
            item = self.playlists_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not playlists:
            self.playlists_panel.hide()
            self.card_grid.max_columns = 5
            self.scroll.setFixedWidth(FIVE_CARD_SCROLL_WIDTH)
            self.card_grid.setMinimumWidth(FIVE_CARD_SCROLL_WIDTH - SCROLL_FRAME_AND_BAR_WIDTH)
            self.card_grid.reflow()
            self.playlist_btn.setEnabled(self._is_current_playlist())
            return
        title = QLabel("Плейлисты")
        title.setStyleSheet("font-weight: 700;")
        self.playlists_layout.addWidget(title)
        for playlist in playlists:
            button = QPushButton(str(playlist.get("title") or "Плейлист"))
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(
                lambda _=False, url=str(playlist.get("url") or ""): self._download_playlist(url)
            )
            self.playlists_layout.addWidget(button)
        self.playlists_layout.addStretch()
        self.playlists_panel.show()
        self.playlist_btn.setEnabled(True)
        self.card_grid.max_columns = 4
        self.scroll.setFixedWidth(FOUR_CARD_SCROLL_WIDTH)
        self.card_grid.setMinimumWidth(FOUR_CARD_SCROLL_WIDTH - SCROLL_FRAME_AND_BAR_WIDTH)
        self.card_grid.reflow()

    def _on_failed(self, message: str):
        self.status_label.setText(classify_download_error(message).title)

    def _set_actions_enabled(self, enabled: bool):
        for control in (
            self.select_all_btn,
            self.clear_btn,
            self.selected_btn,
            self.all_btn,
            self.playlist_btn,
        ):
            control.setEnabled(enabled)
        self.all_btn.setEnabled(enabled and not self._is_current_playlist())
        self.playlist_btn.setEnabled(enabled and (self._is_current_playlist() or bool(self.playlists)))

    def _set_all_checked(self, checked: bool):
        for card in self.card_grid.cards:
            card.set_checked(checked)
        self._refresh_selection_actions()

    def _refresh_selection_actions(self):
        selected = sum(1 for card in self.card_grid.cards if card.checked)
        self.selected_btn.setText(
            f"Скачать выбранное ({selected})" if selected else "Скачать выбранное"
        )

    def _request_thumbnail(self, card: TikTokVideoCard, url: str, kind: str):
        if not url:
            return
        if not hasattr(self, "network"):
            self.network = QNetworkAccessManager(self)
            self.network.finished.connect(self._thumbnail_ready)
        self._thumb_queue.append((card, url, kind))
        self._drain_thumbnail_queue()

    def _drain_thumbnail_queue(self):
        while self._thumb_queue and len(self._thumb_requests) < 6:
            card, url, kind = self._thumb_queue.pop(0)
            request = QNetworkRequest(QUrl(url))
            request.setRawHeader(
                b"User-Agent", b"Mozilla/5.0 Chrome/131 Safari/537.36"
            )
            request.setRawHeader(b"Referer", b"https://www.tiktok.com/")
            reply = self.network.get(request)
            self._thumb_requests[reply] = (card, kind)

    def _thumbnail_ready(self, reply):
        request_data = self._thumb_requests.pop(reply, None)
        card, kind = request_data or (None, "")
        data = bytes(reply.readAll())
        pixmap = QPixmap()
        if card and kind == "animated" and card.set_animated_preview(data):
            pass
        elif card and kind == "cover" and pixmap.loadFromData(data):
            card.set_cover(pixmap)
        elif card:
            logger.warning(f"TikTok thumbnail failed: {reply.errorString()}")
        reply.deleteLater()
        self._drain_thumbnail_queue()

    def _schedule_preview(self, card: TikTokVideoCard):
        if self._pending_card is card and self.preview_timer.isActive():
            return
        self._pending_card = card
        card.preview_hint.setText("Подготовка предпросмотра…")
        self.preview_timer.start(450)

    def _start_pending_preview(self):
        card = self._pending_card
        if not card:
            return
        entry = card.entry
        stream_url = str(entry.get("preview_stream_url") or "")
        if stream_url:
            self._play_preview(card, stream_url, entry.get("preview_headers") or {})
            return
        if self._preview_worker and self._preview_worker.isRunning():
            card.show_cover("Предпросмотр уже подготавливается…")
            return
        self._preview_worker = TikTokPreviewWorker(
            card.video_url, self.settings, self
        )
        self._preview_worker.resolved.connect(self._on_preview_resolved)
        self._preview_worker.start()

    def _start_animated_fallback(self, card: TikTokVideoCard, message: str):
        if self._active_card and self._active_card is not card:
            self._active_card.show_cover()
        self.player.stop()
        self.player.setVideoOutput(None)
        self._active_card = card
        card.start_animated_preview()
        card.preview_hint.setText(message)

    def _on_preview_resolved(
        self, video_url: str, stream_url: str, headers: dict,
        quality: dict, reason: str,
    ):
        card = self.cards_by_url.get(video_url)
        if card and quality:
            card.set_source_quality(quality)
        if card is not self._pending_card:
            return
        if not stream_url:
            message = (
                "Нет потока без водяного знака — скачивание заблокировано."
                if reason == "watermark"
                else "Полный предпросмотр недоступен; показана короткая обложка."
            )
            if card.has_animated_preview:
                self._start_animated_fallback(card, message)
                return
            card.show_cover(message)
            return
        self._play_preview(card, stream_url, headers)

    def _play_preview(self, card: TikTokVideoCard, stream_url: str, headers: dict):
        if self._active_card and self._active_card is not card:
            self._active_card.show_cover()
        self.player.stop()
        self.player.setVideoOutput(card.video_widget)
        self.audio_output.setMuted(True)
        local_url = self._preview_proxy.register(stream_url, headers)
        self.player.setSource(QUrl(local_url))
        self._active_card = card
        card.show_preview()
        self.player.play()

    def _stop_preview(self, card: TikTokVideoCard):
        if self._pending_card is card:
            self._pending_card = None
            self.preview_timer.stop()
        if self._active_card is card:
            self.player.stop()
            self.player.setVideoOutput(None)
            self._active_card = None
        card.show_cover()

    def _on_player_error(self, *_args):
        if self._active_card:
            card = self._active_card
            self.player.stop()
            self.player.setVideoOutput(None)
            self._active_card = None
            if not card.entry.get("_external_preview_tried"):
                card.entry["_external_preview_tried"] = True
                self._pending_card = card
                card.preview_hint.setText("Пробую внешний предпросмотр без водяного знака…")
                self._preview_worker = TikTokPreviewWorker(
                    card.video_url, self.settings, self
                )
                self._preview_worker.resolved.connect(self._on_preview_resolved)
                self._preview_worker.start()
                return
            if card.has_animated_preview:
                self._start_animated_fallback(
                    card,
                    "Полный предпросмотр не запустился; показана короткая обложка.",
                )
                return
            card.show_cover("Предпросмотр недоступен; можно скачать ролик.")

    def _download_one(self, video_url: str):
        self.download_requested.emit(
            self.url, "single", [video_url], self._card_size()
        )
        self.status_label.setText("Видео добавлено в очередь по активному профилю")

    def _accept_selected(self):
        urls = [card.video_url for card in self.card_grid.cards if card.checked]
        if not urls:
            self.status_label.setText("Отметьте хотя бы одно видео")
            return
        self.download_requested.emit(self.url, "selected", urls, self._card_size())
        self.status_label.setText(f"Добавлено в очередь: {len(urls)}")

    def _accept_all(self):
        urls = [card.video_url for card in self.card_grid.cards if card.video_url]
        self.download_requested.emit(self.url, "all", urls, self._card_size())
        self.status_label.setText("Профиль добавлен в очередь" if "@" in self.url else "Плейлист добавлен в очередь")

    def _accept_playlist(self):
        if self._is_current_playlist():
            self._download_playlist(self.url)
            return
        if len(self.playlists) == 1:
            self._download_playlist(str(self.playlists[0].get("url") or ""))
            return
        if self.playlists:
            self.status_label.setText("Выберите нужный плейлист в правой панели")
            return
        self.status_label.setText("У этого профиля TikTok не отдал список плейлистов")

    def _download_playlist(self, playlist_url: str):
        if not playlist_url:
            self.status_label.setText("TikTok не отдал ссылку на плейлист")
            return
        self.download_requested.emit(playlist_url, "playlist", [], self._card_size())
        self.status_label.setText("Плейлист добавлен в очередь")

    def install_queue_section(self, section: QWidget):
        self._queue_section = section
        self.queue_slot.addWidget(section)
        section.setMaximumHeight(132)
        section.setVisible(False)
        self.queue_toggle.setChecked(False)
        self.queue_toggle.setVisible(False)
        self.queue_toggle.setText("Скачивание ▾")

    def set_queue_available(self, available: bool):
        self.queue_toggle.setVisible(available)
        if not available and self._queue_section:
            self.queue_toggle.setChecked(False)
            self.queue_toggle.setText("Скачивание ▾")
            self._queue_section.setVisible(False)

    def release_queue_section(self) -> QWidget | None:
        section = self._queue_section
        if section:
            self.queue_slot.removeWidget(section)
            section.setVisible(True)
        self._queue_section = None
        return section

    def _toggle_queue_section(self):
        if not self._queue_section:
            return
        expanded = self.queue_toggle.isChecked()
        self._queue_section.setVisible(expanded)
        self.queue_toggle.setText("Скачивание ▴" if expanded else "Скачивание ▾")

    def _card_size(self) -> str:
        return "medium"

    def _is_current_playlist(self) -> bool:
        lowered = self.url.lower()
        return "/collection/" in lowered or "/playlist/" in lowered

    def close_catalog(self):
        self.player.stop()
        self.preview_timer.stop()
        self.closed.emit()

    def dispose(self):
        self.player.stop()
        self._preview_proxy.close()
        self.preview_timer.stop()
        running = [
            worker for worker in (
                getattr(self, "worker", None), self._preview_worker
            ) if worker and worker.isRunning()
        ]
        if not running:
            self.deleteLater()
            return
        self._dispose_pending = len(running)
        for worker in running:
            worker.finished.connect(self._dispose_worker_finished)

    def _dispose_worker_finished(self):
        self._dispose_pending -= 1
        if not self._dispose_pending:
            self.deleteLater()
