"""
history_store.py - local download history stored outside the source tree.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from urllib.parse import urlparse

from app.settings_manager import APP_DATA_DIR


HISTORY_FILE = os.path.join(APP_DATA_DIR, "history.json")
MAX_HISTORY_ITEMS = 500


def _read_history() -> list[dict]:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def load_history(limit: int = 200) -> list[dict]:
    return _read_history()[:limit]


def add_history_entry(url: str, title: str, path: str, success: bool, error: str = "") -> None:
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    source = urlparse(url).netloc.lower().replace("www.", "") if url else ""
    entry = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source or "unknown",
        "title": title or url or "Без названия",
        "url": url or "",
        "path": path or "",
        "status": "success" if success else "error",
        "error": error or "",
    }
    history = [entry] + _read_history()
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[:MAX_HISTORY_ITEMS], f, ensure_ascii=False, indent=2)


def clear_history() -> None:
    try:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
    except Exception:
        pass
