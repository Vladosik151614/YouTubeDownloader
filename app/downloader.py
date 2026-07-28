"""
downloader.py — загрузка видео/плейлистов через yt-dlp в отдельном QThread
с защитой от сбоев (пропуск недоступных/приватных/удаленных видео в плейлистах).
"""
import os
import re
import yt_dlp
from PySide6.QtCore import QThread, Signal
from app.logger import logger
from app.binary_manager import get_binary_path
from app.auth_manager import cookie_file_for_url, ensure_cookie_file_for_url, refresh_cookie_file_for_url
from app.download_utils import (
    YtDlpLogCollector,
    format_bytes,
    is_playlist,
    rate_limit_bytes,
    set_sleep_prevention,
)
from app.path_manager import service_output_folder
from app.proxy_config import proxy_url_from_settings
from app.settings_manager import APP_DATA_DIR


class DownloadWorker(QThread):
    """
    Сигналы:
        progress(item_id, percent, speed, eta)
        status(item_id, text)
        finished(item_id, filepath, success, error_msg)
        info_ready(item_id, title, is_playlist, entries_count, estimated_size_str)
    """
    progress = Signal(str, float, str, str)
    status = Signal(str, str)
    finished = Signal(str, str, bool, str)
    info_ready = Signal(str, str, bool, int, str)

    def __init__(self, item_id: str, url: str, output_folder: str, settings: dict, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.url = url
        self.output_folder = output_folder
        self.settings = settings
        self._cancelled = False
        self._ydl_logger = YtDlpLogCollector(item_id)
        self._auth_retry_used = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            if self.settings.get("prevent_sleep", True):
                set_sleep_prevention(True)
            self._download()
        except Exception as e:
            logger.error(f"[{self.item_id}] Download worker exception: {e}")
            self.finished.emit(self.item_id, "", False, str(e))
        finally:
            if self.settings.get("prevent_sleep", True):
                set_sleep_prevention(False)

    def _progress_hook(self, d):
        if self._cancelled:
            raise yt_dlp.utils.DownloadCancelled("Отменено пользователем")
        
        status = d.get("status", "")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            percent = (downloaded / total * 100) if total > 0 else 0
            speed = d.get("_speed_str", "—")
            eta = d.get("_eta_str", "—")
            self.progress.emit(self.item_id, percent, speed, eta)
        elif status == "finished":
            self.status.emit(self.item_id, "Обработка файла...")

    def _build_ydl_opts(self) -> dict:
        ffmpeg_bin = get_binary_path("ffmpeg")
        deno_bin = get_binary_path("deno")
        container = self.settings.get("container", "mp4")
        quality = str(self.settings.get("download_quality", "1080"))
        fps = str(self.settings.get("fps_limit", "best"))
        download_type = self.settings.get("download_type", "video")
        if self.settings.get("auto_route_folders", True):
            self.output_folder = service_output_folder(self.output_folder, self.url, download_type)
            os.makedirs(self.output_folder, exist_ok=True)

        if download_type == "audio":
            fmt = "bestaudio/best"
        elif download_type in {"pictures", "documents"}:
            fmt = "best"
        else:
            height_filter = "" if quality == "best" else f"[height<={quality}]"
            fps_filter = "" if fps == "best" else f"[fps<={fps}]"
            media_filter = f"{height_filter}{fps_filter}"
            if container == "webm":
                fmt = (
                    f"bestvideo[ext=webm]{media_filter}+bestaudio[ext=webm]/"
                    f"bestvideo{media_filter}+bestaudio/"
                    "best"
                )
            else:
                fmt = (
                    f"bestvideo[ext=mp4]{media_filter}+bestaudio[ext=m4a]/"
                    f"bestvideo[ext=mp4][vcodec^=avc]{media_filter}+bestaudio[ext=m4a]/"
                    f"bestvideo{media_filter}+bestaudio/"
                    "best[ext=mp4]/best"
                )
        
        if is_playlist(self.url) and self.settings.get("playlist_subfolders", True):
            filename = "%(playlist_index)03d - %(title)s.%(ext)s" if self.settings.get("playlist_numbering", True) else "%(title)s.%(ext)s"
            outtmpl = os.path.join(self.output_folder, "%(playlist_title)s", filename)
        else:
            outtmpl = os.path.join(self.output_folder, "%(title)s.%(ext)s")
        
        opts = {
            "format": fmt,
            "outtmpl": outtmpl,
            "progress_hooks": [self._progress_hook],
            "logger": self._ydl_logger,
            "merge_output_format": container,
            "skip_download": download_type in {"pictures", "documents"},
            "noplaylist": False,
            "ignoreerrors": True,               # Пропускать ошибки отдельного видео в плейлисте
            "skip_unavailable_fragments": True, # Пропускать поврежденные фрагменты
            "fragment_retries": 10,
            "retries": 5,
            "extractor_retries": 3,
            "socket_timeout": 20,
            "continuedl": True,
            "writeinfojson": False,
            "quiet": True,
            "no_warnings": False,
            "no_color": True,
            "source_address": "0.0.0.0",
            "ffmpeg_location": os.path.dirname(ffmpeg_bin) if os.path.isfile(ffmpeg_bin) else None,
        }

        if download_type == "pictures":
            opts.update({"writethumbnail": True, "writeinfojson": False})
        elif download_type == "documents":
            opts.update({"writedescription": True, "writeinfojson": True, "writesubtitles": True})

        rate_limit = rate_limit_bytes(self.settings.get("speed_limit", "unlimited"))
        if rate_limit:
            opts["ratelimit"] = rate_limit

        proxy_url = proxy_url_from_settings(self.settings)
        if proxy_url:
            opts["proxy"] = proxy_url

        if self.settings.get("skip_duplicates", True):
            os.makedirs(APP_DATA_DIR, exist_ok=True)
            opts["download_archive"] = os.path.join(APP_DATA_DIR, "download_archive.txt")

        if self.settings.get("embed_subtitles", False):
            opts.update({
                "writesubtitles": True,
                "writeautomaticsub": False,
                "subtitleslangs": ["all"],
                "embedsubtitles": True,
            })

        if os.path.isfile(deno_bin):
            opts["js_runtimes"] = {"deno": {"path": deno_bin}}
        
        # Cookies
        cookies_file = cookie_file_for_url(self.url)
        if not cookies_file and self.settings.get("auto_export_cookies", True):
            cookies_file, auth_message = ensure_cookie_file_for_url(self.url)
            if auth_message:
                logger.info(f"[{self.item_id}] Auto cookie export: {auth_message}")
        if not cookies_file:
            cookies_file = self.settings.get("cookies_file", "")
        if cookies_file and os.path.isfile(cookies_file):
            opts["cookiefile"] = cookies_file
        
        cookies_browser = self.settings.get("cookies_from_browser", "")
        if cookies_browser:
            opts["cookiesfrombrowser"] = (cookies_browser, None, None, None)
        
        return opts

    def _playlist_preflight_info(self, opts: dict) -> tuple[dict, bool]:
        """
        Read playlist metadata quickly without resolving every video format first.
        Large YouTube playlists can otherwise sit on "Получение информации..."
        for a very long time before the first file starts downloading.
        """
        if not is_playlist(self.url):
            return {}, False
        flat_opts = dict(opts)
        flat_opts.update({
            "extract_flat": "in_playlist",
            "skip_download": True,
            "playlist_items": None,
            "progress_hooks": [],
        })
        self.status.emit(self.item_id, "Чтение списка плейлиста...")
        logger.info(f"[{self.item_id}] Fast playlist preflight started")
        with yt_dlp.YoutubeDL(flat_opts) as ydl:
            info = ydl.extract_info(self.url, download=False)
        if not info:
            return {}, False
        entries = [entry for entry in (info.get("entries") or []) if entry]
        logger.info(
            f"[{self.item_id}] Fast playlist preflight done: "
            f"title={info.get('title', 'Без названия')}, entries={len(entries)}"
        )
        return info, True

    def _write_m3u(self, files: list[str], playlist_title: str):
        if not files:
            return
        safe_name = re.sub(r'[<>:"/\\\\|?*]+', "_", playlist_title or "playlist").strip() or "playlist"
        m3u_path = os.path.join(self.output_folder, f"{safe_name}.m3u")
        try:
            with open(m3u_path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for path in files:
                    f.write(os.path.abspath(path) + "\n")
            logger.info(f"[{self.item_id}] M3U created: {m3u_path}")
        except Exception as e:
            logger.warning(f"[{self.item_id}] Could not create M3U: {e}")

    def _friendly_error(self, raw_message: str) -> str:
        all_messages = " ".join([raw_message] + self._ydl_logger.messages)
        text = all_messages.lower()

        if "could not copy chrome cookie database" in text or (
            "permission denied" in text and "network\\cookies" in text
        ):
            return (
                "Не удалось прочитать cookies Chrome. Приложение больше не использует Chrome "
                "автоматически: очистите выбор браузера в настройках или укажите свежий cookies.txt."
            )

        if "sign in to confirm" in text or "not a bot" in text:
            return (
                "YouTube просит подтвердить, что это не бот. Приложение уже пробует IPv4; "
                "если ошибка повторится, нужен свежий cookies.txt, потому что прямое чтение Chrome "
                "на этой машине может не работать."
            )

        if "failed to load cookies" in text or "failed to decrypt" in text:
            return (
                "Не удалось загрузить cookies браузера. Уберите Chrome из настроек cookies "
                "или выберите свежий cookies.txt."
            )

        return raw_message

    def _looks_like_auth_error(self, message: str) -> bool:
        text = " ".join([message] + self._ydl_logger.messages).lower()
        markers = [
            "sign in",
            "login",
            "not a bot",
            "confirm your age",
            "age-restricted",
            "private video",
            "members-only",
            "subscriber",
            "cookies",
            "forbidden",
            "http error 403",
            "your ip address is blocked",
        ]
        return any(marker in text for marker in markers)

    def _refresh_cookies_and_retry(self, message: str) -> bool:
        if self._auth_retry_used or not self.settings.get("auto_export_cookies", True):
            return False
        if not self._looks_like_auth_error(message):
            return False
        self._auth_retry_used = True
        self.status.emit(self.item_id, "Обновление доступа...")
        cookies_file, auth_message = refresh_cookie_file_for_url(self.url)
        if auth_message:
            logger.info(f"[{self.item_id}] Auth refresh: {auth_message}")
        if not cookies_file:
            return False
        self._ydl_logger = YtDlpLogCollector(self.item_id)
        return True

    def _snapshot_output_files(self) -> set[str]:
        try:
            files = set()
            for root, _, names in os.walk(self.output_folder):
                for name in names:
                    path = os.path.join(root, name)
                    if os.path.isfile(path):
                        files.add(path)
            return files
        except Exception:
            return set()

    def _new_media_files(self, before: set[str]) -> list[str]:
        media_exts = {".mp4", ".mkv", ".webm", ".m4a", ".mp3", ".opus", ".jpg", ".jpeg", ".png", ".webp", ".json", ".description", ".vtt", ".srt"}
        after = self._snapshot_output_files()
        return sorted(
            path for path in after - before
            if os.path.splitext(path)[1].lower() in media_exts and os.path.getsize(path) > 0
        )

    def _single_output_path(self, ydl, info) -> str:
        filename = ydl.prepare_filename(info)
        base = os.path.splitext(filename)[0]
        candidates = [
            base + ".mp4",
            filename,
            base + ".mkv",
            base + ".webm",
        ]
        for candidate in candidates:
            if os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
                return candidate
        return base + ".mp4"

    def _download(self):
        self.status.emit(self.item_id, "Получение информации...")
        opts = self._build_ydl_opts()
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            logger.info(
                f"[{self.item_id}] Download options: folder={self.output_folder}, "
                f"type={self.settings.get('download_type')}, quality={self.settings.get('download_quality')}, "
                f"fps={self.settings.get('fps_limit')}, container={self.settings.get('container')}, "
                f"playlist_subfolders={self.settings.get('playlist_subfolders')}, "
                f"skip_duplicates={self.settings.get('skip_duplicates')}"
            )
            try:
                if is_playlist(self.url):
                    info, fast_playlist = self._playlist_preflight_info(opts)
                else:
                    self.status.emit(self.item_id, "Получение информации...")
                    info = ydl.extract_info(self.url, download=False)
                    fast_playlist = False
            except Exception as e:
                if self._refresh_cookies_and_retry(str(e)):
                    self._download()
                    return
                raise RuntimeError(self._friendly_error(f"Не удалось получить данные ссылки: {e}"))
            
            if info is None:
                raise RuntimeError(self._friendly_error("Ссылка недоступна или заблокирована"))
            
            pl = is_playlist(self.url) or info.get("_type") == "playlist"
            title = info.get("title", "Без названия")
            
            entries = []
            if pl and "entries" in info:
                # Фильтруем None в случае если отдельные видео недоступны в плейлисте
                entries = [e for e in info["entries"] if e is not None]
            
            count = len(entries) if pl else 1
            if pl and count == 0:
                raise RuntimeError(self._friendly_error("Плейлист найден, но доступных видео в нём нет"))

            total_size = 0
            if pl and not fast_playlist:
                for entry in entries:
                    if entry:
                        total_size += entry.get("filesize") or entry.get("filesize_approx") or 0
            else:
                total_size = info.get("filesize") or info.get("filesize_approx") or 0

            size_str = format_bytes(total_size)
            self.info_ready.emit(self.item_id, title, pl, count, size_str)
            
            self.status.emit(self.item_id, "Загрузка...")
            logger.info(f"[{self.item_id}] Downloading {title} (Плейлист: {pl}, видео: {count}, размер: {size_str})")
            
            files_before = self._snapshot_output_files()
            download_error = None
            try:
                result = ydl.download([self.url])
                if result not in (None, 0):
                    download_error = f"yt-dlp вернул код ошибки: {result}"
            except yt_dlp.utils.DownloadCancelled:
                self.status.emit(self.item_id, "Отменено")
                self.finished.emit(self.item_id, "", False, "Отменено пользователем")
                return
            except Exception as dl_err:
                download_error = str(dl_err)
                logger.warning(f"[{self.item_id}] Download error: {dl_err}")

            if self._ydl_logger.errors:
                download_error = self._ydl_logger.errors[-1]
            logger.info(
                f"[{self.item_id}] yt-dlp finished with warnings={len(self._ydl_logger.messages)} "
                f"errors={len(self._ydl_logger.errors)} last_error={download_error or 'none'}"
            )
            
            if pl:
                new_files = self._new_media_files(files_before)
                if download_error and not new_files:
                    if self._refresh_cookies_and_retry(download_error):
                        self._download()
                        return
                    raise RuntimeError(self._friendly_error(f"Не удалось загрузить плейлист: {download_error}"))
                if download_error and new_files:
                    logger.warning(
                        f"[{self.item_id}] Playlist completed with skipped/problem items. "
                        f"Saved files: {len(new_files)}. Last issue: {download_error}"
                    )
                if self.settings.get("create_m3u", False):
                    self._write_m3u(new_files, title)
                filepath = self.output_folder
            else:
                generated_files = self._new_media_files(files_before)
                filepath = generated_files[0] if self.settings.get("download_type") in {"pictures", "documents"} and generated_files else self._single_output_path(ydl, info)
                if download_error:
                    if self._refresh_cookies_and_retry(download_error):
                        self._download()
                        return
                    raise RuntimeError(self._friendly_error(f"Не удалось загрузить видео: {download_error}"))
                if not os.path.isfile(filepath):
                    raise RuntimeError(self._friendly_error("Загрузка закончилась без готового файла"))
            
            logger.info(f"[{self.item_id}] Download process finished: {filepath}")
            self.status.emit(self.item_id, "Завершено")
            self.finished.emit(self.item_id, filepath, True, "")
