import os
import sys
import unittest
from unittest.mock import patch

import yt_dlp

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QPixmap

from app.link_preview import LinkPreviewWorker
from app.tiktok_catalog import TikTokCatalogWidget
from app.tiktok_card import TikTokVideoCard
from app.tiktok_metadata import TikTokCatalogWorker, _ydl_access_options, resolve_downloadable_quality_batch


class CatalogResponsivenessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_yt_dlp_errors_use_collector_when_stderr_is_broken(self):
        class BrokenStream:
            encoding = "utf-8"
            def isatty(self):
                return False
            def write(self, text):
                raise OSError(22, "Invalid argument")
            def flush(self):
                raise OSError(22, "Invalid argument")

        with patch("app.tiktok_metadata.cookie_file_for_url", return_value=None):
            options = _ydl_access_options("https://www.tiktok.com/@creator", {"auto_export_cookies": False})
        with patch.object(sys, "stderr", BrokenStream()), \
             patch("app.download_utils.logger.error") as log_error:
            with yt_dlp.YoutubeDL(options) as downloader:
                downloader.to_stderr("simulated network error")
        self.assertIn("simulated network error", options["logger"].errors)
        log_error.assert_called_once()

    def test_profile_emits_without_second_sequential_profile_fetch(self):
        captured = {}
        class FakeYDL:
            def __init__(self, options):
                self.options = options
                captured.update(options)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def extract_info(self, url, download=False):
                return {"title": "Profile", "entries": [{"id": "1"}]}

        worker = TikTokCatalogWorker("https://www.tiktok.com/@creator", {})
        received = []
        worker.loaded.connect(lambda *args: received.append(args))
        with patch("app.tiktok_metadata._ydl_access_options", return_value={}), \
             patch("app.tiktok_metadata.yt_dlp.YoutubeDL", FakeYDL), \
             patch("app.tiktok_metadata._profile_source_data", side_effect=AssertionError("unexpected second fetch")), \
             patch("app.tiktok_metadata.resolve_downloadable_quality_batch", return_value=iter(())):
            worker.run()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0][1][0]["id"], "1")
        self.assertEqual(captured["socket_timeout"], 10)
        self.assertEqual(captured["retries"], 1)
        self.assertEqual(captured["extractor_retries"], 1)

    def test_large_catalog_yields_between_batches_and_retains_quality(self):
        widget = TikTokCatalogWidget("https://www.tiktok.com/@creator", {}, auto_load=False)
        entries = [{"index": i, "url": f"https://www.tiktok.com/@creator/video/{i}"} for i in range(45)]
        widget._on_loaded("Profile", entries, [])
        self.assertEqual(len(widget.card_grid.cards), 20)
        self.assertFalse(widget.all_btn.isEnabled())
        widget._apply_quality(entries[-1]["url"], {"label": "720p", "confidence": "verified"})
        for _ in range(10):
            self.app.processEvents()
            if len(widget.card_grid.cards) == len(entries):
                break
        self.assertEqual(len(widget.card_grid.cards), 45)
        self.assertTrue(widget.all_btn.isEnabled())
        self.assertIn("720p", widget.cards_by_url[entries[-1]["url"]].quality_label.text())
        widget.dispose()

    def test_playlist_preview_requests_flat_extraction(self):
        captured = {}
        class FakeYDL:
            def __init__(self, options):
                captured.update(options)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def extract_info(self, url, download=False):
                return {"_type": "playlist", "entries": [{"id": "1"}, {"id": "2"}]}
        worker = LinkPreviewWorker("https://www." + "youtube.com/playlist?list=example", {"auto_export_cookies": False})
        with patch("app.link_preview.cookie_file_for_url", return_value=None), \
             patch("app.link_preview.yt_dlp.YoutubeDL", FakeYDL):
            result = worker._load_preview()
        self.assertEqual(captured["extract_flat"], "in_playlist")
        self.assertEqual(result["count"], 2)

    def test_quality_cancellation_does_not_queue_remaining_profile(self):
        entries = [{"url": f"https://example.com/{i}"} for i in range(100)]
        cancelled = [False]
        with patch("app.tiktok_metadata.tikwm_best_quality", return_value={"label": "720p"}) as probe:
            results = resolve_downloadable_quality_batch(entries, 100, 2, cancelled=lambda: cancelled[0])
            self.assertTrue(next(results)[1])
            cancelled[0] = True
            self.assertEqual(list(results), [])
            self.assertLessEqual(probe.call_count, 2)

    def test_disposed_catalog_ignores_late_profile_result(self):
        widget = TikTokCatalogWidget("https://www.tiktok.com/@creator", {}, auto_load=False)
        widget.dispose()
        widget._on_loaded("Late", [{"url": "https://example.com/1"}], [])
        self.assertEqual(widget.card_grid.cards, [])

    def test_preview_hint_has_room_below_cover_in_both_sizes(self):
        for size_mode in ("medium", "large"):
            card = TikTokVideoCard({"index": 1, "url": "https://example.com/video"}, size_mode)
            card.show()
            self.app.processEvents()
            self.assertGreaterEqual(card.preview_hint.height(), 32)
            self.assertGreater(card.preview_hint.geometry().top(), card.cover_host.geometry().bottom())
            card.show_cover("Полный предпросмотр недоступен; показана короткая обложка.")
            self.app.processEvents()
            self.assertGreater(card.preview_hint.geometry().top(), card.cover_host.geometry().bottom())
            card.close()

    def test_cover_pixmap_is_cropped_to_host_for_any_aspect(self):
        for width, height in ((90, 160), (160, 90), (90, 90)):
            card = TikTokVideoCard({"index": 1, "url": "https://example.com/video"})
            card.show()
            self.app.processEvents()
            cover = QPixmap(width, height)
            cover.fill(QColor("red"))
            card.set_cover(cover)
            self.app.processEvents()
            self.assertEqual(card.cover_label.pixmap().size(), card.cover_host.size())
            self.assertLessEqual(card.cover_label.height(), card.cover_host.height())
            self.assertGreater(card.preview_hint.geometry().top(), card.cover_host.geometry().bottom())
            card.close()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
