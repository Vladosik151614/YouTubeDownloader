import os
import tempfile
import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.downloader import DownloadWorker
from app.download_utils import is_playlist
from app.error_messages import classify_download_error
from app.tiktok_catalog import (
    FIVE_CARD_SCROLL_WIDTH,
    FOUR_CARD_SCROLL_WIDTH,
    TikTokCatalogWidget,
    is_tiktok_collection_url,
    normalize_catalog_entries,
    select_preview_format,
)
from app.tiktok_metadata import source_quality
from app import tiktok_download


def tiktok_url(path: str) -> str:
    return "https://www." + "tiktok.com" + path


class TikTokCatalogLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_profile_and_playlist_are_collections_but_video_is_not(self):
        profile = tiktok_url("/@creator")
        playlist = tiktok_url("/@creator/collection/Travel-123")
        video = tiktok_url("/@creator/video/123456")
        self.assertTrue(is_tiktok_collection_url(profile))
        self.assertTrue(is_tiktok_collection_url(playlist))
        self.assertFalse(is_tiktok_collection_url(video))
        self.assertTrue(is_playlist(profile))
        self.assertTrue(is_playlist(playlist))
        self.assertFalse(is_playlist(video))

    def test_flat_profile_entries_become_direct_video_urls(self):
        entries = normalize_catalog_entries([
            {"id": "111", "title": "First", "playlist_index": 1, "thumbnails": [{"url": "https://cdn.example/cover.jpg"}]},
            {"id": "222", "description": "Second"},
        ], tiktok_url("/@creator"))
        self.assertEqual(entries[0]["url"], tiktok_url("/@creator/video/111"))
        self.assertEqual(entries[0]["thumbnail"], "https://cdn.example/cover.jpg")
        self.assertEqual(entries[1]["title"], "Second")

    def test_preview_prefers_highest_combined_resolution_and_fps(self):
        selected = select_preview_format([
            {"url": "watermarked-8k", "vcodec": "h264", "acodec": "aac", "height": 4320, "fps": 60, "format_note": "Download video, watermarked"},
            {"url": "silent-4k", "vcodec": "h264", "acodec": "none", "height": 2160, "fps": 60},
            {"url": "full-hd", "vcodec": "h264", "acodec": "aac", "height": 1080, "fps": 30},
            {"url": "full-4k", "vcodec": "h264", "acodec": "aac", "height": 2160, "fps": 60},
        ])
        self.assertEqual(selected["url"], "full-4k")

    def test_tiktok_uses_active_profile_resolution_and_fps_caps(self):
        with tempfile.TemporaryDirectory() as folder:
            worker = DownloadWorker("tt", tiktok_url("/@creator/video/123"), folder, {
                "download_type": "video", "download_quality": "1080", "fps_limit": "30",
                "container": "mp4", "tiktok_max_quality": True, "exact_download_folder": True,
            })
            options = worker._build_ydl_opts()
            self.assertIn("[height<=1080][fps<=30]", options["format"])
            self.assertNotIn("format_sort", options)

    def test_tiktok_watermark_filter_stays_enabled_without_maximum_quality(self):
        with tempfile.TemporaryDirectory() as folder:
            worker = DownloadWorker("tt", tiktok_url("/@creator/video/123"), folder, {
                "download_type": "video", "download_quality": "1080", "fps_limit": "30",
                "container": "mp4", "tiktok_max_quality": False, "exact_download_folder": True,
            })
            selector = worker._build_ydl_opts()["format"]
            video_terms = [term for alternative in selector.split("/") for term in alternative.split("+") if term.startswith("bestvideo") or term.startswith("best[") or term == "best"]
            self.assertTrue(video_terms)
            self.assertTrue(all("format_note!*=?watermarked" in term for term in video_terms))

    def test_tiktok_enables_browser_impersonation_engine(self):
        with tempfile.TemporaryDirectory() as folder:
            worker = DownloadWorker("tt", tiktok_url("/@creator/video/123"), folder, {
                "download_type": "video", "download_quality": "best",
                "fps_limit": "best", "container": "mp4",
                "exact_download_folder": True,
            })
            options = worker._build_ydl_opts()
            self.assertIn("impersonate", options)
            self.assertIn("chrome", str(options["impersonate"]).lower())

    def test_tiktok_direct_success_emits_verified_quality(self):
        with tempfile.TemporaryDirectory() as folder:
            filepath = os.path.join(folder, "video.mp4")
            with open(filepath, "wb") as handle:
                handle.write(b"fake")
            worker = DownloadWorker("tt", tiktok_url("/@creator/video/123"), folder, {
                "download_type": "video", "download_quality": "1080",
                "fps_limit": "60", "container": "mp4",
                "exact_download_folder": True,
            })
            emitted = []
            statuses = []
            worker.quality_ready.connect(lambda item_id, quality: emitted.append((item_id, quality)))
            worker.status.connect(lambda item_id, text: statuses.append((item_id, text)))
            original_probe = tiktok_download.probe_file_quality
            try:
                tiktok_download.probe_file_quality = lambda _filepath: {
                    "width": 1080,
                    "height": 1920,
                    "fps": 60,
                    "codec": "H.265",
                    "label": "1080p (1080Г—1920) В· 60 FPS В· H.265",
                    "confidence": "available",
                    "size": 123,
                }
                worker._emit_tiktok_quality_if_needed([filepath])
            finally:
                tiktok_download.probe_file_quality = original_probe
            self.assertEqual(emitted[0][0], "tt")
            self.assertEqual(emitted[0][1]["codec"], "H.265")
            self.assertIn("1080p", statuses[-1][1])

    def test_source_quality_labels_vertical_2k_and_4k(self):
        two_k = source_quality({
            "width": 1440, "height": 2560, "fps": 60, "vcodec": "h265_hvc1",
        })
        four_k = source_quality({
            "width": 2160, "height": 3840, "fps": 60, "vcodec": "h264",
        })
        self.assertEqual(two_k["label"], "2K (1440×2560) · 60 FPS · H.265")
        self.assertEqual(four_k["label"], "4K (2160×3840) · 60 FPS · H.264")

    def test_preview_prefers_h264_for_player_compatibility(self):
        selected = select_preview_format([
            {"url": "hevc-4k", "vcodec": "h265", "acodec": "aac", "width": 2160, "height": 3840},
            {"url": "h264-1080", "vcodec": "h264", "acodec": "aac", "width": 1080, "height": 1920},
        ], prefer_h264=True)
        self.assertEqual(selected["url"], "h264-1080")

    def test_tiktok_web_challenge_has_actionable_error(self):
        info = classify_download_error(
            "ERROR: [TikTok] 123: Unexpected response from webpage request"
        )
        self.assertEqual(info.category, "tiktok_access")
        self.assertIn("cookies", info.user_text())

    def test_tiktok_collection_challenge_and_empty_list_are_specific(self):
        challenge = classify_download_error(
            "ERROR: [TikTokCollection] demo: Unexpected response from webpage request"
        )
        empty = classify_download_error("TIKTOK_EMPTY_COLLECTION")
        self.assertEqual(challenge.category, "tiktok_access")
        self.assertEqual(empty.category, "tiktok_collection_empty")
        self.assertIn("приватной", empty.user_text())

    def test_watermarked_only_download_has_specific_error(self):
        info = classify_download_error("TIKTOK_NO_CLEAN_FORMAT: requested format is not available")
        self.assertEqual(info.category, "tiktok_no_clean_format")
        self.assertIn("водяного знака", info.user_text())

    def test_dialog_uses_medium_cards_and_selected_urls(self):
        dialog = TikTokCatalogWidget(
            tiktok_url("/@creator"), {"tiktok_card_size": "medium"},
            auto_load=False,
        )
        entries = [
            {"index": 1, "id": "1", "url": tiktok_url("/@creator/video/1"), "title": "One", "thumbnail": "", "source_quality": source_quality({"width": 1080, "height": 1920, "fps": 60, "vcodec": "h264"})},
            {"index": 2, "id": "2", "url": tiktok_url("/@creator/video/2"), "title": "Two", "thumbnail": "", "source_quality": {}},
        ]
        dialog._on_loaded("Creator", entries)
        dialog.show()
        self.app.processEvents()
        first_card = dialog.card_grid.cards[0]
        second_card = dialog.card_grid.cards[1]
        self.assertEqual(first_card.width(), 196)
        self.assertIn("1080p", first_card.quality_label.text())
        QTest.mouseMove(first_card.cover_label, first_card.cover_label.rect().center())
        self.app.processEvents()
        self.assertIs(dialog._pending_card, first_card)
        dialog.preview_timer.stop()
        dialog._accept_selected()
        self.assertIn("Отметьте хотя бы одно", dialog.status_label.text())
        second_card.set_checked(True)
        requests = []
        dialog.download_requested.connect(lambda *args: requests.append(args))
        dialog._accept_selected()
        self.assertEqual(requests[0][0:3], (tiktok_url("/@creator"), "selected", [entries[1]["url"]]))
        self.assertEqual(requests[0][3], "medium")
        per_card = []
        dialog.download_requested.connect(lambda *args: per_card.append(args))
        first_card.download_button.click()
        self.assertEqual(per_card[-1][1:3], ("single", [entries[0]["url"]]))
        dialog.player.stop()
        dialog.close()

    def test_playlist_button_is_separate_and_panel_uses_fifth_card_width(self):
        dialog = TikTokCatalogWidget(tiktok_url("/@creator"), {}, auto_load=False)
        entries = [
            {
                "id": str(index),
                "url": tiktok_url(f"/@creator/video/{index}"),
                "title": str(index),
                "thumbnail": "",
            }
            for index in range(1, 7)
        ]
        dialog._on_loaded(
            "Creator",
            entries,
            [{"title": "Mix", "url": tiktok_url("/@creator/collection/Mix-1")}],
        )
        self.app.processEvents()
        self.assertEqual(dialog.card_grid.max_columns, 4)
        self.assertEqual(dialog.scroll.width(), FOUR_CARD_SCROLL_WIDTH)
        self.assertEqual(dialog.scroll.minimumWidth(), FOUR_CARD_SCROLL_WIDTH)
        self.assertEqual(dialog.scroll.maximumWidth(), FOUR_CARD_SCROLL_WIDTH)
        self.assertEqual(dialog.playlists_panel.width(), 196)
        self.assertEqual(dialog.playlist_btn.text(), "Скачать плейлист")
        requests = []
        dialog.download_requested.connect(lambda *args: requests.append(args))
        dialog.playlist_btn.click()
        self.assertEqual(requests[-1][0], tiktok_url("/@creator/collection/Mix-1"))
        self.assertEqual(requests[-1][1], "playlist")
        dialog.close()

    def test_profile_without_playlists_scroll_ends_after_fifth_card(self):
        dialog = TikTokCatalogWidget(tiktok_url("/@creator"), {}, auto_load=False)
        entries = [
            {
                "id": str(index),
                "url": tiktok_url(f"/@creator/video/{index}"),
                "title": str(index),
                "thumbnail": "",
            }
            for index in range(1, 7)
        ]
        dialog._on_loaded("Creator", entries, [])
        self.app.processEvents()
        self.assertEqual(dialog.card_grid.max_columns, 5)
        self.assertFalse(dialog.playlists_panel.isVisible())
        self.assertEqual(dialog.scroll.width(), FIVE_CARD_SCROLL_WIDTH)
        self.assertEqual(dialog.scroll.minimumWidth(), FIVE_CARD_SCROLL_WIDTH)
        self.assertEqual(dialog.scroll.maximumWidth(), FIVE_CARD_SCROLL_WIDTH)
        dialog.close()

    def test_download_all_profile_emits_individual_card_urls(self):
        dialog = TikTokCatalogWidget(tiktok_url("/@creator"), {}, auto_load=False)
        entries = [
            {
                "id": str(index),
                "url": tiktok_url(f"/@creator/video/{index}"),
                "title": str(index),
                "thumbnail": "",
            }
            for index in range(1, 4)
        ]
        dialog._on_loaded("Creator", entries, [])
        requests = []
        dialog.download_requested.connect(lambda *args: requests.append(args))
        dialog.all_btn.click()
        self.assertEqual(requests[-1][1], "all")
        self.assertEqual(requests[-1][2], [entry["url"] for entry in entries])
        dialog.close()

    def test_ssstik_fallback_uses_external_no_watermark_candidate(self):
        class SignalStub:
            def emit(self, *args):
                pass

        class WorkerStub:
            item_id = "tt"
            url = tiktok_url("/@creator/video/123")
            output_folder = tempfile.gettempdir()
            settings = {"download_type": "video"}
            _cancelled = False
            status = SignalStub()
            info_ready = SignalStub()
            progress = SignalStub()

        original_candidates = tiktok_download.ssstik_video_candidates
        original_tikwm_candidates = tiktok_download.tikwm_video_candidates
        original_download = tiktok_download._download_stream
        original_probe = tiktok_download.probe_file_quality
        calls = []
        def fake_download(worker, url, headers, filepath, impersonate, **_kwargs):
            calls.append((url, headers["Referer"], impersonate))
            with open(filepath, "wb") as handle:
                handle.write(b"fake mp4")
            return filepath
        try:
            tiktok_download.tikwm_video_candidates = lambda url: []
            tiktok_download.ssstik_video_candidates = lambda url: [
                {"url": "https://tikcdn.io/ssstik/123", "referer": "https://ssstik.io/", "impersonate": "chrome131", "label": "regular"}
            ]
            tiktok_download._download_stream = fake_download
            tiktok_download.probe_file_quality = (
                lambda filepath: {"width": 1080, "height": 1920, "fps": 30, "codec": "H.264", "label": "1080p (1080×1920) · 30 FPS · H.264", "size": 123}
            )
            filepath, title = tiktok_download.download_tiktok_ssstik_fallback(
                WorkerStub(), "Demo"
            )
        finally:
            tiktok_download.ssstik_video_candidates = original_candidates
            tiktok_download.tikwm_video_candidates = original_tikwm_candidates
            tiktok_download._download_stream = original_download
            tiktok_download.probe_file_quality = original_probe
        self.assertTrue(filepath.endswith(".mp4"))
        self.assertEqual(title, "Demo")
        self.assertEqual(
            calls,
            [("https://tikcdn.io/ssstik/123", "https://ssstik.io/", "chrome131")],
        )

    def test_ssstik_fallback_keeps_best_verified_quality(self):
        class SignalStub:
            def emit(self, *args):
                pass

        with tempfile.TemporaryDirectory() as folder:
            class WorkerStub:
                item_id = "tt"
                url = tiktok_url("/@creator/video/123")
                output_folder = folder
                settings = {"download_type": "video"}
                _cancelled = False
                status = SignalStub()
                info_ready = SignalStub()
                progress = SignalStub()

            original_candidates = tiktok_download.ssstik_video_candidates
            original_tikwm_candidates = tiktok_download.tikwm_video_candidates
            original_download = tiktok_download._download_stream
            original_probe = tiktok_download.probe_file_quality
            try:
                tiktok_download.tikwm_video_candidates = lambda url: []
                tiktok_download.ssstik_video_candidates = lambda url: [
                    {"url": "https://tikcdn.io/ssstik/low", "referer": "https://ssstik.io/", "impersonate": "chrome131", "label": "low"},
                    {"url": "https://tikcdn.io/ssstik/hd", "referer": "https://ssstik.io/", "impersonate": "chrome131", "label": "hd"},
                ]
                def fake_download(worker, url, headers, filepath, impersonate, **_kwargs):
                    with open(filepath, "wb") as handle:
                        handle.write(url.encode("utf-8"))
                    return filepath
                tiktok_download._download_stream = fake_download
                def fake_probe(filepath):
                    with open(filepath, "rb") as handle:
                        data = handle.read().decode("utf-8")
                    if data.endswith("/hd"):
                        return {"width": 1080, "height": 1920, "fps": 30, "codec": "H.264", "label": "1080p (1080×1920) · 30 FPS · H.264", "size": 200}
                    return {"width": 576, "height": 1024, "fps": 30, "codec": "H.264", "label": "576p (576×1024) · 30 FPS · H.264", "size": 100}
                tiktok_download.probe_file_quality = fake_probe
                filepath, _title = tiktok_download.download_tiktok_ssstik_fallback(
                    WorkerStub(), "Demo"
                )
            finally:
                tiktok_download.ssstik_video_candidates = original_candidates
                tiktok_download.tikwm_video_candidates = original_tikwm_candidates
                tiktok_download._download_stream = original_download
                tiktok_download.probe_file_quality = original_probe
            self.assertTrue(os.path.isfile(filepath))
            with open(filepath, "rb") as handle:
                self.assertEqual(handle.read().decode("utf-8"), "https://tikcdn.io/ssstik/hd")

    def test_external_fallback_prefers_verified_tikwm_hd(self):
        class SignalStub:
            def emit(self, *args):
                pass

        with tempfile.TemporaryDirectory() as folder:
            class WorkerStub:
                item_id = "tt"
                url = tiktok_url("/@creator/video/123")
                output_folder = folder
                settings = {"download_type": "video"}
                _cancelled = False
                status = SignalStub()
                info_ready = SignalStub()
                progress = SignalStub()

            original_ssstik = tiktok_download.ssstik_video_candidates
            original_tikwm = tiktok_download.tikwm_video_candidates
            original_download = tiktok_download._download_stream
            original_probe = tiktok_download.probe_file_quality
            try:
                tiktok_download.tikwm_video_candidates = lambda url: [
                    {"url": "https://tikwm.com/low", "referer": "https://www.tikwm.com/", "impersonate": "chrome131", "label": "regular", "priority": 25},
                    {"url": "https://tikwm.com/hd", "referer": "https://www.tikwm.com/", "impersonate": "chrome131", "label": "hd", "priority": 45},
                ]
                tiktok_download.ssstik_video_candidates = lambda url: [
                    {"url": "https://tikcdn.io/ssstik/low", "referer": "https://ssstik.io/", "impersonate": "chrome131", "label": "low", "priority": 10},
                ]

                def fake_download(worker, url, headers, filepath, impersonate, **_kwargs):
                    with open(filepath, "wb") as handle:
                        handle.write(url.encode("utf-8"))
                    return filepath

                tiktok_download._download_stream = fake_download

                def fake_probe(filepath):
                    with open(filepath, "rb") as handle:
                        data = handle.read().decode("utf-8")
                    if data.endswith("/hd"):
                        return {"width": 1080, "height": 1920, "fps": 60, "codec": "H.265", "label": "1080p (1080Г—1920) В· 60 FPS В· H.265", "size": 300}
                    return {"width": 576, "height": 1024, "fps": 30, "codec": "H.264", "label": "576p (576Г—1024) В· 30 FPS В· H.264", "size": 100}

                tiktok_download.probe_file_quality = fake_probe
                filepath, _title = tiktok_download.download_tiktok_ssstik_fallback(
                    WorkerStub(), "Demo"
                )
            finally:
                tiktok_download.ssstik_video_candidates = original_ssstik
                tiktok_download.tikwm_video_candidates = original_tikwm
                tiktok_download._download_stream = original_download
                tiktok_download.probe_file_quality = original_probe
            with open(filepath, "rb") as handle:
                self.assertEqual(handle.read().decode("utf-8"), "https://tikwm.com/hd")

    def test_hover_preview_prefers_full_stream_before_animated_cover(self):
        dialog = TikTokCatalogWidget(tiktok_url("/@creator"), {}, auto_load=False)
        entry = {
            "id": "1",
            "url": tiktok_url("/@creator/video/1"),
            "title": "One",
            "thumbnail": "",
            "preview_stream_url": "https://cdn.example/full.mp4",
            "preview_headers": {"Referer": "https://www.tiktok.com/"},
        }
        dialog._on_loaded("Creator", [entry])
        card = dialog.card_grid.cards[0]
        card._animated_movie = object()
        played = []
        dialog._play_preview = lambda card_arg, url, headers: played.append(
            (card_arg, url, headers)
        )
        dialog._pending_card = card
        dialog._start_pending_preview()
        self.assertEqual(played[0][1], "https://cdn.example/full.mp4")
        dialog.close()


if __name__ == "__main__":
    unittest.main()
