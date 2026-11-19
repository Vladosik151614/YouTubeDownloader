import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch

from app import converter


class ConverterProfileTests(unittest.TestCase):
    def test_cancel_during_initial_probe_prevents_further_work(self):
        worker = converter.ConvertWorker('source.mp4', {})
        results = []
        worker.finished.connect(lambda *args: results.append(args))
        def cancel_during_probe(_path):
            worker.cancel()
            return {'width': 640, 'height': 360, 'fps': 30, 'codec': 'h264'}
        with patch('app.converter.probe_video_info', side_effect=cancel_during_probe), \
             patch('app.converter.probe_audio_presence') as audio_probe, \
             patch('app.converter.subprocess.Popen') as process:
            worker._convert()
        audio_probe.assert_not_called()
        process.assert_not_called()
        self.assertEqual(results[0][3], 'Отменено пользователем')

    def test_probe_uses_fallback_fps_when_average_is_zero_over_zero(self):
        stream = {"codec_name": "h264", "width": 1280, "height": 720,
                  "avg_frame_rate": "0/0", "r_frame_rate": "30000/1001"}
        with patch("app.converter.subprocess.run", return_value=SimpleNamespace(stdout=json.dumps({"streams": [stream]}))):
            info = converter.probe_video_info("sample.mp4")
        self.assertEqual(info["width"], 1280)
        self.assertAlmostEqual(info["fps"], 29.97, places=2)

    def test_upscale_requires_explicit_opt_in(self):
        original_probe = converter.probe_video_info
        try:
            converter.probe_video_info = lambda _path: {
                "codec": "h264", "width": 720, "height": 1280, "fps": 30.0,
            }
            base = {
                "default_codec": "original",
                "container": "mp4",
                "download_quality": "1080",
                "upscale_target": "1440",
                "fps_limit": "60",
            }
            self.assertNotIn(
                "upscale",
                converter.profile_conversion_reasons("video.mp4", base),
            )
            with_upscale = dict(base, upscale_to_profile=True)
            self.assertIn(
                "upscale",
                converter.profile_conversion_reasons("video.mp4", with_upscale),
            )
            self.assertIn(
                "fps_upscale",
                converter.profile_conversion_reasons("video.mp4", with_upscale),
            )
            self.assertEqual(converter.target_resolution(with_upscale), "1440")
        finally:
            converter.probe_video_info = original_probe

    def test_tiktok_landscape_rotation_requires_normalization(self):
        original_probe = converter.probe_video_info
        try:
            converter.probe_video_info = lambda _path: {
                "codec": "h264", "width": 1080, "height": 1920, "fps": 30.0,
                "rotation": 90, "display_width": 1920, "display_height": 1080,
            }
            settings = {
                "default_codec": "original",
                "container": "mp4",
                "download_quality": "1080",
                "fps_limit": "60",
                "source_url": "https://www.tiktok.com/@creator/video/123",
                "normalize_tiktok_landscape": True,
            }
            self.assertIn(
                "tiktok_landscape",
                converter.profile_conversion_reasons("video.mp4", settings),
            )
            self.assertNotIn(
                "tiktok_landscape",
                converter.profile_conversion_reasons(
                    "video.mp4",
                    dict(settings, source_url="https://" + "youtube.com/watch?v=demo"),
                ),
            )
        finally:
            converter.probe_video_info = original_probe


if __name__ == "__main__":
    unittest.main()
