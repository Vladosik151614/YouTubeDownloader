import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.main_window import MainWindow


class PartialPlaylistTests(unittest.TestCase):
    def test_partial_playlist_files_are_processed_without_hiding_failure(self):
        queue = MagicMock()
        queue.title_text.return_value = "Playlist"
        host = SimpleNamespace(
            _workers={"id": object()}, _active_download_ids={"id"}, _paused_urls={},
            _item_paths={}, _item_errors={}, _item_urls={"id": "https://example.invalid/playlist"},
            _item_produced_files={"id": ["/saved/video.mp4"]},
            _item_settings={"id": {"auto_convert": True}}, settings={},
            queue_widget=queue, status_label=MagicMock(),
            _check_and_prompt_conversion=MagicMock(), _start_next_downloads=MagicMock(),
        )
        with patch("app.main_window.add_history_entry"), patch("app.main_window.SupportErrorDialog"):
            MainWindow._on_download_finished(host, "id", "/saved", False, "Частичная ошибка")
        queue.set_finished.assert_called_once_with("id", False)
        queue.update_status.assert_called_with("id", "Ошибка")
        host._check_and_prompt_conversion.assert_called_once_with(
            ["/saved/video.mp4"], is_playlist=False,
            settings={"auto_convert": True}, item_id="id",
        )
