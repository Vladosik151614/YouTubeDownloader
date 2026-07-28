"""
developer_advice.py - client-safe developer mode recommendations.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


def developer_advice_text() -> str:
    return (
        "Что полезно держать в меню разработчика:\n"
        "1. Подробные логи загрузки, обработки, сети и доступа.\n"
        "2. Экспорт безопасного отчёта для поддержки без cookies, токенов и личных путей.\n"
        "3. Проверка скорости интернета и рекомендации по параллельным загрузкам.\n"
        "4. Диагностика браузерного доступа: нужен ли вход, какой сайт запросил доступ.\n"
        "5. Проверка версии системы загрузки и ручной запуск обновления.\n"
        "6. Просмотр последней ошибки простым текстом и техническим текстом отдельно.\n"
        "7. Тест кодеков, видеокарты, FFmpeg и доступных энкодеров.\n"
        "8. Пробная проверка ссылки без скачивания: тип, качество, FPS, субтитры.\n"
        "9. Настройки повторов, таймаутов и лимитов сети для нестабильного интернета.\n"
        "10. Кнопка создать support-пакет, который пользователь сам отправляет разработчику."
    )


def developer_advice_label() -> QLabel:
    label = QLabel(developer_advice_text())
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setObjectName("subtle")
    return label
