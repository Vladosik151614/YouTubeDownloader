"""
speed_test.py - lightweight download speed check for queue recommendations.
"""
import time
from urllib.request import urlopen

from PySide6.QtCore import QThread, Signal


class SpeedTestWorker(QThread):
    finished = Signal(bool, float, int, str)

    def run(self):
        url = "https://speed.cloudflare.com/__down?bytes=3000000"
        start = time.monotonic()
        total = 0
        try:
            with urlopen(url, timeout=12) as response:
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    total += len(chunk)
            elapsed = max(0.001, time.monotonic() - start)
            mbps = (total * 8) / elapsed / 1_000_000
            recommended = 1
            if mbps >= 200:
                recommended = 8
            elif mbps >= 100:
                recommended = 6
            elif mbps >= 50:
                recommended = 4
            elif mbps >= 25:
                recommended = 3
            elif mbps >= 10:
                recommended = 2
            self.finished.emit(True, mbps, recommended, "")
        except Exception as exc:
            self.finished.emit(False, 0.0, 1, str(exc))
