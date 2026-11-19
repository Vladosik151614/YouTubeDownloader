import os
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app.upscale_page import UpscalePage


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class UpscalePageTests(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        _app()

    def test_processing_settings_are_standalone_upscale_profile(self):
        page = UpscalePage({
            "container": "mkv",
            "default_codec": "original",
            "fps_limit": "30",
            "upscale_target": "2160",
            "video_encoder": "libx264",
        })
        page.target_combo.setCurrentIndex(0)
        page.fps_combo.setCurrentIndex(0)
        page.container_combo.setCurrentIndex(0)
        page.codec_combo.setCurrentIndex(0)
        page.encoder_combo.setCurrentIndex(1)
        page.keep_originals_check.setChecked(True)
        page.set_source_file = lambda _path: True
        page.source_path = os.path.abspath("input.mp4")
        page.set_output_folder(os.path.abspath("out"))

        settings = page.build_processing_settings()

        self.assertEqual(settings["download_type"], "video")
        self.assertEqual(settings["download_quality"], "1440")
        self.assertEqual(settings["upscale_target"], "1440")
        self.assertTrue(settings["upscale_to_profile"])
        self.assertEqual(settings["fps_limit"], "60")
        self.assertEqual(settings["container"], "mp4")
        self.assertEqual(settings["default_codec"], "h264")
        self.assertEqual(settings["encoding_mode"], "cpu_only")
        self.assertEqual(settings["video_encoder"], "libx264")
        self.assertTrue(settings["keep_originals"])
        self.assertEqual(settings["output_folder"], os.path.abspath("out"))
        self.assertFalse(settings["ask_before_codec_convert"])

    def test_thread_retained_until_native_finish_and_stopped_on_close(self):
        from PySide6.QtCore import QEventLoop, QThread, QTimer
        from app.converter import ConvertWorker

        class SlowConvertWorker(ConvertWorker):
            def _convert(self):
                self.finished.emit(self.filepath, '', False, 'synthetic')
                QThread.msleep(120)

        page = UpscalePage({})
        page.source_path = os.path.abspath('input.mp4')
        emitted = []
        page._on_finished = lambda *args: emitted.append(args)
        with patch('app.upscale_page.ConvertWorker', SlowConvertWorker):
            self.assertTrue(page.start_processing())
        worker = page._worker
        loop = QEventLoop()
        poll = QTimer()
        poll.setInterval(5)
        poll.timeout.connect(lambda: loop.quit() if emitted else None)
        poll.start()
        QTimer.singleShot(5000, loop.quit)
        loop.exec()
        poll.stop()
        self.assertTrue(emitted)
        self.assertTrue(worker.isRunning())
        self.assertIn(worker, page._live_processing_threads)
        page.close()
        self.assertFalse(worker.isRunning())
        self.assertEqual(page._live_processing_threads, set())

    def test_upscale_shutdown_wait_is_bounded_for_uncooperative_worker(self):
        from PySide6.QtCore import QEventLoop, QThread, QTimer
        from app.converter import ConvertWorker

        class SlowConvertWorker(ConvertWorker):
            def _convert(self):
                QThread.msleep(1500)

        page = UpscalePage({})
        worker = SlowConvertWorker('input.mp4', {}, page)
        page._live_processing_threads.add(worker)
        worker.start()
        started = time.monotonic()
        page._stop_processing_threads()
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 1.2)
        self.assertTrue(worker.isRunning())
        self.assertIn(worker, page._live_processing_threads)
        loop = QEventLoop()
        poll = QTimer()
        poll.setInterval(10)
        poll.timeout.connect(lambda: loop.quit() if not worker.isRunning() else None)
        poll.start()
        QTimer.singleShot(4000, loop.quit)
        loop.exec()
        poll.stop()
        page._finalize_processing_thread(worker)
        self.assertFalse(worker.isRunning())
        self.assertNotIn(worker, page._live_processing_threads)

    def test_accepts_real_video_file(self):
        ffmpeg = os.environ.get("YTD_TEST_FFMPEG")
        if not ffmpeg or not os.path.isfile(ffmpeg):
            self.skipTest("YTD_TEST_FFMPEG is not configured")
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "local-source.mp4")
            subprocess.run([
                ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=10",
                "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", source,
            ], check=True, capture_output=True)

            page = UpscalePage({})

            self.assertTrue(page.set_source_file(source))
            self.assertEqual(page.source_path, os.path.abspath(source))
            self.assertEqual(page.output_folder, os.path.abspath(folder))
            self.assertIn("local-source.mp4", page.file_label.text())
            self.assertEqual(page.before_preview.play_btn.text(), "⏸ Пауза")

    def test_converter_writes_to_selected_output_folder(self):
        ffmpeg = os.environ.get("YTD_TEST_FFMPEG")
        if not ffmpeg or not os.path.isfile(ffmpeg):
            self.skipTest("YTD_TEST_FFMPEG is not configured")
        from PySide6.QtCore import QTimer
        from app.converter import probe_video_info

        with tempfile.TemporaryDirectory() as folder:
            source_dir = os.path.join(folder, "source")
            output_dir = os.path.join(folder, "result")
            os.makedirs(source_dir, exist_ok=True)
            os.makedirs(output_dir, exist_ok=True)
            source = os.path.join(source_dir, "local-source.mp4")
            subprocess.run([
                ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=10",
                "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", source,
            ], check=True, capture_output=True)

            app = _app()
            page = UpscalePage({})
            self.assertTrue(page.set_source_file(source))
            self.assertTrue(page.set_output_folder(output_dir))
            page.target_combo.setCurrentIndex(2)
            page.fps_combo.setCurrentIndex(1)
            page.container_combo.setCurrentIndex(0)
            page.codec_combo.setCurrentIndex(0)
            page.encoder_combo.setCurrentIndex(1)
            page.keep_originals_check.setChecked(True)
            result = []
            page.finished.connect(lambda path, ok, err: result.append((path, ok, err)))
            QTimer.singleShot(0, page.start_btn.click)
            QTimer.singleShot(40000, app.quit)
            app.exec()
            self.assertTrue(result and result[0][1], result)
            out_path = result[0][0]
            self.assertTrue(os.path.isfile(source))
            self.assertTrue(os.path.isfile(out_path))
            self.assertEqual(os.path.dirname(out_path), os.path.abspath(output_dir))
            self.assertTrue(page.before_preview.play_btn.isEnabled())
            self.assertTrue(page.after_preview.play_btn.isEnabled())
            self.assertEqual(page.before_preview.play_btn.text(), "⏸ Пауза")
            self.assertEqual(page.after_preview.play_btn.text(), "⏸ Пауза")
            info = probe_video_info(out_path)
            self.assertEqual(min(info["width"], info["height"]), 1080)
            page.before_preview.release_file()
            page.after_preview.release_file()


if __name__ == "__main__":
    unittest.main()
