"""
converter.py — probing and post-download video codec conversion through ffmpeg.
"""
import os
import json
import subprocess
import uuid
from PySide6.QtCore import QThread, Signal
from app.logger import logger
from app.binary_manager import get_binary_path
from app.process_utils import hidden_subprocess_kwargs


def probe_codec(filepath: str) -> str:
    """Возвращает название видеокодека файла через ffprobe."""
    ffprobe = get_binary_path("ffprobe")
    cmd = [
        ffprobe, "-v", "quiet", "-print_format", "json",
        "-show_streams", "-select_streams", "v:0", filepath
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, **hidden_subprocess_kwargs())
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        if streams:
            return streams[0].get("codec_name", "unknown").lower()
    except Exception as e:
        logger.error(f"ffprobe error for {filepath}: {e}")
    return "unknown"


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
        fps_text = str(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0")
        numerator, _, denominator = fps_text.partition("/")
        fps = float(numerator or 0) / float(denominator or 1)
        return {
            "codec": str(stream.get("codec_name") or "unknown").lower(),
            "width": int(stream.get("width") or 0),
            "height": int(stream.get("height") or 0),
            "fps": fps,
        }
    except Exception as exc:
        logger.error(f"ffprobe profile error for {filepath}: {exc}")
        return {"codec": "unknown", "width": 0, "height": 0, "fps": 0.0}


def has_video_stream(filepath: str) -> bool:
    """Returns True only when the file contains a video stream."""
    ffprobe = get_binary_path("ffprobe")
    cmd = [
        ffprobe, "-v", "quiet", "-print_format", "json",
        "-show_streams", "-select_streams", "v:0", filepath
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, **hidden_subprocess_kwargs())
        data = json.loads(result.stdout or "{}")
        return bool(data.get("streams", []))
    except Exception as e:
        logger.error(f"ffprobe media type error for {filepath}: {e}")
        return False


def is_h264(filepath: str) -> bool:
    return probe_codec(filepath) == "h264"


def normalized_target_codec(settings: dict) -> str:
    codec = str(settings.get("default_codec", "original")).lower()
    aliases = {"avc": "h264", "x264": "h264", "copy": "original", "source": "original"}
    return aliases.get(codec, codec if codec in {"original", "h264", "vp9", "av1"} else "original")


def normalized_target_container(settings: dict) -> str:
    value = str(settings.get("container", "mp4")).lower().lstrip(".")
    return value if value in {"mp4", "mkv", "webm"} else "mp4"


def target_resolution(settings: dict) -> str:
    if settings.get("upscale_to_profile", False):
        value = str(settings.get("upscale_target", "1440"))
        return value if value.isdigit() else "1440"
    return str(settings.get("download_quality", "1080"))


def profile_conversion_reasons(filepath: str, settings: dict) -> list[str]:
    """Return exact active-profile mismatches requested by the active profile."""
    info = probe_video_info(filepath)
    if not info.get("width") or not info.get("height"):
        return ["video_stream"]
    reasons = []
    target_codec = normalized_target_codec(settings)
    if target_codec != "original" and info["codec"] != target_codec:
        reasons.append("codec")
    if os.path.splitext(filepath)[1].lower() != f".{normalized_target_container(settings)}":
        reasons.append("container")
    quality = target_resolution(settings)
    if quality.isdigit():
        target = int(quality)
        source = min(info["width"], info["height"])
        if source > target:
            reasons.append("resolution")
        elif source < target and settings.get("upscale_to_profile", False):
            reasons.append("upscale")
    fps_limit = str(settings.get("fps_limit", "60"))
    if fps_limit.isdigit():
        target_fps = int(fps_limit)
        if info["fps"] > target_fps + 0.1:
            reasons.append("fps")
        elif settings.get("upscale_to_profile", False) and info["fps"] < target_fps - 0.1:
            reasons.append("fps_upscale")
    return reasons


def needs_profile_conversion(filepath: str, settings: dict) -> bool:
    return bool(profile_conversion_reasons(filepath, settings))


def available_encoders() -> set[str]:
    ffmpeg = get_binary_path("ffmpeg")
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10, **hidden_subprocess_kwargs()
        )
        return set(result.stdout.split())
    except Exception:
        return set()


def check_nvenc_available() -> bool:
    """Проверяет доступность NVIDIA h264_nvenc."""
    return "h264_nvenc" in available_encoders()


