"""
YouTube Downloader — точка входа
"""
import sys
import os
import ctypes
import traceback

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from app.binary_manager import (
    ensure_binaries_in_appdata,
    get_resource_path,
    prepare_runtime_path,
)

prepare_runtime_path()
ensure_binaries_in_appdata()

def set_windows_app_id():
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Vlad.YouTubeDownloader.Desktop"
        )
    except Exception:
        pass

from app.main_window import MainWindow

def main():
    if "--spotdl-child" in sys.argv:
        sys.argv.remove("--spotdl-child")
        try:
            from spotdl.console.entry_point import console_entry_point
            console_entry_point()
        except SystemExit:
            raise
        except Exception:
            log_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "YouTubeDownloader", "logs")
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, "spotdl_child_error.log"), "w", encoding="utf-8") as file:
                file.write(traceback.format_exc())
            sys.exit(1)
        return

    if "--browser" in sys.argv or "--web" in sys.argv:
        from app.web_server import run_browser_server
        run_browser_server(open_browser=False)
        return

    set_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName("YouTube Downloader")
    app.setApplicationVersion("0.1.2")
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    icon_path = get_resource_path("youtube.ico")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
