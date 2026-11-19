"""
spotify_engine.py - Spotify metadata downloads through spotDL.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from app.auth_manager import cookie_file
from app.binary_manager import get_binary_path
from app.process_utils import hidden_subprocess_kwargs
from app.media_probe import probe_audio_presence
from app.logger import logger


SPOTIFY_AUDIO_EXTS = {".mp3", ".m4a", ".opus", ".ogg", ".flac", ".wav"}
SPOTIFY_ARCHIVE_SKIP = "SKIPPED_ALREADY_DOWNLOADED:1"
_archive_lock = threading.Lock()


class _CallbackSignal:
    def __init__(self, callback):
        self.callback = callback

    def emit(self, item_id: str, *args):
        self.callback(item_id, *args)


class _CallbackWorker:
    def __init__(self, item_id: str, status_cb, progress_cb):
        self.item_id = item_id
        self._cancelled = False
        self._spotify_process = None
        self.status = _CallbackSignal(status_cb)
        self.progress = _CallbackSignal(progress_cb)


def is_spotify_url(url: str) -> bool:
    return "open.spotify.com" in url.lower() or "spotify.com" in url.lower()


def spotify_output_template(folder: str, playlist_numbering: bool = False) -> str:
    filename = "{list-position} - {artists} - {title}.{output-ext}" if playlist_numbering else "{artists} - {title}.{output-ext}"
    return str(Path(folder) / "{list-name}" / filename)


def snapshot_audio_files(folder: str) -> set[str]:
    root = Path(folder)
    if not root.exists():
        return set()
    return {
        str(path)
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SPOTIFY_AUDIO_EXTS and path.stat().st_size > 0
    }


def spotify_command(url: str, folder: str, settings: dict, *, archive_path: str | None = None, audio_provider: str | None = None, relative_output: bool = False) -> list[str]:
    ffmpeg = get_binary_path("ffmpeg")
    if getattr(sys, "frozen", False):
        command = [sys.executable, "--spotdl-child"]
    else:
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / "main.py"), "--spotdl-child"]
    command.extend([
        "download", url,
        "--output", spotify_output_template("output" if relative_output else folder, settings.get("playlist_numbering", False)),
        "--format", str(settings.get("spotify_audio_format", "mp3")),
        "--bitrate", str(settings.get("spotify_bitrate", "320k")),
        "--audio", *([audio_provider] if audio_provider else ["soundcloud", "youtube-music", "youtube"]),
        "--threads", str(max(1, min(int(settings.get("max_concurrent_downloads", 2) or 2), 8))),
        "--print-errors", "--log-level", "INFO",
    ])
    if os.path.isfile(ffmpeg):
        command.extend(["--ffmpeg", ffmpeg])
    cookies = cookie_file("youtube")
    if os.path.isfile(cookies):
        command.extend(["--cookie-file", cookies])
    if settings.get("skip_duplicates", True):
        command.extend(["--archive", archive_path or os.path.join(folder, ".spotify_archive.txt")])
    if settings.get("create_m3u", False):
        command.extend(["--m3u", os.path.join(folder, "spotify_playlist.m3u")])
    return command


def progress_from_line(line: str) -> float | None:
    match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", line)
    if not match:
        return None
    value = float(match.group(1))
    return max(0.0, min(value, 100.0))


def _identical_files(first: str, second: str) -> bool:
    if os.path.getsize(first) != os.path.getsize(second):
        return False
    with open(first, "rb") as left, open(second, "rb") as right:
        while True:
            chunk = left.read(1024 * 1024)
            if chunk != right.read(1024 * 1024):
                return False
            if not chunk:
                return True


def _promote_spotify_file(path: str, stage: str, folder: str) -> str:
    """Publish a task's own file without replacing a user's existing file."""
    relative = os.path.relpath(path, stage)
    target = os.path.abspath(os.path.join(folder, relative))
    if os.path.commonpath([os.path.abspath(folder), target]) != os.path.abspath(folder):
        raise ValueError("Недопустимый путь файла Spotify")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    base, ext = os.path.splitext(target)
    for number in range(1, 10001):
        candidate = target if number == 1 else f"{base} ({number}){ext}"
        try:
            os.link(path, candidate)
        except FileExistsError:
            # A previous attempt may have published this file before a later
            # operation failed. Reuse only an exact byte-for-byte match.
            if os.path.isfile(candidate) and not os.path.islink(candidate) and _identical_files(path, candidate):
                os.unlink(path)
                return candidate
            continue
        except OSError:
            try:
                with open(candidate, "xb") as output:
                    try:
                        with open(path, "rb") as source:
                            shutil.copyfileobj(source, output)
                    except Exception:
                        output.close()
                        os.unlink(candidate)
                        raise
            except FileExistsError:
                continue
        os.unlink(path)
        return candidate
    raise RuntimeError("Не удалось подобрать свободное имя файла")


def _archive_entries(path: str) -> set[str]:
    if not os.path.isfile(path):
        return set()
    with open(path, encoding="utf-8") as stream:
        return {line.strip() for line in stream if line.strip()}


@contextmanager
def _archive_file_lock(path: str):
    """Serialize archive updates across application processes as well as threads."""
    with open(path + ".lock", "a+b") as lockfile:
        if os.name == "nt":
            import msvcrt
            deadline = time.monotonic() + 15
            while True:
                try:
                    lockfile.seek(0)
                    msvcrt.locking(lockfile.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Архив Spotify занят другой задачей")
                    time.sleep(.05)
            try:
                yield
            finally:
                lockfile.seek(0)
                msvcrt.locking(lockfile.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lockfile.fileno(), fcntl.LOCK_UN)


def _append_validated_archive(path: str, entries: set[str]) -> None:
    """Append, never replace, entries; concurrent workers retain prior entries."""
    if not entries:
        return
    with _archive_lock, _archive_file_lock(path):
        new = entries - _archive_entries(path)
        if new:
            needs_newline = False
            if os.path.isfile(path) and os.path.getsize(path):
                with open(path, "rb") as existing:
                    existing.seek(-1, os.SEEK_END)
                    needs_newline = existing.read(1) != b"\n"
            descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                pending = memoryview((("\n" if needs_newline else "") + "".join(f"{entry}\n" for entry in sorted(new))).encode("utf-8"))
                while pending:
                    written = os.write(descriptor, pending)
                    if not written:
                        raise OSError("Не удалось записать архив Spotify")
                    pending = pending[written:]
            finally:
                os.close(descriptor)


def _publish_spotify_m3u(stage: str, folder: str, promoted_map: dict[str, str], previous_entries: set[str]) -> None:
    # The archive contains URLs only, not local paths. Existing entries might
    # have caused spotDL to skip tracks, so a complete playlist is unknowable.
    if previous_entries:
        raise ValueError("M3U не создан: архив Spotify не содержит путей ранее скачанных треков, поэтому полноту списка нельзя подтвердить")
    source = os.path.join(stage, "spotify_playlist.m3u")
    with open(source, encoding="utf-8-sig") as stream:
        lines = stream.read().splitlines()
    lookup = {os.path.normcase(os.path.abspath(k)): v for k, v in promoted_map.items()}
    seen = set()
    translated = []
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            translated.append(line)
            continue
        path = line.strip()
        if not os.path.isabs(path):
            path = os.path.join(stage, path)
        key = os.path.normcase(os.path.abspath(path))
        if key not in lookup:
            raise ValueError("M3U не создан: путь трека не соответствует проверенным файлам")
        seen.add(key)
        translated.append(os.path.abspath(lookup[key]))
    if seen != set(lookup):
        raise ValueError("M3U не создан: список треков неполный")
    for number in range(1, 10001):
        name = "spotify_playlist.m3u" if number == 1 else f"spotify_playlist ({number}).m3u"
        try:
            with open(os.path.join(folder, name), "x", encoding="utf-8") as playlist:
                playlist.write("\n".join(translated) + "\n")
            return
        except FileExistsError:
            continue
    raise OSError("Не удалось подобрать свободное имя M3U")


def _run_spotify_attempt(worker, url: str, folder: str, settings: dict, audio_provider: str | None) -> tuple[list[str], str]:
    worker._spotify_retry_safe = False
    os.makedirs(folder, exist_ok=True)
    # Each worker writes only to its own directory. A concurrent YouTube or
    # Spotify job must never be mistaken for this job's output.
    stage = os.path.abspath(tempfile.mkdtemp(prefix="ytdl-spotify-", dir=folder))
    real_archive = os.path.join(folder, ".spotify_archive.txt")
    staged_archive = os.path.join(stage, ".spotify_archive.txt")
    previous_entries = set()
    if settings.get("skip_duplicates", True):
        with _archive_lock, _archive_file_lock(real_archive):
            previous_entries = _archive_entries(real_archive)
    if settings.get("skip_duplicates", True):
        with open(staged_archive, "w", encoding="utf-8") as output:
            output.writelines(f"{entry}\n" for entry in sorted(previous_entries))
    # spotDL sanitizes every component in --output, including its parents.
    # Keep the template relative so even a user's dot-prefixed parent path is
    # never silently rewritten outside this task's staging directory.
    command = spotify_command(url, stage, settings, archive_path=staged_archive, audio_provider=audio_provider, relative_output=True)
    worker.status.emit(worker.item_id, "Spotify: получение метаданных...")
    worker._spotify_process = subprocess.Popen(
        command,
        cwd=stage,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        **hidden_subprocess_kwargs(),
    )
    output_tail: list[str] = []
    cancelled = False
    assert worker._spotify_process.stdout is not None
    for raw in worker._spotify_process.stdout:
        if worker._cancelled:
            worker._spotify_process.terminate()
            cancelled = True
            break
        line = raw.strip()
        if not line:
            continue
        output_tail.append(line)
        output_tail = output_tail[-40:]
        if "Found" in line or "Downloading" in line:
            worker.status.emit(worker.item_id, "Spotify: загрузка музыки...")
        percent = progress_from_line(line)
        if percent is not None:
            worker.progress.emit(worker.item_id, percent, "—", "—")
    code = worker._spotify_process.wait()
    cancelled = cancelled or worker._cancelled
    output_stage = os.path.join(stage, "output")
    created = sorted(snapshot_audio_files(output_stage))
    error_text = "\n".join(output_tail[-10:])
    has_error = any(marker in error_text.lower() for marker in ["error", "failed", "forbidden", "unavailable"])
    if cancelled:
        has_error = True
        error_text = f"Отменено пользователем. Незавершённые файлы сохранены: {stage}"
    if (code != 0 or has_error) and not created:
        # No retry for an interrupted collection or a partial provider file.
        def is_empty_m3u(path: Path) -> bool:
            try:
                if path != Path(stage) / "spotify_playlist.m3u" or path.is_symlink() or path.stat().st_size > 128:
                    return False
                return all(line.strip() in ("", "#EXTM3U") for line in path.read_text(encoding="utf-8-sig").splitlines())
            except (OSError, UnicodeError):
                return False
        worker._spotify_retry_safe = not any(
            p.is_file() and os.path.normcase(str(p)) != os.path.normcase(staged_archive) and not is_empty_m3u(p)
            for p in Path(stage).rglob("*")
        )
        error_text = error_text or f"spotDL вернул код ошибки: {code}"
        if not worker._spotify_retry_safe and not cancelled:
            error_text += f"\nВременные файлы сохранены: {stage}"
        return [], error_text
    if (code != 0 or has_error) and created:
        # Audio stream presence alone does not prove a file completed.  A
        # failed or cancelled attempt may have left a playable truncated file.
        logger.warning("[%s] Spotify attempt incomplete; files retained in staging", worker.item_id)
        detail = error_text or f"spotDL вернул код ошибки: {code}"
        if not cancelled:
            detail += f"\nВременные файлы сохранены: {stage}"
        return [], detail
    invalid = [path for path in created if probe_audio_presence(path) is not True]
    if invalid:
        logger.warning("[%s] Spotify audio validation failed; staged files retained", worker.item_id)
        return [], f"Spotify: не удалось проверить звук в {len(invalid)} файлах. Временные файлы сохранены: {stage}"
    if not created:
        from urllib.parse import urlsplit
        def track_id(value):
            try:
                parsed = urlsplit(value)
                match = re.fullmatch(r"/(?:intl-[\w-]+/)?track/([A-Za-z0-9]+)/*", parsed.path)
                return match.group(1) if parsed.hostname and parsed.hostname.lower() == "open.spotify.com" and match else None
            except ValueError:
                return None
        requested = track_id(url)
        if code == 0 and not has_error and requested and any(track_id(entry) == requested for entry in previous_entries):
            if os.path.isfile(staged_archive):
                os.unlink(staged_archive)
            try:
                os.rmdir(stage)
            except OSError:
                pass
            return [], SPOTIFY_ARCHIVE_SKIP
        return [], "Spotify не создал новый аудиофайл; возможно, он уже есть в архиве."
    promoted = []
    try:
        staged_entries = _archive_entries(staged_archive) if settings.get("skip_duplicates", True) else set()
        new_entries = staged_entries - previous_entries
        promoted_map = {}
        for path in created:
            target = _promote_spotify_file(path, output_stage, folder)
            promoted.append(target)
            promoted_map[path] = target
        # spotDL archive entries cannot be reliably mapped to individual files
        # here. Commit only an unambiguous, entirely validated batch.
        if settings.get("skip_duplicates", True) and code == 0 and not has_error and len(new_entries) == len(promoted):
            _append_validated_archive(real_archive, new_entries)
        elif new_entries:
            logger.warning("[%s] Spotify archive not committed: batch is partial or ambiguous", worker.item_id)
        if settings.get("create_m3u", False) and code == 0 and not has_error:
            _publish_spotify_m3u(stage, folder, promoted_map, previous_entries)
        if code != 0 or has_error:
            return promoted, error_text or f"spotDL вернул код ошибки: {code}"
        # Remove only our known temporary control files and empty directories.
        for control in (staged_archive, os.path.join(stage, "spotify_playlist.m3u")):
            if os.path.isfile(control):
                os.unlink(control)
        for root, _, _ in os.walk(stage, topdown=False):
            try:
                os.rmdir(root)
            except OSError:
                pass
        return promoted, ""
    except (OSError, ValueError) as exc:
        logger.exception("[%s] Spotify finalization failed", worker.item_id)
        saved = "\nУже сохранённые файлы:\n" + "\n".join(promoted) if promoted else ""
        return promoted, f"Spotify: не удалось завершить обработку. {exc}{saved}\nВременные файлы сохранены: {stage}"


def run_spotify_download(worker, url: str, folder: str, settings: dict) -> tuple[list[str], str]:
    # spotDL searches providers in order, but a provider that finds a match and
    # then fails during download does not necessarily fall through to the next.
    # Retry only a single track and only this specific provider failure; a
    # partially downloaded playlist must not be silently downloaded again.
    from urllib.parse import urlsplit

    try:
        path = urlsplit(url).path.lower().rstrip("/")
        is_single_track = bool(re.search(r"(?:^|/)track/[^/]+$", path))
    except ValueError:
        is_single_track = False
    providers = ("soundcloud", "youtube-music", "youtube") if is_single_track else (None, "youtube-music", "youtube")
    for index, provider in enumerate(providers):
        # Collections retain spotDL's normal multi-provider search behavior.
        files, error = _run_spotify_attempt(worker, url, folder, settings, provider)
        provider_failed = any(marker in error.lower() for marker in ("audioprovidererror", "no results found for song"))
        if files or not error or worker._cancelled or not provider_failed or index == len(providers) - 1 or not worker._spotify_retry_safe:
            return files, error
        logger.warning("[%s] Spotify provider %s failed; trying %s", worker.item_id, provider, providers[index + 1])
        worker.status.emit(worker.item_id, "Spotify: переключение источника аудио...")
    return [], "Spotify: источники аудио недоступны"


def run_spotify_download_callbacks(task_id: str, url: str, folder: str, settings: dict, status_cb, progress_cb) -> tuple[list[str], str]:
    return run_spotify_download(_CallbackWorker(task_id, status_cb, progress_cb), url, folder, settings)
