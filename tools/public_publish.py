"""
Create and push a sanitized public repository snapshot.

The public snapshot removes owner-only source files and disables owner UI imports
before pushing to the public GitHub repository.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_REPO = "https://github.com/Vladosik151614/YouTubeDownloader.git"
SKIP_DIRS = {".git", "build", "dist", "release", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SKIP_NAMES = {"owner_tools.py", "owner_diagnostics.py", "owner_release_publish.py", "settings.json", "cookies.txt"}
SKIP_SUFFIXES = {".pyc", ".log", ".tmp", ".bak", ".exe", ".dll", ".zip"}


def run(command: list[str], cwd: Path, timeout: int = 180) -> None:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    if output:
        print(output[-5000:])
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(command)}")


def remove_tree(path: Path) -> None:
    def onexc(func, item, exc):
        try:
            os.chmod(item, 0o700)
            func(item)
        except Exception:
            raise exc
    shutil.rmtree(path, onexc=onexc)


def should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if set(rel.parts) & SKIP_DIRS:
        return True
    return path.name in SKIP_NAMES or path.suffix.lower() in SKIP_SUFFIXES


def copy_public_tree(target: Path) -> None:
    for path in ROOT.rglob("*"):
        if not path.is_file() or should_skip(path):
            continue
        rel = path.relative_to(ROOT)
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)


def clear_worktree(target: Path) -> None:
    for path in target.iterdir():
        if path.name == ".git":
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def patch_owner_imports(target: Path) -> None:
    main_window = target / "app" / "main_window.py"
    text = main_window.read_text(encoding="utf-8")
    text = text.replace(
        "from app.owner_tools import OwnerToolsPage, owner_tools_available\n",
        "def owner_tools_available():\n    return False\n\nOwnerToolsPage = None\n",
    )
    main_window.write_text(text, encoding="utf-8")

    readme = target / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        start = text.find("The GitHub push panel is hidden for normal users.")
        if start != -1:
            end = text.find("\n\n", start)
            text = text[:start] + text[end + 2 if end != -1 else len(text):]
        readme.write_text(text, encoding="utf-8")


def main() -> int:
    message = " ".join(sys.argv[1:]).strip() or "Update public release"
    run([sys.executable, "tools\\privacy_check.py"], ROOT)
    run([sys.executable, "tools\\quality_check.py"], ROOT)
    target = Path(tempfile.gettempdir()) / "YouTubeDownloader-public-export"
    if target.exists():
        remove_tree(target)
    run(["git", "clone", PUBLIC_REPO, str(target)], ROOT, timeout=240)
    clear_worktree(target)
    copy_public_tree(target)
    patch_owner_imports(target)
    run([sys.executable, "tools\\privacy_check.py"], target)
    run(["git", "add", "-A"], target)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=target, text=True, capture_output=True)
    if status.stdout.strip():
        run(["git", "commit", "-m", message], target)
        run(["git", "push", "origin", "main"], target, timeout=240)
    else:
        print("Public repository already matches sanitized source.")
    print("Public repository updated without owner-only tools.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
