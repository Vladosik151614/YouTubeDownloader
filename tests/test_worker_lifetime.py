import gc
import tempfile
import time
import unittest
import weakref

from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, QThread, QTimer, Slot
from app.downloader import DownloadWorker
from app.converter import ConvertWorker
from app.main_window import MainWindow


class ThreadOwner(QObject):
    _track_job_thread = MainWindow._track_job_thread
    _job_thread_finished = MainWindow._job_thread_finished
    _finalize_job_thread = MainWindow._finalize_job_thread
    _stop_job_threads = MainWindow._stop_job_threads

    def __init__(self):
        super().__init__()
        self._live_job_threads = set()
        self._conv_workers = {}
        self._workers = {}
        self.running_when_result = 0

    @Slot(str, str, bool, str)
    def result(self, task_id, path, success, error):
        worker = self._workers.pop(task_id)
        if worker.isRunning():
            self.running_when_result += 1
        gc.collect()


class WorkerLifetimeTests(unittest.TestCase):
    def test_real_threads_remain_alive_after_result_until_native_finish(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        owner = ThreadOwner()
        loop = QEventLoop()
        with tempfile.TemporaryDirectory() as folder:
            for index in range(80):
                task_id = str(index)
                worker = DownloadWorker(task_id, 'https://example.invalid/test', folder, {'prevent_sleep': False})
                owner._track_job_thread(worker)
                owner._workers[task_id] = worker
                worker.finished.connect(owner.result)
                reference = weakref.ref(worker)
                def simulate_download(ref=reference, item_id=task_id):
                    ref().finished.emit(item_id, '', False, 'synthetic error')
                    QThread.msleep(30)
                worker._download = simulate_download
                worker.start()
            del worker
            poll = QTimer()
            poll.setInterval(20)
            poll.timeout.connect(lambda: loop.quit() if not owner._live_job_threads else None)
            poll.start()
            QTimer.singleShot(15000, loop.quit)
            loop.exec()
            poll.stop()
            self.assertEqual(owner._workers, {})
            self.assertEqual(owner._live_job_threads, set())
            self.assertGreater(owner.running_when_result, 0)
        app.processEvents()

    def test_shutdown_waits_for_running_worker(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        owner = ThreadOwner()
        with tempfile.TemporaryDirectory() as folder:
            worker = DownloadWorker('shutdown', 'https://example.invalid/test', folder, {'prevent_sleep': False})
            worker._download = lambda: QThread.msleep(80)
            owner._track_job_thread(worker)
            worker.start()
            owner._stop_job_threads()
            self.assertFalse(worker.isRunning())
            self.assertEqual(owner._live_job_threads, set())
        app.processEvents()

    def test_shutdown_wait_is_bounded_for_uncooperative_worker(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        owner = ThreadOwner()
        with tempfile.TemporaryDirectory() as folder:
            worker = DownloadWorker('bounded', 'https://example.invalid/test', folder, {'prevent_sleep': False})
            worker._download = lambda: QThread.msleep(1500)
            owner._track_job_thread(worker)
            worker.start()
            started = time.monotonic()
            owner._stop_job_threads()
            elapsed = time.monotonic() - started
            self.assertLess(elapsed, 1.2)
            self.assertTrue(worker.isRunning())
            self.assertIn(worker, owner._live_job_threads)
            loop = QEventLoop()
            poll = QTimer()
            poll.setInterval(10)
            poll.timeout.connect(lambda: loop.quit() if not owner._live_job_threads else None)
            poll.start()
            QTimer.singleShot(4000, loop.quit)
            loop.exec()
            poll.stop()
            self.assertFalse(worker.isRunning())
            self.assertEqual(owner._live_job_threads, set())
        app.processEvents()

    def test_conversion_same_path_replacement_retains_both_threads(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        owner = ThreadOwner()
        loop = QEventLoop()
        first = ConvertWorker('same.mp4', {})
        second = ConvertWorker('same.mp4', {})
        first._convert = lambda: QThread.msleep(80)
        second._convert = lambda: QThread.msleep(80)
        owner._track_job_thread(first)
        owner._track_job_thread(second)
        owner._conv_workers['same.mp4'] = first
        first.start()
        owner._conv_workers['same.mp4'] = second
        second.start()
        self.assertIn(first, owner._live_job_threads)
        self.assertIn(second, owner._live_job_threads)
        poll = QTimer()
        poll.setInterval(20)
        poll.timeout.connect(lambda: loop.quit() if not owner._live_job_threads else None)
        poll.start()
        QTimer.singleShot(10000, loop.quit)
        loop.exec()
        poll.stop()
        self.assertEqual(owner._live_job_threads, set())
        self.assertEqual(owner._conv_workers, {})
        app.processEvents()
