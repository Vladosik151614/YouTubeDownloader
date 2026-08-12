"""Helpers for files produced by a download task."""
from __future__ import annotations

import os
import re

from app.logger import logger


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
    media_exts = {".mp4", ".mkv", ".webm", ".m4a", ".mp3", ".opus", ".jpg", ".jpeg", ".png", ".webp", ".json", ".description", ".vtt", ".srt"}
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
