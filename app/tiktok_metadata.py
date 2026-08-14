"""TikTok catalog extraction and source-quality metadata helpers."""
from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import yt_dlp
from PySide6.QtCore import QThread, Signal
from yt_dlp.extractor.tiktok import TikTokUserIE

from app.auth_manager import cookie_file_for_url, ensure_cookie_file_for_url
from app.download_utils import _best_thumbnail
from app.error_messages import classify_download_error
from app.logger import logger
from app.tiktok_external import tikwm_best_quality
from app.tiktok_quality import best_quality_info, source_quality as measured_source_quality


def is_tiktok_collection_url(url: str) -> bool:
    value = str(url or "").lower().split("#", 1)[0]
    if "tiktok.com/" not in value or "/video/" in value:
        return False
    markers = ("/playlist/", "/collection/")
    return bool(
        any(marker in value for marker in markers)
        or re.search(r"tiktok\.com/@[^/?]+/?(?:\?.*)?$", value)
    )


def normalize_catalog_entries(entries, source_url: str) -> list[dict]:
    username_match = re.search(r"tiktok\.com/@([^/?]+)", source_url, re.IGNORECASE)
    username = username_match.group(1) if username_match else ""
    result = []
    for position, entry in enumerate(entries or [], start=1):
        if not entry:
            continue
        video_id = str(entry.get("id") or "")
        url = str(
            entry.get("webpage_url")
            or entry.get("original_url")
            or entry.get("url")
            or ""
        )
        if not url.startswith(("http://", "https://")) and username and video_id:
            url = f"https://www.tiktok.com/@{username}/video/{video_id}"
        if not url.startswith(("http://", "https://")):
            continue
        thumbnails = entry.get("thumbnails") or []
        animated_thumbnail = next(
            (str(item.get("url") or "") for item in thumbnails
             if item.get("id") == "dynamicCover"),
            "",
        )
        result.append({
            "index": int(entry.get("playlist_index") or position),
            "id": video_id,
            "url": url,
            "title": str(
                entry.get("title")
                or entry.get("description")
                or f"Видео {position}"
            ),
            "thumbnail": _best_thumbnail(
                entry.get("thumbnail") or "", thumbnails
            ),
            "animated_thumbnail": animated_thumbnail,
            "duration": int(entry.get("duration") or 0),
            "source_quality": source_quality(entry),
        })
    return result


def extract_catalog_playlists(info: dict) -> list[dict]:
    """Return profile playlist/collection links when TikTok exposes them."""
    seen = set()
    result = []

    def visit(value):
        if isinstance(value, dict):
            title = value.get("mixName") or value.get("playlistName") or value.get("title")
            mix_id = value.get("mixId") or value.get("playlistId") or value.get("id")
            url = value.get("webpage_url") or value.get("url")
            if not url and mix_id and info.get("uploader_url"):
                url = f"{str(info['uploader_url']).rstrip('/')}/collection/{title or 'playlist'}-{mix_id}"
            if url and title and "tiktok.com/" in str(url).lower():
                key = str(url)
                if key not in seen:
                    seen.add(key)
                    result.append({"title": str(title), "url": key})
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for key in ("mixes", "playlists", "collections", "playlist"):
        visit(info.get(key))
    return result


def _codec_label(codec: str) -> str:
    value = str(codec or "").lower()
    if any(token in value for token in ("h265", "hevc", "hvc1")):
        return "H.265"
    if any(token in value for token in ("h264", "avc")):
        return "H.264"
    if "vp9" in value:
        return "VP9"
    if any(token in value for token in ("av1", "av01")):
        return "AV1"
    return value.upper() if value and value != "none" else ""


def _resolution_label(width: int, height: int) -> str:
    short_side = min(value for value in (width, height) if value > 0)
    if short_side > 1080:
        return "1080p+"
    if short_side >= 1080:
        return "1080p"
    if short_side >= 720:
        return "720p"
    if short_side >= 540:
        return "540p"
    return f"{short_side}p"


def source_quality(info: dict) -> dict:
    quality = measured_source_quality(info)
    if quality and not info.get("verified_remote") and not info.get("provider"):
        quality["confidence"] = "reported"
    return quality


def select_preview_format(formats: list[dict], *, prefer_h264: bool = False) -> dict:
    candidates = [
        item for item in formats or []
        if item.get("url")
        and item.get("vcodec") != "none"
        and "watermarked" not in str(item.get("format_note") or "").lower()
        and not item.get("has_watermark")
    ]
    combined = [
        item for item in candidates if item.get("acodec") not in {None, "none"}
    ]
    pool = combined or candidates
    if prefer_h264:
        compatible = [
            item for item in pool
            if "h264" in str(item.get("vcodec") or "").lower()
            or "avc" in str(item.get("vcodec") or "").lower()
        ]
        pool = compatible or pool
    return max(
        pool,
        key=lambda item: (
            min(int(item.get("width") or 0), int(item.get("height") or 0)),
            float(item.get("fps") or 0),
            float(item.get("tbr") or 0),
        ),
        default={},
    )


