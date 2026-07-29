"""
settings_developer.py - developer-mode settings section.
"""

from PySide6.QtWidgets import QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget

from app.developer_advice import developer_advice_label
from app.toggle_switch import ToggleSwitch


def _note(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("subtle")
    label.setWordWrap(True)
    return label


def _simple_page(owner, rows: list[tuple[str, str]]) -> QWidget:
    page, layout = owner._page()
    group = QGroupBox("Инструменты")
    group_layout = QVBoxLayout(group)
    group_layout.setContentsMargins(14, 18, 14, 14)
    group_layout.setSpacing(10)
    for name, value in rows:
        card = QFrame()
        card.setObjectName("developer_tool_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 9, 12, 10)
        card_layout.setSpacing(4)
        title = QLabel(name)
        title.setObjectName("developer_tool_title")
        title.setWordWrap(True)
        description = _note(value)
        card_layout.addWidget(title)
        card_layout.addWidget(description)
        group_layout.addWidget(card)
    layout.addWidget(group)
    layout.addStretch()
    return page


def _action_page(owner, rows: list[tuple[str, str, str]]) -> QWidget:
    page, layout = owner._page()
    group = QGroupBox("Инструменты")
    group_layout = QVBoxLayout(group)
    group_layout.setContentsMargins(14, 18, 14, 14)
    group_layout.setSpacing(10)
    for title_text, description_text, method_name in rows:
        card = QFrame()
        card.setObjectName("developer_tool_card")
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 9, 12, 10)
        text_col = QVBoxLayout()
        title = QLabel(title_text)
        title.setObjectName("developer_tool_title")
        title.setWordWrap(True)
        text_col.addWidget(title)
        text_col.addWidget(_note(description_text))
        button = QPushButton("Выполнить")
        button.setMinimumWidth(118)
        button.clicked.connect(getattr(owner, method_name))
        row.addLayout(text_col, 1)
        row.addWidget(button)
        group_layout.addWidget(card)
    layout.addWidget(group)
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
    tabs.setUsesScrollButtons(False)
    panel_layout.addWidget(tabs)

    diag_page, diag_layout = owner._page()
    form = owner._group("Диагностика", diag_layout)
    owner._switch(form, "download_stats_sw", "Отправлять статистику скачиваний")
    owner._switch(form, "show_download_tools_sw", "Показывать инструменты обработки")
    diag_layout.addWidget(developer_advice_label())
    tabs.addTab(diag_page, "Диагностика")

    tabs.addTab(_action_page(owner, [
        ("Последний лог", "Показать последние события загрузки, обработки и доступа.", "_developer_show_latest_log"),
        ("Открыть папку логов", "Открыть локальную папку логов приложения.", "_developer_open_logs"),
        ("Скопировать отчёт", "Скопировать безопасный отчёт без cookies, токенов и паролей.", "_developer_copy_support_report"),
    ]), "Логи")

    tabs.addTab(_action_page(owner, [
        ("Проверка скорости", "Подобрать параллельные загрузки под текущий интернет.", "_run_speed_test"),
        ("Прокси", "Открыть вкладку соединения, где настраиваются тип, сервер, порт и пароль.", "_developer_open_connection_tab"),
        ("Обновить доступ", "Открыть вкладку доступа для cookies/browser-профиля.", "_developer_open_access_tab"),
    ]), "Сеть")

    tabs.addTab(_action_page(owner, [
        ("Браузер", "Открыть настройки доступа к сайтам, где может потребоваться вход.", "_developer_open_access_tab"),
        ("Файл доступа", "Выбрать cookies/access TXT только для ручного режима.", "_browse_cookies"),
        ("Support TXT", "Сохранить безопасный TXT-отчёт для отправки разработчику.", "_developer_save_support_report"),
    ]), "Доступ")

    tabs.addTab(_action_page(owner, [
        ("Кодеки", "Обновить список доступных GPU/CPU энкодеров.", "_developer_refresh_encoders"),
        ("Формат", "Открыть вкладку форматов и кодеков.", "_developer_open_format_tab"),
        ("Система загрузки", "Проверить обновление системы загрузки.", "_run_update"),
    ]), "Видео")

    tabs.addTab(_action_page(owner, [
        ("Папка загрузки", "Открыть текущую папку загрузки.", "_developer_open_download_folder"),
        ("Права записи", "Проверить, что приложение может писать в выбранную папку.", "_developer_check_write_access"),
        ("Локальные данные", "Открыть папку AppData приложения.", "_developer_open_app_data"),
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

    tabs.addTab(_action_page(owner, [
        ("Создать отчёт", "Собрать версию приложения, Windows, настройки без личных данных и последние ошибки.", "_developer_show_support_report"),
        ("Скопировать", "Скопировать текст для отправки разработчику.", "_developer_copy_support_report"),
        ("Сохранить TXT", "Создать файл отчёта, который пользователь сам отправляет в поддержку.", "_developer_save_support_report"),
    ]), "Support-пакет")

    layout.addWidget(owner.developer_panel)
    layout.addStretch()
    return page
