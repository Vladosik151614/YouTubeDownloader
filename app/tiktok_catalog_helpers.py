"""Thumbnail and compact-queue behavior used by the inline TikTok catalog."""
from PySide6.QtCore import QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import QWidget

from app.logger import logger


class CatalogHelpers:
    def _request_thumbnail(self, card, url: str, kind: str):
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
            request.setRawHeader(b"User-Agent", b"Mozilla/5.0 Chrome/131 Safari/537.36")
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

    def _set_preview_sound(self, enabled):
        self.settings["tiktok_preview_sound"] = bool(enabled)
        self.preview_sound_changed.emit(bool(enabled))
        self.sound_btn.setText("Звук: вкл." if enabled else "Звук: выкл.")
        if hasattr(self, "audio_output"):
            self.audio_output.setMuted(not enabled)
        if self._active_card and self._active_card.cover_stack.currentWidget() is self._active_card.video_widget:
            self._active_card.preview_hint.setText(
                "Предпросмотр со звуком" if enabled else "Предпросмотр без звука"
            )


    def _card_size(self) -> str:
        return "medium"


    def _is_current_playlist(self) -> bool:
        lowered = self.url.lower()
        return "/collection/" in lowered or "/playlist/" in lowered
