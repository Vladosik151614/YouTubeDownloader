"""TikTok catalog helpers mixed into MainWindow."""
from __future__ import annotations

from PySide6.QtCore import QTimer

from app.tiktok_catalog import TikTokCatalogWidget


TIKTOK_WINDOW_WIDTH = 1292


def _apply_tiktok_window_width(self):
    target_width = max(self.minimumWidth(), TIKTOK_WINDOW_WIDTH)
    self.setMaximumWidth(target_width)
    self.resize(target_width, self.height())


def open_tiktok_catalog(self, url: str) -> bool:
    self.preview_label.setText("TikTok: каталог открыт ниже на главном экране.")
    old = getattr(self, "_tiktok_catalog", None)
    if old:
        old.release_queue_section()
        self.tiktok_catalog_layout.removeWidget(old)
        old.dispose()
    panel = TikTokCatalogWidget(url, self.settings, self.tiktok_catalog_host)
    panel.closed.connect(lambda: self._close_tiktok_catalog(panel))
    panel.download_requested.connect(self._queue_tiktok_download)
    self._tiktok_catalog = panel
    if not hasattr(self, "_pre_tiktok_max_width"):
        self._pre_tiktok_max_width = self.maximumWidth()
    self.tiktok_catalog_layout.addWidget(panel)
    self.download_layout.removeWidget(self.queue_section)
    panel.install_queue_section(self.queue_section)
    self._refresh_queue_visibility()
    self.tiktok_catalog_host.setMaximumHeight(16777215)
    self.tiktok_catalog_host.show()
    self.download_layout.setStretchFactor(self.tiktok_catalog_host, 1)
    self.queue_widget.setMinimumHeight(92)
    self.queue_widget.setMaximumHeight(132)
    _apply_tiktok_window_width(self)
    QTimer.singleShot(0, lambda: _apply_tiktok_window_width(self))
    QTimer.singleShot(300, lambda: _apply_tiktok_window_width(self))
    self._switch_page(0)
    return True


def queue_tiktok_download(self, source_url: str, mode: str, urls: list, card_size: str):
    task_settings = dict(self.settings)
    targets = list(urls) if urls and mode in {"all", "selected", "single"} else [source_url]
    for video_url in targets:
        self._enqueue_url(video_url, task_settings=task_settings)


def close_tiktok_catalog(self, panel):
    if panel:
        panel.release_queue_section()
        self.tiktok_catalog_layout.removeWidget(panel)
        panel.dispose()
    self.download_layout.addWidget(self.queue_section, 1)
    self.queue_section.setVisible(True)
    self._tiktok_catalog = None
    self.tiktok_catalog_host.setMaximumHeight(0)
    self.tiktok_catalog_host.hide()
    self.download_layout.setStretchFactor(self.tiktok_catalog_host, 0)
    self.queue_widget.setMinimumHeight(0)
    self.queue_widget.setMaximumHeight(16777215)
    self.setMaximumWidth(getattr(self, "_pre_tiktok_max_width", 16777215))
    self._refresh_queue_visibility()


def refresh_queue_visibility(self):
    if not hasattr(self, "queue_widget") or not hasattr(self, "queue_section"):
        return
    has_items = self.queue_widget.table.rowCount() > 0
    panel = getattr(self, "_tiktok_catalog", None)
    if panel and self.tiktok_catalog_host.isVisible():
        panel.set_queue_available(has_items)
        if not has_items:
            self.queue_section.setVisible(False)
        self.download_layout.setStretchFactor(self.queue_section, 0)
        return
    self.queue_section.setVisible(has_items)
    self.download_layout.setStretchFactor(self.queue_section, 1 if has_items else 0)
