"""
Small helpers for download workers.
"""
from __future__ import annotations

import ctypes
import os
import re

from app.logger import logger

TIKTOK_WATERMARK_FILTER = "[format_note!*=?watermarked]"
TIKTOK_NO_WATERMARK_FORMAT = (
    f"bestvideo*{TIKTOK_WATERMARK_FILTER}+bestaudio/"
    f"best{TIKTOK_WATERMARK_FILTER}"
)


def exclude_tiktok_watermarked_formats(selector: str) -> str:
    if TIKTOK_WATERMARK_FILTER in selector:
        return selector
    return re.sub(
        r"\b(bestvideo\*?|best)(?=(?:\[|[+/]|$))",
        rf"\1{TIKTOK_WATERMARK_FILTER}", selector,
    )


def format_bytes(size: int) -> str:
    if not size or size <= 0:
        return "-"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size) < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def is_playlist(url: str) -> bool:
    value = str(url or "").lower().split("#", 1)[0]
    if "tiktok.com/" in value and "/video/" not in value:
        if any(marker in value for marker in ("/playlist/", "/collection/")) or re.search(r"tiktok\.com/@[^/?]+/?(?:\?.*)?$", value):
            return True
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
    if str(thumbnail or "").strip():
        return str(thumbnail).strip()
    usable = [t for t in (thumbnails or []) if str((t or {}).get("url", "")).strip()]
    chosen = max(
        usable,
        key=lambda t: (
            int((t or {}).get("preference") or 0),
            int((t or {}).get("width") or 0) * int((t or {}).get("height") or 0),
        ),
        default={},
    )
    return str((chosen or {}).get("url", ""))


def media_size_bytes(info: dict) -> int:
    """Return the best available size estimate for a selected media item."""
    def positive_int(value) -> int:
        try:
            return max(0, int(float(value or 0)))
        except (TypeError, ValueError, OverflowError):
            return 0

    direct = positive_int(info.get("filesize") or info.get("filesize_approx"))
    if direct:
        return direct
    requested = info.get("requested_formats") or []
    return sum(positive_int(part.get("filesize") or part.get("filesize_approx")) for part in requested if part)


def remove_merged_audio_sidecars(files: list[str], download_type: str = "video") -> list[str]:
    """Remove only yt-dlp format sidecars after a merged video exists."""
    if download_type != "video":
        return files
    media = set(files)
    for path in list(media):
        if not path.lower().endswith(".m4a"):
            continue
        stem = re.sub(r"\.f\d+$", "", os.path.splitext(path)[0], flags=re.IGNORECASE)
        if any(os.path.isfile(stem + ext) for ext in (".mp4", ".mkv", ".webm")):
            try:
                os.remove(path)
                media.discard(path)
            except OSError as exc:
                logger.warning(f"Could not remove merged audio sidecar {path}: {exc}")
    return sorted(media)

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
        size_bytes = media_size_bytes(entry)
        rows.append({
            "index": int(index),
            "title": str(title),
            "url": str(url),
            "thumbnail": str(thumbnail),
            "size_bytes": size_bytes,
            "size": format_bytes(size_bytes),
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
