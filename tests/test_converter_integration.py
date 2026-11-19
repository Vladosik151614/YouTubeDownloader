import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from app.converter import ConvertWorker, probe_audio_presence, probe_codec, probe_video_info


class ConverterIntegrationTests(unittest.TestCase):
    def setUp(self):
        if not os.path.isfile(os.environ.get("YTD_TEST_FFMPEG", "")):
            self.skipTest("YTD_TEST_FFMPEG is not configured")
        self.ffmpeg = os.environ["YTD_TEST_FFMPEG"]

    def _source_video(self, folder: str) -> str:
        path = os.path.join(folder, "source.avi")
        subprocess.run([
            self.ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=10",
            "-t", "1", "-c:v", "mpeg4", path,
        ], check=True, capture_output=True)
        return path

    def _rotated_tiktok_video(self, folder: str) -> str:
        source = os.path.join(folder, "portrait-source.mp4")
        rotated = os.path.join(folder, "tiktok-rotated.mp4")
        subprocess.run([
            self.ffmpeg, "-y", "-f", "lavfi",
            "-i", "testsrc=size=1080x1920:rate=5",
            "-t", "1", "-c:v", "libx264", source,
        ], check=True, capture_output=True)
        subprocess.run([
            self.ffmpeg, "-y", "-display_rotation", "90",
            "-i", source, "-c", "copy", rotated,
        ], check=True, capture_output=True)
        return rotated

    def test_verified_h264_conversion_removes_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self._source_video(folder)
            result = []
            worker = ConvertWorker(source, {
                "default_codec": "h264", "encoding_mode": "cpu_only",
                "video_encoder": "libx264", "keep_originals": False,
            })
            worker.finished.connect(lambda src, out, ok, error: result.append((src, out, ok, error)))
            worker._convert()
            self.assertTrue(result and result[0][2], result)
            output = result[0][1]
            self.assertFalse(os.path.exists(source))
            self.assertTrue(os.path.getsize(output) > 0)
            self.assertEqual(probe_codec(output), "h264")
            self.assertFalse(any(".part-" in name for name in os.listdir(folder)))

    def test_encoder_failure_preserves_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self._source_video(folder)
            worker = ConvertWorker(source, {
                "default_codec": "h264", "encoding_mode": "gpu_only",
                "video_encoder": "definitely_missing_encoder", "keep_originals": False,
            })
            result = []
            worker.finished.connect(lambda src, out, ok, error: result.append((src, out, ok, error)))
            worker.run()
            self.assertTrue(os.path.isfile(source))
            self.assertTrue(result and not result[0][2], result)
            self.assertFalse(any(".part-" in name for name in os.listdir(folder)))

    def test_profile_applies_container_resolution_and_fps(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self._source_video(folder)
            result = []
            worker = ConvertWorker(source, {
                "default_codec": "h264",
                "container": "mp4",
                "download_quality": "60",
                "fps_limit": "5",
                "encoding_mode": "cpu_only",
                "video_encoder": "libx264",
                "keep_originals": False,
            })
            worker.finished.connect(
                lambda src, out, ok, error: result.append((src, out, ok, error))
            )
            worker._convert()
            self.assertTrue(result and result[0][2], result)
            output = result[0][1]
            info = probe_video_info(output)
            self.assertEqual(os.path.splitext(output)[1].lower(), ".mp4")
            self.assertLessEqual(min(info["width"], info["height"]), 60)
            self.assertLessEqual(info["fps"], 5.1)

    def test_profile_upscale_is_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self._source_video(folder)
            worker = ConvertWorker(source, {
                "default_codec": "h264",
                "container": "mp4",
                "download_quality": "60",
                "upscale_target": "180",
                "fps_limit": "20",
                "upscale_to_profile": True,
                "encoding_mode": "cpu_only",
                "video_encoder": "libx264",
                "keep_originals": False,
            })
            result = []
            worker.finished.connect(lambda src, out, ok, error: result.append((src, out, ok, error)))
            worker._convert()
            self.assertTrue(result and result[0][2], result)
            info = probe_video_info(result[0][1])
            self.assertEqual(min(info["width"], info["height"]), 180)
            self.assertGreaterEqual(info["fps"], 19.0)
            output_duration = ConvertWorker(result[0][1], {})._get_duration()
            self.assertGreaterEqual(output_duration, 0.95)

    def test_tiktok_rotated_landscape_is_saved_as_real_16x9(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self._rotated_tiktok_video(folder)
            before = probe_video_info(source)
            self.assertEqual(abs(before["rotation"]), 90)
            self.assertGreater(before["display_width"], before["display_height"])
            worker = ConvertWorker(source, {
                "default_codec": "original",
                "container": "mp4",
                "download_quality": "1080",
                "fps_limit": "60",
                "source_url": "https://www.tiktok.com/@creator/video/123",
                "normalize_tiktok_landscape": True,
                "encoding_mode": "cpu_only",
                "video_encoder": "libx264",
                "keep_originals": False,
            })
            result = []
            worker.finished.connect(
                lambda src, out, ok, error: result.append((src, out, ok, error))
            )
            worker._convert()
            self.assertTrue(result and result[0][2], result)
            output = result[0][1]
            after = probe_video_info(output)
            self.assertGreater(after["width"], after["height"])
            self.assertEqual(abs(after["rotation"]), 0)
            self.assertAlmostEqual(after["width"] / after["height"], 16 / 9, places=1)
            self.assertFalse(os.path.exists(source))

    def test_upscale_and_rotation_preserve_video_and_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            portrait = os.path.join(folder, "portrait.mp4")
            source = os.path.join(folder, "rotated.mp4")
            subprocess.run([
                self.ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc=size=90x160:rate=10",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
                "-t", "1", "-c:v", "libx264", "-c:a", "aac", portrait,
            ], check=True, capture_output=True)
            subprocess.run([self.ffmpeg, "-y", "-display_rotation", "90", "-i", portrait,
                            "-c", "copy", source], check=True, capture_output=True)
            worker = ConvertWorker(source, {
                "default_codec": "h264", "container": "mp4", "encoding_mode": "cpu_only",
                "video_encoder": "libx264", "fps_limit": "10", "upscale_to_profile": True,
                "upscale_target": "144", "source_url": "https://www.tiktok.com/@x/video/1",
                "keep_originals": False,
            })
            result = []
            worker.finished.connect(lambda src, out, ok, error: result.append((src, out, ok, error)))
            worker.run()
            self.assertTrue(result and result[0][2], result)
            info = probe_video_info(result[0][1])
            self.assertEqual(info["height"], 144)
            self.assertEqual(info["width"], 256)
            self.assertTrue(probe_audio_presence(result[0][1]))
            self.assertFalse(os.path.exists(source))

    def test_failed_source_audio_probe_keeps_original(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self._source_video(folder)
            worker = ConvertWorker(source, {"default_codec": "h264", "keep_originals": False})
            result = []
            worker.finished.connect(lambda src, out, ok, error: result.append((src, out, ok, error)))
            with patch("app.converter.probe_audio_presence", return_value=None):
                worker.run()
            self.assertTrue(os.path.isfile(source))
            self.assertTrue(result and not result[0][2], result)

    def test_rotation_only_does_not_apply_disabled_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            portrait = os.path.join(folder, "portrait.mp4")
            source = os.path.join(folder, "rotated.mp4")
            subprocess.run([
                self.ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc=size=90x160:rate=10",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
                "-t", "1", "-c:v", "libx264", "-c:a", "aac", portrait,
            ], check=True, capture_output=True)
            subprocess.run([self.ffmpeg, "-y", "-display_rotation", "90", "-i", portrait,
                            "-c", "copy", source], check=True, capture_output=True)
            worker = ConvertWorker(source, {
                "default_codec": "vp9", "container": "webm", "encoding_mode": "cpu_only",
                "fps_limit": "30", "upscale_to_profile": True, "upscale_target": "144",
                "source_url": "https://www.tiktok.com/@x/video/1", "rotation_only": True,
                "keep_originals": False,
            })
            result = []
            worker.finished.connect(lambda src, out, ok, error: result.append((src, out, ok, error)))
            worker.run()
            self.assertTrue(result and result[0][2], result)
            info = probe_video_info(result[0][1])
            self.assertEqual((info["width"], info["height"]), (160, 90))
            self.assertAlmostEqual(info["fps"], 10, places=1)
            self.assertEqual(info["codec"], "h264")
            self.assertEqual(os.path.splitext(result[0][1])[1], ".mp4")
            self.assertTrue(probe_audio_presence(result[0][1]))

    def test_auto_gpu_error_retries_with_cpu(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self._source_video(folder)
            worker = ConvertWorker(source, {
                "default_codec": "h264", "encoding_mode": "gpu_auto", "keep_originals": True,
            })
            result, messages = [], []
            worker.finished.connect(lambda src, out, ok, error: result.append((src, out, ok, error)))
            worker.log_line.connect(lambda _path, line: messages.append(line))
            # Invalid GPU option deterministically exercises a real ffmpeg failure.
            with patch("app.converter._select_h264_encoder", return_value=(
                "h264_nvenc", ["-invalid_gpu_test_option"], "test GPU"
            )):
                worker.run()
            self.assertTrue(result and result[0][2], result)
            self.assertTrue(os.path.isfile(result[0][1]))
            self.assertTrue(any("процессор" in text for text in messages))


if __name__ == "__main__":
    unittest.main()
