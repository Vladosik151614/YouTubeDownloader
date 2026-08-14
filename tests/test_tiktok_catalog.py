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
from app import tiktok_external
from app import tiktok_metadata
from app.tiktok_metadata import (
    apply_downloadable_quality,
    resolve_downloadable_quality_batch,
    source_quality,
)
from app.tiktok_quality import download_quality_score
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

    def test_tiktok_download_is_capped_at_full_hd_even_with_upscale_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            worker = DownloadWorker("tt", tiktok_url("/@creator/video/123"), folder, {
                "download_type": "video", "download_quality": "2160", "fps_limit": "best",
                "upscale_to_profile": True, "upscale_target": "2160",
                "container": "mp4", "exact_download_folder": True,
            })
            options = worker._build_ydl_opts()
            self.assertIn("[height<=1080][fps<=60]", options["format"])
            self.assertNotIn("[height<=2160]", options["format"])

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

    def test_tiktok_does_not_enable_unavailable_impersonation_by_default(self):
        with tempfile.TemporaryDirectory() as folder:
            worker = DownloadWorker("tt", tiktok_url("/@creator/video/123"), folder, {
                "download_type": "video", "download_quality": "best",
                "fps_limit": "best", "container": "mp4",
                "exact_download_folder": True,
            })
            options = worker._build_ydl_opts()
            self.assertNotIn("impersonate", options)

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

    def test_download_quality_prefers_audio_before_silent_hd(self):
        silent_full_hd = {
            "width": 1080, "height": 1920, "fps": 60,
            "filesize": 5_000_000, "has_audio": False,
        }
        playable_hd = {
            "width": 720, "height": 1280, "fps": 30,
            "filesize": 3_000_000, "has_audio": True,
        }
        self.assertGreater(
            download_quality_score(playable_hd),
            download_quality_score(silent_full_hd),
        )

    def test_source_quality_uses_full_hd_plus_for_large_sources(self):
        over_full_hd = source_quality({
            "width": 1440, "height": 2560, "fps": 60, "vcodec": "h265_hvc1",
        })
        very_large = source_quality({
            "width": 2160, "height": 3840, "fps": 60, "vcodec": "h264",
        })
        self.assertEqual(over_full_hd["label"], "1080p+ (1440×2560) · 60 FPS · H.265")
        self.assertEqual(very_large["label"], "1080p+ (2160×3840) · 60 FPS · H.264")

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

    def test_card_shows_live_quality_probe_state(self):
        dialog = TikTokCatalogWidget(tiktok_url("/@creator"), {}, auto_load=False)
        entry = {
            "index": 1,
            "id": "1",
            "url": tiktok_url("/@creator/video/1"),
            "title": "One",
            "thumbnail": "",
            "source_quality": {
                "label": "720p (720×1280) · 30 FPS · H.264",
                "confidence": "reported",
            },
        }
        dialog._on_loaded("Creator", [entry], [])
        card = dialog.card_grid.cards[0]
        self.assertIn("Проверяем реальное качество", card.quality_label.text())
        self.assertIn("720p", card.quality_label.text())
        self.assertTrue(card._quality_loading_timer.isActive())
        first_text = card.quality_label.text()
        card._animate_quality_loading()
        self.assertNotEqual(first_text, card.quality_label.text())
        card.apply_resolved_quality({
            "label": "1080p (1080×1920) · 60 FPS · H.265",
            "confidence": "available",
        })
        self.assertIn("Макс. доступно", card.quality_label.text())
        self.assertIn("1080p", card.quality_label.text())
        self.assertFalse(card._quality_loading_timer.isActive())
        dialog.close()

    def test_card_marks_quality_probe_failure_without_endless_loading(self):
        dialog = TikTokCatalogWidget(tiktok_url("/@creator"), {}, auto_load=False)
        entry = {
            "index": 1,
            "id": "1",
            "url": tiktok_url("/@creator/video/1"),
            "title": "One",
            "thumbnail": "",
            "source_quality": {
                "label": "720p (720×1280) · 30 FPS · H.264",
                "confidence": "reported",
            },
        }
        dialog._on_loaded("Creator", [entry], [])
        card = dialog.card_grid.cards[0]
        card.apply_resolved_quality({"probe_failed": True})
        self.assertIn("Не удалось подтвердить HD", card.quality_label.text())
        self.assertIn("720p", card.quality_label.text())
        self.assertFalse(card._quality_loading_timer.isActive())
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

    def test_external_fallback_uses_tikwm_no_watermark_candidate(self):
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
            tiktok_download.tikwm_video_candidates = lambda url: [
                {"url": "https://tikwm.com/123", "referer": "https://www.tikwm.com/", "impersonate": "chrome131", "label": "regular"}
            ]
            tiktok_download._download_stream = fake_download
            tiktok_download.probe_file_quality = (
                lambda filepath: {"width": 1080, "height": 1920, "fps": 30, "codec": "H.264", "label": "1080p (1080×1920) · 30 FPS · H.264", "size": 123}
            )
            filepath, title = tiktok_download.download_tiktok_external_quality_fallback(
                WorkerStub(), "Demo"
            )
        finally:
            tiktok_download.tikwm_video_candidates = original_tikwm_candidates
            tiktok_download._download_stream = original_download
            tiktok_download.probe_file_quality = original_probe
        self.assertTrue(filepath.endswith(".mp4"))
        self.assertEqual(title, "Demo")
        self.assertEqual(
            calls,
            [("https://tikwm.com/123", "https://www.tikwm.com/", "chrome131")],
        )

    def test_external_fallback_keeps_best_verified_tikwm_quality(self):
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

            original_tikwm_candidates = tiktok_download.tikwm_video_candidates
            original_download = tiktok_download._download_stream
            original_probe = tiktok_download.probe_file_quality
            try:
                tiktok_download.tikwm_video_candidates = lambda url: [
                    {"url": "https://tikwm.com/low", "referer": "https://www.tikwm.com/", "impersonate": "chrome131", "label": "low"},
                    {"url": "https://tikwm.com/hd", "referer": "https://www.tikwm.com/", "impersonate": "chrome131", "label": "hd"},
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
                filepath, _title = tiktok_download.download_tiktok_external_quality_fallback(
                    WorkerStub(), "Demo"
                )
            finally:
                tiktok_download.tikwm_video_candidates = original_tikwm_candidates
                tiktok_download._download_stream = original_download
                tiktok_download.probe_file_quality = original_probe
            self.assertTrue(os.path.isfile(filepath))
            with open(filepath, "rb") as handle:
                self.assertEqual(handle.read().decode("utf-8"), "https://tikwm.com/hd")

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

            original_tikwm = tiktok_download.tikwm_video_candidates
            original_download = tiktok_download._download_stream
            original_probe = tiktok_download.probe_file_quality
            try:
                tiktok_download.tikwm_video_candidates = lambda url: [
                    {"url": "https://tikwm.com/low", "referer": "https://www.tikwm.com/", "impersonate": "chrome131", "label": "regular", "priority": 25},
                    {"url": "https://tikwm.com/hd", "referer": "https://www.tikwm.com/", "impersonate": "chrome131", "label": "hd", "priority": 45},
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
                filepath, _title = tiktok_download.download_tiktok_external_quality_fallback(
                    WorkerStub(), "Demo"
                )
            finally:
                tiktok_download.tikwm_video_candidates = original_tikwm
                tiktok_download._download_stream = original_download
                tiktok_download.probe_file_quality = original_probe
            with open(filepath, "rb") as handle:
                self.assertEqual(handle.read().decode("utf-8"), "https://tikwm.com/hd")

    def test_tikwm_best_quality_probes_candidates_before_labeling_cards(self):
        original_candidates = tiktok_external.tikwm_video_candidates
        original_probe = tiktok_external.probe_remote_quality
        try:
            tiktok_external.tikwm_video_candidates = lambda url: [
                {"url": "https://tikwm.com/low", "referer": "https://www.tikwm.com/", "label": "low"},
                {"url": "https://tikwm.com/hd", "referer": "https://www.tikwm.com/", "label": "hd"},
            ]

            def fake_probe(url, headers):
                if url.endswith("/hd"):
                    return {
                        "width": 1080, "height": 1920, "fps": 60,
                        "codec": "H.265", "label": "1080p (1080×1920) · 60 FPS · H.265",
                        "has_audio": True, "size": 300,
                    }
                return {
                    "width": 576, "height": 1024, "fps": 30,
                    "codec": "H.264", "label": "576p (576×1024) · 30 FPS · H.264",
                    "has_audio": True, "size": 100,
                }

            tiktok_external.probe_remote_quality = fake_probe
            quality = tiktok_external.tikwm_best_quality(tiktok_url("/@creator/video/123"))
        finally:
            tiktok_external.tikwm_video_candidates = original_candidates
            tiktok_external.probe_remote_quality = original_probe
        self.assertEqual(quality["candidate_label"], "hd")
        self.assertEqual(quality["width"], 1080)
        self.assertEqual(quality["fps"], 60)

    def test_catalog_entries_use_verified_downloadable_quality_limit(self):
        original_best_quality = tiktok_metadata.tikwm_best_quality
        try:
            tiktok_metadata.tikwm_best_quality = lambda url: {
                "width": 1080 if url.endswith("/1") else 720,
                "height": 1920 if url.endswith("/1") else 1280,
                "fps": 60,
                "codec": "H.265",
                "label": "1080p (1080×1920) · 60 FPS · H.265" if url.endswith("/1") else "720p (720×1280) · 60 FPS · H.265",
                "confidence": "available" if url.endswith("/1") else "limited",
                "has_audio": True,
                "size": 123,
            }
            entries = [
                {"url": tiktok_url("/@creator/video/1"), "source_quality": {"label": "576p"}},
                {"url": tiktok_url("/@creator/video/2"), "source_quality": {"label": "576p"}},
            ]
            apply_downloadable_quality(entries, 1)
        finally:
            tiktok_metadata.tikwm_best_quality = original_best_quality
        self.assertIn("1080p", entries[0]["source_quality"]["label"])
        self.assertEqual(entries[1]["source_quality"]["label"], "576p")

    def test_downloadable_quality_batch_respects_limit_and_returns_results(self):
        original_best_quality = tiktok_metadata.tikwm_best_quality
        try:
            tiktok_metadata.tikwm_best_quality = lambda url: {
                "width": 1080,
                "height": 1920,
                "fps": 60,
                "codec": "H.265",
                "label": f"verified {url.rsplit('/', 1)[-1]}",
                "has_audio": True,
                "size": 100,
            }
            entries = [
                {"url": tiktok_url(f"/@creator/video/{index}")}
                for index in range(1, 6)
            ]
            results = list(
                resolve_downloadable_quality_batch(
                    entries, probe_limit=3, max_workers=2,
                )
            )
        finally:
            tiktok_metadata.tikwm_best_quality = original_best_quality
        self.assertEqual(len(results), 3)
        self.assertEqual({url.rsplit("/", 1)[-1] for url, _ in results}, {"1", "2", "3"})

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
