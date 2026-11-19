import os
import tempfile
import unittest
from unittest.mock import patch
from app.downloader import DownloadWorker


class Mp3DownloadTests(unittest.TestCase):
    def test_audio_only_extracts_mp3_without_video_fallback(self):
        with tempfile.TemporaryDirectory() as folder, patch('app.downloader.cookie_file_for_url', return_value=''):
            worker = DownloadWorker('audio-test', 'https://example.invalid/audio', folder,
                                    {'download_type':'audio', 'auto_export_cookies':False, 'skip_duplicates':False})
            opts = worker._build_ydl_opts()
            self.assertEqual(opts['format'], 'bestaudio')
            self.assertFalse(opts['keepvideo'])
            self.assertEqual(opts['postprocessors'][0]['preferredcodec'], 'mp3')
            worker._alternative_retry_used = True
            self.assertEqual(worker._build_ydl_opts()['format'], 'bestaudio[protocol^=http]/bestaudio')

    def test_video_mode_does_not_extract_mp3(self):
        with tempfile.TemporaryDirectory() as folder:
            worker = DownloadWorker('video-test', 'https://example.invalid/video', folder,
                                    {'download_type':'video', 'auto_export_cookies':False, 'skip_duplicates':False})
            self.assertNotIn('postprocessors', worker._build_ydl_opts())
