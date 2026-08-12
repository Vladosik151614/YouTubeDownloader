import os, time, yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget
from PySide6.QtCore import QThread, Signal
from app.logger import logger
from app.binary_manager import get_binary_path
from app.auth_manager import cookie_file_for_url, ensure_cookie_file_for_url, refresh_cookie_file_for_url
from app.download_utils import (
    YtDlpLogCollector,
    exclude_tiktok_watermarked_formats,
    format_bytes,
    is_playlist,
    playlist_entry_rows,
    media_size_bytes,
    remove_merged_audio_sidecars,
    rate_limit_bytes,
    set_sleep_prevention,
    thumbnail_url,
)
from app.download_artifacts import (
    new_media_files,
    single_output_path,
    snapshot_output_files,
    write_m3u,
)
from app.path_manager import service_output_folder
from app.proxy_config import proxy_url_from_settings
from app.settings_manager import APP_DATA_DIR
from app.spotify_engine import is_spotify_url, run_spotify_download
from app.error_messages import classify_download_error
from app.tiktok_download import download_tiktok_clean_stream_fallback, download_tiktok_ssstik_fallback, emit_tiktok_quality
class DownloadWorker(QThread):
    progress = Signal(str, float, str, str); status = Signal(str, str)
    finished = Signal(str, str, bool, str); info_ready = Signal(str, str, bool, int, str)
    thumbnail_ready = Signal(str, str); playlist_items_ready = Signal(str, list)
    playlist_item_progress = Signal(str, int, str, float)
    produced_files = Signal(str, list)
    quality_ready = Signal(str, dict)
    def __init__(self, item_id: str, url: str, output_folder: str, settings: dict, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.url = url
        self.base_output_folder = os.path.abspath(output_folder)
        self.settings = dict(settings)
        download_type = "audio" if is_spotify_url(url) else self.settings.get("download_type", "video")
        self.output_folder = (
            service_output_folder(self.base_output_folder, self.url, download_type)
            if self.settings.get("auto_route_folders", False) and not self.settings.get("exact_download_folder", True)
            else self.base_output_folder
        )
        self._cancelled = False
        self._ydl_logger = YtDlpLogCollector(item_id)
        self._auth_retry_used = False
        self._spotify_process = None
        self._last_progress_time = None
        self._last_downloaded = 0
        self._ema_speed = None
    def cancel(self):
        self._cancelled = True
        if self._spotify_process and self._spotify_process.poll() is None:
            self._spotify_process.terminate()
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
        info = d.get("info_dict") or {}
        playlist_index = info.get("playlist_index")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if downloaded < self._last_downloaded:
                self._last_progress_time = None
                self._last_downloaded = 0
                self._ema_speed = None
            percent = (downloaded / total * 100) if total > 0 else 0
            numeric_speed = d.get("speed")
            now = time.monotonic()
            if not numeric_speed and self._last_progress_time is not None and downloaded >= self._last_downloaded:
                elapsed = now - self._last_progress_time
                if elapsed > 0:
                    numeric_speed = (downloaded - self._last_downloaded) / elapsed
            if numeric_speed and numeric_speed > 0:
                alpha = 0.25
                self._ema_speed = numeric_speed if self._ema_speed is None else alpha * numeric_speed + (1 - alpha) * self._ema_speed
            self._last_progress_time = now
            self._last_downloaded = downloaded
            speed = format_bytes(int(self._ema_speed)) + "/s" if self._ema_speed else d.get("_speed_str", "—")
            remaining = max(0, total - downloaded)
            eta_seconds = int(remaining / self._ema_speed) if total and self._ema_speed else d.get("eta")
            if isinstance(eta_seconds, (int, float)):
                eta_seconds = int(eta_seconds)
                eta = f"{eta_seconds // 60:02d}:{eta_seconds % 60:02d}"
            else:
                eta = d.get("_eta_str", "—")
            self.progress.emit(self.item_id, percent, speed, eta)
            if isinstance(playlist_index, int):
                self.playlist_item_progress.emit(self.item_id, playlist_index, "Загрузка...", percent)
        elif status == "finished":
            self.status.emit(self.item_id, "Обработка файла...")
            if isinstance(playlist_index, int):
                self.playlist_item_progress.emit(self.item_id, playlist_index, "Обработка...", 100.0)
    def _build_ydl_opts(self) -> dict:
        ffmpeg_bin = get_binary_path("ffmpeg")
        deno_bin = get_binary_path("deno")
        container = self.settings.get("container", "mp4")
        quality = str(self.settings.get("download_quality", "1080"))
        fps = str(self.settings.get("fps_limit", "best"))
        download_type = self.settings.get("download_type", "video")
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
        if "tiktok.com/" in self.url.lower() and download_type == "video":
            fmt = exclude_tiktok_watermarked_formats(fmt)
        if is_playlist(self.url):
            filename = "%(playlist_index)03d - %(title)s.%(ext)s" if self.settings.get("playlist_numbering", False) else "%(title)s.%(ext)s"
            if self.settings.get("playlist_subfolders", False) and not self.settings.get("exact_download_folder", True):
                outtmpl = os.path.join(self.output_folder, "%(playlist_title)s", filename)
            else:
                outtmpl = os.path.join(self.output_folder, filename)
        else:
            outtmpl = os.path.join(self.output_folder, "%(title)s.%(ext)s")
        opts = {
            "format": fmt,
            "outtmpl": outtmpl,
            "progress_hooks": [self._progress_hook],
            "logger": self._ydl_logger,
            "merge_output_format": container,
            "keepvideo": False,
            "skip_download": download_type in {"pictures", "documents"},
            "noplaylist": False,
            "ignoreerrors": True,
            "skip_unavailable_fragments": True,
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
        if "tiktok.com/" in self.url.lower():
            try:
                opts["impersonate"] = ImpersonateTarget.from_str(
                    str(self.settings.get("tiktok_impersonate") or "chrome-131:android-14")
                )
            except Exception as exc:
                logger.warning(f"[{self.item_id}] TikTok impersonation disabled: {exc}")
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

    def _friendly_error(self, raw_message: str) -> str:
        combined = " ".join([str(raw_message)] + self._ydl_logger.messages)
        return classify_download_error(combined).user_text()

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

    def _finish_single_success(self, filepath: str):
        self._emit_tiktok_quality_if_needed([filepath])
        self.produced_files.emit(self.item_id, [filepath])
        self.status.emit(self.item_id, "Завершено")
        self.finished.emit(self.item_id, filepath, True, "")

    def _emit_tiktok_quality_if_needed(self, filepaths: list[str]):
        if "tiktok.com/" in self.url.lower():
            emit_tiktok_quality(self, filepaths)

    def _try_tiktok_fallbacks(self, opts: dict, title: str | None = None, *, profile: bool = True) -> bool:
        attempts = []
        if profile:
            attempts.append(("profile", lambda: download_tiktok_clean_stream_fallback(self, opts)))
        attempts.append(("ssstik", lambda: download_tiktok_ssstik_fallback(self, title)))
        for name, attempt in attempts:
            try:
                fallback = attempt()
                if fallback:
                    filepath, _title = fallback
                    self._finish_single_success(filepath)
                    return True
            except yt_dlp.utils.DownloadCancelled:
                self.status.emit(self.item_id, "Отменено")
                self.finished.emit(self.item_id, "", False, "Отменено пользователем")
                return True
            except Exception as fallback_exc:
                logger.warning(f"[{self.item_id}] TikTok {name} fallback failed: {fallback_exc}")
        return False

    def _download(self):
        if is_spotify_url(self.url):
            self._download_spotify()
            return
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
                if self._try_tiktok_fallbacks(opts):
                    return
                if self._refresh_cookies_and_retry(str(e)):
                    self._download()
                    return
                raise RuntimeError(self._friendly_error(f"Не удалось получить данные ссылки: {e}"))
            
            if info is None:
                if self._try_tiktok_fallbacks(opts):
                    return
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

            total_size = sum(media_size_bytes(entry) for entry in entries) if pl else media_size_bytes(info)

            size_str = format_bytes(total_size)
            self.info_ready.emit(self.item_id, title, pl, count, size_str)
            self.thumbnail_ready.emit(self.item_id, thumbnail_url(info))
            if pl:
                self.playlist_items_ready.emit(self.item_id, playlist_entry_rows(entries))
            
            self.status.emit(self.item_id, "Загрузка...")
            logger.info(f"[{self.item_id}] Downloading {title} (Плейлист: {pl}, видео: {count}, размер: {size_str})")
            
            files_before = snapshot_output_files(self.output_folder)
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
            if "tiktok.com/" in self.url.lower() and download_error and "requested format is not available" in download_error.lower():
                download_error = f"TIKTOK_NO_CLEAN_FORMAT: {download_error}"
            
            if pl:
                new_files = remove_merged_audio_sidecars(new_media_files(self.output_folder, files_before), self.settings.get("download_type", "video"))
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
                    write_m3u(self.output_folder, new_files, title)
                self._emit_tiktok_quality_if_needed(new_files)
                self.produced_files.emit(self.item_id, new_files)
                filepath = self.output_folder
            else:
                generated_files = remove_merged_audio_sidecars(new_media_files(self.output_folder, files_before), self.settings.get("download_type", "video"))
                filepath = generated_files[0] if self.settings.get("download_type") in {"pictures", "documents"} and generated_files else single_output_path(ydl, info)
                if download_error:
                    if self._try_tiktok_fallbacks(opts, title, profile=False):
                        return
                    if self._refresh_cookies_and_retry(download_error):
                        self._download()
                        return
                    raise RuntimeError(self._friendly_error(f"Не удалось загрузить видео: {download_error}"))
                if not os.path.isfile(filepath):
                    raise RuntimeError(self._friendly_error("Загрузка закончилась без готового файла"))
                self._emit_tiktok_quality_if_needed([filepath])
                self.produced_files.emit(self.item_id, [filepath])
            
            logger.info(f"[{self.item_id}] Download process finished: {filepath}")
            self.status.emit(self.item_id, "Завершено")
            self.finished.emit(self.item_id, filepath, True, "")

    def _download_spotify(self):
        download_type = "audio"
        os.makedirs(self.output_folder, exist_ok=True)
        logger.info(f"[{self.item_id}] Spotify download started: folder={self.output_folder}")
        self.info_ready.emit(self.item_id, "Spotify music", True, 0, "—")
        files, error = run_spotify_download(self, self.url, self.output_folder, self.settings)
        if error:
            cancelled = "Отменено" in error
            self.status.emit(self.item_id, "Отменено" if cancelled else "Ошибка")
            self.finished.emit(self.item_id, "", False, "Отменено пользователем" if cancelled else self._friendly_error(error))
            return
        if not files:
            self.finished.emit(self.item_id, "", False, "Spotify загрузка закончилась без готовых аудиофайлов.")
            return
        logger.info(f"[{self.item_id}] Spotify download finished: files={len(files)}")
        self.produced_files.emit(self.item_id, list(files))
        self.progress.emit(self.item_id, 100.0, "—", "—")
        self.status.emit(self.item_id, "Завершено")
        self.finished.emit(self.item_id, files[0] if len(files) == 1 else self.output_folder, True, "")
