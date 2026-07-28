"""
Visible bug-fix report for release builds.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget


APP_VERSION = "0.1.1"
FIX_DATE = "2026-07-28"
FIXES = [
    ("Action buttons", "Pause, resume, cancel, retry, open-folder and details buttons no longer use emoji glyphs. They are painted by the app and stay visible on Windows."),
    ("History actions", "History open-folder and details buttons now use the same stable icon system as the download queue."),
    ("Service icons", "YouTube, TikTok, Twitch and SoundCloud cards use refreshed brand-style PNG icons with official colors."),
    ("Large playlists", "Playlist downloads now keep detailed warnings for skipped items and treat the playlist as successful when valid files were saved."),
    ("Playlist startup", "Large playlist loading no longer resolves every video format before starting. The app reads the playlist list quickly, shows the count, then starts downloading."),
    ("Diagnostics", "Download logs now include playlist title, item count, target folder, selected format and warning/error counts."),
    ("Release reporting", "The app includes this bug-fix report, and the same fixes are documented in GitHub release notes and changelog."),
]


class FixReportPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(scroll)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(12)
        scroll.setWidget(page)

        title = QLabel("Отчёт исправлений")
        title.setObjectName("section_title")
        title.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        layout.addWidget(title)

        subtitle = QLabel(f"Версия {APP_VERSION} · дата фикса: {FIX_DATE}")
        subtitle.setObjectName("subtle")
        layout.addWidget(subtitle)

        tested = QLabel("Контрольная проверка: большой YouTube-плейлист, переданный пользователем 2026-07-28.")
        tested.setObjectName("subtle")
        tested.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        tested.setWordWrap(True)
        layout.addWidget(tested)

        for heading, body in FIXES:
            card = QFrame()
            card.setObjectName("tool_band")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(5)
            h = QLabel(heading)
            h.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            card_layout.addWidget(h)
            text = QLabel(body)
            text.setObjectName("subtle")
            text.setWordWrap(True)
            card_layout.addWidget(text)
            layout.addWidget(card)

        layout.addStretch()
