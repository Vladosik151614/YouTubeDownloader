"""
settings_developer.py - developer-mode settings section.
"""

from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget

from app.developer_advice import developer_advice_label
from app.toggle_switch import ToggleSwitch


def _note(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("subtle")
    label.setWordWrap(True)
    return label


def _simple_page(owner, rows: list[tuple[str, str]]) -> QWidget:
    page, layout = owner._page()
    form = owner._group("Инструменты", layout)
    for name, value in rows:
        form.addRow(name, _note(value))
    layout.addStretch()
    return page


def build_developer_tab(owner) -> QWidget:
    page, layout = owner._page()
    intro = QGroupBox("Режим разработчика")
    intro_row = QHBoxLayout(intro)
    owner.developer_mode_sw = ToggleSwitch()
    owner.developer_mode_sw.toggled.connect(owner._set_developer_panel_visible)
    text = QLabel("Показывать расширенную диагностику, логи и технические параметры")
    text.setWordWrap(True)
    intro_row.addWidget(owner.developer_mode_sw)
    intro_row.addWidget(text, 1)
    layout.addWidget(intro)

    owner.developer_panel = QWidget()
    panel_layout = QVBoxLayout(owner.developer_panel)
    panel_layout.setContentsMargins(0, 0, 0, 0)
    panel_layout.setSpacing(10)
    tabs = QTabWidget()
    panel_layout.addWidget(tabs)

    diag_page, diag_layout = owner._page()
    form = owner._group("Диагностика", diag_layout)
    owner._switch(form, "download_stats_sw", "Отправлять статистику скачиваний")
    owner._switch(form, "show_download_tools_sw", "Показывать инструменты обработки")
    diag_layout.addWidget(developer_advice_label())
    tabs.addTab(diag_page, "Диагностика")

    tabs.addTab(_simple_page(owner, [
        ("Последний лог:", "Показывать последние события загрузки, обработки и доступа."),
        ("Последние ошибки:", "Показывать понятную ошибку и техническую строку отдельно."),
        ("Экспорт:", "Сохранять безопасный TXT-отчёт без cookies, токенов и паролей."),
    ]), "Логи")

    tabs.addTab(_simple_page(owner, [
        ("Проверка скорости:", "Подбор параллельных загрузок под интернет пользователя."),
        ("Прокси:", "Подробные поля находятся в разделе Соединение."),
        ("Повторы:", "Настройки повторов и таймаутов для нестабильной сети."),
    ]), "Сеть")

    tabs.addTab(_simple_page(owner, [
        ("Браузер:", "Диагностика доступа к сайтам, где может потребоваться вход."),
        ("Файл доступа:", "Ручной режим только если автоматический доступ не подходит."),
        ("Профиль:", "Пересоздание временного профиля доступа без показа внутренних путей."),
    ]), "Доступ")

    tabs.addTab(_simple_page(owner, [
        ("Кодеки:", "Проверка H.264, VP9, AV1 и доступных энкодеров."),
        ("GPU/CPU:", "Тест видеокарты, CPU-режима и FFmpeg."),
        ("Конвертация:", "Пробная обработка маленького файла перед большой очередью."),
    ]), "Видео")

    tabs.addTab(_simple_page(owner, [
        ("Место:", "Проверка свободного места перед большими плейлистами."),
        ("Права:", "Проверка доступа на запись в выбранную папку."),
        ("Временные файлы:", "Открытие и очистка временных файлов приложения."),
    ]), "Файлы")

    system_page, system_layout = owner._page()
    form = owner._group("Эксперименты", system_layout)
    owner._switch(form, "auto_update_engine_sw", "Автоматически проверять обновления системы загрузки")
    owner.github_repo_edit = QLineEdit()
    owner.github_repo_edit.setPlaceholderText("owner/repository")
    form.addRow("GitHub Releases:", owner.github_repo_edit)
    owner.github_asset_edit = QLineEdit()
    owner.github_asset_edit.setPlaceholderText("YouTubeDownloaderSetup")
    form.addRow("Файл релиза:", owner.github_asset_edit)
    update_group = QGroupBox("Система загрузки")
    row = QHBoxLayout(update_group)
    owner.update_status_label = _note("Система загрузки готова к работе.")
    owner.update_btn = QPushButton("Обновить")
    owner.update_btn.clicked.connect(owner._run_update)
    row.addWidget(owner.update_status_label, 1)
    row.addWidget(owner.update_btn)
    system_layout.addWidget(update_group)
    tabs.addTab(system_page, "Эксперименты")

    tabs.addTab(_simple_page(owner, [
        ("Создать отчёт:", "Собирает версию приложения, Windows, настройки без личных данных и последние ошибки."),
        ("Скопировать:", "Копирует текст для отправки разработчику."),
        ("Сохранить TXT:", "Создаёт файл отчёта, который пользователь сам отправляет в поддержку."),
    ]), "Support-пакет")

    layout.addWidget(owner.developer_panel)
    layout.addStretch()
    return page
