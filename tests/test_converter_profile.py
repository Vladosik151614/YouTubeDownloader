import unittest

from app import converter


class ConverterProfileTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
