import json
import unittest
import yt_dlp
from unittest.mock import patch
from types import SimpleNamespace

from app.download_artifacts import validate_video_with_audio
from app.downloader import ValidatedArchiveYoutubeDL


class MediaValidationTests(unittest.TestCase):
    def probe(self, streams):
        response = SimpleNamespace(returncode=0, stdout=json.dumps({"streams": streams}))
        with patch("app.download_artifacts.subprocess.run", return_value=response):
            return validate_video_with_audio("sample.mp4")

    def test_video_and_audio_are_required(self):
        self.assertTrue(self.probe([{"codec_type": "video"}, {"codec_type": "audio"}])[0])
        self.assertFalse(self.probe([{"codec_type": "video"}])[0])
        self.assertFalse(self.probe([{"codec_type": "audio"}])[0])

    def test_audio_cover_is_not_video(self):
        self.assertFalse(self.probe([{"codec_type": "audio"}, {"codec_type": "video", "disposition": {"attached_pic": 1}}])[0])

    def test_ffprobe_failure_is_not_success(self):
        with patch("app.download_artifacts.subprocess.run", side_effect=FileNotFoundError()):
            self.assertFalse(validate_video_with_audio("sample.mp4")[0])

    def test_archive_is_not_written_before_commit(self):
        with patch.object(yt_dlp.YoutubeDL, "record_download_archive") as write:
            with ValidatedArchiveYoutubeDL({"quiet": True}) as downloader:
                downloader.record_download_archive({"id": "test"})
                write.assert_not_called()
                downloader.commit_validated_archive()
                write.assert_called_once_with({"id": "test"})
