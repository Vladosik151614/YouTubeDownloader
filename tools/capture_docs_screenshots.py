"""
Capture clean, annotated screenshots for the user guide.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QLabel

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "screenshots"
sys.path.insert(0, str(ROOT))


def _rect_for(window, widget, pad=6) -> QRect:
    top_left = widget.mapTo(window, QPoint(0, 0))
    rect = QRect(top_left, widget.size())
    return rect.adjusted(-pad, -pad, pad, pad)


def _draw_labels(path: Path, labels: list[tuple[QRect, str]]) -> None:
    image = path
    pixmap = window.grab()
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#ff4d6d"), 4)
    painter.setPen(pen)
    font = QFont("Segoe UI", 11, QFont.Weight.Bold)
    painter.setFont(font)
    for index, (rect, _text) in enumerate(labels, start=1):
        painter.drawRoundedRect(rect, 8, 8)
        badge = QRect(rect.left(), max(0, rect.top() - 30), 28, 24)
        painter.fillRect(badge, QColor("#ff4d6d"))
        painter.setPen(QColor("#ffffff"))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, str(index))
        painter.setPen(QColor("#ff4d6d"))
    painter.end()
    pixmap.save(str(image), "PNG")


def capture(name: str, labels: list[tuple[QRect, str]]) -> None:
    path = OUT / name
    _draw_labels(path, labels)
    print(path)


def prepare_window():
    window.resize(1280, 760)
    window.settings["download_folder"] = "C:/Downloads/YouTubeDownloader"
    window.folder_display.setText("C:/Downloads/YouTubeDownloader")
    window.url_edit.setText("https://example.com/video")
    window._update_disk_space()
    window.showMaximized()
    app.processEvents()


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    prepare_window()

    window._switch_page(0)
    item_id = "demo"
    window.queue_widget.add_item(item_id, "https://example.com/video")
    window.queue_widget.update_info(item_id, "Sample video title", "125 MB")
    window.queue_widget.update_status(item_id, "Загрузка...")
    window.queue_widget.update_progress(item_id, 42, "8.5 MB/s", "00:40")
    app.processEvents()
    capture(
        "01-download-annotated.png",
        [
            (_rect_for(window, window.url_edit), "Paste link"),
            (_rect_for(window, window.quick_quality_combo), "Choose quality"),
            (_rect_for(window, window.queue_widget), "Track queue"),
            (_rect_for(window, window.folder_display), "Save folder"),
        ],
    )

    window._switch_page(1)
    app.processEvents()
    capture(
        "02-settings-general-annotated.png",
        [
            (_rect_for(window, window.settings_page.tabs), "Settings categories"),
            (_rect_for(window, window.settings_page.language_combo), "Language"),
            (_rect_for(window, window.settings_page.folder_edit), "Default folder"),
        ],
    )

    window.settings_page.tabs.setCurrentIndex(1)
    app.processEvents()
    capture(
        "03-format-annotated.png",
        [
            (_rect_for(window, window.settings_page.quality_combo), "Resolution"),
            (_rect_for(window, window.settings_page.fps_combo), "FPS"),
            (_rect_for(window, window.settings_page.encoder_combo), "Encoder"),
            (_rect_for(window, window.settings_page.auto_convert_sw), "H.264 conversion"),
        ],
    )

    window.settings_page.tabs.setCurrentIndex(3)
    app.processEvents()
    capture(
        "04-connection-annotated.png",
        [
            (_rect_for(window, window.settings_page.concurrent_combo), "Concurrent downloads"),
            (_rect_for(window, window.settings_page.speed_status_label), "Speed check"),
            (_rect_for(window, window.settings_page.proxy_host_edit), "Proxy server"),
        ],
    )

    window.settings_page.tabs.setCurrentIndex(2)
    app.processEvents()
    capture(
        "05-playlists-annotated.png",
        [
            (_rect_for(window, window.settings_page.playlist_subfolders_sw), "Subfolders"),
            (_rect_for(window, window.settings_page.playlist_numbering_sw), "Numbering"),
            (_rect_for(window, window.settings_page.skip_duplicates_sw), "Duplicate archive"),
            (_rect_for(window, window.settings_page.embed_subtitles_sw), "Subtitles"),
        ],
    )

    window.settings_page.tabs.setCurrentIndex(4)
    app.processEvents()
    capture(
        "06-notifications-annotated.png",
        [
            (_rect_for(window, window.settings_page.notify_download_sw), "Download alerts"),
            (_rect_for(window, window.settings_page.confirm_exit_sw), "Exit confirmation"),
            (_rect_for(window, window.settings_page.play_sound_sw), "Sound"),
        ],
    )

    window.settings_page.tabs.setCurrentIndex(5)
    app.processEvents()
    capture(
        "07-access-settings-annotated.png",
        [
            (_rect_for(window, window.settings_page.auto_export_cookies_sw), "Automatic access"),
            (_rect_for(window, window.settings_page.browser_combo), "Manual browser"),
            (_rect_for(window, window.settings_page.cookies_file_edit), "Manual file"),
        ],
    )

    window._switch_page(3)
    app.processEvents()
    cards = window.accounts_page.findChildren(QLabel)
    capture(
        "08-accounts-annotated.png",
        [
            (_rect_for(window, window.accounts_page), "Optional sign-in"),
            (_rect_for(window, cards[3] if len(cards) > 3 else window.accounts_page), "Service access"),
        ],
    )

    window._switch_page(2)
    app.processEvents()
    capture(
        "09-history-annotated.png",
        [
            (_rect_for(window, window.history_page.table), "Download history"),
        ],
    )

    window.close()
    app.quit()


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    os.environ["YTD_PUBLIC_DOCS_MODE"] = "1"
    from app.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    QTimer.singleShot(0, run)
    sys.exit(app.exec())
