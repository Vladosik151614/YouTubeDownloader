"""
settings_page.py - categorized settings with capsule switches.
"""
import os
import sys
import winreg

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QComboBox, QTabWidget, QVBoxLayout, QWidget,
)

from app.converter import available_encoders
from app.settings_developer_actions import install_developer_actions
from app.settings_developer import build_developer_tab
from app.settings_manager import save_settings
from app.speed_test import SpeedTestWorker
from app.toggle_switch import ToggleSwitch
from app.updater import AppUpdateWorker, UpdateWorker


THEME_OPTIONS = (("lux_graphite", "Люкс графит"), ("lux_midnight", "Люкс ночная"), ("lux_silver", "Люкс светлая"))
THEME_INDEX = {key: index for index, (key, _) in enumerate(THEME_OPTIONS)}
THEME_BY_INDEX = {index: key for index, (key, _) in enumerate(THEME_OPTIONS)}


def _combo(values: list[str], width: int = 260) -> QComboBox:
    combo = QComboBox()
    combo.addItems(values)
    combo.setMinimumWidth(width)
    combo.setFixedHeight(36)
    return combo


def _apply_startup(enabled: bool):
    if os.name != "nt":
        return
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
            winreg.SetValueEx(key, "YouTubeDownloader", 0, winreg.REG_SZ, f'"{exe}"')
        else:
            try:
                winreg.DeleteValue(key, "YouTubeDownloader")
            except FileNotFoundError:
                pass


