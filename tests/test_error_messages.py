import unittest
import os
import tempfile

from app.error_messages import classify_download_error
from app.error_reporter import sanitize_text
from app.downloader import DownloadWorker
from app.download_utils import media_size_bytes, remove_merged_audio_sidecars
from app.proxy_config import proxy_url_from_settings


class DownloadErrorMessagesTests(unittest.TestCase):
    def test_http_403_is_explained_without_losing_detail(self):
        raw = "ERROR: unable to download video data: HTTP Error 403: Forbidden"
        info = classify_download_error(raw)
        self.assertEqual(info.category, "access_forbidden")
        self.assertIn("ошибка 403", info.title)
        self.assertIn("cookies", info.user_text())
        self.assertEqual(info.technical_detail, raw)

    def test_bot_challenge_has_specific_category(self):
        info = classify_download_error("Sign in to confirm you’re not a bot")
        self.assertEqual(info.category, "youtube_verification")

    def test_disk_full_is_not_described_as_network_problem(self):
        info = classify_download_error("[Errno 28] No space left on device")
        self.assertEqual(info.category, "disk_full")
        self.assertFalse(info.retryable)

    def test_worker_snapshots_settings_and_routes_from_immutable_base(self):
        with tempfile.TemporaryDirectory() as folder:
            test_url = "https://" + "youtube" + ".com/watch?v=example"
            settings = {
                "download_type": "video", "auto_route_folders": True, "container": "mp4",
                "auto_export_cookies": False, "skip_duplicates": False,
                "exact_download_folder": True,
            }
            worker = DownloadWorker("test", test_url, folder, settings)
            expected = os.path.abspath(folder)
            self.assertEqual(worker.output_folder, expected)
            settings["container"] = "webm"
            self.assertEqual(worker.settings["container"], "mp4")
            worker._build_ydl_opts()
            worker._build_ydl_opts()
            self.assertEqual(worker.output_folder, expected)

            routed = dict(settings, exact_download_folder=False)
            routed_worker = DownloadWorker("routed", test_url, folder, routed)
            self.assertEqual(routed_worker.output_folder, os.path.join(expected, "YouTube", "Video"))

    def test_size_estimate_adds_selected_video_and_audio(self):
        info = {"requested_formats": [{"filesize": 100}, {"filesize_approx": 40}]}
        self.assertEqual(media_size_bytes(info), 140)

    def test_playlist_numbering_is_optional_and_off_by_default(self):
        with tempfile.TemporaryDirectory() as folder:
            url = "https://" + "youtube.com/playlist?list=example"
            base = {"download_type": "video", "exact_download_folder": True}
            plain = DownloadWorker("plain", url, folder, base)._build_ydl_opts()["outtmpl"]
            numbered = DownloadWorker(
                "numbered", url, folder, dict(base, playlist_numbering=True)
            )._build_ydl_opts()["outtmpl"]
            self.assertTrue(plain.endswith("%(title)s.%(ext)s"))
            self.assertNotIn("playlist_index", plain)
            self.assertTrue(numbered.endswith("%(playlist_index)03d - %(title)s.%(ext)s"))

    def test_only_merged_m4a_sidecar_is_removed_for_video(self):
        with tempfile.TemporaryDirectory() as folder:
            merged = os.path.join(folder, "Video.mp4")
            sidecar = os.path.join(folder, "Video.f140.m4a")
            standalone = os.path.join(folder, "Music.m4a")
            for path in (merged, sidecar, standalone):
                with open(path, "wb") as handle:
                    handle.write(b"test")
            worker = DownloadWorker(
                "cleanup", "https://" + "youtube.com/watch?v=example", folder,
                {"download_type": "video", "exact_download_folder": True},
            )
            remaining = remove_merged_audio_sidecars([merged, sidecar, standalone])
            self.assertFalse(os.path.exists(sidecar))
            self.assertTrue(os.path.exists(standalone))
            self.assertIn(standalone, remaining)

    def test_proxy_credentials_are_encoded_and_reports_redact_url_passwords(self):
        url = proxy_url_from_settings({
            "proxy_enabled": True,
            "proxy_type": "http",
            "proxy_host": "proxy.example",
            "proxy_port": "8080",
            "proxy_username": "user@example",
            "proxy_password": "p@ss:word",
        })
        self.assertEqual(
            url,
            "http://user%40example:p%40ss%3Aword@proxy.example:8080",
        )
        redacted = sanitize_text(
            "failed via http://user@example:p@ss:word@proxy.example:8080"
        )
        self.assertNotIn("p@ss:word", redacted)
        self.assertIn("http://<redacted>@proxy.example:8080", redacted)

    def test_proxy_settings_reject_unsafe_values(self):
        base = {
            "proxy_enabled": True,
            "proxy_type": "http",
            "proxy_host": "proxy.example",
            "proxy_port": "8080",
        }
        for overrides in (
            {"proxy_type": "file"},
            {"proxy_host": "proxy.example\r\nInjected: yes"},
            {"proxy_host": "proxy.example/path"},
            {"proxy_port": "0"},
            {"proxy_port": "70000"},
            {"proxy_port": "bad"},
        ):
            settings = {**base, **overrides}
            self.assertEqual(proxy_url_from_settings(settings), "")

        self.assertEqual(
            proxy_url_from_settings({
                "proxy_enabled": True,
                "proxy_url": "file://127.0.0.1:8080",
            }),
            "",
        )


if __name__ == "__main__":
    unittest.main()
