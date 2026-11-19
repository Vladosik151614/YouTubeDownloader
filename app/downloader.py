import os, time, shutil, tempfile, subprocess, yt_dlp
from urllib.parse import urlsplit
from yt_dlp.networking.impersonate import ImpersonateTarget
from PySide6.QtCore import QThread, Signal
from app.logger import logger
from app.binary_manager import get_binary_path
from app.auth_manager import cookie_file_for_url, ensure_cookie_file_for_url, refresh_cookie_file_for_url
from app.download_utils import (
    YtDlpLogCollector,
    format_bytes,
    is_playlist,
    playlist_entry_rows,
    media_size_bytes,
    rate_limit_bytes,
    thumbnail_url,
)
from app.download_artifacts import (
    new_media_files,
    single_output_path,
    snapshot_output_files,
    validate_video_with_audio,
    write_m3u,
)
from app.path_manager import service_output_folder
from app.proxy_config import proxy_url_from_settings
from app.settings_manager import APP_DATA_DIR
from app.spotify_engine import is_spotify_url, run_spotify_download
from app.error_messages import classify_download_error
from app.download_support import DownloadSupportMixin, ValidatedArchiveYoutubeDL, profile_format_selector, validate_video_profile, remux_video_container
SKIPPED_ALREADY_DOWNLOADED = "SKIPPED_ALREADY_DOWNLOADED"
from app.tiktok_download import download_tiktok_clean_stream_fallback, download_tiktok_external_quality_fallback
class ProfileContainerMismatch(RuntimeError):
    """A fallback produced a file that cannot meet the active container without conversion."""
