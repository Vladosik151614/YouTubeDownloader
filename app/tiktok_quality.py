"""TikTok media quality probing and ranking helpers."""
from __future__ import annotations

import os

from app.converter import probe_video_info


def quality_short_side(width: int, height: int) -> int:
    values = [int(value or 0) for value in (width, height) if int(value or 0) > 0]
    return min(values) if values else 0


def quality_label(width: int, height: int) -> str:
    short_side = quality_short_side(width, height)
    if short_side >= 2160:
        return "4K"
    if short_side >= 1440:
        return "2K"
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
    quality.update({
        "filepath": filepath,
        "size": size,
        "score": quality_score({
            "width": width,
            "height": height,
            "fps": fps,
            "filesize": size,
        }),
    })
    return quality


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


def best_quality_info(items: list[dict]) -> dict:
    return max(items or [], key=quality_score, default={})
