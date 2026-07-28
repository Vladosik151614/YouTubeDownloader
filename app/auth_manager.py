"""
auth_manager.py - isolated browser profiles and local cookies for downloads.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from yt_dlp.cookies import extract_cookies_from_browser

from app.logger import logger
from app.process_utils import hidden_subprocess_kwargs
from app.settings_manager import APP_DATA_DIR


AUTH_DIR = os.path.join(APP_DATA_DIR, "auth")
PROFILE_ROOT = os.path.join(AUTH_DIR, "browser_profiles")
COOKIES_DIR = os.path.join(AUTH_DIR, "cookies")

SERVICE_HOSTS = {
    "youtube": ("youtube.com", "youtu.be"),
    "tiktok": ("tiktok.com",),
    "twitch": ("twitch.tv",),
    "soundcloud": ("soundcloud.com",),
    "spotify": ("spotify.com", "open.spotify.com"),
}

LOGIN_URLS = {
    "youtube": "https://" + "www.youtube.com",
    "tiktok": "https://www.tiktok.com/login",
    "twitch": "https://www.twitch.tv/login",
    "soundcloud": "https://soundcloud.com/signin",
    "spotify": "https://open.spotify.com",
}


def service_for_url(url: str) -> str:
    host = urlparse(url).netloc.lower().replace("www.", "")
    for service, hosts in SERVICE_HOSTS.items():
        if any(host == item or host.endswith("." + item) for item in hosts):
            return service
    return ""


def profile_dir(service: str) -> str:
    return os.path.join(PROFILE_ROOT, service)


def cookie_file(service: str) -> str:
    return os.path.join(COOKIES_DIR, f"{service}.cookies.txt")


def cookie_file_for_url(url: str) -> str:
    service = service_for_url(url)
    path = cookie_file(service) if service else ""
    return path if path and os.path.isfile(path) else ""


def ensure_cookie_file_for_url(url: str) -> tuple[str, str]:
    service = service_for_url(url)
    if not service:
        return "", ""

    existing = cookie_file(service)
    if os.path.isfile(existing):
        return existing, ""

    if not os.path.isdir(profile_dir(service)):
        return "", ""

    ok, message = export_service_cookies(service)
    if ok:
        return cookie_file(service), message
    return "", message


def refresh_cookie_file_for_url(url: str) -> tuple[str, str]:
    service = service_for_url(url)
    if not service:
        return "", ""
    if not os.path.isdir(profile_dir(service)):
        return "", "Для этой ссылки нужен вход в аккаунт. Откройте раздел Аккаунты и войдите один раз."
    ok, message = export_service_cookies(service)
    if ok:
        return cookie_file(service), message
    return "", message


def cookie_status(service: str) -> tuple[bool, int, str]:
    path = cookie_file(service)
    if not os.path.isfile(path):
        return False, 0, ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            count = sum(1 for line in f if line.strip() and not line.startswith("#"))
        return count > 0, count, path
    except Exception:
        return False, 0, path


def find_chrome_executable() -> str:
    candidates = [
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return ""


def open_login_browser(service: str) -> str:
    chrome = find_chrome_executable()
    if not chrome:
        raise FileNotFoundError("Chrome не найден. Установите Chrome или укажите cookies.txt вручную.")
    if service not in LOGIN_URLS:
        raise ValueError("Неизвестный сервис авторизации.")

    os.makedirs(profile_dir(service), exist_ok=True)
    args = [
        chrome,
        f"--user-data-dir={profile_dir(service)}",
        "--no-first-run",
        "--no-default-browser-check",
        LOGIN_URLS[service],
    ]
    subprocess.Popen(args, **hidden_subprocess_kwargs())
    logger.info(f"Opened isolated login browser for {service}")
    return profile_dir(service)


def export_service_cookies(service: str) -> tuple[bool, str]:
    if service not in SERVICE_HOSTS:
        return False, "Неизвестный сервис."
    profile = profile_dir(service)
    if not os.path.isdir(profile):
        return False, "Сначала откройте вход и авторизуйтесь."
    try:
        os.makedirs(COOKIES_DIR, exist_ok=True)
        jar = extract_cookies_from_browser("chrome", profile)
        path = cookie_file(service)
        jar.save(path, ignore_discard=True, ignore_expires=True)
        ok, count, _ = cookie_status(service)
        if not ok:
            return False, "Cookies не найдены. Проверьте, что вход выполнен в открытом окне."
        return True, f"Сохранено cookies: {count}"
    except PermissionError:
        return False, "Закройте окно входа этого приложения и повторите сохранение cookies."
    except Exception as exc:
        logger.error(f"Cookie export failed for {service}: {exc}")
        return False, f"Не удалось сохранить cookies: {exc}"


def clear_service_auth(service: str) -> None:
    for path in (cookie_file(service), profile_dir(service)):
        target = Path(path).resolve()
        auth_root = Path(AUTH_DIR).resolve()
        if auth_root not in target.parents and target != auth_root:
            raise RuntimeError("Refusing to delete path outside auth storage")
        if target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)