def _ydl_access_options(url: str, settings: dict) -> dict:
    options = {"quiet": True, "no_warnings": True}
    cookies_file = cookie_file_for_url(url)
    if not cookies_file and settings.get("auto_export_cookies", True):
        cookies_file, _ = ensure_cookie_file_for_url(url)
    if cookies_file and os.path.isfile(cookies_file):
        options["cookiefile"] = cookies_file
    return options


def _video_source_data(parser: TikTokUserIE, video: dict, username: str) -> dict:
    video_id = str(video.get("id") or video.get("aweme_id") or "")
    webpage_url = f"https://www.tiktok.com/@{username}/video/{video_id}"
    parsed = parser._parse_aweme_video_web(
        video, webpage_url, video_id, extract_flat=False
    )
    clean = select_preview_format(parsed.get("formats") or [])
    preview = select_preview_format(
        parsed.get("formats") or [], prefer_h264=True
    )
    video_info = video.get("video") or {}
    fps_values = []
    bitrate_items = (video_info.get("bitrateInfo") or []) + (video_info.get("bit_rate") or [])
    quality_candidates = []
    for item in bitrate_items:
        play_addr = item.get("PlayAddr") or item.get("play_addr") or {}
        width = (
            item.get("Width") or item.get("width")
            or play_addr.get("Width") or play_addr.get("width")
            or video_info.get("width")
        )
        height = (
            item.get("Height") or item.get("height")
            or play_addr.get("Height") or play_addr.get("height")
            or video_info.get("height")
        )
        codec = (
            item.get("CodecType") or item.get("codecType")
            or item.get("codec_type") or video_info.get("codecType")
        )
        bitrate = item.get("Bitrate") or item.get("bitrate") or item.get("bit_rate")
        item_fps = 0
        for key in ("BitrateFPS", "FPS", "fps"):
            try:
                value = float(item.get(key) or 0)
            except (TypeError, ValueError):
                value = 0
            if value:
                fps_values.append(value)
                item_fps = value
        quality_candidates.append({
            "width": width,
            "height": height,
            "fps": item_fps,
            "vcodec": codec,
            "bitrate": bitrate,
        })
    quality_candidates.extend([
        {
            "width": item.get("width"),
            "height": item.get("height"),
            "fps": item.get("fps") or 0,
            "vcodec": item.get("vcodec"),
            "tbr": item.get("tbr") or 0,
        }
        for item in (parsed.get("formats") or [])
        if item.get("url")
        and item.get("vcodec") != "none"
        and "watermarked" not in str(item.get("format_note") or "").lower()
        and not item.get("has_watermark")
    ])
    best_reported = best_quality_info(quality_candidates)
    quality = source_quality({
        "width": best_reported.get("width") or clean.get("width") or video_info.get("width"),
        "height": best_reported.get("height") or clean.get("height") or video_info.get("height"),
        "fps": best_reported.get("fps") or clean.get("fps") or max(fps_values or [0]),
        "vcodec": best_reported.get("vcodec") or clean.get("vcodec") or video_info.get("codecType"),
    })
    return {
        "source_quality": quality,
        "download_stream_url": str(clean.get("url") or ""),
        "download_headers": {
            **(parsed.get("http_headers") or {}),
            **(clean.get("http_headers") or {}),
        },
        "preview_stream_url": str(preview.get("url") or ""),
        "preview_headers": {
            **(parsed.get("http_headers") or {}),
            **(preview.get("http_headers") or {}),
        },
    }


def _profile_source_data(ydl, sec_uid: str, username: str, ids: set[str]) -> dict:
    if not sec_uid or not username or not ids:
        return {}
    parser = TikTokUserIE(ydl)
    cursor = int(time.time() * 1000)
    result = {}
    for _ in range(12):
        response = parser._download_json(
            parser._API_BASE_URL,
            username,
            "Читаю исходное качество TikTok",
            query=parser._build_web_query(sec_uid, cursor),
        )
        videos = response.get("itemList") or []
        for video in videos:
            video_id = str(video.get("id") or "")
            if video_id in ids:
                result[video_id] = _video_source_data(parser, video, username)
        if ids.issubset(result) or not response.get("hasMorePrevious") or not videos:
            break
        next_cursor = int((videos[-1].get("createTime") or 0) * 1000)
        cursor = next_cursor or cursor - 7 * 86_400_000
    for details in result.values():
        for stream_key, headers_key in (
            ("download_stream_url", "download_headers"),
            ("preview_stream_url", "preview_headers"),
        ):
            stream_url = details.get(stream_key) or ""
            if not stream_url:
                continue
            headers = details.setdefault(headers_key, {})
            headers.setdefault("User-Agent", "Mozilla/5.0 Chrome/131 Safari/537.36")
            headers.setdefault("Referer", "https://www.tiktok.com/")
            cookie_header = ydl.cookiejar.get_cookie_header(stream_url)
            if cookie_header:
                headers["Cookie"] = cookie_header
    return result


