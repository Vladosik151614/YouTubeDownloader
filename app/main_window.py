"""
main_window.py — главное окно приложения YouTube Downloader
с аппаратным ускорением GPU, авто-обновлением, пропуском ошибок плейлистов и тонкой настройкой перекодирования.
"""
import os
import sys
import shutil
import uuid
import subprocess
import webbrowser
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QLineEdit, QFileDialog, QMessageBox, QStackedWidget,
    QFrame, QSizePolicy, QDialog, QListWidget, QListWidgetItem,
    QDialogButtonBox, QComboBox, QApplication
)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QFont, QIcon, QColor

from app.settings_manager import load_settings, save_settings
from app.settings_page import SettingsPage
from app.history_page import HistoryPage
from app.accounts_page import AccountsPage
from app.history_store import add_history_entry
from app.queue_widget import QueueWidget
from app.downloader import DownloadWorker
from app.converter import probe_codec, has_video_stream, normalized_target_codec, ConvertWorker
from app.toggle_switch import ToggleSwitch
from app.logger import logger
from app.updater import AppUpdateWorker, UpdateWorker
from app.binary_manager import get_resource_path
from app.link_preview import LinkPreviewWorker
from app.support_dialog import SupportErrorDialog
from app.tray_controller import TrayController
from app.localization import apply_translations, translate
def owner_tools_available():
    return False

OwnerToolsPage = None
from app.process_utils import hidden_subprocess_kwargs
from app.sidebar_button import SidebarNavButton
from app.fix_report_page import APP_VERSION, FixReportPage

