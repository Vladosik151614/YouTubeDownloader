import os
import tempfile
import threading
import unittest
import wave
import subprocess
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import app.spotify_engine as engine
from app.spotify_engine import run_spotify_download_callbacks


class SpotifyArchiveSafetyTest(unittest.TestCase):
    def run_job(self, folder, process, **settings):
        return run_spotify_download_callbacks("test", "https://open.spotify.com/track/test", folder, settings, lambda *args: None, lambda *args: None)

    def test_spotdl_real_formatter_keeps_output_inside_stage(self):
        from spotdl.types.song import Song
        from spotdl.utils.formatter import create_file_name, create_path_object
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / ".parent.with.dots"
            folder.mkdir()
            observed = []
            song = Song(name="Track", artists=["Artist"], artist="Artist", genres=[], disc_number=1,
                        disc_count=1, album_name="Album", album_artist="Artist", duration=1,
                        year=2024, date="2024", track_number=1, tracks_count=1,
                        song_id="id", explicit=False, publisher="", url="https://example.invalid",
                        isrc=None, cover_url=None, copyright_text=None, list_name="List")
            def process(cmd, **kwargs):
                stage = Path(kwargs["cwd"])
                template = cmd[cmd.index("--output") + 1]
                self.assertFalse(Path(template).is_absolute())
                self.assertFalse(stage.name.startswith("."))
                formatted = create_file_name(song, template, "wav")
                destination = (stage / formatted).resolve()
                self.assertTrue(destination.is_relative_to(stage.resolve()))
                song.list_name = None
                single = create_file_name(song, template, "wav")
                self.assertFalse(single.is_absolute())
                self.assertTrue((stage / single).resolve().is_relative_to((stage / "output").resolve()))
                # Demonstrate the real formatter would rewrite the old absolute path.
                old_stage = folder / ".ytdl-spotify-example"
                self.assertNotEqual(create_path_object(str(old_stage / "track.wav")), old_stage / "track.wav")
                destination.parent.mkdir(parents=True, exist_ok=True)
                with wave.open(str(destination), "wb") as stream:
                    stream.setnchannels(1)
                    stream.setsampwidth(2)
                    stream.setframerate(8000)
                    stream.writeframes(b"\x01\x00" * 800)
                archive = Path(cmd[cmd.index("--archive") + 1])
                archive.write_text("validated\n", encoding="utf-8")
                observed.append(destination)
                return OutputProcess("", 0)
            with patch("app.spotify_engine.subprocess", SimpleNamespace(Popen=process, PIPE=subprocess.PIPE, STDOUT=subprocess.STDOUT)):
                files, error = self.run_job(str(folder), process)
            self.assertEqual(error, "")
            self.assertEqual(len(files), 1)
            self.assertTrue(Path(files[0]).is_relative_to(folder))
            self.assertTrue(observed)

    def test_provider_error_retries_single_track_in_separate_stage(self):
        with tempfile.TemporaryDirectory() as folder:
            attempts = []
            def process(cmd, **kwargs):
                provider = cmd[cmd.index("--audio") + 1]
                archive = Path(cmd[cmd.index("--archive") + 1])
                attempts.append((provider, archive.parent))
                if provider == "soundcloud":
                    archive.write_text("unvalidated\n", encoding="utf-8")
                    return OutputProcess("AudioProviderError: source failed\n", 1)
                (archive.parent / "output").mkdir()
                with wave.open(str(archive.parent / "output" / "track.wav"), "wb") as stream:
                    stream.setnchannels(1)
                    stream.setsampwidth(2)
                    stream.setframerate(8000)
                    stream.writeframes(b"\x01\x00" * 800)
                archive.write_text("validated\n", encoding="utf-8")
                return OutputProcess("", 0)
            with patch("app.spotify_engine.subprocess", SimpleNamespace(Popen=process, PIPE=subprocess.PIPE, STDOUT=subprocess.STDOUT)):
                files, error = self.run_job(folder, process)
            self.assertEqual([x[0] for x in attempts], ["soundcloud", "youtube-music"])
            self.assertNotEqual(attempts[0][1], attempts[1][1])
            self.assertEqual(error, "")
            self.assertEqual(len(files), 1)
            self.assertTrue((attempts[0][1] / ".spotify_archive.txt").exists())
            self.assertEqual((Path(folder) / ".spotify_archive.txt").read_text(encoding="utf-8"), "validated\n")

    def test_collection_and_nonprovider_errors_do_not_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            calls = []
            def process(cmd, **kwargs):
                calls.append(cmd)
                stage = Path(cmd[cmd.index("--archive") + 1]).parent
                (stage / "partial.part").write_bytes(b"partial")
                return OutputProcess("AudioProviderError: source failed\n", 1)
            with patch("app.spotify_engine.subprocess", SimpleNamespace(Popen=process, PIPE=subprocess.PIPE, STDOUT=subprocess.STDOUT)):
                files, error = run_spotify_download_callbacks("test", "https://open.spotify.com/playlist/test", folder, {}, lambda *args: None, lambda *args: None)
            self.assertEqual(files, [])
            self.assertIn("AudioProviderError", error)
            self.assertEqual(len(calls), 1)
            calls.clear()
            def unrelated(cmd, **kwargs):
                calls.append(cmd)
                return OutputProcess("ERROR: disk full\n", 1)
            with patch("app.spotify_engine.subprocess", SimpleNamespace(Popen=unrelated, PIPE=subprocess.PIPE, STDOUT=subprocess.STDOUT)):
                files, error = self.run_job(folder, unrelated)
            self.assertEqual(len(calls), 1)
            self.assertIn("disk full", error)

    def test_collection_provider_failure_retries_if_no_partial_files(self):
        with tempfile.TemporaryDirectory() as folder:
            calls = []
            def process(cmd, **kwargs):
                calls.append(cmd[cmd.index("--audio") + 1])
                return OutputProcess("AudioProviderError: source failed\n", 1)
            with patch("app.spotify_engine.subprocess", SimpleNamespace(Popen=process, PIPE=subprocess.PIPE, STDOUT=subprocess.STDOUT)):
                files, error = run_spotify_download_callbacks("test", "https://open.spotify.com/album/test", folder, {}, lambda *args: None, lambda *args: None)
            self.assertEqual(calls, ["soundcloud", "youtube-music", "youtube"])
            self.assertIn("AudioProviderError", error)
            self.assertFalse(files)

    def test_collection_empty_m3u_allows_retry_but_track_entry_does_not(self):
        for m3u, expected in (("#EXTM3U\n", 3), ("#EXTM3U\ntrack.mp3\n", 1)):
            with self.subTest(m3u=m3u), tempfile.TemporaryDirectory() as folder:
                calls = []
                def process(cmd, **kwargs):
                    calls.append(cmd)
                    stage = Path(cmd[cmd.index("--archive") + 1]).parent
                    (stage / "spotify_playlist.m3u").write_text(m3u, encoding="utf-8")
                    return OutputProcess("AudioProviderError: source failed\n", 1)
                with patch("app.spotify_engine.subprocess", SimpleNamespace(Popen=process, PIPE=subprocess.PIPE, STDOUT=subprocess.STDOUT)):
                    run_spotify_download_callbacks("test", "https://open.spotify.com/album/test", folder, {"create_m3u": True}, lambda *args: None, lambda *args: None)
                self.assertEqual(len(calls), expected)

    def test_archive_skip_requires_matching_track_and_clean_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / ".spotify_archive.txt").write_text("https://open.spotify.com/track/test\n", encoding="utf-8")
            with patch("app.spotify_engine.subprocess", SimpleNamespace(Popen=lambda *a, **kw: OutputProcess("Saved archive", 0), PIPE=subprocess.PIPE, STDOUT=subprocess.STDOUT)):
                files, error = self.run_job(folder, None)
            self.assertEqual((files, error), ([], engine.SPOTIFY_ARCHIVE_SKIP))
            self.assertFalse(list(Path(folder).glob("ytdl-spotify-*")))
            with patch("app.spotify_engine.subprocess", SimpleNamespace(Popen=lambda *a, **kw: OutputProcess("ERROR: network", 1), PIPE=subprocess.PIPE, STDOUT=subprocess.STDOUT)):
                files, error = self.run_job(folder, None)
            self.assertNotEqual(error, engine.SPOTIFY_ARCHIVE_SKIP)

    def test_partial_validation_keeps_all_files_in_staging(self):
        with tempfile.TemporaryDirectory() as folder:
            def process(cmd, **kwargs):
                archive = Path(cmd[cmd.index("--archive") + 1])
                output = archive.parent / "output"
                output.mkdir()
                with wave.open(str(output / "good.wav"), "wb") as stream:
                    stream.setnchannels(1)
                    stream.setsampwidth(2)
                    stream.setframerate(8000)
                    stream.writeframes(b"\x01\x00" * 800)
                (output / "bad.mp3").write_bytes(b"bad")
                archive.write_text("good\nbad\n", encoding="utf-8")
                return OutputProcess("", 0)
            with patch("app.spotify_engine.subprocess", SimpleNamespace(Popen=process, PIPE=subprocess.PIPE, STDOUT=subprocess.STDOUT)):
                files, error = self.run_job(folder, process)
            self.assertEqual(files, [])
            self.assertIn("не удалось проверить звук", error)
            self.assertFalse((Path(folder) / ".spotify_archive.txt").exists())
            self.assertTrue(list(Path(folder).glob("ytdl-spotify-*/output/bad.mp3")))
            self.assertTrue(list(Path(folder).glob("ytdl-spotify-*/output/good.wav")))

    def test_cancel_preserves_truncated_audio_in_staging(self):
        with tempfile.TemporaryDirectory() as folder:
            worker = engine._CallbackWorker("test", lambda *a: None, lambda *a: None)
            def process(cmd, **kwargs):
                archive = Path(cmd[cmd.index("--archive") + 1])
                output = archive.parent / "output"
                output.mkdir()
                with wave.open(str(output / "good.wav"), "wb") as stream:
                    stream.setnchannels(1)
                    stream.setsampwidth(2)
                    stream.setframerate(8000)
                    stream.writeframes(b"\x01\x00" * 800)
                path = output / "good.wav"
                path.write_bytes(path.read_bytes()[:100])
                self.assertTrue(engine.probe_audio_presence(str(path)))
                archive.write_text("new\n", encoding="utf-8")
                worker._cancelled = True
                return OutputProcess("", 1)
            with patch("app.spotify_engine.subprocess", SimpleNamespace(Popen=process, PIPE=subprocess.PIPE, STDOUT=subprocess.STDOUT)):
                files, error = engine.run_spotify_download(worker, "https://open.spotify.com/track/test", folder, {})
            self.assertEqual(files, [])
            self.assertTrue(error.startswith("Отменено пользователем"))
            self.assertIn("Незавершённые файлы", error)
            self.assertFalse((Path(folder) / ".spotify_archive.txt").exists())
            self.assertTrue(list(Path(folder).glob("ytdl-spotify-*/output/good.wav")))

    def test_no_provider_match_tries_next_source(self):
        with tempfile.TemporaryDirectory() as folder:
            calls = []
            def process(cmd, **kwargs):
                calls.append(cmd[cmd.index("--audio") + 1])
                return OutputProcess("LookupError: No results found for song: example\n", 1)
            with patch("app.spotify_engine.subprocess", SimpleNamespace(Popen=process, PIPE=subprocess.PIPE, STDOUT=subprocess.STDOUT)):
                files, error = self.run_job(folder, process)
            self.assertEqual(files, [])
            self.assertIn("No results found", error)
            self.assertEqual(calls, ["soundcloud", "youtube-music", "youtube"])

    def test_invalid_output_never_enters_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / ".spotify_archive.txt"
            archive.write_text("existing\n", encoding="utf-8")

            def process(cmd, **kwargs):
                stage = Path(cmd[cmd.index("--archive") + 1]).parent
                (stage / "output").mkdir()
                (stage / "output" / "broken.mp3").write_bytes(b"broken audio")
                (stage / ".spotify_archive.txt").write_text("existing\nnew\n", encoding="utf-8")
                return FakeProcess()

            with patch("app.spotify_engine.subprocess", SimpleNamespace(Popen=process, PIPE=subprocess.PIPE, STDOUT=subprocess.STDOUT)):
                files, error = self.run_job(folder, process)
            self.assertEqual(files, [])
            self.assertTrue(error)
            self.assertEqual(archive.read_text(encoding="utf-8"), "existing\n")
            self.assertTrue(list(Path(folder).glob("ytdl-spotify-*/output/broken.mp3")))

    def test_concurrent_results_and_archive_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            barrier = threading.Barrier(2)
            def process(cmd, **kwargs):
                archive = Path(cmd[cmd.index("--archive") + 1])
                (archive.parent / "output").mkdir()
                output = archive.parent / "output" / "same.wav"
                with wave.open(str(output), "wb") as stream:
                    stream.setnchannels(1)
                    stream.setsampwidth(2)
                    stream.setframerate(8000)
                    value = 1 if threading.current_thread().name.endswith("0") else 2
                    stream.writeframes(bytes((value, 0)) * 800)
                archive.write_text(threading.current_thread().name + "\n", encoding="utf-8")
                (archive.parent / "spotify_playlist.m3u").write_text("#EXTM3U\n" + str(output) + "\n", encoding="utf-8")
                barrier.wait(timeout=10)
                return FakeProcess()

            with patch("app.spotify_engine.subprocess", SimpleNamespace(Popen=process, PIPE=subprocess.PIPE, STDOUT=subprocess.STDOUT)):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [pool.submit(self.run_job, folder, process, create_m3u=True) for _ in range(2)]
                    results = [future.result(timeout=30) for future in futures]
            self.assertTrue(all(not error and len(files) == 1 for files, error in results), results)
            self.assertEqual(len({files[0] for files, _ in results}), 2)
            self.assertEqual(len((Path(folder) / ".spotify_archive.txt").read_text(encoding="utf-8").splitlines()), 2)
            for files, _ in results:
                self.assertTrue(os.path.isfile(files[0]))
            self.assertEqual(len(list(Path(folder).glob("spotify_playlist*.m3u"))), 2)

    def test_playlist_order_and_archived_tracks(self):
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder) / "stage"
            stage.mkdir()
            first, second = stage / "a.mp3", stage / "b.mp3"
            (stage / "spotify_playlist.m3u").write_text(f"#EXTM3U\n{second}\n{first}\n", encoding="utf-8")
            mapping = {str(first): str(Path(folder) / "A.mp3"), str(second): str(Path(folder) / "B.mp3")}
            with self.assertRaisesRegex(ValueError, "архив"):
                engine._publish_spotify_m3u(str(stage), folder, mapping, {"old-track"})
            self.assertFalse(list(Path(folder).glob("spotify_playlist*.m3u")))
            engine._publish_spotify_m3u(str(stage), folder, mapping, set())
            lines = (Path(folder) / "spotify_playlist.m3u").read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[1:], [mapping[str(second)], mapping[str(first)]])

    def test_retry_after_partial_promotion_does_not_duplicate_file(self):
        with tempfile.TemporaryDirectory() as folder:
            def process(cmd, **kwargs):
                archive = Path(cmd[cmd.index("--archive") + 1])
                (archive.parent / "output").mkdir()
                for name, value in (("a.wav", 1), ("b.wav", 2)):
                    with wave.open(str(archive.parent / "output" / name), "wb") as stream:
                        stream.setnchannels(1)
                        stream.setsampwidth(2)
                        stream.setframerate(8000)
                        stream.writeframes(bytes((value, 0)) * 800)
                archive.write_text("one\ntwo\n", encoding="utf-8")
                return FakeProcess()

            original = engine._promote_spotify_file
            count = 0
            def fail_second(*args):
                nonlocal count
                count += 1
                if count == 2:
                    raise OSError("test disk failure")
                return original(*args)
            mocked_subprocess = SimpleNamespace(Popen=process, PIPE=subprocess.PIPE, STDOUT=subprocess.STDOUT)
            with patch("app.spotify_engine.subprocess", mocked_subprocess):
                with patch("app.spotify_engine._promote_spotify_file", fail_second):
                    files, error = self.run_job(folder, process)
                self.assertEqual(len(files), 1)
                self.assertIn(files[0], error)
                self.assertFalse((Path(folder) / ".spotify_archive.txt").exists())
                retried, error = self.run_job(folder, process)
            self.assertFalse(error, error)
            self.assertEqual(len(retried), 2)
            self.assertEqual(len(list(Path(folder).glob("*.wav"))), 2)


class FakeProcess:
    stdout = iter(())
    def wait(self):
        return 0


class OutputProcess:
    def __init__(self, output, code):
        self.stdout = iter(output.splitlines())
        self.code = code

    def wait(self):
        return self.code


if __name__ == "__main__":
    unittest.main()