class SettingsPage(QWidget):
    settings_changed = Signal(dict)

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = dict(settings)
        self._update_worker = None
        self._app_update_worker = None
        self._speed_worker = None
        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(12)

        title = QLabel("Настройки")
        title.setObjectName("section_title")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(False)
        self.tabs.addTab(self._general_tab(), "Основные")
        self.tabs.addTab(self._format_tab(), "Формат")
        self.tabs.addTab(self._playlist_tab(), "Плейлисты")
        self.tabs.addTab(self._connection_tab(), "Соединение")
        self.tabs.addTab(self._notifications_tab(), "Уведомления")
        self.tabs.addTab(self._access_tab(), "Доступ")
        self.tabs.addTab(self._developer_tab(), "Разработчик")
        layout.addWidget(self.tabs, 1)

        row = QHBoxLayout()
        row.addStretch()
        save_btn = QPushButton("Сохранить")
        save_btn.setObjectName("primary_btn")
        save_btn.setMaximumWidth(150)
        save_btn.clicked.connect(self._save)
        row.addWidget(save_btn)
        layout.addLayout(row)

    def _page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        return page, layout

    def _group(self, title: str, parent_layout: QVBoxLayout) -> QFormLayout:
        group = QGroupBox(title)
        form = QFormLayout(group)
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        parent_layout.addWidget(group)
        return form

    def _grid_group(self, title: str, parent_layout: QVBoxLayout) -> tuple[QGroupBox, QGridLayout]:
        group = QGroupBox(title)
        grid = QGridLayout(group)
        grid.setContentsMargins(20, 22, 20, 18)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)
        grid.setColumnMinimumWidth(0, 95)
        grid.setColumnStretch(1, 1)
        grid.setColumnMinimumWidth(2, 95)
        grid.setColumnStretch(3, 1)
        parent_layout.addWidget(group)
        return group, grid

    def _grid_row(self, grid: QGridLayout, row: int, label_text: str, widget: QWidget, column: int = 0):
        label = QLabel(label_text)
        label.setMinimumWidth(90)
        grid.setRowMinimumHeight(row, 46)
        grid.addWidget(label, row, column)
        grid.addWidget(widget, row, column + 1)

    def _grid_switch(self, grid: QGridLayout, row: int, attr: str, text: str, column: int = 0):
        wrap = QHBoxLayout()
        widget = ToggleSwitch()
        label = QLabel(text)
        label.setWordWrap(True)
        grid.setRowMinimumHeight(row, 40)
        wrap.addWidget(widget)
        wrap.addWidget(label, 1)
        grid.addLayout(wrap, row, column, 1, 2)
        setattr(self, attr, widget)
        return widget

    def _switch(self, form: QFormLayout, attr: str, text: str):
        row = QHBoxLayout()
        widget = ToggleSwitch()
        label = QLabel(text)
        label.setWordWrap(True)
        row.addWidget(widget)
        row.addWidget(label, 1)
        form.addRow("", row)
        setattr(self, attr, widget)
        return widget

    def _general_tab(self):
        page, layout = self._page()
        form = self._group("Приложение", layout)

        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Папка для загрузки")
        browse_btn = QPushButton("Обзор")
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self.folder_edit)
        folder_row.addWidget(browse_btn)
        form.addRow("Папка:", folder_row)
        self._switch(form, "auto_route_folders_sw", "Автоматически раскладывать загрузки по сервисам и типам")

        self.theme_combo = _combo([label for _, label in THEME_OPTIONS])
        form.addRow("Тема:", self.theme_combo)

        self.language_combo = _combo(["Русский", "English", "Deutsch", "Italiano"])
        form.addRow("Язык:", self.language_combo)

        self._switch(form, "background_on_close_sw", "Переходить в фоновый режим при закрытии окна")
        self._switch(form, "launch_on_startup_sw", "Открывать приложение при запуске Windows")
        self._switch(form, "auto_update_app_sw", "Автоматически проверять обновления приложения")
        self._switch(form, "auto_download_updates_sw", "Автоматически загружать обновления")
        self._switch(form, "beta_updates_sw", "Устанавливать бета-версии")
        self.app_update_status_label = QLabel("Проверка обновлений использует GitHub Releases после настройки репозитория.")
        self.app_update_status_label.setObjectName("subtle")
        self.app_update_status_label.setWordWrap(True)
        app_update_btn = QPushButton("Проверить обновление приложения")
        app_update_btn.setMaximumWidth(250)
        app_update_btn.clicked.connect(self._run_app_update_check)
        row = QHBoxLayout()
        row.addWidget(self.app_update_status_label, 1)
        row.addWidget(app_update_btn)
        form.addRow("Обновления:", row)
        layout.addStretch()
        return page

    def _format_tab(self):
        page, layout = self._page()
        _, grid = self._grid_group("Загрузка", layout)
        row = 0

        self.download_type_combo = _combo(["Видео", "Только аудио", "Картинки/миниатюры", "Документы/описания"], 260)
        self._grid_row(grid, row, "Тип:", self.download_type_combo)
        self.quality_combo = _combo(["Лучшее", "2160p", "1440p", "1080p", "720p", "480p"])
        self._grid_row(grid, row, "Качество:", self.quality_combo, 2)
        row += 1

        self.fps_combo = _combo(["Лучшее", "60 FPS", "30 FPS"])
        self._grid_row(grid, row, "Кадры:", self.fps_combo)
        self.container_combo = _combo(["MP4", "MKV", "WebM"])
        self._grid_row(grid, row, "Контейнер:", self.container_combo, 2)
        row += 1

        self.codec_combo = _combo([])
        self._grid_row(grid, row, "Кодек:", self.codec_combo)
        self.encoding_mode_combo = _combo(["Авто: видеокарта, потом процессор", "Только видеокарта", "Только процессор"], 290)
        self._grid_row(grid, row, "Режим:", self.encoding_mode_combo, 2)
        row += 1

        self.encoder_combo = _combo(["Авто", "NVIDIA NVENC", "Intel Quick Sync", "AMD AMF", "CPU x264"])
        self._grid_row(grid, row, "Энкодер:", self.encoder_combo)
        self.encoder_status_label = QLabel("")
        self.encoder_status_label.setObjectName("subtle")
        self._grid_row(grid, row, "Доступно:", self.encoder_status_label, 2)
        row += 1

        self._grid_switch(grid, row, "auto_convert_sw", "Автоматически менять кодек после скачивания, если выбран не оригинал")
        self._grid_switch(grid, row, "ask_codec_convert_sw", "Спрашивать перед сменой кодека", 2)
        row += 1
        self._grid_switch(grid, row, "keep_originals_sw", "Сохранять оригиналы после конвертации")
        self._grid_switch(grid, row, "show_all_codecs_sw", "Показывать AV1 и VP9", 2)

        _, music_grid = self._grid_group("Музыка Spotify", layout)
        self.spotify_format_combo = _combo(["MP3", "M4A", "Opus", "FLAC", "WAV"])
        self._grid_row(music_grid, 0, "Формат:", self.spotify_format_combo)
        self.spotify_bitrate_combo = _combo(["320k", "256k", "192k", "160k", "128k", "Авто"])
        self._grid_row(music_grid, 0, "Битрейт:", self.spotify_bitrate_combo, 2)
        layout.addStretch()
        return page

    def _playlist_tab(self):
        page, layout = self._page()
        form = self._group("Плейлисты, каналы и результаты поиска", layout)
        self._switch(form, "playlist_subfolders_sw", "Создавать подпапки для плейлистов, каналов и результатов поиска")
        self._switch(form, "playlist_numbering_sw", "Нумеровать файлы")
        self._switch(form, "skip_duplicates_sw", "Пропускать уже скачанные элементы")
        self._switch(form, "create_m3u_sw", "Создавать файл .m3u")
        self._switch(form, "embed_subtitles_sw", "Встраивать субтитры, если доступны")
        self._switch(form, "remove_finished_sw", "Удалять завершённые элементы из списка")
        self._switch(form, "avoid_duplicate_names_sw", "Защита от одинаковых названий файлов")
        self._switch(form, "suggest_channel_download_sw", "Предлагать скачать канал после нескольких видео с него")
        layout.addStretch()
        return page

    def _connection_tab(self):
        page, layout = self._page()
        form = self._group("Скорость и сеть", layout)

        self.concurrent_combo = QComboBox()
        self.concurrent_combo.addItems([f"{i} загрузка" if i == 1 else f"{i} загрузки" for i in range(1, 11)])
        form.addRow("Одновременно:", self.concurrent_combo)

        self.speed_limit_combo = QComboBox()
        self.speed_limit_combo.addItems(["Безлимитно", "50 Мбит/с", "25 Мбит/с", "10 Мбит/с", "4 Мбит/с", "2 Мбит/с"])
        form.addRow("Лимит:", self.speed_limit_combo)
        self.speed_status_label = QLabel("Проверка подберет рекомендуемое количество загрузок.")
        self.speed_status_label.setObjectName("subtle")
        speed_btn = QPushButton("Проверить скорость")
        speed_btn.clicked.connect(self._run_speed_test)
        speed_row = QHBoxLayout()
        speed_row.addWidget(self.speed_status_label, 1)
        speed_row.addWidget(speed_btn)
        form.addRow("Сеть:", speed_row)

        self._switch(form, "proxy_enabled_sw", "Использовать прокси")
        self.proxy_type_combo = QComboBox()
        self.proxy_type_combo.addItems(["HTTP", "HTTPS", "SOCKS4", "SOCKS5"])
        form.addRow("Тип:", self.proxy_type_combo)

        self.proxy_host_edit = QLineEdit()
        self.proxy_host_edit.setPlaceholderText("127.0.0.1")
        form.addRow("Сервер:", self.proxy_host_edit)

        self.proxy_port_edit = QLineEdit()
        self.proxy_port_edit.setPlaceholderText("8080")
        form.addRow("Порт:", self.proxy_port_edit)

        self.proxy_user_edit = QLineEdit()
        self.proxy_user_edit.setPlaceholderText("необязательно")
        form.addRow("Логин:", self.proxy_user_edit)

        self.proxy_password_edit = QLineEdit()
        self.proxy_password_edit.setPlaceholderText("необязательно")
        self.proxy_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Пароль:", self.proxy_password_edit)
        self._switch(form, "prevent_sleep_sw", "Предотвращать сон до завершения загрузок")
        layout.addStretch()
        return page

    def _notifications_tab(self):
        page, layout = self._page()
        form = self._group("Уведомления", layout)
        self._switch(form, "notify_download_sw", "Показывать уведомление о завершении загрузки")
        self._switch(form, "notify_processing_sw", "Показывать уведомление о завершении обработки")
        self._switch(form, "notify_new_content_sw", "Напоминать скачать новый контент")
        self._switch(form, "notify_recommendations_sw", "Показывать похожие видео и рекомендации")
        self._switch(form, "confirm_exit_sw", "Запрашивать подтверждение при активных загрузках")
        self._switch(form, "notification_center_sw", "Показывать в центре уведомлений")
        self._switch(form, "play_sound_sw", "Проигрывать звук оповещений")
        layout.addStretch()
        return page

    def _access_tab(self):
        page, layout = self._page()
        form = self._group("Аккаунты и доступ", layout)
        self._switch(form, "auto_export_cookies_sw", "Автоматически обновлять доступ, когда сайт требует вход")

        self.browser_combo = QComboBox()
        self.browser_combo.addItems(["(не использовать)", "chrome", "firefox", "edge", "safari", "opera", "brave", "vivaldi"])
        form.addRow("Браузер вручную:", self.browser_combo)

        file_row = QHBoxLayout()
        self.cookies_file_edit = QLineEdit()
        self.cookies_file_edit.setPlaceholderText("Путь к файлу доступа, если нужен ручной режим")
        browse_btn = QPushButton("Обзор")
        browse_btn.clicked.connect(self._browse_cookies)
        file_row.addWidget(self.cookies_file_edit)
        file_row.addWidget(browse_btn)
        form.addRow("Файл:", file_row)
        layout.addStretch()
        return page

    def _developer_tab(self):
        return build_developer_tab(self)

    def _set_developer_panel_visible(self, visible: bool):
        if hasattr(self, "developer_panel"):
            self.developer_panel.setVisible(visible)

    def _load_values(self):
        self.folder_edit.setText(self.settings.get("download_folder", "C:\\"))
        self.theme_combo.setCurrentIndex(THEME_INDEX.get(self.settings.get("theme", "lux_graphite"), 0))
        self.language_combo.setCurrentIndex({"ru": 0, "en": 1, "de": 2, "it": 3}.get(self.settings.get("language", "en"), 1))
        self.download_type_combo.setCurrentIndex({"video": 0, "audio": 1, "pictures": 2, "documents": 3}.get(self.settings.get("download_type", "video"), 0))
        self.quality_combo.setCurrentIndex({"best": 0, "2160": 1, "1440": 2, "1080": 3, "720": 4, "480": 5}.get(str(self.settings.get("download_quality", "1080")), 3))
        self.fps_combo.setCurrentIndex({"best": 0, "60": 1, "30": 2}.get(str(self.settings.get("fps_limit", "best")), 0))
        self.container_combo.setCurrentIndex({"mp4": 0, "mkv": 1, "webm": 2}.get(self.settings.get("container", "mp4"), 0))
        self.encoding_mode_combo.setCurrentIndex({"gpu_auto": 0, "gpu_only": 1, "cpu_only": 2}.get(self.settings.get("encoding_mode", "gpu_auto"), 0))
        self.encoder_combo.setCurrentIndex({"auto": 0, "h264_nvenc": 1, "h264_qsv": 2, "h264_amf": 3, "libx264": 4}.get(self.settings.get("video_encoder", "auto"), 0))
        self.spotify_format_combo.setCurrentIndex({"mp3": 0, "m4a": 1, "opus": 2, "flac": 3, "wav": 4}.get(self.settings.get("spotify_audio_format", "mp3"), 0))
        self.spotify_bitrate_combo.setCurrentIndex({"320k": 0, "256k": 1, "192k": 2, "160k": 3, "128k": 4, "auto": 5}.get(self.settings.get("spotify_bitrate", "320k"), 0))
        self.concurrent_combo.setCurrentIndex(max(0, min(9, int(self.settings.get("max_concurrent_downloads", 2)) - 1)))
        self.speed_limit_combo.setCurrentIndex({"unlimited": 0, "50m": 1, "25m": 2, "10m": 3, "4m": 4, "2m": 5}.get(self.settings.get("speed_limit", "unlimited"), 0))
        self.proxy_type_combo.setCurrentIndex({"http": 0, "https": 1, "socks4": 2, "socks5": 3}.get(self.settings.get("proxy_type", "http"), 0))
        self.proxy_host_edit.setText(self.settings.get("proxy_host", ""))
        self.proxy_port_edit.setText(self.settings.get("proxy_port", ""))
        self.proxy_user_edit.setText(self.settings.get("proxy_username", ""))
        self.proxy_password_edit.setText(self.settings.get("proxy_password", ""))
        self.browser_combo.setCurrentIndex(max(0, self.browser_combo.findText(self.settings.get("cookies_from_browser", ""))))
        self.cookies_file_edit.setText(self.settings.get("cookies_file", ""))
        self.github_repo_edit.setText(self.settings.get("github_update_repo", ""))
        self.github_asset_edit.setText(self.settings.get("github_update_asset", "YouTubeDownloaderSetup"))
        self._load_codecs()
        self._set_switches()
        self._update_encoder_status()

    def _load_codecs(self):
        self.codec_combo.clear()
        self.codec_combo.addItems(["Оригинал", "h264 (рекомендуется)"])
        if self.settings.get("show_all_codecs", True):
            self.codec_combo.addItems(["vp9", "av1"])
        codec = self.settings.get("default_codec", "original")
        indexes = {"original": 0, "h264": 1, "vp9": 2, "av1": 3}
        self.codec_combo.setCurrentIndex(indexes.get(codec, 0) if indexes.get(codec, 0) < self.codec_combo.count() else 0)

    def _set_switches(self):
        pairs = {
            "background_on_close_sw": ("background_on_close", False),
            "auto_route_folders_sw": ("auto_route_folders", True),
            "launch_on_startup_sw": ("launch_on_startup", False),
            "auto_update_app_sw": ("auto_update_app", True),
            "auto_download_updates_sw": ("auto_download_updates", True),
            "beta_updates_sw": ("install_beta_updates", False),
            "auto_convert_sw": ("auto_convert", False),
            "ask_codec_convert_sw": ("ask_before_codec_convert", True),
            "keep_originals_sw": ("keep_originals", False),
            "show_all_codecs_sw": ("show_all_codecs", True),
            "playlist_subfolders_sw": ("playlist_subfolders", True),
            "playlist_numbering_sw": ("playlist_numbering", True),
            "skip_duplicates_sw": ("skip_duplicates", True),
            "create_m3u_sw": ("create_m3u", False),
            "embed_subtitles_sw": ("embed_subtitles", False),
            "remove_finished_sw": ("remove_finished_from_list", False),
            "suggest_channel_download_sw": ("suggest_channel_download", True),
            "proxy_enabled_sw": ("proxy_enabled", False),
            "prevent_sleep_sw": ("prevent_sleep", True),
            "notify_download_sw": ("notify_download_finished", True),
            "notify_processing_sw": ("notify_processing_finished", True),
            "notify_new_content_sw": ("notify_new_content", False),
            "notify_recommendations_sw": ("notify_recommendations", False),
            "confirm_exit_sw": ("confirm_exit_with_active_downloads", True),
            "notification_center_sw": ("show_in_notification_center", True),
            "play_sound_sw": ("play_notification_sound", False),
            "auto_export_cookies_sw": ("auto_export_cookies", True),
            "developer_mode_sw": ("developer_mode", False),
            "auto_update_engine_sw": ("auto_update_ytdlp", False),
            "download_stats_sw": ("download_stats", False),
            "show_download_tools_sw": ("show_download_tools", True),
            "avoid_duplicate_names_sw": ("avoid_duplicate_names", False),
        }
        for attr, (key, default) in pairs.items():
            getattr(self, attr).setChecked(self.settings.get(key, default))
        self._set_developer_panel_visible(self.settings.get("developer_mode", False))

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выбрать папку загрузки", self.folder_edit.text() or "C:\\")
        if folder:
            self.folder_edit.setText(folder)

    def _browse_cookies(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать файл доступа", "", "Text Files (*.txt);;All Files (*)")
        if path:
            self.cookies_file_edit.setText(path)

    def _update_encoder_status(self):
        found = available_encoders()
        labels = [name for key, name in (("h264_nvenc", "NVIDIA"), ("h264_qsv", "Intel"), ("h264_amf", "AMD")) if key in found]
        labels.append("CPU")
        self.encoder_status_label.setText(", ".join(labels))

    def _run_update(self):
        self.update_btn.setEnabled(False)
        self.update_status_label.setText("Проверка и скачивание обновлений...")
        self._update_worker = UpdateWorker()
        self._update_worker.finished.connect(self._on_update_finished)
        self._update_worker.start()

    def _run_app_update_check(self):
        self._save()
        self.app_update_status_label.setText("Проверяю обновление приложения...")
        self._app_update_worker = AppUpdateWorker(self.settings, download=False)
        self._app_update_worker.checked.connect(self._on_app_update_checked)
        self._app_update_worker.start()

    def _on_app_update_checked(self, info: dict):
        self.app_update_status_label.setText(info.get("message", "Проверка завершена."))
        if not info.get("ok"):
            QMessageBox.information(self, "Обновление приложения", info.get("message", "Источник обновлений не настроен."))
            return
        message = f"Доступна версия {info.get('version')}." if info.get("available") else "Установлена последняя версия приложения."
        QMessageBox.information(self, "Обновление приложения", message)

    def _run_speed_test(self):
        self.speed_status_label.setText("Проверяю скорость...")
        self._speed_worker = SpeedTestWorker()
        self._speed_worker.finished.connect(self._on_speed_finished)
        self._speed_worker.start()

    def _on_speed_finished(self, ok: bool, mbps: float, recommended: int, error: str):
        if not ok:
            self.speed_status_label.setText(f"Не удалось проверить скорость: {error}")
            return
        idx = max(0, min(9, recommended - 1))
        self.concurrent_combo.setCurrentIndex(idx)
        self.speed_status_label.setText(f"Скорость: {mbps:.1f} Мбит/с. Рекомендовано: {recommended}.")

    def _on_update_finished(self, success: bool, msg: str):
        self.update_btn.setEnabled(True)
        self.update_status_label.setText(msg)
        (QMessageBox.information if success else QMessageBox.warning)(self, "Обновление", msg)

    def _save(self):
        maps = {
            "download_type": {0: "video", 1: "audio", 2: "pictures", 3: "documents"},
            "quality": {0: "best", 1: "2160", 2: "1440", 3: "1080", 4: "720", 5: "480"},
            "fps": {0: "best", 1: "60", 2: "30"},
            "container": {0: "mp4", 1: "mkv", 2: "webm"},
            "encoding": {0: "gpu_auto", 1: "gpu_only", 2: "cpu_only"},
            "encoder": {0: "auto", 1: "h264_nvenc", 2: "h264_qsv", 3: "h264_amf", 4: "libx264"},
            "theme": THEME_BY_INDEX,
            "language": {0: "ru", 1: "en", 2: "de", 3: "it"},
            "speed": {0: "unlimited", 1: "50m", 2: "25m", 3: "10m", 4: "4m", 5: "2m"},
            "codec": {0: "original", 1: "h264", 2: "vp9", 3: "av1"},
            "spotify_format": {0: "mp3", 1: "m4a", 2: "opus", 3: "flac", 4: "wav"},
            "spotify_bitrate": {0: "320k", 1: "256k", 2: "192k", 3: "160k", 4: "128k", 5: "auto"},
        }
        browser_text = self.browser_combo.currentText()
        self.settings.update({
            "download_folder": self.folder_edit.text() or "C:\\",
            "theme": maps["theme"].get(self.theme_combo.currentIndex(), "lux_graphite"),
            "language": maps["language"].get(self.language_combo.currentIndex(), "en"),
            "download_type": maps["download_type"].get(self.download_type_combo.currentIndex(), "video"),
            "download_quality": maps["quality"].get(self.quality_combo.currentIndex(), "1080"),
            "fps_limit": maps["fps"].get(self.fps_combo.currentIndex(), "best"),
            "container": maps["container"].get(self.container_combo.currentIndex(), "mp4"),
            "default_codec": maps["codec"].get(self.codec_combo.currentIndex(), "h264"),
            "encoding_mode": maps["encoding"].get(self.encoding_mode_combo.currentIndex(), "gpu_auto"),
            "video_encoder": maps["encoder"].get(self.encoder_combo.currentIndex(), "auto"),
            "prefer_gpu": self.encoding_mode_combo.currentIndex() != 2,
            "max_concurrent_downloads": self.concurrent_combo.currentIndex() + 1,
            "speed_limit": maps["speed"].get(self.speed_limit_combo.currentIndex(), "unlimited"),
            "proxy_url": "",
            "proxy_type": {0: "http", 1: "https", 2: "socks4", 3: "socks5"}.get(self.proxy_type_combo.currentIndex(), "http"),
            "proxy_host": self.proxy_host_edit.text().strip(),
            "proxy_port": self.proxy_port_edit.text().strip(),
            "proxy_username": self.proxy_user_edit.text().strip(),
            "proxy_password": self.proxy_password_edit.text().strip(),
            "cookies_from_browser": "" if browser_text.startswith("(") else browser_text,
            "cookies_file": self.cookies_file_edit.text(),
            "github_update_repo": self.github_repo_edit.text().strip(),
            "github_update_asset": self.github_asset_edit.text().strip() or "YouTubeDownloaderSetup",
            "spotify_audio_format": maps["spotify_format"].get(self.spotify_format_combo.currentIndex(), "mp3"),
            "spotify_bitrate": maps["spotify_bitrate"].get(self.spotify_bitrate_combo.currentIndex(), "320k"),
        })
        for attr, key in {
            "background_on_close_sw": "background_on_close",
            "auto_route_folders_sw": "auto_route_folders",
            "launch_on_startup_sw": "launch_on_startup",
            "auto_update_app_sw": "auto_update_app",
            "auto_download_updates_sw": "auto_download_updates",
            "beta_updates_sw": "install_beta_updates",
            "auto_convert_sw": "auto_convert",
            "ask_codec_convert_sw": "ask_before_codec_convert",
            "keep_originals_sw": "keep_originals",
            "show_all_codecs_sw": "show_all_codecs",
            "playlist_subfolders_sw": "playlist_subfolders",
            "playlist_numbering_sw": "playlist_numbering",
            "skip_duplicates_sw": "skip_duplicates",
            "create_m3u_sw": "create_m3u",
            "embed_subtitles_sw": "embed_subtitles",
            "remove_finished_sw": "remove_finished_from_list",
            "suggest_channel_download_sw": "suggest_channel_download",
            "proxy_enabled_sw": "proxy_enabled",
            "prevent_sleep_sw": "prevent_sleep",
            "notify_download_sw": "notify_download_finished",
            "notify_processing_sw": "notify_processing_finished",
            "notify_new_content_sw": "notify_new_content",
            "notify_recommendations_sw": "notify_recommendations",
            "confirm_exit_sw": "confirm_exit_with_active_downloads",
            "notification_center_sw": "show_in_notification_center",
            "play_sound_sw": "play_notification_sound",
            "auto_export_cookies_sw": "auto_export_cookies",
            "developer_mode_sw": "developer_mode",
            "auto_update_engine_sw": "auto_update_ytdlp",
            "download_stats_sw": "download_stats",
            "show_download_tools_sw": "show_download_tools",
            "avoid_duplicate_names_sw": "avoid_duplicate_names",
        }.items():
            self.settings[key] = getattr(self, attr).isChecked()
        _apply_startup(self.settings.get("launch_on_startup", False))
        save_settings(self.settings)
        self.settings_changed.emit(self.settings)


install_developer_actions(SettingsPage)
