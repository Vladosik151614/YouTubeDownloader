"""
spotify_engine.py - Spotify metadata downloads through spotDL.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from app.auth_manager import cookie_file
from app.binary_manager import get_binary_path
from app.process_utils import hidden_subprocess_kwargs


SPOTIFY_AUDIO_EXTS = {".mp3", ".m4a", ".opus", ".ogg", ".flac", ".wav"}


class _CallbackSignal:
    def __init__(self, callback):
        self.callback = callback

    def emit(self, item_id: str, *args):
        self.callback(item_id, *args)


class _CallbackWorker:
    def __init__(self, item_id: str, status_cb, progress_cb):
        self.item_id = item_id
        self._cancelled = False
        self._spotify_process = None
        self.status = _CallbackSignal(status_cb)
        self.progress = _CallbackSignal(progress_cb)


def is_spotify_url(url: str) -> bool:
    return "open.spotify.com" in url.lower() or "spotify.com" in url.lower()


def spotify_output_template(folder: str, playlist_numbering: bool = True) -> str:
    filename = "{list-position} - {artists} - {title}.{output-ext}" if playlist_numbering else "{artists} - {title}.{output-ext}"
    return str(Path(folder) / "{list-name}" / filename)


def snapshot_audio_files(folder: str) -> set[str]:
    root = Path(folder)
    if not root.exists():
        return set()
    return {
        str(path)
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SPOTIFY_AUDIO_EXTS and path.stat().st_size > 0
    }


def spotify_command(url: str, folder: str, settings: dict) -> list[str]:
    ffmpeg = get_binary_path("ffmpeg")
    if getattr(sys, "frozen", False):
        command = [sys.executable, "--spotdl-child"]
    else:
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / "main.py"), "--spotdl-child"]
    command.extend([
        "download", url,
        "--output", spotify_output_template(folder, settings.get("playlist_numbering", True)),
        "--format", str(settings.get("spotify_audio_format", "mp3")),
        "--bitrate", str(settings.get("spotify_bitrate", "320k")),
        "--audio", "soundcloud", "youtube-music", "youtube",
        "--threads", str(max(1, min(int(settings.get("max_concurrent_downloads", 2) or 2), 8))),
        "--print-errors", "--log-level", "INFO",
    ])
    if os.path.isfile(ffmpeg):
        command.extend(["--ffmpeg", ffmpeg])
    cookies = cookie_file("youtube")
    if os.path.isfile(cookies):
        command.extend(["--cookie-file", cookies])
    if settings.get("skip_duplicates", True):
        command.extend(["--archive", os.path.join(folder, ".spotify_archive.txt")])
    if settings.get("create_m3u", False):
        command.extend(["--m3u", os.path.join(folder, "spotify_playlist.m3u")])
    return command


def progress_from_line(line: str) -> float | None:
    match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", line)
    if not match:
        return None
    value = float(match.group(1))
    return max(0.0, min(value, 100.0))


def run_spotify_download(worker, url: str, folder: str, settings: dict) -> tuple[list[str], str]:
    os.makedirs(folder, exist_ok=True)
    before = snapshot_audio_files(folder)
    command = spotify_command(url, folder, settings)
    worker.status.emit(worker.item_id, "Spotify: получение метаданных...")
    worker._spotify_process = subprocess.Popen(
        command,
        cwd=Path(__file__).resolve().parents[1],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        **hidden_subprocess_kwargs(),
    )
    output_tail: list[str] = []
    assert worker._spotify_process.stdout is not None
    for raw in worker._spotify_process.stdout:
        if worker._cancelled:
            worker._spotify_process.terminate()
            return [], "Отменено пользователем"
        line = raw.strip()
        if not line:
            continue
        output_tail.append(line)
        output_tail = output_tail[-40:]
        if "Found" in line or "Downloading" in line:
            worker.status.emit(worker.item_id, "Spotify: загрузка музыки...")
        percent = progress_from_line(line)
        if percent is not None:
            worker.progress.emit(worker.item_id, percent, "—", "—")
    code = worker._spotify_process.wait()
    created = sorted(snapshot_audio_files(folder) - before)
    error_text = "\n".join(output_tail[-10:])
    has_error = any(marker in error_text.lower() for marker in ["error", "failed", "forbidden", "unavailable"])
    if (code != 0 or has_error) and not created:
        return [], error_text or f"spotDL вернул код ошибки: {code}"
    return created, ""


def run_spotify_download_callbacks(task_id: str, url: str, folder: str, settings: dict, status_cb, progress_cb) -> tuple[list[str], str]:
    return run_spotify_download(_CallbackWorker(task_id, status_cb, progress_cb), url, folder, settings)