def apply_downloadable_quality(entries: list[dict], probe_limit: int = 5) -> None:
    """Update visible catalog entries with verified downloadable quality."""
    for entry in entries[:max(0, int(probe_limit or 0))]:
        try:
            verified_quality = tikwm_best_quality(entry["url"])
        except Exception as exc:
            logger.warning(
                f"TikTok downloadable quality probe unavailable: {exc}"
            )
            continue
        if verified_quality:
            entry["source_quality"] = verified_quality


def resolve_downloadable_quality_batch(
    entries: list[dict], probe_limit: int = 100, max_workers: int = 5,
):
    """Yield verified downloadable quality results without blocking the catalog UI."""
    targets = [
        entry for entry in entries[:max(0, int(probe_limit or 0))]
        if entry.get("url")
    ]
    if not targets:
        return
    workers = max(1, min(8, int(max_workers or 1), len(targets)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_entry = {
            executor.submit(tikwm_best_quality, entry["url"]): entry
            for entry in targets
        }
        for future in as_completed(future_to_entry):
            entry = future_to_entry[future]
            try:
                quality = future.result()
            except Exception as exc:
                logger.warning(
                    f"TikTok downloadable quality probe unavailable: {exc}"
                )
                yield entry["url"], {"probe_failed": True}
                continue
            if quality:
                yield entry["url"], quality
            else:
                yield entry["url"], {"probe_failed": True}


class TikTokCatalogWorker(QThread):
    loaded = Signal(str, list, list)
    quality_resolved = Signal(str, dict)
    failed = Signal(str)

    def __init__(self, url: str, settings: dict, parent=None):
        super().__init__(parent)
        self.url = url
        self.settings = dict(settings)

    def run(self):
        try:
            options = _ydl_access_options(self.url, self.settings)
            options.update({
                "extract_flat": "in_playlist",
                "skip_download": True,
                "noplaylist": False,
            })
            limit = int(self.settings.get("tiktok_catalog_limit") or 0)
            if limit > 0:
                options["playlistend"] = limit
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(self.url, download=False) or {}
                entries = normalize_catalog_entries(info.get("entries") or [], self.url)
                playlists = extract_catalog_playlists(info)
                username_match = re.search(r"tiktok\.com/@([^/?]+)", self.url)
                if username_match and entries:
                    try:
                        details = _profile_source_data(
                            ydl,
                            str(info.get("id") or ""),
                            username_match.group(1),
                            {entry["id"] for entry in entries},
                        )
                        for entry in entries:
                            entry.update(details.get(entry["id"], {}))
                    except Exception as exc:
                        logger.warning(
                            f"TikTok source metadata fallback unavailable: {exc}"
                        )
            if not entries:
                if "/collection/" in self.url.lower() or "/playlist/" in self.url.lower():
                    raise RuntimeError("TIKTOK_EMPTY_COLLECTION")
                raise RuntimeError("TikTok не вернул доступные видео профиля")
            self.loaded.emit(str(info.get("title") or "TikTok"), entries, playlists)
            probe_limit = int(self.settings.get("tiktok_quality_probe_limit") or 100)
            workers = int(self.settings.get("tiktok_quality_probe_workers") or 5)
            for url, verified_quality in resolve_downloadable_quality_batch(
                entries, probe_limit, workers,
            ):
                self.quality_resolved.emit(url, verified_quality)
        except Exception as exc:
            self.failed.emit(classify_download_error(str(exc)).user_text())


class TikTokPreviewWorker(QThread):
    resolved = Signal(str, str, dict, dict, str)

    def __init__(self, video_url: str, settings: dict, parent=None):
        super().__init__(parent)
        self.video_url = video_url
        self.settings = dict(settings)

    def run(self):
        reason = "unavailable"
        try:
            options = _ydl_access_options(self.video_url, self.settings)
            options.update({"noplaylist": True, "skip_download": True})
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(self.video_url, download=False) or {}
                formats = info.get("formats") or []
                source = select_preview_format(formats)
                playable = select_preview_format(formats, prefer_h264=True)
                reason = "watermark" if formats and not playable else "unavailable"
                if not playable:
                    raise RuntimeError("Поток предпросмотра недоступен")
                stream_url = str(playable["url"])
                headers = {
                    str(key): str(value)
                    for origin in (
                        info.get("http_headers") or {},
                        playable.get("http_headers") or {},
                    )
                    for key, value in origin.items() if value is not None
                }
                headers.setdefault(
                    "User-Agent", "Mozilla/5.0 Chrome/131 Safari/537.36"
                )
                headers.setdefault("Referer", "https://www.tiktok.com/")
                cookie_header = ydl.cookiejar.get_cookie_header(stream_url)
                if cookie_header:
                    headers["Cookie"] = cookie_header
            self.resolved.emit(
                self.video_url, stream_url, headers, source_quality(source), ""
            )
        except Exception as exc:
            logger.warning(
                f"TikTok preview unavailable: "
                f"{classify_download_error(str(exc)).category}"
            )
            self.resolved.emit(self.video_url, "", {}, {}, reason)
