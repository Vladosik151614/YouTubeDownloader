"""External TikTok fallback providers."""
from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin

from curl_cffi import requests


def tikwm_video_candidates(video_url: str) -> list[dict]:
    """Return TikWM direct MP4 candidates, preferring its HD/original stream."""
    session = requests.Session(impersonate="chrome131")
    base_url = "https://www.tikwm.com"
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
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
    if payload.get("code") != 0:
        raise RuntimeError(str(payload.get("msg") or "TikWM API не отдал видео"))
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


def ssstik_video_candidates(video_url: str) -> list[dict]:
    """Return ssstik MP4 candidates, including HD unlock links when exposed."""
    session = requests.Session(impersonate="chrome131")
    base_url = "https://ssstik.io"
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    home = session.get(
        base_url + "/",
        headers={"User-Agent": user_agent},
        timeout=20,
    )
    if home.status_code >= 400:
        raise RuntimeError(f"ssstik home HTTP {home.status_code}")
    token_match = (
        re.search(r"tt:'([\w\d]+)'", home.text)
        or re.search(r"tt\s*[:=]\s*[\"']([\w\d]+)", home.text)
    )
    if not token_match:
        raise RuntimeError("ssstik не отдал ключ загрузки")
    headers = {
        "User-Agent": user_agent,
        "Origin": base_url,
        "Referer": base_url + "/",
        "HX-Current-URL": base_url + "/",
        "HX-Request": "true",
        "HX-Target": "target",
        "HX-Trigger": "_gcaptcha_pt",
    }
    response = session.post(
        base_url + "/abc?url=dl",
        data={"id": video_url, "locale": "en", "tt": token_match.group(1)},
        headers=headers,
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"ssstik parse HTTP {response.status_code}")
    candidates = []
    seen = set()

    hidden_tt = ""
    hidden_match = re.search(r'name="tt"\s+value="([^"]+)"', response.text)
    if hidden_match:
        hidden_tt = unescape(hidden_match.group(1))

    def add(url: str, label: str, priority: int, *, method: str = "GET"):
        url = unescape(urljoin(base_url + "/", url or ""))
        if not url or url in seen:
            return
        if not url.startswith(("http://", "https://")):
            return
        seen.add(url)
        candidates.append({
            "url": url,
            "label": label,
            "priority": priority,
            "referer": base_url + "/",
            "impersonate": "chrome131",
            "provider": "ssstik",
            "method": method,
            "data": {"tt": hidden_tt} if method == "POST" and hidden_tt else {},
        })

    for attrs, text in re.findall(r"<a\b([^>]*)>(.*?)</a>", response.text, re.I | re.S):
        href_match = re.search(r'href="([^"]+)"', attrs)
        direct_match = re.search(r'data-directurl="([^"]+)"', attrs)
        class_match = re.search(r'class="([^"]+)"', attrs)
        id_match = re.search(r'id="([^"]+)"', attrs)
        marker = " ".join([
            class_match.group(1) if class_match else "",
            id_match.group(1) if id_match else "",
            re.sub(r"<[^>]+>", " ", text),
        ]).lower()
        is_hd = "hd" in marker or "full" in marker
        if direct_match:
            add(direct_match.group(1), "ssstik Full HD", 30 if is_hd else 15, method="POST")
        if href_match:
            href = unescape(href_match.group(1))
            if href.startswith("https://tikcdn.io/ssstik/") and "/m/" not in href:
                add(href, "ssstik Full HD" if is_hd else "ssstik no-watermark", 20 if is_hd else 10)
    return sorted(candidates, key=lambda item: item["priority"], reverse=True)


def ssstik_video_links(video_url: str) -> list[str]:
    """Return public ssstik no-watermark MP4 candidates for a TikTok video URL."""
    return [candidate["url"] for candidate in ssstik_video_candidates(video_url)]
