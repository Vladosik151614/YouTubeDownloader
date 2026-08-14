"""External TikTok fallback providers used by the application."""
from __future__ import annotations

import threading
import time
from html import unescape
from urllib.parse import urljoin

from curl_cffi import requests

from app.logger import logger
from app.tiktok_quality import download_quality_score, probe_remote_quality

_TIKWM_API_LOCK = threading.Lock()
_TIKWM_LAST_API_REQUEST = 0.0


def _wait_for_tikwm_api_slot(min_interval: float = 1.4) -> None:
    """TikWM free endpoint rate-limits bursts; keep discovery steady."""
    global _TIKWM_LAST_API_REQUEST
    with _TIKWM_API_LOCK:
        now = time.monotonic()
        wait = min_interval - (now - _TIKWM_LAST_API_REQUEST)
        if wait > 0:
            time.sleep(wait)
        _TIKWM_LAST_API_REQUEST = time.monotonic()


def tikwm_video_candidates(video_url: str) -> list[dict]:
    """Return TikWM direct MP4 candidates, preferring its HD/original stream."""
    session = requests.Session(impersonate="chrome131")
    base_url = "https://www.tikwm.com"
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    payload = {}
    last_error = ""
    for attempt in range(4):
        _wait_for_tikwm_api_slot()
        response = session.post(
            base_url + "/api/",
            data={"url": video_url, "hd": 1},
            headers={
                "User-Agent": user_agent,
                "Origin": base_url,
                "Referer": base_url + "/originalDownloader.html",
            },
            timeout=30,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"TikWM API HTTP {response.status_code}")
        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError("TikWM API вернул не JSON") from exc
        if payload.get("code") == 0:
            break
        last_error = str(payload.get("msg") or "TikWM API не отдал видео")
        if "limit" not in last_error.lower():
            raise RuntimeError(last_error)
        time.sleep(1.5 + attempt)
    if payload.get("code") != 0:
        raise RuntimeError(last_error or "TikWM API не отдал видео")
    data = payload.get("data") or {}
    candidates = []
    seen = set()

    def add(key: str, label: str, priority: int):
        url = data.get(key)
        if not isinstance(url, str) or not url:
            return
        url = unescape(urljoin(base_url + "/", url))
        if url in seen or not url.startswith(("http://", "https://")):
            return
        seen.add(url)
        candidates.append({
            "url": url,
            "label": label,
            "priority": priority,
            "referer": base_url + "/originalDownloader.html",
            "impersonate": "chrome131",
            "provider": "tikwm",
            "method": "GET",
            "data": {},
        })

    add("hdplay", "TikWM HD/original", 45)
    add("play", "TikWM no-watermark", 25)
    return candidates


def tikwm_best_quality(video_url: str) -> dict:
    """Probe TikWM candidates and return the best real downloadable quality."""
    best = {}
    for candidate in tikwm_video_candidates(video_url):
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Referer": str(candidate.get("referer") or "https://www.tikwm.com/"),
        }
        try:
            quality = probe_remote_quality(str(candidate["url"]), headers)
        except Exception as exc:
            logger.warning(f"TikWM quality probe failed for {video_url}: {exc}")
            continue
        quality["candidate"] = candidate
        quality["provider"] = "tikwm"
        quality["candidate_label"] = str(candidate.get("label") or "TikWM")
        if not best or download_quality_score(quality) > download_quality_score(best):
            best = quality
    return best