def _select_h264_encoder(settings: dict) -> tuple[str, list[str], str]:
    requested = settings.get("video_encoder", "auto")
    mode = settings.get("encoding_mode", "gpu_auto")
    encoders = available_encoders()

    profiles = {
        "h264_nvenc": (["-preset", "p4", "-rc", "vbr", "-cq", "20"], "NVIDIA NVENC"),
        "h264_qsv": (["-preset", "medium", "-global_quality", "20"], "Intel Quick Sync"),
        "h264_amf": (["-quality", "balanced", "-qp_i", "20", "-qp_p", "22"], "AMD AMF"),
        "libx264": (["-preset", "fast", "-crf", "18"], "CPU x264"),
    }

    candidates: list[str]
    if mode == "cpu_only":
        candidates = ["libx264"]
    elif requested != "auto":
        candidates = [requested]
        if mode != "gpu_only":
            candidates.append("libx264")
    else:
        candidates = ["h264_nvenc", "h264_qsv", "h264_amf"]
        if mode != "gpu_only":
            candidates.append("libx264")

    for encoder in candidates:
        if encoder == "libx264" or encoder in encoders:
            args, label = profiles[encoder]
            return encoder, args, label

    raise RuntimeError("Не найден доступный H.264 энкодер для выбранного режима")


def _select_video_codec(settings: dict) -> tuple[str, list[str], str]:
    target = normalized_target_codec(settings)
    if target == "h264":
        encoder, args, label = _select_h264_encoder(settings)
        return encoder, args, label
    if target == "vp9":
        return "libvpx-vp9", ["-crf", "30", "-b:v", "0", "-row-mt", "1"], "VP9"
    if target == "av1":
        return "libaom-av1", ["-crf", "30", "-b:v", "0", "-cpu-used", "6"], "AV1"
    raise RuntimeError("Кодек оставлен оригинальным, конвертация не требуется")


def _source_encoder(codec: str, settings: dict) -> tuple[str, list[str], str]:
    if codec == "h264":
        return _select_h264_encoder(settings)
    if codec == "vp9":
        return "libvpx-vp9", ["-crf", "30", "-b:v", "0", "-row-mt", "1"], "VP9"
    if codec == "av1":
        return "libaom-av1", ["-crf", "30", "-b:v", "0", "-cpu-used", "6"], "AV1"
    if codec in {"hevc", "h265"} and "libx265" in available_encoders():
        return "libx265", ["-preset", "fast", "-crf", "22"], "H.265"
    raise RuntimeError(
        "Для изменения разрешения или FPS исходного кодека выберите H.264, VP9 или AV1"
    )


