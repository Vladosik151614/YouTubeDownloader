"""Quick profile handlers for the main window."""

from app.converter import normalized_target_codec
from app.settings_manager import save_settings


def _set_combo(combo, index: int):
    combo.blockSignals(True)
    combo.setCurrentIndex(index)
    combo.blockSignals(False)


def _refresh_settings_page(window):
    if hasattr(window, "settings_page"):
        window.settings_page.settings = dict(window.settings)
        window.settings_page._load_values()


def sync_quick_controls(window):
    maps = {
        "quick_quality_combo": ({"best": 0, "2160": 1, "1440": 2, "1080": 3, "720": 4, "480": 5}, "download_quality", "1080", 3),
        "quick_container_combo": ({"mp4": 0, "mkv": 1, "webm": 2}, "container", "mp4", 0),
        "quick_encoder_combo": ({"auto": 0, "h264_nvenc": 1, "h264_qsv": 2, "h264_amf": 3, "libx264": 4}, "video_encoder", "auto", 0),
        "quick_upscale_target_combo": ({"1440": 0, "2160": 1}, "upscale_target", "1440", 0),
    }
    for attr, (mapping, key, default, fallback) in maps.items():
        if hasattr(window, attr):
            _set_combo(getattr(window, attr), mapping.get(str(window.settings.get(key, default)), fallback))
    if hasattr(window, "quick_codec_combo"):
        _set_combo(window.quick_codec_combo, {"original": 0, "h264": 1, "vp9": 2, "av1": 3}.get(normalized_target_codec(window.settings), 0))
    for attr, key in (("quick_numbering_switch", "playlist_numbering"), ("quick_upscale_switch", "upscale_to_profile")):
        if hasattr(window, attr):
            switch = getattr(window, attr)
            switch.blockSignals(True)
            switch.setChecked(window.settings.get(key, False))
            switch.blockSignals(False)


def save_quick_setting(window, key: str, value: str):
    window.settings[key] = value
    if key == "video_encoder":
        window.settings["encoding_mode"] = "cpu_only" if value == "libx264" else "gpu_auto"
        window.settings["prefer_gpu"] = value != "libx264"
    save_settings(window.settings)
    _refresh_settings_page(window)


def on_quick_quality_changed(window, index: int):
    save_quick_setting(window, "download_quality", {0: "best", 1: "2160", 2: "1440", 3: "1080", 4: "720", 5: "480"}.get(index, "1080"))


def on_quick_container_changed(window, index: int):
    save_quick_setting(window, "container", {0: "mp4", 1: "mkv", 2: "webm"}.get(index, "mp4"))


def on_quick_encoder_changed(window, index: int):
    save_quick_setting(window, "video_encoder", {0: "auto", 1: "h264_nvenc", 2: "h264_qsv", 3: "h264_amf", 4: "libx264"}.get(index, "auto"))


def on_quick_codec_changed(window, index: int):
    window.settings["default_codec"] = {0: "original", 1: "h264", 2: "vp9", 3: "av1"}.get(index, "original")
    window.settings["auto_convert"] = window.settings["default_codec"] != "original"
    save_settings(window.settings)
    _refresh_settings_page(window)


def on_quick_numbering_toggled(window, checked: bool):
    window.settings["playlist_numbering"] = bool(checked)
    save_settings(window.settings)
    _refresh_settings_page(window)


def on_quick_upscale_toggled(window, checked: bool):
    window.settings["upscale_to_profile"] = bool(checked)
    if checked:
        window.settings["auto_convert"] = True
    save_settings(window.settings)
    _refresh_settings_page(window)
    if checked and hasattr(window, "quick_auto_convert_switch"):
        window.quick_auto_convert_switch.blockSignals(True)
        window.quick_auto_convert_switch.setChecked(True)
        window.quick_auto_convert_switch.blockSignals(False)


def on_quick_upscale_target_changed(window, index: int):
    window.settings["upscale_target"] = {0: "1440", 1: "2160"}.get(index, "1440")
    save_settings(window.settings)
    _refresh_settings_page(window)
