"""Helpers for download staging, progress and bounded retries."""
from app.media_container import remux_video_container
import os
import shutil
import tempfile
import time
import subprocess
from urllib.parse import urlsplit

import yt_dlp
from app.auth_manager import refresh_cookie_file_for_url
from app.download_utils import YtDlpLogCollector, exclude_tiktok_watermarked_formats, format_bytes, is_playlist, set_sleep_prevention
from app.error_messages import classify_download_error
from app.logger import logger, redact_sensitive
from app.download_artifacts import validate_video_with_audio
from app.spotify_engine import SPOTIFY_ARCHIVE_SKIP, run_spotify_download
from app.binary_manager import get_binary_path
from app.process_utils import hidden_subprocess_kwargs
from app.playlist_recovery import PlaylistRecoveryMixin


def profile_format_selector(quality, fps, container, tiktok=False, ydl_logger=None, alternative=False):
    """Filter by the short video side before yt-dlp ranks formats.

    Both 1920x1080 and 1080x1920 are 1080p. Unknown metadata is retained
    only when no fully described video satisfies the profile.
    """
    limit = int(quality) if str(quality).isdigit() else None
    max_fps = int(fps) if str(fps).isdigit() else None
    audio = 'webm' if container == 'webm' else 'm4a'
    expression = f'bestvideo*+(bestaudio[ext={audio}]/bestaudio)/best'
    if alternative:
        expression = f'best/bestvideo*+(bestaudio[ext={audio}]/bestaudio)'
    if tiktok:
        expression = exclude_tiktok_watermarked_formats(expression)
    parser = yt_dlp.YoutubeDL({'quiet': True, 'logger': ydl_logger} if ydl_logger else {'quiet': True})
    select = parser.build_format_selector(expression)

    def select_for_profile(context):
        known, unknown, audio_only = [], [], []
        for fmt in context.get('formats', []):
            if fmt.get('vcodec') == 'none':
                audio_only.append(fmt)
                continue
            width, height, rate = fmt.get('width'), fmt.get('height'), fmt.get('fps')
            if limit and width and height and min(width, height) > limit:
                continue
            if max_fps and rate and rate > max_fps:
                continue
            # TikTok often omits FPS even on its Full HD formats. Do not
            # discard those in favour of a fully described low-res stream;
            # validate the actual FPS after downloading instead.
            (known if (not limit or (width and height)) else unknown).append(fmt)
        usable = known or unknown
        def video_rank(fmt):
            if fmt.get('vcodec') == 'none':
                return (0, 0.0)
            width, height = fmt.get('width') or 0, fmt.get('height') or 0
            try:
                return (min(int(width), int(height)), float(fmt.get('fps') or 0),
                        float(fmt.get('tbr') or fmt.get('vbr') or 0),
                        int(fmt.get('filesize') or fmt.get('filesize_approx') or 0))
            except (TypeError, ValueError):
                return (0, 0.0)
        # yt-dlp may rank extractor "quality" ahead of resolution.  Keep its
        # original ordering for ties and audio tracks but prefer known spatial
        # resolution and FPS for video, respecting the selected upper bounds.
        eligible = [fmt for fmt in context.get('formats', []) if fmt in usable or fmt in audio_only]
        filtered = dict(context, formats=sorted(eligible, key=video_rank))
        yield from select(filtered)

    return select_for_profile


def validate_video_profile(path, settings, url, item_id=''):
    """Never silently present unknown/excess dimensions or frame rate as a match."""
    from app.converter import probe_video_info
    info = probe_video_info(path)
    quality, fps = str(settings.get('download_quality', '1080')), str(settings.get('fps_limit', 'best'))
    host = (urlsplit(url).hostname or '').lower()
    is_tiktok = host == 'tiktok.com' or host.endswith('.tiktok.com')
    limit = min(int(quality), 1080) if quality.isdigit() and is_tiktok else int(quality) if quality.isdigit() else 1080 if is_tiktok else None
    max_fps = min(int(fps), 60) if fps.isdigit() and is_tiktok else int(fps) if fps.isdigit() else 60 if is_tiktok else None
    width, height, rate = int(info.get('width') or 0), int(info.get('height') or 0), float(info.get('fps') or 0)
    logger.info('[%s] stage=profile_validation actual=%sx%s fps=%.3f codec=%s limit=%s fps_limit=%s',
                item_id, width, height, rate, info.get('codec', 'unknown'), limit or 'best', max_fps or 'best')
    if not width or not height or (max_fps and not rate):
        return False, 'Не удалось подтвердить разрешение или частоту кадров скачанного видео'
    if (limit and min(width, height) > limit) or (max_fps and rate > max_fps + .1):
        return False, 'Доступное видео превышает выбранное разрешение или FPS; файл сохранён'
    return True, ''




