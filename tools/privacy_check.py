"""
Local pre-publish safety check.

Fails when source files contain common secrets, local absolute paths,
cookies, or generated build artifacts that should not be pushed to GitHub.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXCLUDED_DIRS = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "release",
    "venv",
    ".venv",
}

EXCLUDED_SUFFIXES = {
    ".dll",
    ".exe",
    ".ico",
    ".jpg",
    ".jpeg",
    ".png",
    ".pyc",
    ".zip",
}

BLOCKED_FILE_NAMES = {
    ".env",
    "cookies.txt",
    "settings.json",
}

PATTERNS = [
    ("Windows user path", re.compile(r"C:\\Users\\[^\\\s\"']+", re.IGNORECASE)),
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}\b")),
    ("Generic secret assignment", re.compile(r"(?i)\b(secret|password|passwd|token|api[_-]?key|client_secret)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]")),
    ("Concrete YouTube test URL", re.compile(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+", re.IGNORECASE)),
]

ALLOWLIST_SNIPPETS = [
    "https://www.youtube.com/watch?v=... или playlist...",
    "youtube.com/watch?v=...",
]


def should_skip(path: Path) -> bool:
    rel_parts = set(path.relative_to(ROOT).parts)
    if rel_parts & EXCLUDED_DIRS:
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    if path.name.lower() in BLOCKED_FILE_NAMES:
        return False
    return False


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def main() -> int:
    issues: list[str] = []

    for blocked_dir in ("build", "dist", "release", "__pycache__"):
        if (ROOT / blocked_dir).exists():
            issues.append(f"Generated directory exists: {blocked_dir}/")

    for path in ROOT.rglob("*"):
        if not path.is_file() or should_skip(path):
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel == "tools/privacy_check.py":
            continue
        if path.name.lower() in BLOCKED_FILE_NAMES:
            issues.append(f"Blocked local/config file present: {rel}")
            continue
        text = read_text(path)
        for label, pattern in PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(0)
                if any(snippet in value for snippet in ALLOWLIST_SNIPPETS):
                    continue
                issues.append(f"{label}: {rel}:{text[:match.start()].count(chr(10)) + 1}")

    if issues:
        print("Privacy check failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("Privacy check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
