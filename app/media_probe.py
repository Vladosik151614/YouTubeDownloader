"""Bounded ffprobe helpers used for validating and transforming videos."""
import json
import subprocess
from app.binary_manager import get_binary_path
from app.logger import logger
from app.process_utils import hidden_subprocess_kwargs


def probe_codec(filepath: str) -> str:
    cmd = [get_binary_path("ffprobe"), "-v", "quiet", "-print_format", "json",
           "-show_streams", "-select_streams", "v:0", filepath]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, **hidden_subprocess_kwargs())
        streams = json.loads(result.stdout).get("streams", [])
        if streams:
            return streams[0].get("codec_name", "unknown").lower()
    except Exception as exc:
        logger.error(f"ffprobe error for {filepath}: {exc}")
    return "unknown"


def rotation_from_stream(stream: dict) -> int:
    values = [(stream.get("tags") or {}).get("rotate")]
    for item in stream.get("side_data_list") or []:
        if isinstance(item, dict):
            values.append(item.get("rotation"))
    for value in values:
        try:
            rotation = int(round(float(value)))
        except (TypeError, ValueError):
            continue
        while rotation <= -180:
            rotation += 360
        while rotation > 180:
            rotation -= 360
        return rotation
    return 0


def has_video_stream(filepath: str) -> bool:
    cmd = [get_binary_path("ffprobe"), "-v", "quiet", "-print_format", "json",
           "-show_streams", "-select_streams", "v:0", filepath]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, **hidden_subprocess_kwargs())
        return bool(json.loads(result.stdout or "{}").get("streams", []))
    except Exception as exc:
        logger.error(f"ffprobe media type error for {filepath}: {exc}")
        return False


def probe_audio_presence(filepath: str) -> bool | None:
    """Return None on probe failure, distinct from a genuinely silent source."""
    try:
        result = subprocess.run(
            [get_binary_path("ffprobe"), "-v", "error", "-of", "json",
             "-show_entries", "stream=codec_type", "-select_streams", "a", filepath],
            capture_output=True, text=True, timeout=30, **hidden_subprocess_kwargs(),
        )
        if result.returncode:
            return None
        streams = json.loads(result.stdout).get("streams")
        if not isinstance(streams, list):
            return None
        return any(item.get("codec_type") == "audio" for item in streams)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def available_encoders() -> set[str]:
    try:
        result = subprocess.run(
            [get_binary_path("ffmpeg"), "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10, **hidden_subprocess_kwargs(),
        )
        return set(result.stdout.split())
    except Exception:
        return set()

def probe_video_info(filepath: str) -> dict:
    """Read the first video stream properties used by the active profile."""
    ffprobe = get_binary_path("ffprobe")
    cmd = [
        ffprobe, "-v", "quiet", "-print_format", "json",
        "-show_streams", "-select_streams", "v:0", filepath,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            **hidden_subprocess_kwargs(),
        )
        stream = (json.loads(result.stdout or "{}").get("streams") or [{}])[0]
        fps = 0.0
        for rate in (stream.get("avg_frame_rate"), stream.get("r_frame_rate")):
            try:
                numerator, _, denominator = str(rate or "0").partition("/")
                parsed = float(numerator or 0) / float(denominator or 1)
                if parsed > 0:
                    fps = parsed
                    break
            except (ValueError, ZeroDivisionError):
                continue
        rotation = rotation_from_stream(stream)
        return {
            "codec": str(stream.get("codec_name") or "unknown").lower(),
            "width": int(stream.get("width") or 0),
            "height": int(stream.get("height") or 0),
            "fps": fps,
            "rotation": rotation,
            "display_width": int(stream.get("height") or 0) if abs(rotation) in {90, 270} else int(stream.get("width") or 0),
            "display_height": int(stream.get("width") or 0) if abs(rotation) in {90, 270} else int(stream.get("height") or 0),
        }
    except Exception as exc:
        logger.error(f"ffprobe profile error for {filepath}: {exc}")
        return {
            "codec": "unknown", "width": 0, "height": 0, "fps": 0.0,
            "rotation": 0, "display_width": 0, "display_height": 0,
        }
