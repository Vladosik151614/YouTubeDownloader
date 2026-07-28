"""
path_manager.py - output folder routing for services and media types.
"""
from __future__ import annotations

import os
import re

from app.auth_manager import service_for_url


SERVICE_FOLDER = {
    "youtube": "YouTube",
    "soundcloud": "SoundCloud",
    "twitch": "Twitch",
    "tiktok": "TikTok",
    "spotify": "Spotify",
}


def safe_name(value: str, fallback: str = "download") -> str:
    cleaned = re.sub(r'[<>:"/\\\\|?*]+', "_", value or "").strip().strip(".")
    return cleaned[:120] or fallback


def default_download_root() -> str:
    return os.path.join(os.path.expanduser("~"), "Videos", "YouTubeDownloader").replace("\\", "/")


def service_output_folder(base_folder: str, url: str, download_type: str = "video") -> str:
    service = service_for_url(url)
    service_dir = SERVICE_FOLDER.get(service, "Other")
    if download_type == "audio" or service in {"soundcloud", "spotify"}:
        media_dir = "Music"
    elif download_type == "pictures":
        media_dir = "Pictures"
    elif download_type == "documents":
        media_dir = "Documents"
    else:
        media_dir = "Video"
    return os.path.join(base_folder, service_dir, media_dir)
