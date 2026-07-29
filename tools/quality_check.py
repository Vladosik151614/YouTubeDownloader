"""
Project quality gate.

Run before rebuilds and before preparing GitHub changes:
    python tools/quality_check.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MAX_LINES = 450
UI_MAX_LINES = 550
MAIN_WINDOW_TEMP_MAX_LINES = 900
MAX_FILE_BYTES = 45 * 1024

UI_MODULES = {
    "app/settings_page.py",
    "app/queue_widget.py",
    "app/localization.py",
}

TEMP_LINE_EXCEPTIONS = {
    "app/main_window.py": MAIN_WINDOW_TEMP_MAX_LINES,
}

FORBIDDEN_DIRS = [
    "build",
    "dist",
    "release",
    "__pycache__",
    "app/__pycache__",
    "tools/__pycache__",
]


def line_count(path: Path) -> int:
    return path.read_text(encoding="utf-8", errors="ignore").count("\n") + 1


def max_lines_for(rel: str) -> int:
    if rel in TEMP_LINE_EXCEPTIONS:
        return TEMP_LINE_EXCEPTIONS[rel]
    if rel in UI_MODULES:
        return UI_MAX_LINES
    return DEFAULT_MAX_LINES


def run_privacy_check() -> list[str]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "privacy_check.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode == 0:
        return []
    return ["privacy_check.py failed:", result.stdout.strip(), result.stderr.strip()]


def main() -> int:
    issues: list[str] = []

    for directory in FORBIDDEN_DIRS:
        if (ROOT / directory).exists():
            issues.append(f"Generated directory must be removed before publish: {directory}/")

    for path in sorted((ROOT / "app").rglob("*.py")) + sorted((ROOT / "tools").rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel == "tools/quality_check.py":
            continue
        lines = line_count(path)
        allowed = max_lines_for(rel)
        if lines > allowed:
            issues.append(f"{rel}: {lines} lines exceeds limit {allowed}")
        if path.stat().st_size > MAX_FILE_BYTES:
            kb = path.stat().st_size / 1024
            issues.append(f"{rel}: {kb:.1f} KB exceeds limit {MAX_FILE_BYTES / 1024:.0f} KB")

    issues.extend(run_privacy_check())

    if issues:
        print("Quality check failed:")
        for issue in issues:
            if issue:
                print(f"- {issue}")
        return 1

    print("Quality check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
