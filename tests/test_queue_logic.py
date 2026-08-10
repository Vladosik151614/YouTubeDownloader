import unittest

from app.download_utils import _best_thumbnail, media_size_bytes, playlist_entry_rows


class QueueDataLogicTests(unittest.TestCase):
    def test_thumbnail_accepts_cdn_url_without_extension(self):
        url = "https://cdn.example.test/image?id=42"
        self.assertEqual(_best_thumbnail("", [{"url": url, "width": 320, "height": 180}]), url)

    def test_thumbnail_prefers_larger_image_at_same_preference(self):
        thumbnails = [
            {"url": "small", "width": 120, "height": 90},
            {"url": "large", "width": 1280, "height": 720},
        ]
        self.assertEqual(_best_thumbnail("", thumbnails), "large")

    def test_media_size_uses_direct_or_requested_format_sum(self):
        self.assertEqual(media_size_bytes({"filesize": 123}), 123)
        self.assertEqual(
            media_size_bytes({"requested_formats": [{"filesize": 100}, {"filesize_approx": 25}]}),
            125,
        )

    def test_playlist_rows_include_size_and_stable_fallback_index(self):
        rows = playlist_entry_rows([
            {"title": "One", "filesize": 1024},
            {"title": "Two", "playlist_index": 7},
        ])
        self.assertEqual(rows[0]["index"], 1)
        self.assertEqual(rows[0]["size_bytes"], 1024)
        self.assertEqual(rows[0]["size"], "1.0 KB")
        self.assertEqual(rows[1]["index"], 7)


if __name__ == "__main__":
    unittest.main()