from app.theme import app_qss


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self._workers = {}       # item_id -> DownloadWorker
        self._conv_workers = {}  # filepath -> ConvertWorker
        self._item_urls = {}     # item_id -> source URL
        self._item_paths = {}    # item_id -> downloaded file/folder
        self._item_errors = {}   # item_id -> last error
        self._paused_urls = {}   # item_id -> source URL paused by user
        self._pending_downloads = []
        self._active_download_ids = set()
        self._preview_worker = None
        self._app_update_worker = None
        self._tray = None
        self._owner_tools_enabled = owner_tools_available()
        
        self._setup_window()
        self._apply_style()
        self._build_ui()
        self._tray = TrayController(self)
        self._start_monitors()
        QTimer.singleShot(2500, self._auto_check_app_update)

    def _setup_window(self):
        self.setWindowTitle("YouTube Downloader")
        self.setMinimumSize(900, 620)
        self.resize(1080, 700)
        
        # Устанавливаем иконку окна из файла youtube.ico если он есть
        ico_path = get_resource_path("youtube.ico")
        if os.path.isfile(ico_path):
            self.setWindowIcon(QIcon(ico_path))

    def _apply_style(self):
        self.setStyleSheet(app_qss(self.settings.get("theme", "graphite_red")))

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setObjectName("content_area")
        self.stack.addWidget(self._build_download_page())   # page 0
        self.stack.addWidget(self._build_settings_widget()) # page 1
        self.stack.addWidget(self._build_history_widget())  # page 2
        self.stack.addWidget(self._build_accounts_widget()) # page 3
        self.stack.addWidget(self._build_fix_report_widget()) # page 4
        if self._owner_tools_enabled:
            self.stack.addWidget(self._build_owner_tools_widget()) # page 5

        root_layout.addWidget(self._build_sidebar())
        root_layout.addWidget(self.stack, 1)

        self._switch_page(0)
        self.status_label = QLabel("Готов к загрузке")
        self.disk_space_label = QLabel("💾 Диск: —")
        self.disk_space_label.setStyleSheet("font-weight: bold;")
        self.version_label = QLabel(f"v{APP_VERSION}")
        self.version_label.setStyleSheet("color: #777;")
        
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().addPermanentWidget(self.version_label)
        self.statusBar().addPermanentWidget(self.disk_space_label)
        self._apply_language()

    def _apply_language(self):
        apply_translations(self, self.settings.get("language", "ru"))

    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(176)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 14, 10, 14)
        layout.setSpacing(5)

        logo = QLabel("▶  YT Downloader")
        logo.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        logo.setStyleSheet("color: #e94560; margin-bottom: 12px;")
        layout.addWidget(logo)

        self._nav_btns = []
        nav_items = [
            ("download", "Загрузка", 0),
            ("settings", "Настройки", 1),
            ("history", "История", 2),
            ("accounts", "Аккаунты", 3),
            ("fixes", "Исправления", 4),
        ]
        if self._owner_tools_enabled:
            nav_items.append(("github", "GitHub", 5))
        for icon_name, label, page_idx in nav_items:
            btn = SidebarNavButton(icon_name, label)
            btn.setCheckable(False)
            btn.clicked.connect(lambda _, i=page_idx: self._switch_page(i))
            layout.addWidget(btn)
            self._nav_btns.append(btn)

        layout.addStretch()

        return sidebar

    def _switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_btns):
            btn.setProperty("active", str(i == index).lower())
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _mini_combo(self, label_text: str, combo: QComboBox) -> QWidget:
        box = QFrame()
        box.setObjectName("smart_card")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(9, 5, 9, 7)
        layout.setSpacing(3)
        label = QLabel(label_text)
        label.setObjectName("mini_label")
        layout.addWidget(label)
        combo.setMinimumWidth(104)
        combo.setMaximumWidth(132)
        layout.addWidget(combo)
        return box

    def _build_download_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(11)

        hdr = QLabel("Загрузка видео, музыки и плейлистов")
        hdr.setObjectName("section_title")
        hdr.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        layout.addWidget(hdr)

        subtitle = QLabel("Поддержка видео, музыки, плейлистов, каналов и клипов")
        subtitle.setObjectName("subtle")
        layout.addWidget(subtitle)

        tool_band = QFrame()
        tool_band.setObjectName("tool_band")
        tool_layout = QVBoxLayout(tool_band)
        tool_layout.setContentsMargins(12, 12, 12, 12)
        tool_layout.setSpacing(9)

        top_actions = QHBoxLayout()
        top_actions.setSpacing(10)
        paste_btn = QPushButton("Вставить ссылку")
        paste_btn.setObjectName("primary_btn")
        paste_btn.setMinimumHeight(38)
        paste_btn.setMinimumWidth(132)
        paste_btn.clicked.connect(self._paste_from_clipboard)
        top_actions.addWidget(paste_btn)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Вставьте ссылку на видео, аудио, плейлист, канал или клип...")
        self.url_edit.setMinimumHeight(38)
        self.url_edit.returnPressed.connect(self._add_to_queue)
        top_actions.addWidget(self.url_edit, 1)

        add_btn = QPushButton("Скачать")
        add_btn.setMinimumHeight(38)
        add_btn.setMinimumWidth(96)
        add_btn.clicked.connect(self._add_to_queue)
        top_actions.addWidget(add_btn)
        preview_btn = QPushButton("Проверить")
        preview_btn.setMinimumHeight(38)
        preview_btn.clicked.connect(self._preview_link)
        top_actions.addWidget(preview_btn)
        tool_layout.addLayout(top_actions)

        self.preview_label = QLabel("Проверка ссылки покажет сервис, тип, качество, FPS и субтитры.")
        self.preview_label.setObjectName("subtle")
        self.preview_label.setWordWrap(True)
        tool_layout.addWidget(self.preview_label)

        smart_row = QHBoxLayout()
        smart_row.setSpacing(8)
        
        smart_card = QFrame()
        smart_card.setObjectName("smart_card")
        smart_layout = QHBoxLayout(smart_card)
        smart_layout.setContentsMargins(10, 8, 10, 8)
        smart_layout.setSpacing(8)
        self.quick_auto_convert_switch = ToggleSwitch(checked=self.settings.get("auto_convert", True))
        self.quick_auto_convert_switch.toggled.connect(self._on_quick_auto_convert_toggled)
        smart_label = QLabel("Профиль загрузки")
        smart_label.setObjectName("mini_label")
        smart_layout.addWidget(self.quick_auto_convert_switch)
        smart_layout.addWidget(smart_label)
        smart_row.addWidget(smart_card)

        self.quick_quality_combo = QComboBox()
        self.quick_quality_combo.addItems(["Лучшее", "2160p", "1440p", "1080p", "720p", "480p"])
        self.quick_quality_combo.currentIndexChanged.connect(self._on_quick_quality_changed)
        smart_row.addWidget(self._mini_combo("Качество", self.quick_quality_combo))

        self.quick_container_combo = QComboBox()
        self.quick_container_combo.addItems(["MP4", "MKV", "WebM"])
        self.quick_container_combo.currentIndexChanged.connect(self._on_quick_container_changed)
        smart_row.addWidget(self._mini_combo("Контейнер", self.quick_container_combo))

        self.quick_encoder_combo = QComboBox()
        self.quick_encoder_combo.addItems(["Авто GPU", "NVENC", "QSV", "AMF", "CPU"])
        self.quick_encoder_combo.currentIndexChanged.connect(self._on_quick_encoder_changed)
        smart_row.addWidget(self._mini_combo("Энкодер", self.quick_encoder_combo))

        self.quick_codec_combo = QComboBox()
        self.quick_codec_combo.addItems(["Оригинал", "H.264", "VP9", "AV1"])
        self.quick_codec_combo.currentIndexChanged.connect(self._on_quick_codec_changed)
        smart_row.addWidget(self._mini_combo("Кодек", self.quick_codec_combo))

        smart_row.addStretch()
        tool_layout.addLayout(smart_row)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        folder_label = QLabel("📁 Папка:")
        folder_label.setObjectName("subtle")
        folder_row.addWidget(folder_label)

        self.folder_display = QLabel(self.settings.get("download_folder", "C:\\"))
        self.folder_display.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        folder_row.addWidget(self.folder_display, 1)

        change_folder_btn = QPushButton("Изменить")
        change_folder_btn.setMinimumWidth(82)
        change_folder_btn.clicked.connect(self._change_folder)
        folder_row.addWidget(change_folder_btn)

        open_folder_btn = QPushButton("📂  Открыть")
        open_folder_btn.setMinimumWidth(96)
        open_folder_btn.clicked.connect(self._open_download_folder)
        folder_row.addWidget(open_folder_btn)

        clear_btn = QPushButton("🗑  Очистить")
        clear_btn.setMinimumWidth(90)
        clear_btn.clicked.connect(self._clear_finished)
        folder_row.addWidget(clear_btn)

        tool_layout.addLayout(folder_row)
        self._sync_quick_controls()
        layout.addWidget(tool_band)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #0f3460;")
        layout.addWidget(line)

        queue_hdr = QLabel("📋  Очередь загрузок")
        queue_hdr.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        queue_hdr.setObjectName("subtle")
        layout.addWidget(queue_hdr)

        self.queue_widget = QueueWidget()
        self.queue_widget.cancel_requested.connect(self._cancel_item)
        self.queue_widget.pause_requested.connect(self._pause_item)
        self.queue_widget.resume_requested.connect(self._resume_item)
        self.queue_widget.open_requested.connect(self._open_queue_item)
        self.queue_widget.retry_requested.connect(self._retry_item)
        self.queue_widget.details_requested.connect(self._show_item_details)
        layout.addWidget(self.queue_widget, 1)

        return page

    def _build_settings_widget(self):
        self.settings_page = SettingsPage(self.settings)
        self.settings_page.settings_changed.connect(self._on_settings_changed)
        return self.settings_page

    def _build_history_widget(self):
        self.history_page = HistoryPage()
        return self.history_page

    def _build_accounts_widget(self):
        self.accounts_page = AccountsPage()
        return self.accounts_page

    def _build_fix_report_widget(self):
        self.fix_report_page = FixReportPage()
        return self.fix_report_page

    def _build_owner_tools_widget(self):
        self.owner_tools_page = OwnerToolsPage()
        return self.owner_tools_page

    def _start_monitors(self):
        self._update_disk_space()
        self.space_timer = QTimer(self)
        self.space_timer.setInterval(5000)
        self.space_timer.timeout.connect(self._update_disk_space)
        self.space_timer.start()

    def _auto_check_app_update(self):
        if not self.settings.get("auto_update_app", True):
            return
        if not self.settings.get("github_update_repo", "").strip():
            return
        self._app_update_worker = AppUpdateWorker(self.settings, download=False)
        self._app_update_worker.checked.connect(self._on_app_update_checked)
        self._app_update_worker.start()

    def _on_app_update_checked(self, info: dict):
        if not info.get("ok") or not info.get("available"):
            return
        reply = QMessageBox.question(
            self,
            "Обновление приложения",
            f"Доступна новая версия {info.get('version')}.\n\nСкачать и запустить обновленную версию?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if self.settings.get("auto_download_updates", True):
            self.status_label.setText("Скачиваю обновление приложения...")
            self._app_update_worker = AppUpdateWorker(self.settings, download=True)
            self._app_update_worker.downloaded.connect(self._on_app_update_downloaded)
            self._app_update_worker.start()
        elif info.get("html_url"):
            webbrowser.open(info["html_url"])

    def _on_app_update_downloaded(self, success: bool, path: str):
        if not success:
            QMessageBox.warning(self, "Обновление приложения", path)
            return
        reply = QMessageBox.question(
            self,
            "Обновление приложения",
            "Обновленная версия скачана. Закрыть приложение и запустить новый файл?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            subprocess.Popen([path], **hidden_subprocess_kwargs())
            if self._tray:
                self._tray.allow_close = True
            QApplication.quit()
        except Exception as exc:
            QMessageBox.warning(self, "Обновление приложения", f"Не удалось запустить обновление:\n{exc}")

    def _notify(self, title: str, message: str):
        if self._tray:
            self._tray.notify(title, message)

    def closeEvent(self, event):
        self._tray.handle_close_event(event) if self._tray else event.accept()

    def _update_disk_space(self):
        folder = self.settings.get("download_folder", "C:\\")
        try:
            os.makedirs(folder, exist_ok=True)
            target = folder if os.path.exists(folder) else os.path.dirname(folder)
            total, used, free = shutil.disk_usage(target)
            free_gb = free / (1024 ** 3)
            drive_name = os.path.splitdrive(os.path.abspath(target))[0] or "C:"
            self.disk_space_label.setText(f"💾 {drive_name} Свободно: {free_gb:.1f} ГБ")
        except Exception:
            self.disk_space_label.setText("💾 Диск: N/A")

    def _on_quick_auto_convert_toggled(self, checked: bool):
        self.settings["auto_convert"] = checked
        save_settings(self.settings)
        if hasattr(self, 'settings_page'):
            self.settings_page.settings = dict(self.settings)
            self.settings_page.auto_convert_sw.setChecked(checked)

    def _paste_from_clipboard(self):
        text = QApplication.clipboard().text().strip()
        if text:
            self.url_edit.setText(text)
            self.status_label.setText("Ссылка вставлена. Нажмите «Скачать», чтобы начать загрузку.")
        else:
            self.status_label.setText("Буфер обмена пуст")

    def _sync_quick_controls(self):
        if hasattr(self, "quick_quality_combo"):
            quality_idx = {"best": 0, "2160": 1, "1440": 2, "1080": 3, "720": 4, "480": 5}.get(
                str(self.settings.get("download_quality", "1080")), 3
            )
            self.quick_quality_combo.blockSignals(True)
            self.quick_quality_combo.setCurrentIndex(quality_idx)
            self.quick_quality_combo.blockSignals(False)
        if hasattr(self, "quick_container_combo"):
            container_idx = {"mp4": 0, "mkv": 1, "webm": 2}.get(self.settings.get("container", "mp4"), 0)
            self.quick_container_combo.blockSignals(True)
            self.quick_container_combo.setCurrentIndex(container_idx)
            self.quick_container_combo.blockSignals(False)
        if hasattr(self, "quick_encoder_combo"):
            encoder_idx = {
                "auto": 0,
                "h264_nvenc": 1,
                "h264_qsv": 2,
                "h264_amf": 3,
                "libx264": 4,
            }.get(self.settings.get("video_encoder", "auto"), 0)
            self.quick_encoder_combo.blockSignals(True)
            self.quick_encoder_combo.setCurrentIndex(encoder_idx)
            self.quick_encoder_combo.blockSignals(False)
        if hasattr(self, "quick_codec_combo"):
            codec_idx = {"original": 0, "h264": 1, "vp9": 2, "av1": 3}.get(
                normalized_target_codec(self.settings), 0
            )
            self.quick_codec_combo.blockSignals(True)
            self.quick_codec_combo.setCurrentIndex(codec_idx)
            self.quick_codec_combo.blockSignals(False)

    def _save_quick_setting(self, key: str, value: str):
        self.settings[key] = value
        if key == "video_encoder":
            self.settings["encoding_mode"] = "cpu_only" if value == "libx264" else "gpu_auto"
            self.settings["prefer_gpu"] = value != "libx264"
        save_settings(self.settings)
        if hasattr(self, "settings_page"):
            self.settings_page.settings = dict(self.settings)
            self.settings_page._load_values()

    def _on_quick_quality_changed(self, index: int):
        self._save_quick_setting("download_quality", {0: "best", 1: "2160", 2: "1440", 3: "1080", 4: "720", 5: "480"}.get(index, "1080"))

    def _on_quick_container_changed(self, index: int):
        self._save_quick_setting("container", {0: "mp4", 1: "mkv", 2: "webm"}.get(index, "mp4"))

    def _on_quick_encoder_changed(self, index: int):
        self._save_quick_setting("video_encoder", {0: "auto", 1: "h264_nvenc", 2: "h264_qsv", 3: "h264_amf", 4: "libx264"}.get(index, "auto"))

    def _on_quick_codec_changed(self, index: int):
        codec = {0: "original", 1: "h264", 2: "vp9", 3: "av1"}.get(index, "original")
        self.settings["default_codec"] = codec
        self.settings["auto_convert"] = codec != "original"
        save_settings(self.settings)
        if hasattr(self, "settings_page"):
            self.settings_page.settings = dict(self.settings)
            self.settings_page._load_values()

    def _add_to_queue(self):
        url = self.url_edit.text().strip()
        if not url:
            self.status_label.setText("Введите URL!")
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            QMessageBox.warning(self, "Ошибка", "Введите корректный URL (http:// или https://)")
            return

        if self._enqueue_url(url):
            self.url_edit.clear()

    def _preview_link(self):
        url = self.url_edit.text().strip()
        if not url or not url.startswith(("http://", "https://")):
            self.preview_label.setText("Вставьте корректную ссылку для проверки.")
            return
        self.preview_label.setText("Проверяю ссылку...")
        self._preview_worker = LinkPreviewWorker(url, self.settings)
        self._preview_worker.ready.connect(self._on_preview_ready)
        self._preview_worker.start()

    def _on_preview_ready(self, data: dict):
        if not data.get("ok"):
            self.preview_label.setText(f"Не удалось проверить ссылку: {data.get('error', 'ошибка')}")
            return
        self.preview_label.setText(
            f"{data['service']} · {data['kind']} · {data['title']} · "
            f"Длительность: {data['duration']} · Элементов: {data['count']} · "
            f"Качество: {data['qualities']} · FPS: {data['fps']} · Субтитры: {data['subtitles']}"
        )

    def _enqueue_url(self, url: str) -> bool:
        item_id = str(uuid.uuid4())[:8]
        output_folder = self.settings.get("download_folder", "C:\\")
        try:
            os.makedirs(output_folder, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка папки", f"Не удалось создать папку: {e}")
            return False

        self.queue_widget.add_item(item_id, url)
        self._item_urls[item_id] = url
        self.status_label.setText(f"Добавлено в очередь: {url[:50]}...")

        worker = DownloadWorker(item_id, url, output_folder, self.settings)
        worker.progress.connect(self._on_progress)
        worker.status.connect(self._on_status)
        worker.finished.connect(self._on_download_finished)
        worker.info_ready.connect(self._on_info_ready)
        worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        worker.playlist_items_ready.connect(self._on_playlist_items_ready)
        worker.playlist_item_progress.connect(self._on_playlist_item_progress)
        self._workers[item_id] = worker
        self._pending_downloads.append(item_id)
        self._start_next_downloads()
        logger.info(f"[{item_id}] Queued: {url}")
        return True

    def _start_next_downloads(self):
        max_active = max(1, int(self.settings.get("max_concurrent_downloads", 2)))
        while self._pending_downloads and len(self._active_download_ids) < max_active:
            item_id = self._pending_downloads.pop(0)
            worker = self._workers.get(item_id)
            if not worker:
                continue
            self._active_download_ids.add(item_id)
            worker.start()
            logger.info(f"[{item_id}] Started download worker")

    def _cancel_item(self, item_id: str):
        worker = self._workers.get(item_id)
        if worker:
            if item_id in self._pending_downloads:
                self._pending_downloads.remove(item_id)
                self._workers.pop(item_id, None)
                self._item_errors[item_id] = "Отменено до запуска"
                self.queue_widget.set_result(item_id, "", "Отменено до запуска")
                self.queue_widget.set_finished(item_id, False)
                self.queue_widget.update_status(item_id, "Отменено")
                self.status_label.setText("Загрузка отменена")
                return
            worker.cancel()
            self.queue_widget.update_status(item_id, "Отменено")
            self.queue_widget.set_result(item_id, "", "Отменено пользователем")
            self.queue_widget.set_finished(item_id, False)
            self.status_label.setText("Загрузка отменена")
            logger.info(f"[{item_id}] Cancelled by user")
        self._paused_urls.pop(item_id, None)

    def _pause_item(self, item_id: str):
        url = self._item_urls.get(item_id, "")
        worker = self._workers.get(item_id)
        if not url:
            return
        self._paused_urls[item_id] = url
        if item_id in self._pending_downloads:
            self._pending_downloads.remove(item_id)
        if worker:
            worker.cancel()
        self.queue_widget.update_status(item_id, "Пауза")
        self.status_label.setText("Загрузка поставлена на паузу")

    def _resume_item(self, item_id: str):
        url = self._paused_urls.pop(item_id, "") or self._item_urls.get(item_id, "")
        if not url:
            QMessageBox.warning(self, "Продолжить", "Не найдена ссылка для продолжения.")
            return
        self._enqueue_url(url)

    def _change_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Выбрать папку для загрузок",
            self.settings.get("download_folder", "C:\\")
        )
        if folder:
            self.settings["download_folder"] = folder
            save_settings(self.settings)
            self.folder_display.setText(folder)
            self._update_disk_space()
            if hasattr(self, 'settings_page'):
                self.settings_page.settings = dict(self.settings)
                self.settings_page._load_values()

    def _open_download_folder(self):
        folder = self.settings.get("download_folder", "C:\\")
        try:
            os.makedirs(folder, exist_ok=True)
            os.startfile(os.path.abspath(folder))
            self.status_label.setText(f"Открыта папка: {folder}")
        except Exception as e:
            logger.error(f"Cannot open download folder: {e}")
            QMessageBox.critical(self, "Ошибка папки", f"Не удалось открыть папку:\n{e}")

    def _clear_finished(self):
        self.queue_widget.clear_finished()

    def _open_queue_item(self, item_id: str):
        path = self._item_paths.get(item_id) or self.queue_widget.result_path(item_id)
        if not path:
            path = self.settings.get("download_folder", "C:\\")
        try:
            target = path if os.path.isdir(path) else os.path.dirname(path)
            if not target:
                target = self.settings.get("download_folder", "C:\\")
            os.makedirs(target, exist_ok=True)
            os.startfile(os.path.abspath(target))
            self.status_label.setText(f"Открыта папка: {target}")
        except Exception as e:
            logger.error(f"Cannot open queue item folder [{item_id}]: {e}")
            QMessageBox.critical(self, "Ошибка папки", f"Не удалось открыть папку:\n{e}")

    def _retry_item(self, item_id: str):
        url = self._item_urls.get(item_id)
        if not url:
            QMessageBox.warning(self, "Повтор", "Не найдена ссылка для повтора.")
            return
        self._enqueue_url(url)

    def _show_item_details(self, item_id: str):
        url = self._item_urls.get(item_id, "")
        path = self._item_paths.get(item_id, "")
        error = self._item_errors.get(item_id) or self.queue_widget.error_text(item_id) or "Подробностей нет."
        SupportErrorDialog(self, url, path, error, self.settings).exec()

    def _on_progress(self, item_id: str, percent: float, speed: str, eta: str):
        self.queue_widget.update_progress(item_id, percent, speed, eta)
        self.status_label.setText(f"Загрузка [{item_id}]: {percent:.1f}% | ⚡ Скорость: {speed} | ⏱ ETA: {eta}")

    def _on_status(self, item_id: str, text: str):
        self.queue_widget.update_status(item_id, text)

    def _on_info_ready(self, item_id: str, title: str, is_pl: bool, count: int, size_str: str):
        self.queue_widget.update_info(item_id, title, size_str)
        tag = f"[Плейлист: {count} видео]" if is_pl else "[Видео]"
        self.queue_widget.update_status(item_id, f"{tag} Загрузка...")
        self.status_label.setText(f"Получены данные: {title} (Размер: {size_str})")

    def _on_playlist_items_ready(self, item_id: str, entries: list):
        self.queue_widget.set_playlist_items(item_id, entries)

    def _on_thumbnail_ready(self, item_id: str, thumbnail: str):
        self.queue_widget.set_item_thumbnail(item_id, thumbnail)

    def _on_playlist_item_progress(self, item_id: str, playlist_index: int, status: str, percent: float):
        self.queue_widget.update_playlist_item(item_id, playlist_index, status, percent)

    def _on_download_finished(self, item_id: str, filepath: str, success: bool, error_msg: str):
        self._workers.pop(item_id, None)
        self._active_download_ids.discard(item_id)
        if item_id in self._paused_urls and error_msg == "Отменено пользователем":
            self.queue_widget.update_status(item_id, "Пауза")
            self._start_next_downloads()
            return
        self._item_paths[item_id] = filepath or ""
        self._item_errors[item_id] = error_msg or ""
        self.queue_widget.set_result(item_id, filepath or "", error_msg or "")
        self.queue_widget.set_finished(item_id, success)
        url = self._item_urls.get(item_id, "")
        title = self.queue_widget.title_text(item_id) or url
        add_history_entry(url, title, filepath or "", success, error_msg or "")
        if hasattr(self, "history_page"):
            self.history_page.refresh()
        
        if success:
            self.queue_widget.update_status(item_id, "Завершено")
            self.status_label.setText(f"Загрузка завершена: {os.path.basename(filepath or 'файл')}")
            logger.info(f"[{item_id}] Done: {filepath}")
            self._update_disk_space()
            if self.settings.get("notify_download_finished", True):
                self._notify("Загрузка завершена", os.path.basename(filepath or "Файл сохранен"))
            
            if self.settings.get("auto_convert", True) is True:
                if filepath and os.path.isfile(filepath):
                    self._check_and_prompt_conversion([filepath], is_playlist=False)
                elif filepath and os.path.isdir(filepath):
                    video_files = []
                    for root, _, names in os.walk(filepath):
                        video_files.extend(
                            os.path.join(root, f)
                            for f in names
                            if f.lower().endswith((".mp4", ".mkv", ".webm"))
                        )
                    if video_files:
                        self._check_and_prompt_conversion(video_files, is_playlist=True)
            else:
                logger.info(f"Auto-convert is DISABLED by user toggle switch for [{item_id}]")
            if self.settings.get("remove_finished_from_list", False):
                QTimer.singleShot(1200, lambda iid=item_id: self.queue_widget.remove_item(iid))
        elif error_msg == "Отменено пользователем":
            self.queue_widget.update_status(item_id, "Отменено")
            self.status_label.setText("Загрузка отменена")
            logger.info(f"[{item_id}] Cancelled")
        else:
            self.queue_widget.update_status(item_id, "Ошибка")
            self.status_label.setText(f"Ошибка: {error_msg}")
            logger.error(f"[{item_id}] Failed: {error_msg}")
            if error_msg and error_msg != "Отменено пользователем":
                SupportErrorDialog(self, url, filepath or "", error_msg, self.settings).exec()
        self._start_next_downloads()

    def _check_and_prompt_conversion(self, filepaths: list, is_playlist: bool = False):
        target_codec = normalized_target_codec(self.settings)
        if target_codec == "original" or not self.settings.get("auto_convert", False):
            return
        needs_conversion = [
            f for f in filepaths
            if os.path.isfile(f) and has_video_stream(f) and probe_codec(f) != target_codec
        ]
        if not needs_conversion:
            return

        codec_label = target_codec.upper() if target_codec != "h264" else "H.264"
        should_convert = True
        if self.settings.get("ask_before_codec_convert", True):
            if is_playlist:
                msg = (
                    f"Плейлист скачан. Найдено файлов для смены кодека: {len(needs_conversion)}.\n\n"
                    f"Изменить кодек на {codec_label}? Оригиналы будут удалены, если в настройках не включено сохранение оригиналов."
                )
            elif len(needs_conversion) == 1:
                msg = (
                    f"Видео скачано:\n\n{os.path.basename(needs_conversion[0])}\n\n"
                    f"Изменить кодек на {codec_label}? Оригинал будет удалён, если в настройках не включено сохранение оригиналов."
                )
            else:
                names = "\n".join(f"• {os.path.basename(f)}" for f in needs_conversion[:10])
                msg = f"Изменить кодек этих файлов на {codec_label}?\n\n{names}"
            reply = QMessageBox.question(
                self,
                f"Смена кодека на {codec_label}",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            should_convert = reply == QMessageBox.StandardButton.Yes
        if should_convert:
            for fp in needs_conversion:
                self._start_conversion(fp)

    def _legacy_check_and_prompt_conversion(self, filepaths: list):
        non_h264 = [
            f for f in filepaths
            if os.path.isfile(f) and has_video_stream(f) and probe_codec(f) != "h264"
        ]
        if not non_h264:
            return
        if len(non_h264) == 1:
            msg = f"Видео использует не H.264 кодек:\n\n{os.path.basename(non_h264[0])}\n\nКонвертировать сейчас в H.264?"
        else:
            names = "\n".join(f"• {os.path.basename(f)}" for f in non_h264[:10])
            if len(non_h264) > 10:
                names += f"\n... и ещё {len(non_h264) - 10}"
            msg = f"Следующие видео требуют перекодирования в H.264:\n\n{names}\n\nПерекодировать на GPU NVIDIA?"
        
        reply = QMessageBox.question(self, "Перекодирование H.264 (NVIDIA GPU)", msg,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            for fp in non_h264:
                self._start_conversion(fp)

    def _start_conversion(self, filepath: str):
        fake_id = "conv_" + str(uuid.uuid4())[:6]
        self.queue_widget.add_item(fake_id, os.path.basename(filepath))
        self.queue_widget.update_status(fake_id, "Конвертация (NVIDIA GPU)...")

        worker = ConvertWorker(filepath, self.settings)
        worker.progress.connect(lambda fp, pct, fid=fake_id: self.queue_widget.update_progress(fid, pct, "—", "—"))
        worker.finished.connect(lambda fp, out, ok, err, fid=fake_id: self._on_conv_finished(fid, fp, out, ok, err))
        self._conv_workers[filepath] = worker
        worker.start()
        logger.info(f"Started GPU conversion: {filepath}")

    def _on_conv_finished(self, fake_id: str, filepath: str, out_path: str, success: bool, error: str):
        self._item_paths[fake_id] = out_path or filepath or ""
        self._item_errors[fake_id] = error or ""
        self.queue_widget.set_result(fake_id, out_path or filepath or "", error or "")
        self.queue_widget.set_finished(fake_id, success)
        if success:
            self.queue_widget.update_status(fake_id, "Завершено")
            self.status_label.setText(f"Конвертация завершена: {os.path.basename(out_path)}")
            self._update_disk_space()
            if self.settings.get("notify_processing_finished", True):
                self._notify("Обработка завершена", os.path.basename(out_path or filepath or "Файл готов"))
        else:
            self.queue_widget.update_status(fake_id, "Ошибка")
            QMessageBox.critical(self, "Ошибка конвертации", f"Не удалось конвертировать:\n{error}")

    def _on_settings_changed(self, new_settings: dict):
        self.settings = new_settings
        self._apply_style()
        self.folder_display.setText(self.settings.get("download_folder", "C:\\"))
        if hasattr(self, 'quick_auto_convert_switch'):
            self.quick_auto_convert_switch.setChecked(self.settings.get("auto_convert", True))
        self._sync_quick_controls()
        self._apply_language()
        self._update_disk_space()
        self._start_next_downloads()
        self.status_label.setText(translate("Настройки сохранены", self.settings.get("language", "en")))
        logger.info("Settings updated")

