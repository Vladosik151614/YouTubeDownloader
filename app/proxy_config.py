"""
proxy_config.py - normalized proxy settings for network calls.
"""


def proxy_url_from_settings(settings: dict) -> str:
    if not settings.get("proxy_enabled", False):
        return ""

    legacy = str(settings.get("proxy_url", "")).strip()
    if legacy:
        return legacy

    host = str(settings.get("proxy_host", "")).strip()
    port = str(settings.get("proxy_port", "")).strip()
    if not host or not port:
        return ""

    proxy_type = str(settings.get("proxy_type", "http")).strip().lower() or "http"
    username = str(settings.get("proxy_username", "")).strip()
    password = str(settings.get("proxy_password", "")).strip()
    auth = f"{username}:{password}@" if username or password else ""
    return f"{proxy_type}://{auth}{host}:{port}"