class DownloadWorker(DownloadSupportMixin, QThread):
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
        self._alternative_retry_used = False
        # An archive is only a record of a past successful job; it does not
        # prove that the user still has a usable copy in the selected folder.
        # A single download that is skipped exclusively by that archive gets
        # one isolated retry without the archive instead of being presented as
        # a final "success" or an unrecoverable skip.
        self._archive_retry_used = False
        self._spotify_process = None
        self._last_progress_time = None
        self._last_downloaded = 0
        self._ema_speed = None
        self._staging_dir = None
    def _build_ydl_opts(self) -> dict:
        ffmpeg_bin = get_binary_path("ffmpeg")
        deno_bin = get_binary_path("deno")
        node_bin = get_binary_path("node")
        container = self.settings.get("container", "mp4")
        quality = str(self.settings.get("download_quality", "1080"))
        fps = str(self.settings.get("fps_limit", "best"))
        download_type = self.settings.get("download_type", "video")
        if "tiktok.com/" in self.url.lower() and download_type == "video":
            quality = "1080" if quality == "best" or (quality.isdigit() and int(quality) > 1080) else quality
            fps = "60" if fps == "best" or (fps.isdigit() and int(fps) > 60) else fps
        os.makedirs(self.output_folder, exist_ok=True)
        if download_type == "audio":
            # Never fetch video for the audio-only workflow. Fail clearly if
            # the service exposes no separate audio track.
            fmt = "bestaudio[protocol^=http]/bestaudio" if self._alternative_retry_used else "bestaudio"
        elif download_type in {"pictures", "documents"}:
            fmt = "best"
        else:
            fmt = profile_format_selector(quality, fps, container, 'tiktok.com/' in self.url.lower(), self._ydl_logger, self._alternative_retry_used)
        if is_playlist(self.url):
            filename = "%(playlist_index)03d - %(title)s.%(ext)s" if self.settings.get("playlist_numbering", False) else "%(title)s.%(ext)s"
            if self.settings.get("playlist_subfolders", False) and not self.settings.get("exact_download_folder", True):
                outtmpl = os.path.join(self._work_dir(), "%(playlist_title)s", filename)
            else:
                outtmpl = os.path.join(self._work_dir(), filename)
        else:
            outtmpl = os.path.join(self._work_dir(), "%(title)s.%(ext)s")
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
            impersonate = str(self.settings.get("tiktok_impersonate") or "").strip()
            if impersonate:
                try:
                    opts["impersonate"] = ImpersonateTarget.from_str(impersonate)
                except Exception as exc:
                    logger.warning(f"[{self.item_id}] TikTok impersonation disabled: {exc}")
        if download_type == "audio":
            opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}]
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
        if self.settings.get("skip_duplicates", True) and not self._archive_retry_used:
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
        elif os.path.isfile(node_bin):
            opts["js_runtimes"] = {"node": {"path": node_bin}}
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
        if self._alternative_retry_used:
            # A single public-YouTube fallback, only after a recoverable failure.
            # Keep resolution/FPS limits; do not pretend this is a different engine.
            host = (urlsplit(self.url).hostname or "").lower()
            if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com"}:
                opts.pop("cookiefile", None)
                opts.pop("cookiesfrombrowser", None)
        return opts
    def _finish_single_success(self, filepath):
        return DownloadSupportMixin._finish_single_success(self, filepath, video_validator=validate_video_with_audio, profile_validator=validate_video_profile)
    def _prepare_video_container(self, filepath):
        try:
            return remux_video_container(filepath, self.settings.get('container', 'mp4'), self.item_id)
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            if self.settings.get('auto_convert', False) and not self.settings.get('ask_before_codec_convert', True):
                logger.info('[%s] stage=remux outcome=deferred_to_profile', self.item_id)
                return filepath
            raise ProfileContainerMismatch(str(exc)) from exc

    def _try_tiktok_fallbacks(self, opts: dict, title: str | None = None, *, profile: bool = True) -> bool:
        hostname = (urlsplit(self.url).hostname or "").lower()
        path = urlsplit(self.url).path.lower()
        is_short_url = hostname in {"vm.tiktok.com", "vt.tiktok.com"}
        is_single_video = "/video/" in path or is_short_url
        if (hostname != "tiktok.com" and not hostname.endswith(".tiktok.com")) or not is_single_video:
            return False
        if self._cancelled or self.settings.get("download_type", "video") != "video" or is_playlist(self.url):
            return False
        attempts = []
        if profile:
            attempts.append(("profile", lambda: download_tiktok_clean_stream_fallback(self, opts)))
        attempts.append(("external_quality", lambda: download_tiktok_external_quality_fallback(self, title)))
        for name, attempt in attempts:
            started = time.monotonic()
            try:
                if self._cancelled:
                    raise yt_dlp.utils.DownloadCancelled("Отменено пользователем")
                self.status.emit(self.item_id, "Пробуем другой способ загрузки TikTok...")
                logger.info(f"[{self.item_id}] TikTok fallback attempt: {name}")
                destination_folder = self.output_folder
                self.output_folder = self._work_dir()
                try:
                    fallback = attempt()
                finally:
                    self.output_folder = destination_folder
                if fallback:
                    filepath, _title = fallback
                    self._finish_single_success(filepath)
                    logger.info("[%s] stage=fallback provider=%s outcome=success elapsed=%.2fs", self.item_id, name, time.monotonic() - started)
                    return True
            except yt_dlp.utils.DownloadCancelled:
                self.status.emit(self.item_id, "Отменено")
                self.finished.emit(self.item_id, "", False, "Отменено пользователем")
                return True
            except ProfileContainerMismatch as mismatch:
                logger.warning("[%s] stage=fallback category=container_mismatch error=%s", self.item_id, mismatch)
                self.finished.emit(self.item_id, filepath, False, str(mismatch))
                return True
            except Exception as fallback_exc:
                logger.warning("[%s] stage=fallback provider=%s category=%s elapsed=%.2fs error=%s", self.item_id, name, classify_download_error(str(fallback_exc)).category, time.monotonic() - started, fallback_exc)
        return False

    def _download(self):
        if is_spotify_url(self.url):
            self._download_spotify()
            return
        self.status.emit(self.item_id, "Получение информации...")
        opts = self._build_ydl_opts()
        
        with ValidatedArchiveYoutubeDL(opts) as ydl:
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
            except yt_dlp.utils.DownloadCancelled:
                self.status.emit(self.item_id, "Отменено")
                self.finished.emit(self.item_id, "", False, "Отменено пользователем")
                return
            except Exception as e:
                if self._try_tiktok_fallbacks(opts):
                    return
                if self._refresh_cookies_and_retry(str(e)):
                    self._fresh_retry_stage()
                    self._download()
                    return
                if self._retry_youtube_alternative(str(e)):
                    return
                raise RuntimeError(self._friendly_error(f"Не удалось получить данные ссылки: {e}"))
            
            if info is None:
                if not is_playlist(self.url) and ydl.skipped_archive_ids and not self._ydl_logger.errors:
                    if self._retry_after_archive_skip():
                        return
                    self.finished.emit(self.item_id, "", False, f"{SKIPPED_ALREADY_DOWNLOADED}:1")
                    return
                if self._try_tiktok_fallbacks(opts):
                    return
                if self._ydl_logger.errors and self._retry_youtube_alternative(self._ydl_logger.errors[-1]):
                    return
                raise RuntimeError(self._friendly_error("Ссылка недоступна или заблокирована"))
            
            pl = is_playlist(self.url) or info.get("_type") == "playlist"
            title = info.get("title", "Без названия")
            
            entries = []
            unavailable_entries = 0
            if pl and "entries" in info:
                # Фильтруем None в случае если отдельные видео недоступны в плейлисте
                raw_entries = list(info["entries"] or [])
                entries = [e for e in raw_entries if e is not None]
                unavailable_entries = len(raw_entries) - len(entries)
            
            count = len(entries) if pl else 1
            if pl and count == 0:
                raise RuntimeError(self._friendly_error("Плейлист найден, но доступных видео в нём нет"))

            total_size = sum(media_size_bytes(entry) for entry in entries) if pl else media_size_bytes(info)

            size_str = format_bytes(total_size)
            self.info_ready.emit(self.item_id, title, pl, count, size_str)
            self.thumbnail_ready.emit(self.item_id, thumbnail_url(info))
            if pl:
                self.playlist_items_ready.emit(self.item_id, playlist_entry_rows(entries))
            tracking = self._setup_playlist_tracking(ydl, entries, unavailable_entries) if pl else None
            
            self.status.emit(self.item_id, "Загрузка...")
            logger.info(f"[{self.item_id}] Downloading {title} (Плейлист: {pl}, видео: {count}, размер: {size_str})")
            
            files_before = snapshot_output_files(self._work_dir())
            ydl.skipped_archive_ids.clear()
            if hasattr(ydl, 'skipped_archive_entries'):
                ydl.skipped_archive_entries.clear()
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
            if unavailable_entries and not download_error:
                download_error = f"Недоступных элементов в плейлисте: {unavailable_entries}."
            logger.info(
                f"[{self.item_id}] yt-dlp finished with warnings={len(self._ydl_logger.messages)} "
                f"errors={len(self._ydl_logger.errors)} last_error={download_error or 'none'}"
            )
            if "tiktok.com/" in self.url.lower() and download_error and "requested format is not available" in download_error.lower():
                download_error = f"TIKTOK_NO_CLEAN_FORMAT: {download_error}"
            skipped_count = len(ydl.skipped_archive_ids)
            if skipped_count > count:
                download_error = download_error or "Не удалось подтвердить число пропущенных роликов в архиве."
            
            if pl:
                new_files = new_media_files(self._work_dir(), files_before)
                if self.settings.get("download_type", "video") == "video":
                    checked = []
                    for path in new_files:
                        if os.path.splitext(path)[1].lower() not in {".mp4", ".mkv", ".webm", ".mov"}:
                            continue
                        result = validate_video_with_audio(path)
                        checked.append((path, validate_video_profile(path, self.settings, self.url, self.item_id) if result[0] else result))
                    new_files = [path for path, (valid, _) in checked if valid]
                    invalid = [reason for _, (valid, reason) in checked if not valid]
                    if invalid:
                        download_error = download_error or 'invalid video output: ' + invalid[0]
                elif self.settings.get('download_type') == 'audio':
                    checked = [path for path in new_files if self._has_complete_retry_output([path])]
                    if len(checked) != len(new_files):
                        download_error = download_error or 'invalid audio output: не удалось проверить аудиопоток'
                    new_files = checked
                if new_files and len(new_files) + skipped_count < count:
                    recovered = self._retry_missing_playlist_items(ydl, tracking, new_files, skipped_count, download_error)
                    if recovered:
                        new_files.extend(recovered)
                        download_error = None
                if download_error and not new_files:
                    if self._refresh_cookies_and_retry(download_error):
                        self._fresh_retry_stage()
                        self._download()
                        return
                    if self._retry_youtube_alternative(download_error):
                        return
                    raise RuntimeError(self._friendly_error(f"Не удалось загрузить плейлист: {download_error}"))
                if download_error and new_files:
                    logger.warning(
                        f"[{self.item_id}] Playlist completed with skipped/problem items. "
                        f"Saved files: {len(new_files)}. Last issue: {download_error}"
                    )
                if not new_files:
                    if not download_error and skipped_count == count:
                        self.finished.emit(self.item_id, "", False, f"{SKIPPED_ALREADY_DOWNLOADED}:{skipped_count}")
                        return
                    raise RuntimeError(self._friendly_error("Не создано ни одного полного файла. Возможно, ролики пропущены как ранее скачанные."))
                if len(new_files) + skipped_count < count and self.settings.get("download_type", "video") in {"video", "audio"}:
                    download_error = download_error or f"Получено полных файлов: {len(new_files)} из {count}; некоторые могли быть пропущены."
                prepared = []
                for path in new_files:
                    try:
                        prepared.append(self._prepare_video_container(path) if self.settings.get('download_type', 'video') == 'video' else path)
                    except ProfileContainerMismatch as exc:
                        download_error = download_error or str(exc)
                new_files = [self._promote_output(path) for path in prepared]
                if not new_files:
                    raise RuntimeError(download_error or 'Не удалось сохранить видео в выбранном контейнере')
                if self.settings.get("create_m3u", False):
                    write_m3u(self.output_folder, new_files, title)
                self._emit_tiktok_quality_if_needed(new_files)
                self.produced_files.emit(self.item_id, new_files)
                filepath = self.output_folder
                if download_error:
                    self.finished.emit(self.item_id, filepath, False, "Плейлист загружен не полностью: " + self._friendly_error(download_error))
                    return
            else:
                generated_files = new_media_files(self._work_dir(), files_before)
                expected_path = single_output_path(ydl, info)
                if self.settings.get("download_type", "video") == "video":
                    candidates = [path for path in generated_files if os.path.splitext(path)[1].lower() in {".mp4", ".mkv", ".webm", ".mov"}]
                    filepath = expected_path if expected_path in candidates else (candidates[0] if candidates else "")
                else:
                    filepath = expected_path if expected_path in generated_files else (generated_files[0] if generated_files else "")
                if download_error:
                    # Never retry over an already complete output.  If only
                    # partial/broken files exist, a new isolated attempt is
                    # safe and the previous data is retained for recovery.
                    complete = self._has_complete_retry_output(generated_files)
                    if not complete:
                        self._fresh_retry_stage()
                        if self._try_tiktok_fallbacks(opts, title, profile=False):
                            return
                        if self._refresh_cookies_and_retry(download_error):
                            self._fresh_retry_stage()
                            self._download()
                            return
                        if self._retry_youtube_alternative(download_error):
                            return
                    raise RuntimeError(self._friendly_error(f"Не удалось загрузить видео: {download_error}"))
                if not os.path.isfile(filepath):
                    if not download_error and skipped_count == 1 and not generated_files:
                        if self._retry_after_archive_skip():
                            return
                        self.finished.emit(self.item_id, "", False, f"{SKIPPED_ALREADY_DOWNLOADED}:1")
                        return
                    raise RuntimeError(self._friendly_error("Загрузка не создала новый файл. Возможно, видео пропущено как ранее скачанное."))
                if self.settings.get("download_type", "video") == "video":
                    valid, error = validate_video_with_audio(filepath)
                    if valid:
                        valid, error = validate_video_profile(filepath, self.settings, self.url, self.item_id)
                    if not valid:
                        if self._try_tiktok_fallbacks(opts, title):
                            return
                        if self._retry_youtube_alternative('invalid video output'):
                            return
                        raise RuntimeError(error + ". Файл сохранён для диагностики; повторите загрузку.")
                    filepath = self._prepare_video_container(filepath)
                elif self.settings.get('download_type') == 'audio' and not self._has_complete_retry_output([filepath]):
                    if self._retry_youtube_alternative('invalid audio output'):
                        return
                    raise RuntimeError('Не удалось проверить аудиопоток. Файл сохранён для диагностики.')
                filepath = self._promote_output(filepath)
                self._emit_tiktok_quality_if_needed([filepath])
                self.produced_files.emit(self.item_id, [filepath])
            logger.info(f"[{self.item_id}] Download process finished: {filepath}")
            # A partially successful playlist must not mark failed items as
            # downloaded. Retry remains possible for every unverified item.
            if not pl or len(new_files) + skipped_count >= count:
                ydl.commit_validated_archive()
            self.status.emit(self.item_id, "Завершено")
            note = f"{SKIPPED_ALREADY_DOWNLOADED}:{skipped_count}" if skipped_count else ""
            self.finished.emit(self.item_id, filepath, True, note)
