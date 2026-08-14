"""
proxy_config.py - normalized proxy settings for network calls.
"""
from urllib.parse import quote, urlparse


ALLOWED_PROXY_TYPES = {"http", "https", "socks4", "socks5"}


def _valid_host(host: str) -> bool:
    if not host or len(host) > 255:
        return False
    blocked = set("/\\@:#?&=%\r\n\t ")
    return not any(char in blocked for char in host)


def _valid_port(port: str) -> bool:
    if not port.isdigit():
        return False
    value = int(port)
    return 1 <= value <= 65535


def _safe_legacy_proxy(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_PROXY_TYPES:
        return ""
    if not parsed.hostname or not _valid_host(parsed.hostname):
        return ""
    try:
        parsed_port = parsed.port
    except ValueError:
        return ""
    if parsed_port is None or not _valid_port(str(parsed_port)):
        return ""
    if any(char in url for char in "\r\n\t"):
        return ""
    return url


def proxy_url_from_settings(settings: dict) -> str:
    if not settings.get("proxy_enabled", False):
        return ""

    legacy = str(settings.get("proxy_url", "")).strip()
    if legacy:
        return _safe_legacy_proxy(legacy)

    host = str(settings.get("proxy_host", "")).strip()
    port = str(settings.get("proxy_port", "")).strip()
    if not host or not port:
        return ""

    proxy_type = str(settings.get("proxy_type", "http")).strip().lower() or "http"
    if proxy_type not in ALLOWED_PROXY_TYPES:
        return ""
    if not _valid_host(host) or not _valid_port(port):
        return ""
    username = str(settings.get("proxy_username", "")).strip()
    password = str(settings.get("proxy_password", "")).strip()
    auth = ""
    if username or password:
        auth = f"{quote(username, safe='')}:{quote(password, safe='')}@"
    return f"{proxy_type}://{auth}{host}:{port}"
