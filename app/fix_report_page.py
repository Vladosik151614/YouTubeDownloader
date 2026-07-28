"""
Visible bug-fix report for release builds.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from app.settings_manager import APP_DATA_DIR


APP_VERSION = "0.1.1"
FIX_DATE = "2026-07-28"
FIXES = [
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

        subtitle = QLabel(f"Версия {APP_VERSION} · дата фикса: {FIX_DATE}")
        subtitle.setObjectName("subtle")
        layout.addWidget(subtitle)

        tested = QLabel("Контрольная проверка: большой YouTube-плейлист, переданный пользователем 2026-07-28.")
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

        for severity, color, heading, body in FIXES + load_owner_fixes():
            card = QFrame()
            card.setObjectName("tool_band")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(7)
            top = QHBoxLayout()
            h = QLabel(heading)
            h.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            top.addWidget(h, 1)
            badge = QLabel(severity)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"background: {color}; color: #1b1b1b; border-radius: 9px; "
                "padding: 3px 8px; font-size: 11px; font-weight: 700;"
            )
            top.addWidget(badge)
            card_layout.addLayout(top)
            text = QLabel(body)
            text.setObjectName("subtle")
            text.setWordWrap(True)
            card_layout.addWidget(text)
            layout.addWidget(card)

        layout.addStretch()
