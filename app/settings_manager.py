"""
settings_manager.py — сохранение и загрузка настроек приложения в JSON
"""
import json
import os
import sys

APP_NAME = "YouTubeDownloader"
APP_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), APP_NAME)
SETTINGS_FILE = os.path.join(APP_DATA_DIR, "settings.json")

os.makedirs(APP_DATA_DIR, exist_ok=True)

def _default_download_folder() -> str:
    return os.path.join(os.path.expanduser("~"), "Videos", "YouTubeDownloader").replace("\\", "/")


def _legacy_default_download_folder() -> str:
    return os.path.join(os.path.expanduser("~"), "Videos", "youtube").replace("\\", "/")

def _legacy_settings_files() -> list[str]:
    files = []
    if getattr(sys, "frozen", False):
        files.append(os.path.join(os.path.dirname(sys.executable), "settings.json"))
        if hasattr(sys, "_MEIPASS"):
            files.append(os.path.join(sys._MEIPASS, "settings.json"))
    files.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.json"))
    return [p for p in files if p != SETTINGS_FILE]

DEFAULTS = {
    "download_folder": _default_download_folder(),
    "download_type": "video",
    "download_quality": "1080",
    "fps_limit": "60",
    "container": "mp4",
    "default_codec": "original",
    "auto_convert": False,
    "ask_before_codec_convert": True,
    "encoding_mode": "gpu_auto",
    "video_encoder": "auto",
    "prefer_gpu": True,
    "keep_originals": False,
    "auto_update_ytdlp": False,
    "auto_update_app": True,
    "auto_download_updates": True,
    "install_beta_updates": False,
    "github_update_repo": "Vladosik151614/YouTubeDownloader",
    "github_update_asset": "YouTubeDownloaderSetup",
    "background_on_close": False,
    "launch_on_startup": False,
    "language": "en",
    "playlist_subfolders": True,
    "playlist_numbering": True,
    "auto_route_folders": True,
    "skip_duplicates": True,
    "create_m3u": False,
    "embed_subtitles": False,
    "show_all_codecs": True,
    "prevent_sleep": True,
    "remove_finished_from_list": False,
    "show_download_tools": True,
    "suggest_channel_download": True,
    "speed_limit": "unlimited",
    "proxy_enabled": False,
    "proxy_url": "",
    "proxy_type": "http",
    "proxy_host": "",
    "proxy_port": "",
    "proxy_username": "",
    "proxy_password": "",
    "notify_download_finished": True,
    "notify_processing_finished": True,
    "notify_new_content": False,
    "notify_recommendations": False,
    "confirm_exit_with_active_downloads": True,
    "show_in_notification_center": True,
    "play_notification_sound": False,
    "max_concurrent_downloads": 2,
    "cookies_from_browser": "",
    "cookies_file": "",
    "auto_export_cookies": True,
    "download_stats": False,
    "developer_mode": False,
    "avoid_duplicate_names": False,
    "theme": "lux_graphite",
}

def _read_settings_file(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULTS)
        merged.update(data)
        if "ask_before_codec_convert" not in data and data.get("default_codec") == "h264":
            merged["default_codec"] = "original"
            merged["auto_convert"] = False
        current_folder = str(merged.get("download_folder", "")).replace("\\", "/")
        if current_folder == _legacy_default_download_folder():
            merged["download_folder"] = _default_download_folder()
        if merged.get("theme") not in {"lux_graphite", "lux_midnight", "lux_silver"}:
            merged["theme"] = "lux_graphite"
        if merged.get("language") not in {"en", "de", "it"}:
            merged["language"] = "en"
        return merged
    except Exception:
        return None

def load_settings() -> dict:
    data = _read_settings_file(SETTINGS_FILE)
    if data is not None:
        return data

    for legacy_file in _legacy_settings_files():
        if os.path.exists(legacy_file):
            data = _read_settings_file(legacy_file)
            if data is not None:
                save_settings(data)
                return data

    defaults = dict(DEFAULTS)
    save_settings(defaults)
    return defaults


def save_settings(settings: dict) -> None:
    try:
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Settings] Cannot save: {e}")
