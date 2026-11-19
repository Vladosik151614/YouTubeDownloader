"""Local developer diagnostics. Never store raw URL parameters or credentials."""
import logging
import os
import platform
import re
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from importlib import metadata
from urllib.parse import urlsplit, urlunsplit

APP_NAME = "YouTubeDownloader"
BASE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), APP_NAME)
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Query strings often contain signed media links, session identifiers or API keys.
_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_HEADER = re.compile(r"(?im)\b(cookie|set-cookie|authorization|proxy-authorization)\s*:\s*[^\r\n]*")
_COOKIE_ASSIGN = re.compile(r"(?im)([\"']?\b(?:cookies?|set-cookie)\b[\"']?\s*[=:]\s*)[^\r\n]*")
_SECRET = re.compile(
    r"(?i)([\"']?(?:access_token|refresh_token|id_token|token|api[_-]?key|client[_-]?secret|password|passwd|sessionid|session_id|sid_tt|msToken)[\"']?\s*[=:]\s*)"
    r"(?:[\"'][^\"']*[\"']|[^\s,;&}\]]+)"
)
_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+")


def _safe_url(match):
    value = match.group(0)
    try:
        parts = urlsplit(value)
        # Discard userinfo as well as query and fragment, including signed URLs.
        host = parts.hostname or ""
        if ":" in host:
            host = f"[{host}]"
        if parts.port:
            host += f":{parts.port}"
        return urlunsplit((parts.scheme, host, parts.path, "", "")) + ("?[скрыто]" if parts.query else "")
    except ValueError:
        return "[URL скрыт]"


def redact_sensitive(value):
    """Redact common credentials; diagnostics may still contain personal paths/titles."""
    text = str(value)
    text = _HEADER.sub(lambda m: m.group(1) + ": [скрыто]", text)
    text = _COOKIE_ASSIGN.sub(r"\1[скрыто]", text)
    text = _URL.sub(_safe_url, text)
    text = _SECRET.sub(r"\1[скрыто]", text)
    return _BEARER.sub(r"\1 [скрыто]", text)


def dependency_version(package):
    """Report the loaded Qt version when frozen builds omit package metadata."""
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        if package == 'PySide6':
            try:
                from PySide6 import __version__
                return __version__
            except ImportError:
                pass
        return 'недоступна'


class SafeFormatter(logging.Formatter):
    def format(self, record):
        # Format first so exception tracebacks and interpolation receive the same filtering.
        return redact_sensitive(super().format(record))


def cleanup_old_logs(max_age_seconds=30 * 24 * 3600):
    """Remove only this application's old log files, not arbitrary user files."""
    now = time.time()
    try:
        for filename in os.listdir(LOGS_DIR):
            if not re.fullmatch(r"ytdl_\d{8}_\d{6}_\d+\.log(?:\.\d+)?", filename):
                continue
            filepath = os.path.join(LOGS_DIR, filename)
            try:
                if os.path.isfile(filepath) and now - os.path.getmtime(filepath) > max_age_seconds:
                    os.remove(filepath)
            except OSError:
                continue
    except OSError:
        pass


cleanup_old_logs()
_log_filename = os.path.join(LOGS_DIR, f"ytdl_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}.log")
_formatter = SafeFormatter("%(asctime)s [%(levelname)s] [%(threadName)s] %(module)s:%(lineno)d %(message)s")
logger = logging.getLogger("ytdownloader")
logger.setLevel(logging.DEBUG)
logger.propagate = False
if not logger.handlers:
    file_handler = RotatingFileHandler(_log_filename, maxBytes=2 * 1024 * 1024, backupCount=4, encoding="utf-8")
    file_handler.setFormatter(_formatter)
    logger.addHandler(file_handler)
    # A windowed PyInstaller process may expose a broken stderr handle.
    # The rotating local file remains available without a console stream.
    if not getattr(sys, "frozen", False) and sys.stderr is not None:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(_formatter)
        logger.addHandler(stream_handler)
    logger.info("Диагностика запущена; журнал хранится локально")
    versions = []
    for package in ("yt-dlp", "yt-dlp-ejs", "PySide6", "curl_cffi"):
        versions.append(f"{package}={dependency_version(package)}")
    logger.info(
        "Окружение: ОС=%s Python=%s frozen=%s PID=%s зависимости: %s",
        platform.platform(), platform.python_version(), bool(getattr(sys, "frozen", False)),
        os.getpid(), ", ".join(versions),
    )
