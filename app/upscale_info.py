import os
from app.converter import probe_video_info

def _format_video_info(path: str) -> str:
    if not path or not os.path.isfile(path):
        return "Файл не выбран"
    info = probe_video_info(path)
    size_mb = os.path.getsize(path) / 1024 / 1024
    fps = info.get("fps") or 0
    fps_text = f"{fps:.1f}".rstrip("0").rstrip(".") if fps else "—"
    width = info.get("width") or 0
    height = info.get("height") or 0
    resolution = f"{width}×{height}" if width and height else "—"
    return (
        f"{os.path.basename(path)}\n"
        f"{resolution} · {fps_text} FPS · {info.get('codec', 'unknown')} · "
        f"{size_mb:.1f} МБ"
    )


def _codec_label(codec: str) -> str:
    return {
        "original": "Оригинал",
        "h264": "H.264",
        "vp9": "VP9",
        "av1": "AV1",
    }.get(codec, codec.upper())
