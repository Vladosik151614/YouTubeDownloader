"""Probing and post-download video codec conversion through ffmpeg."""
from app.media_probe import probe_video_info
import os
import json
import subprocess
import uuid
from PySide6.QtCore import QThread, Signal
from app.logger import logger
from app.binary_manager import get_binary_path
from app.process_utils import hidden_subprocess_kwargs
from app.media_probe import probe_codec, has_video_stream, probe_audio_presence, rotation_from_stream, available_encoders


def is_tiktok_source(settings: dict) -> bool:
    return "tiktok.com/" in str(settings.get("source_url") or "").lower()


def needs_tiktok_landscape_normalization(filepath: str, settings: dict) -> bool:
    """True when TikTok stored a landscape clip behind rotate metadata."""
    if not settings.get("normalize_tiktok_landscape", True):
        return False
    if not is_tiktok_source(settings):
        return False
    info = probe_video_info(filepath)
    if not info.get("width") or not info.get("height"):
        return False
    display_width = int(info.get("display_width") or info.get("width") or 0)
    display_height = int(info.get("display_height") or info.get("height") or 0)
    return abs(int(info.get("rotation") or 0)) in {90, 270} and display_width > display_height


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
    if needs_tiktok_landscape_normalization(filepath, settings):
        reasons.append("tiktok_landscape")
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
        if self._cancelled:
            self.finished.emit(self.filepath, "", False, "Отменено пользователем")
            return
        keep_originals = self.settings.get("keep_originals", False)
        source_info = probe_video_info(self.filepath)
        if self._cancelled:
            self.finished.emit(self.filepath, "", False, "Отменено пользователем")
            return
        source_has_audio = probe_audio_presence(self.filepath)
        if self._cancelled:
            self.finished.emit(self.filepath, "", False, "Отменено пользователем")
            return
        if source_has_audio is None:
            raise RuntimeError("Не удалось проверить звук исходного файла. Исходный файл сохранён.")
        duration = self._get_duration()
        if self._cancelled:
            self.finished.emit(self.filepath, "", False, "Отменено пользователем")
            return
        rotation_only = bool(self.settings.get("rotation_only", False))
        if rotation_only and not needs_tiktok_landscape_normalization(self.filepath, self.settings):
            raise RuntimeError("Не подтверждён поворот TikTok-видео; исходник сохранён.")
        reasons = ["tiktok_landscape"] if rotation_only else profile_conversion_reasons(self.filepath, self.settings)
        target_codec = "original" if rotation_only else normalized_target_codec(self.settings)
        output_ext = os.path.splitext(self.filepath)[1].lower() if rotation_only else f".{normalized_target_container(self.settings)}"
        if rotation_only and output_ext not in {".mp4", ".mov", ".mkv", ".webm"}:
            raise RuntimeError("Невозможно безопасно сохранить исходный контейнер при повороте; исходник сохранён.")
        filters = []
        quality = target_resolution(self.settings)
        if "tiktok_landscape" in reasons:
            rotation = int(source_info.get("rotation") or 0)
            filters.append("transpose=2" if rotation > 0 else "transpose=1")
        if ("resolution" in reasons or "upscale" in reasons) and quality.isdigit():
            limit = int(quality)
            # Filters run after transpose, so scaling must use display orientation.
            rotated = "tiktok_landscape" in reasons
            width = source_info.get("display_width", source_info["width"]) if rotated else source_info["width"]
            height = source_info.get("display_height", source_info["height"]) if rotated else source_info["height"]
            scale_filter = (
                f"scale=-2:{limit}:flags=lanczos"
                if width >= height
                else f"scale={limit}:-2:flags=lanczos"
            )
            if "upscale" in reasons:
                scale_filter += ",unsharp=5:5:0.8:3:3:0.4"
            filters.append(scale_filter)
        fps_limit = str(self.settings.get("fps_limit", "60"))
        if "fps" in reasons and fps_limit.isdigit():
            filters.append(f"fps={int(fps_limit)}")
        elif "fps_upscale" in reasons and fps_limit.isdigit():
            source_fps = float(source_info.get("fps") or 0)
            if source_fps > 0 and duration > 0:
                filters.append(f"tpad=stop_mode=clone:stop_duration={2.0 / source_fps:.6f}")
            filters.append(
                f"minterpolate=fps={int(fps_limit)}:"
                "mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
            )
            if duration > 0:
                filters.append(f"trim=duration={duration:.6f}")

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
        
        source_base, _ = os.path.splitext(self.filepath)
        output_folder = str(self.settings.get("output_folder") or "").strip()
        if output_folder:
            os.makedirs(output_folder, exist_ok=True)
            base = os.path.join(output_folder, os.path.basename(source_base))
        else:
            base = source_base
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
        
        cmd = [ffmpeg, "-y"]
        if "tiktok_landscape" in reasons:
            cmd += ["-noautorotate", "-display_rotation", "0"]
        cmd += ["-i", self.filepath, "-c:v", encoder] + preset_args
        if filters:
            cmd += ["-vf", ",".join(filters)]
        if "tiktok_landscape" in reasons:
            cmd += ["-metadata:s:v:0", "rotate=0"]
        audio_codec = "libopus" if output_ext == ".webm" else "aac"
        cmd += ["-c:a", "copy"] if rotation_only else [
            "-c:a", audio_codec, "-b:a", "160k" if audio_codec == "libopus" else "192k",
        ]
        if output_ext == ".mp4":
            cmd += ["-movflags", "+faststart"]
        cmd += ["-progress", "pipe:1", "-nostats", temp_path]
        
        logger.info(f"Running ffmpeg: {' '.join(cmd)}")
        
        out_time_us = 0
        output_tail = []
        for attempt in range(2):
            if self._cancelled:
                self.finished.emit(self.filepath, "", False, "Отменено пользователем")
                return
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", **hidden_subprocess_kwargs(),
            )
            # cancel() can run between the check above and Popen assigning the
            # process; terminate immediately instead of waiting for output.
            if self._cancelled and self._proc.poll() is None:
                try:
                    self._proc.terminate()
                except OSError:
                    logger.warning("Не удалось остановить процесс конвертации", exc_info=True)
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
            if self._cancelled:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                self.finished.emit(self.filepath, "", False, "Отменено пользователем")
                return
            if not self._proc.returncode or self._cancelled:
                break
            if (attempt == 0 and encoder in {"h264_nvenc", "h264_qsv", "h264_amf"}
                    and self.settings.get("encoding_mode", "gpu_auto") != "gpu_only"):
                logger.warning("GPU encoder %s failed; retrying with CPU x264", encoder)
                self.log_line.emit(self.filepath, "Видеокарта недоступна, повторяю обработку на процессоре")
                encoder_position = cmd.index("-c:v") + 1
                cmd[encoder_position:encoder_position + 1 + len(preset_args)] = [
                    "libx264", "-preset", "fast", "-crf", "18",
                ]
                continue
            break
        
        expected_codec = source_codec if target_codec == "original" else target_codec
        if not os.path.isfile(temp_path):
            remaining_mismatches = ["missing"]
        elif rotation_only:
            output_info = probe_video_info(temp_path)
            remaining_mismatches = [] if (
                output_info.get("width") == source_info.get("display_width")
                and output_info.get("height") == source_info.get("display_height")
                and not output_info.get("rotation")
                and abs(output_info.get("fps", 0) - source_info.get("fps", 0)) < 0.1
            ) else ["rotation_or_fps"]
        else:
            remaining_mismatches = profile_conversion_reasons(temp_path, self.settings)
        verified = (
            self._proc.returncode == 0
            and os.path.isfile(temp_path)
            and os.path.getsize(temp_path) > 0
            and has_video_stream(temp_path)
            and probe_codec(temp_path) == expected_codec
            and not remaining_mismatches
        )
        if verified:
            output_has_audio = probe_audio_presence(temp_path)
            if output_has_audio is None or (source_has_audio and not output_has_audio):
                verified = False
        if self._cancelled:
            verified = False
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
