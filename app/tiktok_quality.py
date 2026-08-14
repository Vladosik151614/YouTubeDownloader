"""TikTok media quality probing and ranking helpers."""
from __future__ import annotations

import os
import json
import subprocess
from fractions import Fraction

from app.converter import probe_video_info
from app.binary_manager import get_binary_path
from app.logger import logger
from app.process_utils import hidden_subprocess_kwargs


def quality_short_side(width: int, height: int) -> int:
    values = [int(value or 0) for value in (width, height) if int(value or 0) > 0]
    return min(values) if values else 0


def quality_label(width: int, height: int) -> str:
    short_side = quality_short_side(width, height)
    if short_side > 1080:
        return "1080p+"
    if short_side >= 1080:
        return "1080p"
    if short_side >= 720:
        return "720p"
    return f"{short_side}p" if short_side else ""


def codec_label(codec: str) -> str:
    value = str(codec or "").lower()
    if any(token in value for token in ("h265", "hevc", "hvc1")):
        return "H.265"
    if any(token in value for token in ("h264", "avc")):
        return "H.264"
    if "vp9" in value:
        return "VP9"
    if any(token in value for token in ("av1", "av01")):
        return "AV1"
    return value.upper() if value and value != "none" else ""


def source_quality(info: dict) -> dict:
    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    try:
        fps_value = float(info.get("fps") or 0)
    except (TypeError, ValueError):
        fps_value = 0
    codec = codec_label(info.get("vcodec") or info.get("codec"))
    if not width or not height:
        return {}
    fps = int(round(fps_value)) if fps_value else 0
    parts = [f"{quality_label(width, height)} ({width}×{height})"]
    if fps:
        parts.append(f"{fps} FPS")
    if codec:
        parts.append(codec)
    return {
        "width": width,
        "height": height,
        "fps": fps,
        "codec": codec,
        "label": " · ".join(parts),
        "confidence": "limited" if quality_short_side(width, height) < 1080 else "available",
    }


def probe_file_quality(filepath: str) -> dict:
    info = probe_video_info(filepath)
    stream_info = probe_media_streams(filepath)
    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    fps = float(info.get("fps") or 0)
    size = os.path.getsize(filepath) if os.path.isfile(filepath) else 0
    quality = source_quality({
        "width": width,
        "height": height,
        "fps": fps,
        "codec": info.get("codec"),
    })
    audio_codec = codec_label(stream_info.get("audio_codec") or "")
    quality.update({
        "filepath": filepath,
        "size": size,
        "has_audio": bool(stream_info.get("has_audio")),
        "audio_codec": audio_codec,
        "score": quality_score({
            "width": width,
            "height": height,
            "fps": fps,
            "filesize": size,
            "has_audio": bool(stream_info.get("has_audio")),
        }),
    })
    return quality


def _fps_from_stream(stream: dict) -> float:
    for key in ("avg_frame_rate", "r_frame_rate"):
        value = str(stream.get(key) or "")
        if not value or value == "0/0":
            continue
        try:
            return float(Fraction(value))
        except (ValueError, ZeroDivisionError):
            continue
    try:
        return float(stream.get("fps") or 0)
    except (TypeError, ValueError):
        return 0.0


def _headers_argument(headers: dict | None) -> str:
    if not headers:
        return ""
    lines = []
    for key, value in headers.items():
        if value is None:
            continue
        clean_key = str(key).replace("\r", "").replace("\n", "")
        clean_value = str(value).replace("\r", "").replace("\n", "")
        lines.append(f"{clean_key}: {clean_value}")
    return "\r\n".join(lines) + ("\r\n" if lines else "")


def probe_remote_quality(url: str, headers: dict | None = None, timeout: int = 45) -> dict:
    """Probe a remote MP4 stream so catalog cards show downloadable quality."""
    ffprobe = get_binary_path("ffprobe")
    cmd = [
        ffprobe, "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format",
    ]
    header_text = _headers_argument(headers)
    if header_text:
        cmd.extend(["-headers", header_text])
    cmd.append(url)
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        **hidden_subprocess_kwargs(),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe remote probe failed")
    data = json.loads(result.stdout or "{}")
    streams = data.get("streams") or []
    video_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "video"),
        None,
    )
    audio_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "audio"),
        None,
    )
    if not video_stream:
        raise RuntimeError("ffprobe не подтвердил видеопоток")
    size = int((data.get("format") or {}).get("size") or 0)
    bitrate = int(
        video_stream.get("bit_rate")
        or (data.get("format") or {}).get("bit_rate")
        or 0
    )
    quality = source_quality({
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": _fps_from_stream(video_stream),
        "codec": video_stream.get("codec_name"),
    })
    audio_codec = codec_label((audio_stream or {}).get("codec_name") or "")
    quality.update({
        "size": size,
        "bitrate": bitrate,
        "has_audio": bool(audio_stream),
        "audio_codec": audio_codec,
        "score": quality_score({
            "width": quality.get("width"),
            "height": quality.get("height"),
            "fps": quality.get("fps"),
            "filesize": size or bitrate,
            "has_audio": bool(audio_stream),
        }),
        "verified_remote": True,
    })
    return quality


def probe_media_streams(filepath: str) -> dict:
    """Read all media streams so TikTok quality checks can reject silent videos."""
    ffprobe = get_binary_path("ffprobe")
    cmd = [
        ffprobe, "-v", "quiet", "-print_format", "json",
        "-show_streams", filepath,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            **hidden_subprocess_kwargs(),
        )
        data = json.loads(result.stdout or "{}")
        streams = data.get("streams") or []
        audio_stream = next(
            (stream for stream in streams if stream.get("codec_type") == "audio"),
            None,
        )
        video_stream = next(
            (stream for stream in streams if stream.get("codec_type") == "video"),
            None,
        )
        return {
            "has_audio": bool(audio_stream),
            "audio_codec": str((audio_stream or {}).get("codec_name") or "").lower(),
            "has_video": bool(video_stream),
        }
    except Exception as exc:
        logger.error(f"ffprobe stream error for {filepath}: {exc}")
        return {"has_audio": False, "audio_codec": "", "has_video": False}


def quality_score(info: dict) -> tuple[int, float, int, int]:
    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    pixels = width * height
    try:
        fps = float(info.get("fps") or 0)
    except (TypeError, ValueError):
        fps = 0.0
    bitrate = int(info.get("tbr") or info.get("bitrate") or info.get("filesize") or info.get("size") or 0)
    return (quality_short_side(width, height), fps, pixels, bitrate)


def download_quality_score(info: dict) -> tuple[int, int, float, int, int]:
    """Rank actual downloads: usable audio first, then visual quality."""
    has_audio = 1 if info.get("has_audio") else 0
    visual = quality_score(info)
    return (has_audio, *visual)


def best_quality_info(items: list[dict]) -> dict:
    return max(items or [], key=quality_score, default={})
