"""
Small helpers for download workers.
"""
from __future__ import annotations

import ctypes
import os
import re

from app.logger import logger


def format_bytes(size: int) -> str:
    if not size or size <= 0:
        return "-"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size) < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def is_playlist(url: str) -> bool:
    playlist_patterns = [
        r"list=",
        r"/playlist\?",
        r"youtube\.com/playlist",
    ]
    return any(re.search(pattern, url) for pattern in playlist_patterns)


def rate_limit_bytes(value: str) -> int | None:
    limits = {
        "50m": 50 * 1024 * 1024 // 8,
        "25m": 25 * 1024 * 1024 // 8,
        "10m": 10 * 1024 * 1024 // 8,
        "4m": 4 * 1024 * 1024 // 8,
        "2m": 2 * 1024 * 1024 // 8,
    }
    return limits.get(value)


def _best_thumbnail(thumbnail: str, thumbnails: list[dict]) -> str:
    if thumbnail:
        return str(thumbnail)
    usable = [
        t for t in thumbnails
        if str((t or {}).get("url", "")).lower().split("?", 1)[0].endswith((".jpg", ".jpeg", ".png"))
    ]
    chosen = usable[-1] if usable else (thumbnails[-1] if thumbnails else {})
    return str((chosen or {}).get("url", ""))


def playlist_entry_rows(entries: list[dict]) -> list[dict]:
    rows = []
    for fallback_index, entry in enumerate(entries, start=1):
        if not entry:
            continue
        index = entry.get("playlist_index") or fallback_index
        title = entry.get("title") or entry.get("id") or f"Видео {index}"
        url = entry.get("webpage_url") or entry.get("url") or ""
        thumbnail = entry.get("thumbnail") or ""
        thumbnails = entry.get("thumbnails") or []
        thumbnail = _best_thumbnail(thumbnail, thumbnails)
        rows.append({
            "index": int(index),
            "title": str(title),
            "url": str(url),
            "thumbnail": str(thumbnail),
        })
    return rows


def thumbnail_url(info: dict) -> str:
    thumbnail = info.get("thumbnail") or ""
    thumbnails = info.get("thumbnails") or []
    return _best_thumbnail(thumbnail, thumbnails)


def set_sleep_prevention(enabled: bool) -> None:
    if os.name != "nt":
        return
    try:
        flags = 0x80000000 | 0x00000001 | 0x00000002 if enabled else 0x80000000
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
    except Exception:
        pass


class YtDlpLogCollector:
    def __init__(self, item_id: str):
        self.item_id = item_id
        self.messages = []
        self.errors = []

    def debug(self, msg):
        if msg.startswith("[debug]"):
            logger.debug(f"[{self.item_id}] yt-dlp {msg}")

    def warning(self, msg):
        self.messages.append(str(msg))
        logger.warning(f"[{self.item_id}] yt-dlp warning: {msg}")

    def error(self, msg):
        msg = str(msg)
        self.messages.append(msg)
        self.errors.append(msg)
        logger.error(f"[{self.item_id}] yt-dlp error: {msg}")
