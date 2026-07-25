"""
converter.py — определение кодека и аппаратно-ускоренная конвертация в H.264/MP4 через NVIDIA NVENC / ffmpeg
"""
import os
import json
import subprocess
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


class ConvertWorker(QThread):
    """
    Конвертирует видеофайл в H.264/AAC MP4.
    Приоритет кодирования — аппаратное ускорение NVIDIA NVENC.
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
        self.settings = settings
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
        encoder, preset_args, encoder_label = _select_h264_encoder(self.settings)
        logger.info(f"Using {encoder_label} for encoding: {self.filepath}")
        self.log_line.emit(self.filepath, f"Кодирование: {encoder_label}")
        
        base, _ = os.path.splitext(self.filepath)
        out_path = base + "_h264.mp4"
        if self.filepath.endswith("_h264.mp4"):
            out_path = base + "_conv.mp4"
        
        ffmpeg = get_binary_path("ffmpeg")
        duration = self._get_duration()
        
        cmd = [
            ffmpeg, "-y",
            "-i", self.filepath,
            "-c:v", encoder,
        ] + preset_args + [
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            "-nostats",
            out_path,
        ]
        
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
        
        if self._proc.returncode == 0 and os.path.isfile(out_path):
            logger.info(f"Conversion success: {out_path}")
            if not keep_originals:
                try:
                    os.remove(self.filepath)
                    logger.info(f"Removed original file: {self.filepath}")
                except Exception as e:
                    logger.warning(f"Could not remove original: {e}")
            self.finished.emit(self.filepath, out_path, True, "")
        else:
            stderr_tail = "\n".join(output_tail)[-700:]
            logger.error(f"ffmpeg conversion error (code {self._proc.returncode}): {stderr_tail}")
            detail = f"Ошибка ffmpeg (код {self._proc.returncode})"
            if stderr_tail:
                detail += f": {stderr_tail}"
            self.finished.emit(self.filepath, "", False, detail)
