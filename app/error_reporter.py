"""
error_reporter.py - sanitized support reports for users and GitHub issues.
"""
from __future__ import annotations

import os
import platform
import re
from urllib.parse import quote, urlparse

APP_VERSION = "0.1.2"
GITHUB_NEW_ISSUE_URL = "https://github.com/Vladosik151614/YouTubeDownloader/issues/new"


def sanitize_text(value: str) -> str:
    home = os.path.expanduser("~").replace("\\", "/")
    text = str(value or "").replace("\\", "/")
    text = text.replace(home, "%USERPROFILE%")
    text = re.sub(r"(?i)(password|passwd|token|secret|cookie|api[_-]?key)=\\S+", r"\\1=<redacted>", text)
    text = re.sub(r"(?i)(password|passwd|token|secret|cookie|api[_-]?key)['\"]?\\s*[:=]\\s*['\"][^'\"]+['\"]", r"\\1=<redacted>", text)
    text = re.sub(r"C:/Users/[^/\\s\"']+", "%USERPROFILE%", text)
    return text


def safe_url_summary(url: str) -> str:
    parsed = urlparse(url or "")
    if not parsed.netloc:
        return "unknown"
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.split('/')[0] if parsed.path else ''}"


def build_support_report(
    *,
    service: str,
    url: str,
    error_category: str,
    user_message: str,
    settings: dict,
    raw_error: str = "",
    developer_mode: bool = False,
) -> str:
    lines = [
        f"App version: {APP_VERSION}",
        f"OS: {platform.platform()}",
        f"Service: {service or 'unknown'}",
        f"URL summary: {safe_url_summary(url)}",
        f"Error category: {error_category or 'unknown'}",
        f"Message: {sanitize_text(user_message)}",
        "Download profile:",
        f"- type: {settings.get('download_type', 'video')}",
        f"- quality: {settings.get('download_quality', '1080')}",
        f"- fps: {settings.get('fps_limit', '60')}",
        f"- container: {settings.get('container', 'mp4')}",
        f"- codec: {settings.get('default_codec', 'h264')}",
        f"- proxy enabled: {bool(settings.get('proxy_enabled', False))}",
        f"- auto access refresh: {bool(settings.get('auto_export_cookies', True))}",
    ]
    if developer_mode and raw_error:
        lines.extend(["Raw error:", sanitize_text(raw_error)[-2000:]])
    return "\n".join(lines)


def github_issue_url(report: str, title: str = "Download Error") -> str:
    if not GITHUB_NEW_ISSUE_URL:
        return ""
    return f"{GITHUB_NEW_ISSUE_URL}?template=download_error.yml&title={quote(title)}&body={quote(report)}"
