"""Background inspection of downloaded files before applying their profile."""
import os
from PySide6.QtCore import QThread, Signal
from app.logger import logger
from app.converter import has_video_stream, needs_profile_conversion, needs_tiktok_landscape_normalization


class ConversionScanWorker(QThread):
    scan_ready = Signal(str, list, dict, bool)

    def __init__(self, item_id: str, filepaths: list, settings: dict, is_playlist: bool):
        super().__init__()
        self.item_id = item_id
        self.filepaths = list(filepaths)
        self.settings = dict(settings)
        self.is_playlist = is_playlist
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            selected = []
            for filepath in self.filepaths:
                if self._cancelled:
                    return
                if not os.path.isfile(filepath):
                    continue
                if self.settings.get("auto_convert", True):
                    if has_video_stream(filepath) and not self._cancelled and needs_profile_conversion(filepath, self.settings):
                        selected.append(filepath)
                elif needs_tiktok_landscape_normalization(filepath, self.settings):
                    selected.append(filepath)
            if not self._cancelled:
                settings = dict(self.settings)
                if not settings.get("auto_convert", True):
                    settings.update(auto_convert=True, ask_before_codec_convert=False, rotation_only=True)
                self.scan_ready.emit(self.item_id, selected, settings, self.is_playlist)
        except Exception:
            logger.exception("[%s] Failed to inspect files for conversion", self.item_id)
            if not self._cancelled:
                self.scan_ready.emit(self.item_id, [], dict(self.settings), self.is_playlist)
