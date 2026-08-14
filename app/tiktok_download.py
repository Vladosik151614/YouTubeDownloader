"""TikTok-specific download fallback helpers."""
from __future__ import annotations

import os
import re
import tempfile
import time

import yt_dlp
from curl_cffi import requests

from app.logger import logger
from app.tiktok_external import tikwm_video_candidates
from app.tiktok_metadata import _profile_source_data
from app.tiktok_quality import download_quality_score, probe_file_quality, quality_score


def _emit_signal(worker, signal_name: str, *args) -> None:
    """Emit UI status/progress safely without invalidating a downloaded candidate."""
    signal = getattr(worker, signal_name, None)
    if signal is None or not hasattr(signal, "emit"):
        return
    try:
        signal.emit(*args)
    except Exception as exc:
        logger.warning(f"[{getattr(worker, 'item_id', '')}] TikTok signal {signal_name} failed: {exc}")


def emit_tiktok_quality(worker, filepaths: list[str]):
    """Probe completed TikTok files and update the queue with real media quality."""
    best_quality = {}
    for filepath in filepaths or []:
        if not os.path.isfile(filepath):
            continue
        try:
            quality = probe_file_quality(filepath)
        except Exception as exc:
            logger.warning(f"[{worker.item_id}] TikTok quality probe failed: {exc}")
            continue
        if not quality.get("width") or not quality.get("height"):
            continue
        if not best_quality or quality_score(quality) > quality_score(best_quality):
            best_quality = quality
    if best_quality:
        _emit_signal(worker, "quality_ready", worker.item_id, best_quality)
        label = best_quality.get("label") or "качество проверено"
        if best_quality.get("confidence") == "limited":
            label = f"{label} · HD не подтверждён"
        _emit_signal(worker, "status", worker.item_id, f"TikTok скачан: {label}")


def _safe_filename(folder: str, title: str, ext: str = ".mp4") -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", title or "TikTok video")
    name = name.strip(" .")[:180] or "TikTok video"
    if not ext.startswith("."):
        ext = "." + ext
    path = os.path.join(folder, name + ext)
    if not os.path.exists(path):
        return path
    base = os.path.join(folder, name)
    for index in range(2, 1000):
        candidate = f"{base} ({index}){ext}"
        if not os.path.exists(candidate):
            return candidate
    return f"{base} ({int(time.time())}){ext}"


