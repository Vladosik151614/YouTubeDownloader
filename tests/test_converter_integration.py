import os
import subprocess
import tempfile
import unittest

from app.converter import ConvertWorker, probe_codec, probe_video_info


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


if __name__ == "__main__":
    unittest.main()
