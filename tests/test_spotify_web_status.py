import tempfile
import unittest
from unittest.mock import patch

import app.web_server as web
from app.spotify_engine import SPOTIFY_ARCHIVE_SKIP


class SpotifyWebStatusTest(unittest.TestCase):
    def test_empty_result_is_error_and_archive_skip_is_not_success(self):
        for result, expected in ((([], ""), "Ошибка"), (([], SPOTIFY_ARCHIVE_SKIP), "Пропущено: есть в архиве")):
            with self.subTest(result=result), tempfile.TemporaryDirectory() as folder:
                tasks = {"case": {"url": "https://open.spotify.com/track/test"}}
                with patch.object(web, "TASKS", tasks), \
                     patch.object(web, "load_settings", return_value={"download_folder": folder, "auto_route_folders": False}), \
                     patch.object(web, "run_spotify_download_callbacks", return_value=result), \
                     patch.object(web, "add_history_entry") as history:
                    web._download_task("case")
                self.assertEqual(tasks["case"]["status"], expected)
                self.assertFalse(history.call_args.args[3])

    def test_partial_error_includes_saved_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            tasks = {"case": {"url": "https://open.spotify.com/album/test"}}
            with patch.object(web, "TASKS", tasks), \
                 patch.object(web, "load_settings", return_value={"download_folder": folder, "auto_route_folders": False}), \
                 patch.object(web, "run_spotify_download_callbacks", return_value=(["saved.mp3"], "write error")), \
                 patch.object(web, "add_history_entry"):
                web._download_task("case")
            self.assertEqual(tasks["case"]["status"], "Ошибка")
            self.assertIn("saved.mp3", tasks["case"]["error"])
            self.assertEqual(tasks["case"]["files"], ["saved.mp3"])
