"""
link_preview.py - metadata preview before download.
"""
from __future__ import annotations

import os

import yt_dlp
from PySide6.QtCore import QThread, Signal

from app.auth_manager import cookie_file_for_url, ensure_cookie_file_for_url, service_for_url
from app.binary_manager import get_binary_path
from app.download_utils import YtDlpLogCollector


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
        if service == "spotify":
            kind = "Плейлист" if any(part in self.url.lower() for part in ["/playlist/", "/album/", "/artist/"]) else "Аудио"
            return {
                "ok": True,
                "service": "Spotify",
                "kind": kind,
                "title": self.url,
                "duration": "—",
                "count": 0 if kind == "Плейлист" else 1,
                "qualities": "Audio",
                "fps": "—",
                "subtitles": "—",
                "size": 0,
            }
        cookies_file = cookie_file_for_url(self.url)
        if not cookies_file and self.settings.get("auto_export_cookies", True):
            cookies_file, _ = ensure_cookie_file_for_url(self.url)
        opts = {
            "quiet": True,
            "no_warnings": True,
            # Frozen Windows builds may have no valid stderr handle. Route
            # yt-dlp diagnostics through the local redacted logger instead.
            "logger": YtDlpLogCollector("link-preview"),
            "noplaylist": False,
            # A playlist may contain hundreds of items. Fetching every video
            # here delays the preview by minutes; individual links still get
            # full metadata, while playlist entries stay lightweight.
            "extract_flat": "in_playlist",
            "socket_timeout": 15,
            "ffmpeg_location": os.path.dirname(get_binary_path("ffmpeg")),
        }
        deno = get_binary_path("deno")
        node = get_binary_path("node")
        if os.path.isfile(deno):
            opts["js_runtimes"] = {"deno": {"path": deno}}
        elif os.path.isfile(node):
            opts["js_runtimes"] = {"node": {"path": node}}
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
            "kind": "Плейлист" if is_playlist else ("Аудио" if service in {"soundcloud", "spotify"} else "Видео"),
            "title": info.get("title") or self.url,
            "duration": _duration_text(info.get("duration")),
            "count": len(entries) if is_playlist else 1,
            "qualities": ", ".join(f"{h}p" for h in heights[:6]) or "—",
            "fps": ", ".join(str(v) for v in fps[:4]) or "—",
            "subtitles": ", ".join((subtitles or automatic)[:5]) or "—",
            "size": size or 0,
        }
