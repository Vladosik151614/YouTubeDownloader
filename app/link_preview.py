"""
link_preview.py - metadata preview before download.
"""
from __future__ import annotations

import os

import yt_dlp
from PySide6.QtCore import QThread, Signal

from app.auth_manager import cookie_file_for_url, ensure_cookie_file_for_url, service_for_url
from app.binary_manager import get_binary_path


def _duration_text(seconds) -> str:
    try:
        seconds = int(seconds or 0)
    except Exception:
        return "—"
    if seconds <= 0:
        return "—"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class LinkPreviewWorker(QThread):
    ready = Signal(dict)

    def __init__(self, url: str, settings: dict, parent=None):
        super().__init__(parent)
        self.url = url
        self.settings = settings

    def run(self):
        try:
            self.ready.emit(self._load_preview())
        except Exception as exc:
            self.ready.emit({"ok": False, "error": str(exc)})

    def _load_preview(self) -> dict:
        service = service_for_url(self.url) or "unknown"
        cookies_file = cookie_file_for_url(self.url)
        if not cookies_file and self.settings.get("auto_export_cookies", True):
            cookies_file, _ = ensure_cookie_file_for_url(self.url)
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": False,
            "extract_flat": False,
            "ffmpeg_location": os.path.dirname(get_binary_path("ffmpeg")),
        }
        if cookies_file and os.path.isfile(cookies_file):
            opts["cookiefile"] = cookies_file

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(self.url, download=False)
        if not info:
            raise RuntimeError("Ссылка недоступна")

        is_playlist = info.get("_type") == "playlist" or bool(info.get("entries"))
        entries = [e for e in info.get("entries", []) if e] if is_playlist else []
        formats = info.get("formats") or []
        heights = sorted({f.get("height") for f in formats if f.get("height")}, reverse=True)
        fps = sorted({int(f.get("fps")) for f in formats if f.get("fps")}, reverse=True)
        subtitles = sorted((info.get("subtitles") or {}).keys())
        automatic = sorted((info.get("automatic_captions") or {}).keys())
        size = info.get("filesize") or info.get("filesize_approx")

        return {
            "ok": True,
            "service": service.title(),
            "kind": "Плейлист" if is_playlist else ("Аудио" if service == "soundcloud" else "Видео"),
            "title": info.get("title") or self.url,
            "duration": _duration_text(info.get("duration")),
            "count": len(entries) if is_playlist else 1,
            "qualities": ", ".join(f"{h}p" for h in heights[:6]) or "—",
            "fps": ", ".join(str(v) for v in fps[:4]) or "—",
            "subtitles": ", ".join((subtitles or automatic)[:5]) or "—",
            "size": size or 0,
        }
