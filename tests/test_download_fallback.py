import tempfile
import unittest
import os
import wave
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from app.downloader import DownloadWorker
from app.download_artifacts import new_media_files


class DownloadFallbackTests(unittest.TestCase):
    def worker(self, url, **settings):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return DownloadWorker("fallback-test", url, folder.name, {
            "download_type": "video", "download_quality": "1080", "fps_limit": "60",
            "auto_export_cookies": False, "skip_duplicates": False, **settings,
        })

    def test_youtube_fallback_only_once_and_return_to_primary_next_task(self):
        worker = self.worker("https://www." + "youtube.com/watch?v=example")
        with patch.object(worker, "_download") as download:
            self.assertTrue(worker._retry_youtube_alternative("HTTP Error 403: Forbidden"))
            self.assertFalse(worker._retry_youtube_alternative("HTTP Error 403: Forbidden"))
            download.assert_called_once()
        opts = worker._build_ydl_opts()
        base = {'ext':'mp4','vcodec':'h264','acodec':'aac','protocol':'https'}
        formats = [dict(base,format_id='good',width=1080,height=1920,fps=60),dict(base,format_id='too-big',width=2160,height=3840,fps=60)]
        selected = list(opts['format']({'formats':formats,'incomplete_formats':False}))
        self.assertEqual(selected[0]['format_id'], 'good')
        self.assertNotIn("cookiefile", opts)
        next_worker = self.worker("https://www." + "youtube.com/watch?v=example")
        self.assertFalse(next_worker._alternative_retry_used)

    def test_twitch_gets_one_alternative_without_discarding_cookies(self):
        worker = self.worker('https://www.twitch.tv/videos/123')
        with patch.object(worker, '_download') as download:
            self.assertTrue(worker._retry_youtube_alternative('HTTP Error 403: Forbidden'))
            self.assertFalse(worker._retry_youtube_alternative('HTTP Error 403: Forbidden'))
            download.assert_called_once()

    def test_does_not_retry_private_or_rate_limited(self):
        for error in ("private video", "HTTP Error 429: Too many requests", "age-restricted", "DRM"):
            worker = self.worker("https://www." + "youtube.com/watch?v=abc")
            with patch.object(worker, "_download") as download:
                self.assertFalse(worker._retry_youtube_alternative(error))
                download.assert_not_called()

    def test_other_service_playlist_and_audio_retry_once(self):
        for url, kind in (("https://vimeo.com/123", "video"),
                          ("https://www." + "youtube.com/playlist?list=PL123", "video"),
                          ("https://soundcloud.com/example/track", "audio")):
            worker = self.worker(url, download_type=kind)
            with patch.object(worker, '_download') as download:
                self.assertTrue(worker._retry_youtube_alternative('HTTP Error 403'))
                self.assertFalse(worker._retry_youtube_alternative('HTTP Error 403'))
                download.assert_called_once()

    def test_retry_keeps_partial_file_in_previous_isolated_stage(self):
        worker = self.worker('https://vimeo.com/123')
        old_stage = worker._work_dir()
        partial = os.path.join(old_stage, 'video.part')
        Path(partial).write_bytes(b'part of a download')
        with patch.object(worker, '_download') as download:
            self.assertTrue(worker._retry_youtube_alternative('HTTP Error 403'))
            download.assert_called_once()
        new_stage = worker._work_dir()
        self.assertNotEqual(old_stage, new_stage)
        self.assertEqual(Path(partial).read_bytes(), b'part of a download')

    def test_retry_rejects_non_http_and_unrelated_error(self):
        worker = self.worker('file:///tmp/a')
        self.assertFalse(worker._retry_youtube_alternative('HTTP Error 403'))
        worker = self.worker('https://vimeo.com/123')
        self.assertFalse(worker._retry_youtube_alternative('disk full'))

    def test_audio_retry_requires_ffprobe_confirmed_audio(self):
        worker = self.worker('https://soundcloud.com/example/track', download_type='audio')
        broken = Path(worker.output_folder) / 'broken.webm'
        broken.write_bytes(b'x')
        self.assertFalse(worker._has_complete_retry_output([str(broken)]))
        valid = Path(worker.output_folder) / 'valid.wav'
        with wave.open(str(valid), 'wb') as output:
            output.setparams((1, 2, 8000, 8000, 'NONE', 'not compressed'))
            output.writeframes(b'\x00\x00' * 8000)
        self.assertTrue(worker._has_complete_retry_output([str(valid)]))
        with patch('app.media_probe.probe_audio_presence', return_value=None):
            self.assertFalse(worker._has_complete_retry_output([str(valid)]))

    def test_invalid_single_audio_never_reports_success_or_commits_archive(self):
        worker = self.worker('https://soundcloud.com/example/track', download_type='audio', prevent_sleep=False)
        results, archives = [], []
        worker.finished.connect(lambda *args: results.append(args))

        class FakeYDL:
            def __init__(self, opts):
                self.opts = opts
                self.skipped_archive_ids = set()
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def extract_info(self, url, download=False): return {'title': 'broken', 'ext': 'webm'}
            def prepare_filename(self, info):
                return self.opts['outtmpl'].replace('%(title)s', 'broken').replace('%(ext)s', 'webm')
            def download(self, urls):
                Path(self.prepare_filename({})).write_bytes(b'x')
                return 0
            def commit_validated_archive(self): archives.append(True)

        with patch('app.downloader.ValidatedArchiveYoutubeDL', FakeYDL):
            worker.run()
        self.assertFalse(results[-1][2], results[-1])
        self.assertEqual(archives, [])

    def test_spotify_archive_skip_reports_non_success_without_error(self):
        worker = self.worker('https://open.spotify.com/track/123', download_type='audio')
        results, statuses = [], []
        worker.finished.connect(lambda *args: results.append(args))
        worker.status.connect(lambda *args: statuses.append(args))
        with patch('app.download_support.run_spotify_download', return_value=([], 'SKIPPED_ALREADY_DOWNLOADED:1')):
            worker._download_spotify()
        self.assertEqual(results[-1][1:], ('', False, 'SKIPPED_ALREADY_DOWNLOADED:1'))
        self.assertIn('Пропущено', statuses[-1][-1])

    def test_spotify_invalid_audio_never_reports_success(self):
        worker = self.worker('https://open.spotify.com/track/123', download_type='audio')
        results = []
        worker.finished.connect(lambda *args: results.append(args))
        broken = Path(worker.output_folder) / 'broken.mp3'
        broken.write_bytes(b'x')
        with patch('app.download_support.run_spotify_download', return_value=([str(broken)], '')):
            worker._download_spotify()
        self.assertFalse(results[-1][2], results[-1])

    def test_spotify_valid_audio_uses_audio_validation_even_in_video_profile(self):
        worker = self.worker('https://open.spotify.com/track/123', download_type='video')
        results, produced = [], []
        worker.finished.connect(lambda *args: results.append(args))
        worker.produced_files.connect(lambda _, paths: produced.extend(paths))
        saved = Path(worker.output_folder) / 'audio.wav'
        with wave.open(str(saved), 'wb') as output:
            output.setparams((1, 2, 8000, 8000, 'NONE', 'not compressed'))
            output.writeframes(b'\x00\x00' * 8000)
        with patch('app.download_support.run_spotify_download', return_value=([str(saved)], '')):
            worker._download_spotify()
        self.assertTrue(results[-1][2], results[-1])
        self.assertEqual(produced, [str(saved)])

    def test_spotify_partial_failure_exposes_valid_saved_files_and_redacts_log(self):
        worker = self.worker('https://open.spotify.com/playlist/123', download_type='audio', prevent_sleep=False)
        results, produced = [], []
        worker.finished.connect(lambda *args: results.append(args))
        worker.produced_files.connect(lambda _, paths: produced.extend(paths))
        saved = Path(worker.output_folder) / 'saved.wav'
        with wave.open(str(saved), 'wb') as output:
            output.setparams((1, 2, 8000, 8000, 'NONE', 'not compressed'))
            output.writeframes(b'\x00\x00' * 8000)
        invalid = Path(worker.output_folder) / 'bad.mp3'
        invalid.write_bytes(b'x')
        error = 'provider failed https://example.com/download?token=secretvalue\nВременные файлы сохранены: C:\\test\\stage'
        with patch('app.download_support.run_spotify_download', return_value=([str(saved), str(invalid)], error)), \
             patch('app.download_support.logger.warning') as warning:
            worker.run()
        self.assertEqual(produced, [str(saved)])
        self.assertFalse(results[-1][2])
        self.assertEqual(results[-1][1], worker.output_folder)
        self.assertIn(str(saved), results[-1][3])
        self.assertIn('C:\\test\\stage', results[-1][3])
        self.assertNotIn('secretvalue', results[-1][3])
        self.assertNotIn(str(invalid), results[-1][3])
        log_args = str(warning.call_args)
        self.assertIn('provider failed', log_args)
        self.assertNotIn('secretvalue', log_args)

    def test_spotify_partial_cancellation_still_exposes_files(self):
        worker = self.worker('https://open.spotify.com/playlist/123', download_type='audio')
        results, produced = [], []
        worker.finished.connect(lambda *args: results.append(args))
        worker.produced_files.connect(lambda _, paths: produced.extend(paths))
        saved = Path(worker.output_folder) / 'saved.wav'
        with wave.open(str(saved), 'wb') as output:
            output.setparams((1, 2, 8000, 8000, 'NONE', 'not compressed'))
            output.writeframes(b'\x00\x00' * 8000)
        with patch('app.download_support.run_spotify_download', return_value=([str(saved)], 'Отменено пользователем')):
            worker._download_spotify()
        self.assertEqual(produced, [str(saved)])
        self.assertFalse(results[-1][2])
        self.assertIn(str(saved), results[-1][3])

    def test_partial_audio_playlist_does_not_commit_or_report_success(self):
        worker = self.worker('https://www.' + 'youtube.com/playlist?list=PL123', download_type='audio', prevent_sleep=False)
        results, produced, archives = [], [], []
        worker.finished.connect(lambda *args: results.append(args))
        worker.produced_files.connect(lambda _, files: produced.extend(files))

        class FakeYDL:
            def __init__(self, opts):
                self.opts = opts
                self.skipped_archive_ids = set()
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def download(self, urls):
                folder = Path(self.opts['outtmpl']).parent
                (folder / 'broken.webm').write_bytes(b'x')
                with wave.open(str(folder / 'valid.mp3'), 'wb') as output:
                    output.setparams((1, 2, 8000, 8000, 'NONE', 'not compressed'))
                    output.writeframes(b'\x00\x00' * 8000)
                return 0
            def commit_validated_archive(self): archives.append(True)

        info = {'title': 'list', '_type': 'playlist', 'entries': [{'id': '1'}, {'id': '2'}]}
        with patch('app.downloader.ValidatedArchiveYoutubeDL', FakeYDL), \
             patch.object(worker, '_playlist_preflight_info', return_value=(info, False)):
            worker.run()
        self.assertFalse(results[-1][2], results[-1])
        self.assertEqual(len(produced), 1)
        self.assertEqual(archives, [])

    def test_missing_audio_playlist_entry_does_not_report_success(self):
        worker = self.worker('https://www.' + 'youtube.com/playlist?list=PL123', download_type='audio', prevent_sleep=False)
        results, archives = [], []
        worker.finished.connect(lambda *args: results.append(args))

        class FakeYDL:
            def __init__(self, opts):
                self.opts = opts
                self.skipped_archive_ids = set()
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def download(self, urls):
                path = Path(self.opts['outtmpl']).parent / 'valid.mp3'
                with wave.open(str(path), 'wb') as output:
                    output.setparams((1, 2, 8000, 8000, 'NONE', 'not compressed'))
                    output.writeframes(b'\x00\x00' * 8000)
                return 0
            def commit_validated_archive(self): archives.append(True)

        info = {'title': 'list', '_type': 'playlist', 'entries': [{'id': '1'}, {'id': '2'}]}
        with patch('app.downloader.ValidatedArchiveYoutubeDL', FakeYDL), \
             patch.object(worker, '_playlist_preflight_info', return_value=(info, False)):
            worker.run()
        self.assertFalse(results[-1][2], results[-1])
        self.assertEqual(archives, [])

    def test_unexpected_failure_records_exception_traceback(self):
        worker = self.worker('https://vimeo.com/123', prevent_sleep=False)
        result = []
        worker.finished.connect(lambda *args: result.append(args))
        with patch.object(worker, '_download', side_effect=RuntimeError('test failure')), \
             patch('app.downloader.logger.exception') as report:
            worker.run()
        report.assert_called_once()
        self.assertFalse(result[0][2])

    def test_incomplete_video_retry_uses_new_stage_and_preserves_old(self):
        worker = self.worker('https://vimeo.com/123', prevent_sleep=False)
        results, attempts = [], []
        worker.finished.connect(lambda *args: results.append(args))

        class FakeYDL:
            def __init__(self, opts):
                self.opts = opts
                self.skipped_archive_ids = set()
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def extract_info(self, url, download=False):
                return {'title': 'sample', 'ext': 'mp4'}
            def prepare_filename(self, info):
                return self.opts['outtmpl'].replace('%(title)s', 'sample').replace('%(ext)s', 'mp4')
            def download(self, urls):
                path = self.prepare_filename({})
                attempts.append(path)
                Path(path).write_bytes(b'broken' if len(attempts) == 1 else b'complete')
                if len(attempts) == 1:
                    self.opts['logger'].errors.append('HTTP Error 403: Forbidden')
                    return 1
                return 0
            def commit_validated_archive(self):
                pass

        def validate(path):
            return (Path(path).read_bytes() == b'complete', 'invalid')

        with patch('app.downloader.ValidatedArchiveYoutubeDL', FakeYDL), \
             patch('app.download_artifacts.validate_video_with_audio', side_effect=validate), \
             patch('app.downloader.validate_video_with_audio', side_effect=validate), \
             patch('app.downloader.validate_video_profile', return_value=(True, '')):
            worker.run()
        self.assertEqual(len(attempts), 2)
        self.assertNotEqual(os.path.dirname(attempts[0]), os.path.dirname(attempts[1]))
        self.assertEqual(Path(attempts[0]).read_bytes(), b'broken')
        self.assertTrue(results[-1][2], results[-1])
        self.assertEqual(Path(results[-1][1]).read_bytes(), b'complete')

    def test_tiktok_external_fallback_never_used_for_profiles_playlists_or_audio(self):
        urls = ("https://www.tiktok.com/@creator", "https://www.tiktok.com/@creator/collection/123", "https://www." + "youtube.com/watch?v=123")
        for url in urls:
            worker = self.worker(url)
            with patch("app.downloader.download_tiktok_external_quality_fallback") as external:
                self.assertFalse(worker._try_tiktok_fallbacks({}))
                external.assert_not_called()
        worker = self.worker("https://www.tiktok.com/@creator/video/123", download_type="audio")
        with patch("app.downloader.download_tiktok_external_quality_fallback") as external:
            self.assertFalse(worker._try_tiktok_fallbacks({}))
            external.assert_not_called()

    def test_tiktok_fallback_stops_after_first_success(self):
        worker = self.worker("https://www.tiktok.com/@creator/video/123")
        with patch("app.downloader.download_tiktok_clean_stream_fallback", return_value=("video.mp4", "title")), \
             patch("app.downloader.download_tiktok_external_quality_fallback") as external, \
             patch.object(worker, "_finish_single_success") as finish:
            self.assertTrue(worker._try_tiktok_fallbacks({}))
            finish.assert_called_once_with("video.mp4")
            external.assert_not_called()

    def test_tiktok_mp4_fallback_cannot_silently_satisfy_webm_profile(self):
        worker = self.worker('https://www.tiktok.com/@creator/video/123', container='webm', auto_convert=False)
        results = []
        worker.finished.connect(lambda *args: results.append(args))
        with patch('app.downloader.download_tiktok_clean_stream_fallback', return_value=('video.mp4', 'title')), \
             patch('app.downloader.validate_video_with_audio', return_value=(True, '')), \
             patch('app.downloader.validate_video_profile', return_value=(True, '')), \
             patch('app.downloader.remux_video_container', side_effect=RuntimeError('Не удалось сохранить WEBM')):
            self.assertTrue(worker._try_tiktok_fallbacks({}))
        self.assertFalse(results[0][2])
        self.assertIn('WEBM', results[0][3])

    def test_concurrent_tasks_do_not_share_or_overwrite_results(self):
        with tempfile.TemporaryDirectory() as folder:
            first = DownloadWorker("first", "https://" + "youtube.com/watch?v=1", folder, {})
            second = DownloadWorker("second", "https://" + "youtube.com/watch?v=2", folder, {})
            first_source = os.path.join(first._work_dir(), "same.mp4")
            second_source = os.path.join(second._work_dir(), "same.mp4")
            with open(first_source, "wb") as f:
                f.write(b"first-task")
            with open(second_source, "wb") as f:
                f.write(b"second-task")
            self.assertNotEqual(first._work_dir(), second._work_dir())
            with ThreadPoolExecutor(max_workers=2) as executor:
                result = list(executor.map(lambda pair: pair[0]._promote_output(pair[1]),
                                           ((first, first_source), (second, second_source))))
            self.assertEqual(len(set(result)), 2)
            self.assertEqual({Path(path).read_bytes() for path in result}, {b"first-task", b"second-task"})
            first._cleanup_staging()
            second._cleanup_staging()

    def test_rejects_path_from_another_task(self):
        with tempfile.TemporaryDirectory() as folder:
            first = DownloadWorker("first", "https://" + "youtube.com/watch?v=1", folder, {})
            second = DownloadWorker("second", "https://" + "youtube.com/watch?v=2", folder, {})
            foreign = os.path.join(second._work_dir(), "other.mp4")
            with open(foreign, "wb") as f:
                f.write(b"other-task")
            with self.assertRaises(RuntimeError):
                first._promote_output(foreign)
            self.assertTrue(os.path.isfile(foreign))

    def test_playlist_and_another_worker_have_isolated_file_snapshots(self):
        with tempfile.TemporaryDirectory() as folder:
            playlist = DownloadWorker("playlist", "https://" + "youtube.com/playlist?list=PL1", folder, {})
            single = DownloadWorker("single", "https://" + "youtube.com/watch?v=1", folder, {})
            pstage = playlist._work_dir()
            sstage = single._work_dir()
            for stage, names in ((pstage, ("one.mp4", "two.mp4")), (sstage, ("foreign.mp4",))):
                for name in names:
                    with open(os.path.join(stage, name), "wb") as stream:
                        stream.write(b"sample")
            playlist_files = new_media_files(pstage, set())
            self.assertEqual({os.path.basename(p) for p in playlist_files}, {"one.mp4", "two.mp4"})
            self.assertNotIn(os.path.join(sstage, "foreign.mp4"), playlist_files)
            for path in playlist_files:
                playlist._promote_output(path)
            self.assertTrue(os.path.exists(os.path.join(sstage, "foreign.mp4")))
