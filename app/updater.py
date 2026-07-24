"""
updater.py - download-system and application update workers.
"""
import json
import os
import re
import tempfile
import sys
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PySide6.QtCore import QThread, Signal
from app.logger import logger

APP_VERSION = "0.1.0"


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", value or "")
    return tuple(int(part) for part in parts[:4]) or (0,)


def _is_newer(remote: str, local: str = APP_VERSION) -> bool:
    return _version_tuple(remote) > _version_tuple(local)


class UpdateWorker(QThread):
    """
    Поток для проверки и выполнения обновлений yt-dlp.
    Сигналы:
        finished(success, message)
    """
    finished = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            logger.info("Starting download-system update check & upgrade...")
            cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode == 0:
                output = res.stdout.strip()
                if "Requirement already satisfied" in output:
                    msg = "Система загрузки уже обновлена."
                else:
                    msg = "Система загрузки обновлена."
                logger.info(f"Update result: {msg}")
                self.finished.emit(True, msg)
            else:
                err = res.stderr.strip() or "Ошибка установки через pip"
                logger.error(f"Update failed: {err}")
                self.finished.emit(False, f"Не удалось обновить: {err[:200]}")
        except Exception as e:
            logger.error(f"Update error: {e}")
            self.finished.emit(False, str(e))


class AppUpdateWorker(QThread):
    checked = Signal(dict)
    downloaded = Signal(bool, str)

    def __init__(self, settings: dict, download: bool = False, parent=None):
        super().__init__(parent)
        self.settings = dict(settings)
        self.download = download

    def run(self):
        try:
            release = self._latest_release()
            if not release:
                self.checked.emit({"ok": False, "message": "Источник обновлений приложения не настроен."})
                return
            info = self._release_info(release)
            self.checked.emit(info)
            if self.download and info.get("available"):
                self._download_asset(info)
        except Exception as exc:
            logger.error(f"Application update check failed: {exc}")
            self.checked.emit({"ok": False, "message": f"Не удалось проверить обновление: {exc}"})

    def _latest_release(self) -> dict | None:
        repo = str(self.settings.get("github_update_repo", "")).strip()
        if not repo:
            return None
        endpoint = "releases" if self.settings.get("install_beta_updates", False) else "releases/latest"
        url = f"https://api.github.com/repos/{repo}/{endpoint}"
        request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "YouTubeDownloader-Updater"})
        try:
            with urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"GitHub вернул ошибку {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError("нет соединения с сервером обновлений") from exc
        if isinstance(data, list):
            stable = [item for item in data if not item.get("draft")]
            if not self.settings.get("install_beta_updates", False):
                stable = [item for item in stable if not item.get("prerelease")]
            return stable[0] if stable else None
        return data

    def _release_info(self, release: dict) -> dict:
        tag = str(release.get("tag_name") or release.get("name") or "").lstrip("v")
        asset = self._find_asset(release)
        return {
            "ok": True,
            "available": _is_newer(tag),
            "version": tag,
            "current": APP_VERSION,
            "name": release.get("name") or tag,
            "notes": release.get("body") or "",
            "html_url": release.get("html_url") or "",
            "asset_name": asset.get("name", "") if asset else "",
            "asset_url": asset.get("browser_download_url", "") if asset else "",
            "message": "Доступно обновление приложения." if _is_newer(tag) else "Установлена последняя версия приложения.",
        }

    def _find_asset(self, release: dict) -> dict | None:
        pattern = str(self.settings.get("github_update_asset", "YouTubeDownloaderSetup")).lower()
        assets = release.get("assets") or []
        for asset in assets:
            name = str(asset.get("name", ""))
            if name.lower().endswith(".exe") and pattern in name.lower():
                return asset
        return None

    def _download_asset(self, info: dict) -> None:
        asset_url = info.get("asset_url", "")
        asset_name = info.get("asset_name", "") or "YouTubeDownloaderSetup.exe"
        if not asset_url:
            self.downloaded.emit(False, "В релизе не найден установщик приложения.")
            return
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", asset_name)
        target = os.path.join(tempfile.gettempdir(), safe_name)
        request = Request(asset_url, headers={"User-Agent": "YouTubeDownloader-Updater"})
        try:
            with urlopen(request, timeout=60) as response, open(target, "wb") as file:
                while True:
                    chunk = response.read(1024 * 128)
                    if not chunk:
                        break
                    file.write(chunk)
        except Exception as exc:
            self.downloaded.emit(False, f"Не удалось скачать обновление: {exc}")
            return
        self.downloaded.emit(True, target)
