"""
Visible bug-fix report for release builds.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QToolButton, QVBoxLayout, QWidget

from app.settings_manager import APP_DATA_DIR


APP_VERSION = "0.1.2"
RELEASES = [
    {
        "version": "0.1.2",
        "date": "2026-07-29",
        "summary": "Spotify music engine, separate music folders and release report grouping.",
        "expanded": True,
        "fixes": [
            ("Критично", "#ff5a66", "Spotify engine", "Добавлен отдельный music-engine на базе spotDL: Spotify-ссылки больше не отправляются в yt-dlp, а обрабатываются отдельным аудио-пайплайном."),
            ("Серьёзно", "#f0b84a", "Spotify загрузки", "Поддержаны Spotify треки, альбомы и плейлисты через метаданные Spotify и поиск доступного аудиоисточника с сохранением музыки в MP3."),
            ("Серьёзно", "#f0b84a", "Аккаунты Spotify", "В раздел «Аккаунты» добавлен Spotify с отдельным Chrome-профилем. Вход остаётся необязательным и нужен только если сервис ограничивает доступ."),
            ("Средне", "#c78cff", "Папки по сервисам", "Spotify и SoundCloud автоматически сохраняются в отдельные музыкальные папки, а видео-сервисы остаются в своих видео-папках."),
            ("Средне", "#c78cff", "Предпросмотр Spotify", "Проверка ссылки распознаёт Spotify и показывает корректный тип контента без ошибки yt-dlp."),
            ("Средне", "#c78cff", "Иконка Spotify", "Добавлена сервисная иконка Spotify в едином размере для карточек аккаунтов и интерфейса."),
            ("Серьёзно", "#f0b84a", "Вкладка «Формат»", "Исправлены слишком узкие поля выбора качества, кадров, контейнера, кодека, энкодера и Spotify-музыки в настройках."),
            ("Серьёзно", "#f0b84a", "Меню разработчика", "Вкладки разработчика больше не режут описания: инструменты показаны отдельными читаемыми карточками без наложения текста."),
            ("Средне", "#c78cff", "Действия разработчика", "В меню разработчика добавлены реальные действия: открыть логи, сохранить support-отчёт, проверить папку, сеть, доступ и энкодеры."),
            ("Инфо", "#54c76d", "Owner GitHub Sync", "Для владельца добавлена синхронизация исходников owner/public без создания новой версии и без пересоздания GitHub Release."),
            ("Инфо", "#54c76d", "История исправлений", "Список исправлений теперь группируется по версиям: старые релизы можно свернуть и раскрыть стрелкой в стиле интерфейса."),
        ],
    },
    {
        "version": "0.1.1",
        "date": "2026-07-28",
        "summary": "Large playlists, action icons, themes, localization and installer workflow.",
        "expanded": False,
        "fixes": [
    ("Критично", "#ff5a66", "Большие плейлисты", "Плейлисты на десятки видео быстро читают список, показывают количество элементов и начинают загрузку без долгого зависания на подготовке."),
    ("Критично", "#ff5a66", "Раскрываемый плейлист", "В очереди появилась строка-папка плейлиста: её можно раскрыть и увидеть список видео, статусы и прогресс отдельных элементов."),
    ("Серьёзно", "#f0b84a", "Скачивание по кнопке", "Кнопка «Вставить ссылку» теперь только вставляет URL в поле, а запуск загрузки выполняет отдельная кнопка «Скачать»."),
    ("Серьёзно", "#f0b84a", "Отмена загрузки", "Отменённые элементы сразу получают статус «Отменено» и больше не превращаются в обычную ошибку после ответа загрузчика."),
    ("Серьёзно", "#f0b84a", "Смена кодека", "На главном экране появился выбор кодека: Оригинал, H.264, VP9 и AV1. Для плейлиста подтверждение задаётся один раз, для одиночного видео — отдельно."),
    ("Серьёзно", "#f0b84a", "Список видео", "Раскрытый список плейлиста получил более стабильный скролл и перерисовку, чтобы таблица не делилась визуально на части."),
    ("Серьёзно", "#f0b84a", "Кнопки действий", "Пауза, продолжить, отменить, повторить, открыть папку и детали больше не зависят от emoji-шрифтов Windows и рисуются самим приложением."),
    ("Серьёзно", "#f0b84a", "История", "Кнопки открытия папки и просмотра деталей в истории используют ту же стабильную систему иконок, что и очередь."),
    ("Средне", "#c78cff", "Обложки видео", "Очередь показывает миниатюры для одиночных видео, основной строки плейлиста и видео внутри раскрытого плейлиста, если сервис отдаёт thumbnail."),
    ("Средне", "#c78cff", "Единый размер картинок", "Миниатюры видео и плейлистов теперь вставляются в одинаковый фиксированный холст, поэтому строки очереди выглядят ровнее."),
    ("Серьёзно", "#f0b84a", "Темы оформления", "Оставлены три lux-темы и исправлены цвета вкладок, полей, текста и панелей, чтобы светлая и тёмные темы не смешивались между собой."),
    ("Средне", "#c78cff", "Настройки", "Горизонтальный скролл в настройках отключён, длинные строки переносятся, а кнопка сохранения больше не вылезает за область окна."),
    ("Средне", "#c78cff", "Языки", "Английский стал языком по умолчанию. В настройках доступны Русский, English, Deutsch и Italiano с улучшенными переводами основных экранов."),
    ("Средне", "#c78cff", "Плавность интерфейса", "Добавлен кэш тем и миниатюр очереди, чтобы повторные переключения и повторяющиеся обложки обрабатывались быстрее."),
    ("Средне", "#c78cff", "Меню разработчика", "В режим разработчика добавлены понятные рекомендации по диагностике: логи, сеть, доступ, кодеки, проверки ссылок и безопасный отчёт для поддержки."),
    ("Средне", "#c78cff", "Иконки сервисов", "Карточки YouTube, TikTok, Twitch и SoundCloud используют обновленные брендовые PNG-иконки с узнаваемыми цветами."),
    ("Средне", "#c78cff", "Диагностика", "В логах загрузки сохраняются название плейлиста, количество видео, целевая папка, формат, предупреждения и последние ошибки."),
    ("Инфо", "#54c76d", "Отчёт исправлений", "Эта страница показывает, что было исправлено, уровень важности и дату фикса внутри самого приложения."),
        ],
    },
]
OWNER_FIXES_FILE = Path(APP_DATA_DIR) / "owner_fix_reports.json"


def load_owner_fixes() -> list[tuple[str, str, str, str]]:
    try:
        data = json.loads(OWNER_FIXES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    fixes = []
    for item in data if isinstance(data, list) else []:
        fixes.append((
            str(item.get("severity", "Инфо")),
            str(item.get("color", "#54c76d")),
            str(item.get("title", "Owner note")),
            str(item.get("body", "")),
        ))
    return fixes


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

        subtitle = QLabel(f"Текущая версия {APP_VERSION} · отчёты сгруппированы по обновлениям")
        subtitle.setObjectName("subtle")
        layout.addWidget(subtitle)

        tested = QLabel("Контрольная проверка: Spotify engine, большие плейлисты, папки по сервисам и public/owner release workflow.")
        tested.setObjectName("subtle")
        tested.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        tested.setWordWrap(True)
        layout.addWidget(tested)

        legend = QHBoxLayout()
        legend.setSpacing(8)
        for label, color in [("Критично", "#ff5a66"), ("Серьёзно", "#f0b84a"), ("Средне", "#c78cff"), ("Инфо", "#54c76d")]:
            pill = QLabel(label)
            pill.setStyleSheet(
                f"background: {color}; color: #1b1b1b; border-radius: 10px; "
                "padding: 4px 9px; font-weight: 700; font-size: 11px;"
            )
            legend.addWidget(pill)
        legend.addStretch()
        layout.addLayout(legend)

        for release in RELEASES:
            layout.addWidget(self._release_block(release))
        owner_fixes = load_owner_fixes()
        if owner_fixes:
            layout.addWidget(self._release_block({
                "version": "Owner",
                "date": "local",
                "summary": "Private owner notes stored only on this computer.",
                "expanded": True,
                "fixes": owner_fixes,
            }))

        layout.addStretch()

    def _release_block(self, release: dict) -> QWidget:
        box = QFrame()
        box.setObjectName("tool_band")
        outer = QVBoxLayout(box)
        outer.setContentsMargins(12, 10, 12, 12)
        header = QHBoxLayout()
        toggle = QToolButton()
        toggle.setArrowType(Qt.ArrowType.DownArrow if release.get("expanded") else Qt.ArrowType.RightArrow)
        toggle.setStyleSheet("QToolButton { border: 0; color: #f0446b; padding: 3px; }")
        header.addWidget(toggle)
        title = QLabel(f"v{release['version']} · {release['date']}")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        header.addWidget(title)
        summary = QLabel(release.get("summary", ""))
        summary.setObjectName("subtle")
        header.addWidget(summary, 1)
        outer.addLayout(header)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 8, 0, 0)
        for severity, color, heading, text in release.get("fixes", []):
            body_layout.addWidget(self._fix_card(severity, color, heading, text))
        body.setVisible(bool(release.get("expanded")))
        toggle.clicked.connect(lambda: self._toggle_release(toggle, body))
        outer.addWidget(body)
        return box

    def _toggle_release(self, toggle: QToolButton, body: QWidget):
        visible = not body.isVisible()
        body.setVisible(visible)
        toggle.setArrowType(Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow)

    def _fix_card(self, severity: str, color: str, heading: str, body: str) -> QWidget:
        card = QFrame()
        card.setObjectName("subtle_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        top = QHBoxLayout()
        h = QLabel(heading)
        h.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        top.addWidget(h, 1)
        badge = QLabel(severity)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"background: {color}; color: #1b1b1b; border-radius: 9px; padding: 3px 8px; font-size: 11px; font-weight: 700;")
        top.addWidget(badge)
        card_layout.addLayout(top)
        text = QLabel(body)
        text.setObjectName("subtle")
        text.setWordWrap(True)
        card_layout.addWidget(text)
        return card
