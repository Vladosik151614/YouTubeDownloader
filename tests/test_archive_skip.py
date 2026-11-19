import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.download_support import ValidatedArchiveYoutubeDL
from app.downloader import DownloadWorker, SKIPPED_ALREADY_DOWNLOADED
from app.main_window import MainWindow
import app.history_store as history_store


class ArchiveSkipTests(unittest.TestCase):
    def test_pause_retains_staging_path(self):
        queue = MagicMock()
        host = SimpleNamespace(_workers={"id": object()}, _active_download_ids={"id"},
                               _paused_urls={"id": "url"}, _item_errors={}, queue_widget=queue,
                               status_label=MagicMock(), _start_next_downloads=MagicMock())
        message = "Отменено пользователем. Незавершённые файлы сохранены: C:\\test\\stage"
        MainWindow._on_download_finished(host, "id", "", False, message)
        self.assertEqual(host._item_errors["id"], message)
        queue.set_result.assert_called_once_with("id", "", message)
        host.status_label.setText.assert_called_once_with(message)

    def test_archived_id_is_counted_once(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = os.path.join(folder, "archive.txt")
            with open(archive, "w", encoding="utf-8") as stream:
                stream.write("youtube example\n")
            with ValidatedArchiveYoutubeDL({"quiet": True, "download_archive": archive}) as ydl:
                self.assertTrue(ydl.in_download_archive({"id": "example", "extractor_key": "Youtube"}))
                self.assertTrue(ydl.in_download_archive({"id": "example", "extractor_key": "Youtube"}))
                self.assertEqual(ydl.skipped_archive_ids, {"youtube example"})
                self.assertEqual(ydl.skipped_archive_entries, set())
                self.assertTrue(ydl.in_download_archive({"id": "example", "extractor_key": "Youtube", "playlist_index": 3}))
                self.assertTrue(ydl.in_download_archive({"id": "example", "extractor_key": "Youtube", "playlist_index": 3}))
                self.assertEqual(ydl.skipped_archive_entries, {("youtube example", 3, "example")})

    def test_preflight_does_not_hide_archived_playlist_entries(self):
        worker = DownloadWorker("id", "https://example.invalid/playlist?list=1", tempfile.gettempdir(), {})
        captured = {}
        class FakeYDL:
            def __init__(self, options):
                captured.update(options)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def extract_info(self, *args, **kwargs):
                return {"entries": [{"id": "x"}]}
        with patch("app.download_support.is_playlist", return_value=True), patch("app.download_support.yt_dlp.YoutubeDL", FakeYDL):
            info, is_fast = worker._playlist_preflight_info({"download_archive": "archive.txt"})
        self.assertTrue(is_fast)
        self.assertEqual(len(info["entries"]), 1)
        self.assertNotIn("download_archive", captured)

    def test_only_skipped_does_not_show_error_or_claim_success(self):
        queue = MagicMock()
        queue.title_text.return_value = "Video"
        host = SimpleNamespace(
            _workers={"id": object()}, _active_download_ids={"id"}, _paused_urls={},
            _item_paths={}, _item_errors={}, _item_urls={"id": "https://example.invalid"},
            _item_produced_files={}, _item_settings={"id": {}}, settings={},
            queue_widget=queue, status_label=MagicMock(),
            _check_and_prompt_conversion=MagicMock(), _start_next_downloads=MagicMock(),
        )
        marker = f"{SKIPPED_ALREADY_DOWNLOADED}:1"
        with patch("app.main_window.add_history_entry") as history, patch("app.main_window.SupportErrorDialog") as dialog:
            MainWindow._on_download_finished(host, "id", "", False, marker)
        queue.set_finished.assert_called_once_with("id", None)
        queue.update_status.assert_called_with("id", "Пропущено: есть в архиве")
        history.assert_called_once_with("https://example.invalid", "Video", "", False, marker)
        dialog.assert_not_called()
        host._check_and_prompt_conversion.assert_not_called()

    def test_single_archive_skip_retries_once_without_archive(self):
        worker = DownloadWorker("id", "https://www.youtube.com/watch?v=example", tempfile.gettempdir(), {})
        worker._fresh_retry_stage = MagicMock()
        worker._download = MagicMock()

        self.assertTrue(worker._retry_after_archive_skip())
        self.assertTrue(worker._archive_retry_used)
        worker._fresh_retry_stage.assert_called_once_with()
        worker._download.assert_called_once_with()
        self.assertFalse(worker._retry_after_archive_skip())

    def test_playlist_archive_skip_never_bypasses_duplicate_protection(self):
        worker = DownloadWorker("id", "https://www.youtube.com/playlist?list=example", tempfile.gettempdir(), {})
        worker._fresh_retry_stage = MagicMock()
        worker._download = MagicMock()

        self.assertFalse(worker._retry_after_archive_skip())
        worker._fresh_retry_stage.assert_not_called()
        worker._download.assert_not_called()

    def test_history_records_skipped_and_mixed_distinctly(self):
        with tempfile.TemporaryDirectory() as folder:
            history_file = os.path.join(folder, "history.json")
            with patch.object(history_store, "APP_DATA_DIR", folder), patch.object(history_store, "HISTORY_FILE", history_file):
                history_store.add_history_entry("", "skip", "", False, f"{SKIPPED_ALREADY_DOWNLOADED}:1")
                history_store.add_history_entry("", "mixed", folder, True, f"{SKIPPED_ALREADY_DOWNLOADED}:1")
                records = history_store.load_history()
            self.assertEqual([r["status"] for r in records], ["success_with_skips", "skipped"])
            self.assertIn("наличие файла не проверялось", records[1]["error"])