class ValidatedArchiveYoutubeDL(yt_dlp.YoutubeDL):
    """Defer archive writes until the caller has validated the downloaded files."""
    def __init__(self, *args, **kwargs):
        self._pending_archive = []
        self.skipped_archive_ids = set()
        self.skipped_archive_entries = set()
        super().__init__(*args, **kwargs)

    def in_download_archive(self, info_dict):
        skipped = super().in_download_archive(info_dict)
        if skipped:
            archive_id = self._make_archive_id(info_dict)
            if archive_id:
                self.skipped_archive_ids.add(archive_id)
                index, identifier = info_dict.get('playlist_index'), info_dict.get('id')
                if isinstance(index, int) and not isinstance(index, bool) and index > 0 and identifier:
                    self.skipped_archive_entries.add((archive_id, index, str(identifier)))
        return skipped

    def record_download_archive(self, info_dict):
        self._pending_archive.append(dict(info_dict))

    def commit_validated_archive(self):
        for info in self._pending_archive:
            super().record_download_archive(info)
        self._pending_archive.clear()


class DownloadSupportMixin(PlaylistRecoveryMixin):
    def cancel(self):
        self._cancelled = True
        if self._spotify_process and self._spotify_process.poll() is None:
            self._spotify_process.terminate()

    def _emit_tiktok_quality_if_needed(self, filepaths: list[str]):
        if 'tiktok.com/' in self.url.lower():
            from app.tiktok_download import emit_tiktok_quality
            emit_tiktok_quality(self, filepaths)

    def run(self):
        started = time.monotonic()
        logger.info("[%s] stage=start host=%s type=%s", self.item_id, urlsplit(self.url).hostname or "unknown", self.settings.get("download_type", "video"))
        try:
            if self.settings.get("prevent_sleep", True):
                set_sleep_prevention(True)
            self._download()
        except Exception as e:
            logger.exception("[%s] stage=failed category=%s elapsed=%.2fs", self.item_id, classify_download_error(str(e)).category, time.monotonic() - started)
            self.finished.emit(self.item_id, "", False, str(e))
        finally:
            logger.info("[%s] stage=finished elapsed=%.2fs cancelled=%s", self.item_id, time.monotonic() - started, self._cancelled)
            self._cleanup_staging()
            if self.settings.get("prevent_sleep", True):
                set_sleep_prevention(False)

    def _work_dir(self):
        if self._staging_dir is None:
            os.makedirs(self.output_folder, exist_ok=True)
            self._staging_dir = tempfile.mkdtemp(prefix=".ytdl-task-", dir=self.output_folder)
        return self._staging_dir

    def _promote_output(self, source):
        """Move our own staged file to the destination without overwriting any file."""
        stage = os.path.abspath(self._work_dir())
        source = os.path.abspath(source)
        if os.path.commonpath([stage, source]) != stage or not os.path.isfile(source):
            raise RuntimeError("Результат загрузки находится вне временной папки задачи")
        rel = os.path.relpath(source, stage)
        parts = rel.split(os.sep)
        if getattr(self, '_isolated_playlist_stage', False) and len(parts) >= 3 and parts[0] == '__playlist_items__':
            rel = os.path.join(*parts[3:] if len(parts) >= 4 and parts[2] == '__retry__' else parts[2:])
        destination = os.path.abspath(os.path.join(self.output_folder, rel))
        if os.path.commonpath([os.path.abspath(self.output_folder), destination]) != os.path.abspath(self.output_folder):
            raise RuntimeError("Недопустимый путь сохранения результата")
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        base, ext = os.path.splitext(destination)
        for number in range(1, 10001):
            candidate = destination if number == 1 else f"{base} ({number}){ext}"
            try:
                # Both paths normally reside on the same filesystem. Hard-link
                # creation is atomic and cannot replace an existing result.
                os.link(source, candidate)
            except FileExistsError:
                continue
            except OSError:
                try:
                    with open(candidate, "xb") as target:
                        try:
                            with open(source, "rb") as origin:
                                shutil.copyfileobj(origin, target, length=1024 * 1024)
                        except Exception:
                            target.close()
                            os.unlink(candidate)
                            raise
                except FileExistsError:
                    continue
            os.unlink(source)
            return candidate
        raise RuntimeError("Не удалось подобрать свободное имя файла")

    def _cleanup_staging(self):
        # Only remove empty directories created for this worker. Incomplete
        # files are retained for diagnostics/recovery instead of being deleted.
        if not self._staging_dir or not os.path.isdir(self._staging_dir):
            return
        for root, _dirs, _files in os.walk(self._staging_dir, topdown=False):
            try:
                os.rmdir(root)
            except OSError:
                pass

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

    def _fresh_retry_stage(self):
        # Never resume an alternate format into a previous attempt's partial
        # file. Preserve nonempty staged data for recovery/diagnosis.
        previous = self._staging_dir
        self._cleanup_staging()
        if previous and os.path.isdir(previous):
            logger.info('[%s] stage=retry previous_attempt_retained=%s', self.item_id, previous)
        self._staging_dir = None

    def _has_complete_retry_output(self, paths, *, output_type=None):
        """Be conservative: do not redownload a valid output after an error."""
        if (output_type or self.settings.get('download_type', 'video')) == 'audio':
            from app.media_probe import probe_audio_presence
            return any(os.path.splitext(p)[1].lower() in {'.m4a', '.mp3', '.opus', '.webm', '.wav', '.flac', '.ogg'}
                       and os.path.isfile(p) and probe_audio_presence(p) is True for p in paths)
        from app.download_artifacts import validate_video_with_audio
        return any(validate_video_with_audio(p)[0] for p in paths
                   if os.path.splitext(p)[1].lower() in {'.mp4', '.mkv', '.webm', '.mov'} and os.path.isfile(p))

    def _retry_youtube_alternative(self, reason: str) -> bool:
        parsed = urlsplit(self.url)
        host = (parsed.hostname or "").lower()
        if (parsed.scheme.lower() not in {"http", "https"} or not host
                or self._cancelled or self._alternative_retry_used
                or self.settings.get("download_type", "video") not in {"video", "audio"}):
            return False
        text = str(reason or "").lower()
        # Do not retry private, age-restricted, missing, DRM or rate-limited
        # content: another format cannot provide the missing authorization.
        if any(token in text for token in ("private", "sign in", "login", "age-restricted", "members-only", "429", "too many requests", "drm", "unavailable", "cancel")):
            return False
        if not any(token in text for token in ("requested format", "http error 403", "forbidden", "http error 404", "timed out", "timeout", "connection reset", "invalid audio output", "invalid video output")):
            return False
        self._alternative_retry_used = True
        self._ydl_logger = YtDlpLogCollector(self.item_id)
        logger.info("[%s] stage=retry provider=yt-dlp-alternative host=%s reason_category=%s", self.item_id, host, classify_download_error(str(reason)).category)
        self.status.emit(self.item_id, "Пробуем альтернативный формат загрузки...")
        self._fresh_retry_stage()
        self._download()
        return True
    def _playlist_preflight_info(self, opts: dict) -> tuple[dict, bool]:
        if not is_playlist(self.url):
            return {}, False
        flat_opts = dict(opts)
        # Preflight must show the entire available playlist even when some or
        # all entries are already in the download archive. The actual download
        # still receives and applies the archive in its own YoutubeDL instance.
        flat_opts.pop("download_archive", None)
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

    def _download_spotify(self):
        download_type = "audio"
        os.makedirs(self.output_folder, exist_ok=True)
        logger.info(f"[{self.item_id}] Spotify download started: folder={self.output_folder}")
        self.info_ready.emit(self.item_id, "Spotify music", True, 0, "—")
        files, error = run_spotify_download(self, self.url, self.output_folder, self.settings)
        if error == SPOTIFY_ARCHIVE_SKIP and not files:
            self.status.emit(self.item_id, "Пропущено: есть в архиве")
            self.finished.emit(self.item_id, "", False, SPOTIFY_ARCHIVE_SKIP)
            return
        if error:
            cancelled = "Отменено" in error
            # spotDL may have successfully promoted some tracks before an error.
            # Preserve and report only files whose audio can still be verified;
            # a partial batch must never be presented as a successful download.
            valid_files = [path for path in files if self._has_complete_retry_output([path], output_type='audio')]
            logger.warning('[%s] Spotify partial/error: saved=%s returned=%s details=%s',
                           self.item_id, len(valid_files), len(files), redact_sensitive(error))
            if valid_files:
                self.produced_files.emit(self.item_id, list(valid_files))
                reason = error if cancelled else self._friendly_error(error)
                marker = "Временные файлы сохранены: "
                if not cancelled and marker in error:
                    reason += "\n" + redact_sensitive(error[error.rfind(marker):])
                shown = '\n'.join(valid_files[:5])
                more = f'\nИ ещё файлов: {len(valid_files) - 5}' if len(valid_files) > 5 else ''
                message = f'{reason}\nЧасть файлов сохранена ({len(valid_files)}):\n{shown}{more}'
                self.status.emit(self.item_id, 'Отменено' if cancelled else 'Ошибка')
                self.finished.emit(self.item_id, self.output_folder, False, message)
                return
            self.status.emit(self.item_id, "Отменено" if cancelled else "Ошибка")
            message = error if cancelled else self._friendly_error(error)
            marker = "Временные файлы сохранены: "
            if not cancelled and marker in error:
                message += "\n" + redact_sensitive(error[error.rfind(marker):])
            self.finished.emit(self.item_id, "", False, message)
            return
        if not files:
            self.finished.emit(self.item_id, "", False, "Spotify загрузка закончилась без готовых аудиофайлов.")
            return
        invalid = [path for path in files if not self._has_complete_retry_output([path], output_type='audio')]
        if invalid:
            logger.warning('[%s] Spotify files failed audio validation: %s', self.item_id, invalid)
            self.finished.emit(self.item_id, "", False, "Spotify: не удалось проверить звук в некоторых файлах; файлы сохранены для диагностики.")
            return
        logger.info(f"[{self.item_id}] Spotify download finished: files={len(files)}")
        self.produced_files.emit(self.item_id, list(files))
        self.progress.emit(self.item_id, 100.0, "—", "—")
        self.status.emit(self.item_id, "Завершено")
        self.finished.emit(self.item_id, files[0] if len(files) == 1 else self.output_folder, True, "")

    def _finish_single_success(self, filepath: str, *, video_validator=validate_video_with_audio, profile_validator=validate_video_profile):
        if self.settings.get("download_type", "video") == "video":
            valid, error = video_validator(filepath)
            if not valid:
                raise RuntimeError(error + ". Файл сохранён для диагностики; повторите загрузку.")
            valid, error = profile_validator(filepath, self.settings, self.url, self.item_id)
            if not valid:
                raise RuntimeError(error)
            filepath = self._prepare_video_container(filepath)
        filepath = self._promote_output(filepath)
        self._emit_tiktok_quality_if_needed([filepath])
        self.produced_files.emit(self.item_id, [filepath])
        self.status.emit(self.item_id, "Завершено")
        self.finished.emit(self.item_id, filepath, True, "")


    def _retry_after_archive_skip(self) -> bool:
        """Retry one single-item archive skip without disabling protection globally.

        yt-dlp's archive only stores an extractor ID, not the path to a
        validated local output.  Retrying once in a fresh staging directory is
        the only safe way to recover a missing/deleted output automatically.
        Playlist recovery is intentionally handled separately: bypassing the
        archive for an entire playlist can redownload every valid item.
        """
        if self._archive_retry_used or is_playlist(self.url):
            return False
        self._archive_retry_used = True
        logger.info("[%s] Archive skip recovery: retrying single item without archive", self.item_id)
        self.status.emit(self.item_id, "Проверяем запись архива и восстанавливаем файл…")
        self._fresh_retry_stage()
        self._download()
        return True
