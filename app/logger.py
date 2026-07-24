"""
logger.py — логирование ошибок и событий в папку logs/
с автоматической очисткой логов старше 1 часа.
"""
import logging
import os
import time
from datetime import datetime

APP_NAME = "YouTubeDownloader"
BASE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), APP_NAME)
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

def cleanup_old_logs(max_age_seconds: int = 3600):
    """Удаляет лог-файлы старше указанного времени (по умолчанию 1 час)."""
    now = time.time()
    try:
        for filename in os.listdir(LOGS_DIR):
            if filename.endswith(".log"):
                filepath = os.path.join(LOGS_DIR, filename)
                if os.path.isfile(filepath):
                    file_age = now - os.path.getmtime(filepath)
                    if file_age > max_age_seconds:
                        try:
                            os.remove(filepath)
                        except Exception:
                            pass
    except Exception:
        pass

# Выполняем очистку старых логов при запуске
cleanup_old_logs(max_age_seconds=3600)

_log_filename = os.path.join(LOGS_DIR, f"ytdl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_log_filename, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("ytdownloader")
