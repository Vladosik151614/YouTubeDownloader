"""Allowlisted release input: never export local runtimes, media or diagnostics."""
from pathlib import Path
import subprocess

SOURCE_DIRS = {"app", "tools", "tests", "docs", "installer", ".github", "bin"}
SOURCE_SUFFIXES = {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".iss", ".bat", ".ps1", ".spec", ".ico", ".png", ".svg"}
TOP_FILES = {".gitignore", "LICENSE", "main.py", "requirements.txt", "youtube.ico", "YouTubeDownloader.spec", "YouTube_Downloader_Specification.txt", "build.bat", "check_privacy.bat", "check_quality.bat", "run.bat", "setup.bat"}


def release_files(root):
    root = Path(root).resolve()
    if (root / '.git').exists():
        result = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=root, capture_output=True, check=True)
        paths = [root / name for name in result.stdout.decode('utf-8').split('\0') if name]
    else:
        paths = root.rglob('*')
    for path in sorted(set(paths)):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part.startswith(('.local-', '.spotify-', '__pycache__')) or part in {'.git', '.venv', 'logs', 'auth', 'owner_diagnostics'} for part in rel.parts):
            continue
        if path.name in {'settings.json', 'cookies.txt', '.env'} or 'cookies' in path.name.lower():
            continue
        if rel.parts[0] not in SOURCE_DIRS and not (len(rel.parts) == 1 and (path.name in TOP_FILES or path.suffix == '.md')):
            continue
        if path.suffix.lower() not in SOURCE_SUFFIXES and path.name not in TOP_FILES:
            continue
        if rel.as_posix() == 'docs/tiktok_hd_sound_2026-11-17.md':
            continue
        yield path
