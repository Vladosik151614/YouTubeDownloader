import os

def _snapshot_files(folder: str) -> set[str]:
    try:
        return {
            os.path.join(folder, name)
            for name in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, name))
        }
    except Exception:
        return set()


def _media_files(paths: set[str]) -> list[str]:
    exts = {".mp4", ".mkv", ".webm", ".m4a", ".mp3", ".opus", ".jpg", ".jpeg", ".png", ".webp", ".json", ".description", ".vtt", ".srt"}
    return sorted(
        path for path in paths
        if os.path.splitext(path)[1].lower() in exts and os.path.getsize(path) > 0
    )


def _rate_limit_bytes(value: str) -> int | None:
    limits = {
        "50m": 50 * 1024 * 1024 // 8,
        "25m": 25 * 1024 * 1024 // 8,
        "10m": 10 * 1024 * 1024 // 8,
        "4m": 4 * 1024 * 1024 // 8,
        "2m": 2 * 1024 * 1024 // 8,
    }
    return limits.get(value)
