import os
import tempfile
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from app.conversion_scan import ConversionScanWorker


class ConversionScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_probe_does_not_block_main_event_loop(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            loop = QEventLoop()
            worker = ConversionScanWorker("task", [f.name], {"auto_convert": True}, False)
            results, ticks = [], []
            worker.scan_ready.connect(lambda *args: results.append(args))
            worker.finished.connect(loop.quit)
            with patch("app.conversion_scan.has_video_stream", side_effect=lambda _: (time.sleep(.25), True)[1]), \
                 patch("app.conversion_scan.needs_profile_conversion", return_value=True):
                QTimer.singleShot(30, lambda: ticks.append("responsive"))
                worker.start()
                QTimer.singleShot(2000, loop.quit)
                loop.exec()
                worker.wait()
            self.assertEqual(ticks, ["responsive"])
            self.assertEqual(results[0][0], "task")
            self.assertEqual(results[0][1], [f.name])

    def test_cancel_skips_remaining_probes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "video.mp4")
            with open(path, "wb") as file:
                file.write(b"x")
            worker = ConversionScanWorker("task", [path], {}, False)
            worker.cancel()
            with patch("app.conversion_scan.has_video_stream") as probe:
                worker.run()
            probe.assert_not_called()

    def test_disabled_profile_still_checks_tiktok_normalization(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            worker = ConversionScanWorker("task", [f.name], {"auto_convert": False}, False)
            result = []
            worker.scan_ready.connect(lambda *args: result.append(args))
            with patch("app.conversion_scan.needs_tiktok_landscape_normalization", return_value=True):
                worker.run()
            self.assertEqual(result[0][1], [f.name])
            self.assertFalse(result[0][2]["ask_before_codec_convert"])
            self.assertTrue(result[0][2]["rotation_only"])
