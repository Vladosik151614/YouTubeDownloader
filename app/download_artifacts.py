"""Helpers for files produced by a download task."""
from __future__ import annotations

import os
import re
import json
import subprocess

from app.logger import logger
from app.binary_manager import get_binary_path
from app.process_utils import hidden_subprocess_kwargs


def validate_video_with_audio(path: str) -> tuple[bool, str]:
    """Do not report an audio-only, silent or uninspectable file as a complete video."""
    try:
        result = subprocess.run(
            [get_binary_path("ffprobe"), "-v", "error", "-show_entries",
             "stream=codec_type:stream_disposition=attached_pic", "-of", "json", path],
            capture_output=True, text=True, timeout=30, **hidden_subprocess_kwargs(),
        )
        if result.returncode:
            return False, "Не удалось проверить потоки файла через ffprobe"
        streams = json.loads(result.stdout).get("streams", [])
        video = any(s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic") for s in streams)
        audio = any(s.get("codec_type") == "audio" for s in streams)
        if not video or not audio:
            return False, "В файле отсутствует " + ("видео и звук" if not video and not audio else "видео" if not video else "звук")
        return True, ""
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        logger.warning("Media validation failed: %s", exc)
        return False, "Не удалось проверить видео и звук: проверьте доступность ffprobe"


def snapshot_output_files(folder: str) -> set[str]:
    try:
        files = set()
        for root, _, names in os.walk(folder):
            for name in names:
                path = os.path.join(root, name)
                if os.path.isfile(path):
                    files.add(path)
        return files
    except Exception:
        return set()


def new_media_files(folder: str, before: set[str]) -> list[str]:
    media_exts = {".mp4", ".mov", ".mkv", ".webm", ".m4a", ".mp3", ".opus", ".jpg", ".jpeg", ".png", ".webp", ".json", ".description", ".vtt", ".srt"}
    after = snapshot_output_files(folder)
    return sorted(
        path for path in after - before
        if os.path.splitext(path)[1].lower() in media_exts and os.path.getsize(path) > 0
    )


def single_output_path(ydl, info) -> str:
    filename = ydl.prepare_filename(info)
    base = os.path.splitext(filename)[0]
    for candidate in (base + ".mp4", filename, base + ".mkv", base + ".webm"):
        if os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
            return candidate
    return base + ".mp4"


def write_m3u(folder: str, files: list[str], playlist_title: str):
    if not files:
        return
    safe_name = re.sub(r'[<>:"/\\\\|?*]+', "_", playlist_title or "playlist").strip() or "playlist"
    m3u_path = os.path.join(folder, f"{safe_name}.m3u")
    try:
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for path in files:
                f.write(os.path.abspath(path) + "\n")
        logger.info(f"M3U created: {m3u_path}")
    except Exception as e:
        logger.warning(f"Could not create M3U: {e}")