class ConvertWorker(QThread):
    """
    Конвертирует видеофайл в выбранный кодек.
    Сигналы:
        progress(filepath, percent)
        finished(filepath, out_path, success, error_msg)
        log_line(filepath, text)
    """
    progress = Signal(str, float)
    finished = Signal(str, str, bool, str)
    log_line = Signal(str, str)

    def __init__(self, filepath: str, settings: dict, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.settings = dict(settings)
        self._cancelled = False
        self._proc = None

    def cancel(self):
        self._cancelled = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def run(self):
        try:
            self._convert()
        except Exception as e:
            logger.error(f"Conversion error {self.filepath}: {e}")
            self.finished.emit(self.filepath, "", False, str(e))

    def _get_duration(self) -> float:
        """Получить длительность видео в секундах через ffprobe."""
        ffprobe = get_binary_path("ffprobe")
        try:
            cmd = [ffprobe, "-v", "quiet", "-print_format", "json",
                   "-show_format", self.filepath]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, **hidden_subprocess_kwargs())
            data = json.loads(r.stdout)
            dur = float(data.get("format", {}).get("duration", 0))
            return dur
        except Exception:
            return 0.0

    def _convert(self):
        keep_originals = self.settings.get("keep_originals", False)
        source_info = probe_video_info(self.filepath)
        reasons = profile_conversion_reasons(self.filepath, self.settings)
        target_codec = normalized_target_codec(self.settings)
        output_ext = f".{normalized_target_container(self.settings)}"
        filters = []
        quality = target_resolution(self.settings)
        if ("resolution" in reasons or "upscale" in reasons) and quality.isdigit():
            limit = int(quality)
            scale_filter = (
                f"scale=-2:{limit}:flags=lanczos"
                if source_info["width"] >= source_info["height"]
                else f"scale={limit}:-2:flags=lanczos"
            )
            if "upscale" in reasons:
                scale_filter += ",unsharp=5:5:0.8:3:3:0.4"
            filters.append(scale_filter)
        fps_limit = str(self.settings.get("fps_limit", "60"))
        if "fps" in reasons and fps_limit.isdigit():
            filters.append(f"fps={int(fps_limit)}")
        elif "fps_upscale" in reasons and fps_limit.isdigit():
            filters.append(
                f"minterpolate=fps={int(fps_limit)}:"
                "mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
            )

        source_codec = source_info.get("codec", "unknown")
        codec_already_matches = (
            target_codec == "original" or target_codec == source_codec
        )
        if codec_already_matches and not filters:
            encoder, preset_args, encoder_label = "copy", [], "без перекодирования"
        elif target_codec == "original":
            encoder, preset_args, encoder_label = _source_encoder(
                source_codec, self.settings
            )
        else:
            encoder, preset_args, encoder_label = _select_video_codec(self.settings)
        logger.info(f"Using {encoder_label} for encoding: {self.filepath}")
        self.log_line.emit(self.filepath, f"Кодирование: {encoder_label}")
        
        base, _ = os.path.splitext(self.filepath)
        suffix = target_codec if target_codec != "original" else "profile"
        out_path = base + f"_{suffix}{output_ext}"
        if os.path.abspath(self.filepath) == os.path.abspath(out_path):
            out_path = base + f"_converted{output_ext}"
        if os.path.exists(out_path):
            counter = 2
            candidate = out_path
            while os.path.exists(candidate):
                candidate = base + f"_{suffix}_{counter}{output_ext}"
                counter += 1
            out_path = candidate
        temp_path = os.path.splitext(out_path)[0] + f".part-{uuid.uuid4().hex[:8]}{output_ext}"
        
        ffmpeg = get_binary_path("ffmpeg")
        duration = self._get_duration()
        
        cmd = [
            ffmpeg, "-y",
            "-i", self.filepath,
            "-c:v", encoder,
        ] + preset_args
        if filters:
            cmd += ["-vf", ",".join(filters)]
        audio_codec = "libopus" if output_ext == ".webm" else "aac"
        cmd += [
            "-c:a", audio_codec,
            "-b:a", "160k" if audio_codec == "libopus" else "192k",
        ]
        if output_ext == ".mp4":
            cmd += ["-movflags", "+faststart"]
        cmd += ["-progress", "pipe:1", "-nostats", temp_path]
        
        logger.info(f"Running ffmpeg: {' '.join(cmd)}")
        
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            **hidden_subprocess_kwargs(),
        )
        
        out_time_us = 0
        output_tail = []
        if self._proc.stdout:
            for line in self._proc.stdout:
                if self._cancelled:
                    self._proc.terminate()
                    try:
                        self._proc.wait(timeout=5)
                    except Exception:
                        pass
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except OSError:
                            pass
                    self.finished.emit(self.filepath, "", False, "Отменено пользователем")
                    return
                
                line = line.strip()
                if line:
                    output_tail.append(line)
                    output_tail = output_tail[-40:]
                if line.startswith("out_time_us="):
                    try:
                        out_time_us = int(line.split("=")[1])
                        if duration > 0:
                            pct = min(100.0, (out_time_us / 1_000_000) / duration * 100)
                            self.progress.emit(self.filepath, pct)
                    except Exception:
                        pass
        
        self._proc.wait()
        if self._proc.stdout:
            self._proc.stdout.close()
        
        expected_codec = source_codec if target_codec == "original" else target_codec
        remaining_mismatches = (
            profile_conversion_reasons(temp_path, self.settings)
            if os.path.isfile(temp_path) else ["missing"]
        )
        verified = (
            self._proc.returncode == 0
            and os.path.isfile(temp_path)
            and os.path.getsize(temp_path) > 0
            and has_video_stream(temp_path)
            and probe_codec(temp_path) == expected_codec
            and not remaining_mismatches
        )
        if verified:
            os.replace(temp_path, out_path)
            logger.info(f"Conversion verified and finalized: {out_path}")
            if not keep_originals:
                try:
                    os.remove(self.filepath)
                    logger.info(f"Removed original file: {self.filepath}")
                except Exception as e:
                    warning = f"Новый файл готов, но исходный файл не удалось удалить: {e}"
                    logger.warning(warning)
                    self.finished.emit(self.filepath, out_path, True, warning)
                    return
            self.finished.emit(self.filepath, out_path, True, "")
        else:
            actual_codec = probe_codec(temp_path) if os.path.isfile(temp_path) else "unknown"
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            stderr_tail = "\n".join(output_tail)[-700:]
            logger.error(f"ffmpeg conversion error (code {self._proc.returncode}): {stderr_tail}")
            detail = (
                f"Перекодирование не завершено или итоговый кодек не прошёл проверку "
                f"(ожидался {expected_codec}, получен {actual_codec}, "
                f"несовпадения профиля: {', '.join(remaining_mismatches) or 'нет'}, "
                f"код ffmpeg {self._proc.returncode}). "
                "Исходный файл сохранён."
            )
            if stderr_tail:
                detail += f": {stderr_tail}"
            self.finished.emit(self.filepath, "", False, detail)