def _download_stream(
    worker, stream_url: str, headers: dict, filepath: str, *, impersonate: str,
    method: str = "GET", data: dict | None = None,
) -> str:
    downloaded = 0
    last_emit = time.monotonic()
    request_method = requests.post if str(method).upper() == "POST" else requests.get
    response = request_method(
        stream_url,
        headers=headers,
        data=data or None,
        timeout=30,
        impersonate=impersonate,
        stream=True,
    )
    temp_path = filepath + ".part"
    try:
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP Error {response.status_code}: {response.reason}")
        content_type = str(response.headers.get("Content-Type") or "").lower()
        if content_type and not any(token in content_type for token in ("video", "mp4", "octet-stream")):
            raise RuntimeError(f"Источник вернул не видео: {content_type}")
        total = int(response.headers.get("Content-Length") or 0)
        with open(temp_path, "wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if worker._cancelled:
                    raise yt_dlp.utils.DownloadCancelled("Отменено пользователем")
                if not chunk:
                    continue
                output.write(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                if total and now - last_emit >= 0.25:
                    _emit_signal(
                        worker,
                        "progress",
                        worker.item_id,
                        min(99.0, downloaded / total * 100),
                        "—",
                        "—",
                    )
                    last_emit = now
        os.replace(temp_path, filepath)
    finally:
        response.close()
        if os.path.isfile(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
    if not os.path.isfile(filepath) or os.path.getsize(filepath) <= 0:
        raise RuntimeError("Загрузка TikTok закончилась без готового файла")
    _emit_signal(worker, "progress", worker.item_id, 100.0, "—", "—")
    return filepath


def _candidate_headers(candidate: dict) -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Referer": str(candidate.get("referer") or "https://www.tiktok.com/"),
        **{
            str(key): str(value)
            for key, value in (candidate.get("headers") or {}).items()
            if value is not None
        },
    }


def _quality_display(quality: dict) -> str:
    label = str((quality or {}).get("label") or "")
    if label and (quality or {}).get("confidence") == "limited":
        return f"{label} · HD не подтверждён"
    return label


def _download_best_candidate(worker, candidates: list[dict], final_title: str) -> tuple[str, str]:
    if not candidates:
        raise RuntimeError("TikTok не отдал MP4-кандидаты без водяного знака")
    downloaded = []
    best = None
    video_id_match = re.search(r"/video/(\d+)", worker.url)
    video_id = video_id_match.group(1) if video_id_match else "video"
    try:
        for index, candidate in enumerate(candidates, start=1):
            temp = tempfile.NamedTemporaryFile(
                prefix=f".tiktok-quality-{video_id}-{index}-",
                suffix=".mp4",
                dir=worker.output_folder,
                delete=False,
            )
            temp_path = temp.name
            temp.close()
            if os.path.exists(temp_path):
                os.remove(temp_path)
            label = str(candidate.get("label") or candidate.get("provider") or "TikTok")
            _emit_signal(worker, "status", worker.item_id, f"Проверяю качество TikTok: {label}...")
            try:
                _download_stream(
                    worker,
                    str(candidate["url"]),
                    _candidate_headers(candidate),
                    temp_path,
                    impersonate=str(candidate.get("impersonate") or "chrome131"),
                    method=str(candidate.get("method") or "GET"),
                    data=candidate.get("data") or None,
                )
                quality = probe_file_quality(temp_path)
                if not quality.get("width") or not quality.get("height"):
                    raise RuntimeError("ffprobe не подтвердил видеопоток")
                quality["candidate"] = candidate
                downloaded.append((temp_path, quality))
                logger.info(
                    f"[{worker.item_id}] TikTok candidate {label}: "
                    f"{quality.get('label')} size={quality.get('size')}"
                )
                if best is None or download_quality_score(quality) > download_quality_score(best[1]):
                    best = (temp_path, quality)
                    _emit_signal(worker, "status", worker.item_id, f"Лучший TikTok-кандидат: {_quality_display(quality)}")
            except yt_dlp.utils.DownloadCancelled:
                raise
            except Exception as exc:
                logger.warning(f"[{worker.item_id}] TikTok candidate {label} rejected: {exc}")
                if os.path.isfile(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
        if best is None:
            raise RuntimeError("TikTok не дал рабочий no-watermark поток подходящего качества")
        final_path = _safe_filename(worker.output_folder, final_title, ".mp4")
        os.replace(best[0], final_path)
        for loser_path, _quality in downloaded:
            if loser_path != best[0] and os.path.isfile(loser_path):
                try:
                    os.remove(loser_path)
                except OSError:
                    pass
        best[1]["filepath"] = final_path
        _emit_signal(worker, "status", worker.item_id, f"Скачано TikTok: {_quality_display(best[1])}")
        _emit_signal(worker, "quality_ready", worker.item_id, best[1])
        return final_path, _quality_display(best[1])
    except Exception:
        for temp_path, _quality in downloaded:
            if os.path.isfile(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
        raise


def download_tiktok_external_quality_fallback(worker, title: str | None = None) -> tuple[str, str] | None:
    """Try independent no-watermark MP4 fallbacks for a direct TikTok video."""
    if "tiktok.com/" not in worker.url.lower() or "/video/" not in worker.url.lower():
        return None
    if worker.settings.get("download_type", "video") != "video":
        return None
    _emit_signal(worker, "status", worker.item_id, "TikTok заблокировал прямой поток, ищу лучший HD/no-watermark кандидат...")
    logger.info(f"[{worker.item_id}] TikTok independent external quality fallback started")
    candidates = []
    errors = []
    for provider_name, provider in (
        ("TikWM", tikwm_video_candidates),
    ):
        try:
            provider_candidates = provider(worker.url)
            logger.info(
                f"[{worker.item_id}] {provider_name} candidates: {len(provider_candidates)}"
            )
            candidates.extend(provider_candidates)
        except Exception as exc:
            errors.append(f"{provider_name}: {exc}")
            logger.warning(f"[{worker.item_id}] {provider_name} fallback discovery failed: {exc}")
    if not candidates:
        detail = "; ".join(errors) if errors else "независимый HD-источник не отдал ссылку"
        raise RuntimeError(f"Не удалось получить TikTok MP4 без водяного знака: {detail}")
    candidates = sorted(candidates, key=lambda item: int(item.get("priority") or 0), reverse=True)
    video_id_match = re.search(r"/video/(\d+)", worker.url)
    video_id = video_id_match.group(1) if video_id_match else "video"
    final_title = title or f"TikTok {video_id}"
    _emit_signal(worker, "info_ready", worker.item_id, final_title, False, 1, "—")
    _emit_signal(worker, "status", worker.item_id, "Загрузка TikTok через no-watermark fallback...")
    filepath, label = _download_best_candidate(worker, candidates, final_title)
    if label:
        _emit_signal(worker, "status", worker.item_id, f"TikTok скачан в лучшем доступном качестве: {label}")
    return filepath, final_title


def download_tiktok_clean_stream_fallback(worker, opts: dict) -> tuple[str, str] | None:
    """Try saving a clean TikTok stream via profile metadata after direct extraction fails."""
    match = re.search(r"tiktok\.com/@([^/?]+)/video/(\d+)", worker.url, re.IGNORECASE)
    if not match or worker.settings.get("download_type", "video") != "video":
        return None
    username, video_id = match.group(1), match.group(2)
    profile_url = f"https://www.tiktok.com/@{username}"
    fallback_opts = dict(opts)
    fallback_opts.update({
        "extract_flat": "in_playlist",
        "skip_download": True,
        "progress_hooks": [],
        "playlist_items": None,
    })
    _emit_signal(worker, "status", worker.item_id, "TikTok заблокировал прямую ссылку, ищу чистый поток через профиль...")
    logger.info(f"[{worker.item_id}] TikTok direct fallback through profile: @{username}/{video_id}")
    with yt_dlp.YoutubeDL(fallback_opts) as ydl:
        profile_info = ydl.extract_info(profile_url, download=False) or {}
        title = f"TikTok {video_id}"
        for entry in profile_info.get("entries") or []:
            if str(entry.get("id") or "") == video_id:
                title = str(entry.get("title") or entry.get("description") or title)
                break
        details = _profile_source_data(
            ydl, str(profile_info.get("id") or ""), username, {video_id}
        ).get(video_id, {})
    stream_url = str(details.get("download_stream_url") or "")
    if not stream_url:
        raise RuntimeError("TIKTOK_NO_CLEAN_FORMAT: профиль найден, но чистый поток для скачивания не отдан")
    headers = {
        str(key): str(value)
        for key, value in (details.get("download_headers") or {}).items()
        if value is not None
    }
    headers.setdefault("User-Agent", "Mozilla/5.0 Chrome/131 Safari/537.36")
    headers.setdefault("Referer", "https://www.tiktok.com/")
    filepath = _safe_filename(worker.output_folder, title, ".mp4")
    _emit_signal(worker, "info_ready", worker.item_id, title, False, 1, "—")
    _emit_signal(worker, "status", worker.item_id, "Загрузка чистого потока TikTok...")
    _download_stream(
        worker, stream_url, headers, filepath, impersonate="chrome131_android"
    )
    quality = probe_file_quality(filepath)
    if quality.get("label"):
        _emit_signal(worker, "status", worker.item_id, f"TikTok скачан: {_quality_display(quality)}")
        quality["filepath"] = filepath
        _emit_signal(worker, "quality_ready", worker.item_id, quality)
    return filepath, title
