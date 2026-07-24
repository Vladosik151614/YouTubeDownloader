"""
binary_manager.py — менеджер путей к ffmpeg, ffprobe, deno и yt-dlp
обеспечивает быстрый запуск приложения и поддержку переносной/системной конфигурации
"""
import os
import sys
import shutil

APP_NAME = "YouTubeDownloader"
LOCAL_APP_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), APP_NAME)
LOCAL_APP_DATA_BIN = os.path.join(LOCAL_APP_DATA_DIR, "bin")
STACHER_DIR = os.path.join(os.path.expanduser("~"), ".stacher")

os.makedirs(LOCAL_APP_DATA_BIN, exist_ok=True)

def get_base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_resource_base_dir() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return get_base_dir()

def get_resource_path(relative_path: str) -> str:
    return os.path.join(get_resource_base_dir(), relative_path)

def _candidate_binary_paths(executable_name: str) -> list[str]:
    return [
        os.path.join(get_resource_base_dir(), "bin", executable_name),
        os.path.join(get_base_dir(), "bin", executable_name),
        os.path.join(LOCAL_APP_DATA_BIN, executable_name),
        os.path.join(STACHER_DIR, executable_name),
    ]

def get_binary_path(name: str) -> str:
    """
    Ищет бинарный файл (ffmpeg, ffprobe, yt-dlp) в следующем порядке:
    1. В ресурсах PyInstaller / рядом со скриптом в папочке bin/
    2. В %LOCALAPPDATA%\\YouTubeDownloader\\bin\\
    3. В папке Stacher (%USERPROFILE%\\.stacher)
    4. В системном PATH
    """
    executable_name = name + ".exe" if os.name == "nt" and not name.endswith(".exe") else name
    
    for candidate in _candidate_binary_paths(executable_name):
        if os.path.isfile(candidate):
            return candidate

    system_path = shutil.which(name)
    if system_path:
        return system_path
        
    return executable_name

def prepare_runtime_path() -> None:
    dirs = [
        os.path.join(get_resource_base_dir(), "bin"),
        os.path.join(get_base_dir(), "bin"),
        LOCAL_APP_DATA_BIN,
        STACHER_DIR,
    ]
    existing_dirs = [d for d in dirs if os.path.isdir(d)]
    if existing_dirs:
        current_path = os.environ.get("PATH", "")
        os.environ["PATH"] = os.pathsep.join(existing_dirs + [current_path])

def ensure_binaries_in_appdata():
    """
    Если бинарники есть рядом с exe, мы можем закешировать их в AppData
    или использовать из локальной папки.
    """
    for bin_name in ["ffmpeg.exe", "ffprobe.exe", "deno.exe", "yt-dlp.exe"]:
        local_file = os.path.join(get_resource_base_dir(), "bin", bin_name)
        if not os.path.isfile(local_file):
            local_file = os.path.join(get_base_dir(), "bin", bin_name)
        target_file = os.path.join(LOCAL_APP_DATA_BIN, bin_name)
        if os.path.isfile(local_file) and not os.path.isfile(target_file):
            try:
                shutil.copy2(local_file, target_file)
            except Exception:
                pass
