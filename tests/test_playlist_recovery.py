import os
import tempfile
import unittest
import wave
from pathlib import Path
from yt_dlp import YoutubeDL

from app.downloader import DownloadWorker


class PlaylistRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.worker = DownloadWorker('recovery', 'https://example.com/playlist', self.folder.name,
                                     {'download_type': 'audio', 'prevent_sleep': False})
        self.stage = Path(self.worker._work_dir())
        self.attempts = []
        self.retry_formats = []
        self.changed = False
        self.padded = False
        outer = self

        class FakeYDL:
            def __init__(self, opts):
                self.params = opts
                self._pending_archive = []
                self.skipped_archive_ids = set()
                self.processor = None
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def add_post_processor(self, processor, when=None):
                assert when == 'after_move'
                self.processor = processor
            def download(self, urls):
                outer.attempts.append(self.params['playlist_items'])
                outer.retry_formats.append(self.params.get('format'))
                item = {'playlist_index': 2, 'id': 'changed' if outer.changed else 'b'}
                if self.params['match_filter'](item, incomplete=False):
                    return 0
                if outer.padded:
                    with YoutubeDL({'quiet': True}) as formatter:
                        rendered = formatter.evaluate_outtmpl(self.params['outtmpl']['default'], {
                            **item, '__last_playlist_index': 100, 'title': 'same', 'ext': 'wav'})
                    path = Path(rendered)
                else:
                    path = Path(self.params['outtmpl']['default'].replace('%(playlist_index)s', '2').replace('%(title)s', 'same').replace('%(ext)s', 'wav'))
                path.parent.mkdir(parents=True, exist_ok=True)
                outer.make_audio(path)
                self.processor.run({**item, 'filepath': str(path)})
                self._pending_archive.append(item)
                return 0
        self.YDL = FakeYDL
        self.ydl = FakeYDL({'outtmpl': {'default': str(self.stage / '%(title)s.%(ext)s')}})
        self.tracking = self.worker._setup_playlist_tracking(self.ydl, [{'id': 'a'}, {'id': 'b'}], 0)
        self.first = self.stage / '__playlist_items__' / '1' / 'same.wav'
        self.first.parent.mkdir(parents=True)
        self.make_audio(self.first)
        self.ydl.processor.run({'playlist_index': 1, 'id': 'a', 'filepath': str(self.first)})

    @staticmethod
    def make_audio(path):
        with wave.open(str(path), 'wb') as output:
            output.setparams((1, 2, 8000, 8000, 'NONE', 'not compressed'))
            output.writeframes(b'\x00\x00' * 8000)

    def test_only_missing_position_is_retried_and_same_names_are_preserved(self):
        recovered = self.worker._retry_missing_playlist_items(self.ydl, self.tracking, [str(self.first)], 0, 'HTTP Error 403')
        self.assertEqual(self.attempts, ['2'])
        self.assertEqual(self.retry_formats, ['bestaudio[protocol^=http]/bestaudio'])
        self.assertEqual(len(recovered), 1)
        first = self.worker._promote_output(str(self.first))
        second = self.worker._promote_output(recovered[0])
        self.assertEqual(Path(first).name, 'same.wav')
        self.assertEqual(Path(second).name, 'same (2).wav')
        self.assertEqual(os.path.dirname(first), self.folder.name)
        self.assertEqual(os.path.dirname(second), self.folder.name)

    def test_changed_playlist_identity_never_downloads_or_commits(self):
        self.changed = True
        result = self.worker._retry_missing_playlist_items(self.ydl, self.tracking, [str(self.first)], 0, 'HTTP Error 403')
        self.assertIsNone(result)
        self.assertEqual(self.ydl._pending_archive, [])
        self.assertTrue(self.first.exists())

    def test_retry_accepts_real_yt_dlp_zero_padded_playlist_index(self):
        self.padded = True
        recovered = self.worker._retry_missing_playlist_items(self.ydl, self.tracking, [str(self.first)], 0, 'HTTP Error 403')
        self.assertIsNotNone(recovered)
        self.assertIn(os.path.join('002', '__retry__'), recovered[0])

    def test_ambiguous_paths_and_archive_skips_do_not_retry(self):
        self.ydl.processor.run({'playlist_index': 2, 'id': 'b', 'filepath': str(self.first)})
        self.assertIsNone(self.worker._retry_missing_playlist_items(self.ydl, self.tracking, [str(self.first)], 0, 'HTTP Error 403'))
        self.assertIsNone(self.worker._retry_missing_playlist_items(self.ydl, self.tracking, [str(self.first)], 1, 'HTTP Error 403'))
        self.assertEqual(self.attempts, [])

    def test_unambiguous_archived_item_is_excluded_from_retry(self):
        expected, collector = self.tracking
        expected[3] = 'c'
        self.ydl.skipped_archive_ids = {'youtube c'}
        self.ydl.skipped_archive_entries = {('youtube c', 3, 'c')}
        recovered = self.worker._retry_missing_playlist_items(self.ydl, self.tracking, [str(self.first)], 1, 'HTTP Error 403')
        self.assertEqual(self.attempts, ['2'])
        self.assertEqual(len(recovered), 1)

    def test_ambiguous_archive_identity_never_retries(self):
        expected, _ = self.tracking
        expected[3] = 'c'
        self.ydl.skipped_archive_ids = {'youtube c'}
        for observations in (set(), {('youtube c', 3, 'wrong')},
                             {('youtube c', 1, 'a')},
                             {('youtube c', 3, 'c'), ('youtube c', 2, 'b')},
                             {('other c', 3, 'c')}):
            with self.subTest(observations=observations):
                self.ydl.skipped_archive_entries = observations
                self.assertIsNone(self.worker._retry_missing_playlist_items(self.ydl, self.tracking, [str(self.first)], 1, 'HTTP Error 403'))
        self.assertEqual(self.attempts, [])

    def test_duplicate_preflight_identity_disables_tracking(self):
        self.assertIsNone(self.worker._setup_playlist_tracking(self.ydl, [{'id': 'a'}, {'id': 'a'}], 0))
