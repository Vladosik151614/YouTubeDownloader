"""Standalone local-video upscale and profile conversion page."""
from __future__ import annotations
from app.upscale_info import _format_video_info, _codec_label

import os

from PySide6.QtCore import QUrl, Signal, QObject, SIGNAL, Slot, Qt
from PySide6.QtGui import QFont
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QComboBox,
    QCheckBox,
    QApplication,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.converter import ConvertWorker, has_video_stream, probe_codec, probe_video_info
from app.thread_shutdown import cancel_and_wait_bounded


VIDEO_EXTENSIONS = (".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".ts")






class _VideoPreview(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("smart_card")
        self._path = ""
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._audio.setMuted(True)
        self._player.setAudioOutput(self._audio)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        label = QLabel(title)
        label.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        layout.addWidget(label)

        self.video = QVideoWidget()
        self.video.setMinimumHeight(220)
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._player.setVideoOutput(self.video)
        layout.addWidget(self.video, 1)

        self.info_label = QLabel("Файл не выбран")
        self.info_label.setObjectName("subtle")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        actions = QHBoxLayout()
        self.play_btn = QPushButton("▶ Смотреть")
        self.play_btn.clicked.connect(self._toggle)
        self.play_btn.setEnabled(False)
        actions.addWidget(self.play_btn)
        self.open_btn = QPushButton("Папка")
        self.open_btn.clicked.connect(self._open_folder)
        self.open_btn.setEnabled(False)
        actions.addWidget(self.open_btn)
        actions.addStretch()
        layout.addLayout(actions)

    def set_file(self, path: str, *, autoplay: bool = False):
        self._path = path if path and os.path.isfile(path) else ""
        self.info_label.setText(_format_video_info(self._path))
        enabled = bool(self._path)
        self.play_btn.setEnabled(enabled)
        self.open_btn.setEnabled(enabled)
        if enabled:
            self._player.setSource(QUrl.fromLocalFile(os.path.abspath(self._path)))
            if autoplay:
                self.play()
            else:
                self.play_btn.setText("▶ Смотреть")
        else:
            self.release_file()

    def release_file(self):
        self._player.stop()
        self._player.setSource(QUrl())
        self.play_btn.setText("▶ Смотреть")

    def play(self):
        if not self._path:
            return
        self._audio.setMuted(True)
        self._player.play()
        self.play_btn.setText("⏸ Пауза")

    def _toggle(self):
        if not self._path:
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self.play_btn.setText("▶ Смотреть")
        else:
            self.play()

    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self._path:
            self._player.setPosition(0)
            self.play()

    def _open_folder(self):
        if self._path:
            os.startfile(os.path.dirname(os.path.abspath(self._path)))


class UpscalePage(QWidget):
    """User-facing page for local files: source video -> improved/profile output."""

    status_changed = Signal(str)
    finished = Signal(str, bool, str)

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = dict(settings)
        self.source_path = ""
        self.result_path = ""
        self.output_folder = ""
        self._worker: ConvertWorker | None = None
        self._live_processing_threads = set()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._stop_processing_threads)
        self._build_ui()
        self._load_defaults()

    def set_base_settings(self, settings: dict):
        self.settings = dict(settings)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(12)

        title = QLabel("Upscale · улучшение локального видео")
        title.setObjectName("section_title")
        title.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        root.addWidget(title)

        subtitle = QLabel(
            "Выберите обычный видеофайл с диска, задайте 2K/4K, FPS, контейнер и кодек. "
            "После обработки можно сравнить исходник и результат."
        )
        subtitle.setObjectName("subtle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        controls = QFrame()
        controls.setObjectName("tool_band")
        grid = QGridLayout(controls)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        self.file_label = QLabel("Файл не выбран")
        self.file_label.setObjectName("subtle")
        self.file_label.setWordWrap(True)
        choose_btn = QPushButton("Выбрать видео")
        choose_btn.setObjectName("primary_btn")
        choose_btn.clicked.connect(self.choose_file)
        grid.addWidget(choose_btn, 0, 0)
        grid.addWidget(self.file_label, 0, 1, 1, 5)

        self.folder_label = QLabel("Папка результата: рядом с исходником")
        self.folder_label.setObjectName("subtle")
        self.folder_label.setWordWrap(True)
        folder_btn = QPushButton("Выбрать папку")
        folder_btn.clicked.connect(self.choose_output_folder)
        open_folder_btn = QPushButton("Открыть папку")
        open_folder_btn.clicked.connect(self.open_output_folder)
        grid.addWidget(folder_btn, 1, 0)
        grid.addWidget(self.folder_label, 1, 1, 1, 4)
        grid.addWidget(open_folder_btn, 1, 5)

        self.target_combo = QComboBox()
        self.target_combo.addItems(["2K · 1440p", "4K · 2160p", "Full HD · 1080p"])
        grid.addWidget(QLabel("Цель:"), 2, 0)
        grid.addWidget(self.target_combo, 2, 1)

        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["60 FPS", "30 FPS", "Не менять FPS"])
        grid.addWidget(QLabel("FPS:"), 2, 2)
        grid.addWidget(self.fps_combo, 2, 3)

        self.container_combo = QComboBox()
        self.container_combo.addItems(["MP4", "MKV", "WebM"])
        grid.addWidget(QLabel("Контейнер:"), 2, 4)
        grid.addWidget(self.container_combo, 2, 5)

        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["H.264", "Оригинал", "VP9", "AV1"])
        grid.addWidget(QLabel("Кодек:"), 3, 0)
        grid.addWidget(self.codec_combo, 3, 1)

        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems(["Авто GPU", "CPU", "NVENC", "QSV", "AMF"])
        grid.addWidget(QLabel("Энкодер:"), 3, 2)
        grid.addWidget(self.encoder_combo, 3, 3)

        self.keep_originals_check = QCheckBox("Сохранить исходник")
        self.keep_originals_check.setChecked(True)
        grid.addWidget(self.keep_originals_check, 3, 4)

        self.start_btn = QPushButton("Улучшить видео")
        self.start_btn.setObjectName("primary_btn")
        self.start_btn.clicked.connect(self.start_processing)
        grid.addWidget(self.start_btn, 3, 5)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        grid.addWidget(self.progress, 4, 0, 1, 6)

        self.status_label = QLabel("Готово к выбору файла")
        self.status_label.setObjectName("subtle")
        self.status_label.setWordWrap(True)
        grid.addWidget(self.status_label, 5, 0, 1, 6)

        root.addWidget(controls)

        previews = QHBoxLayout()
        previews.setSpacing(12)
        self.before_preview = _VideoPreview("До")
        self.after_preview = _VideoPreview("После")
        previews.addWidget(self.before_preview, 1)
        previews.addWidget(self.after_preview, 1)
        root.addLayout(previews, 1)

    def _load_defaults(self):
        self.target_combo.setCurrentIndex({"1440": 0, "2160": 1, "1080": 2}.get(
            str(self.settings.get("upscale_target", "1440")), 0
        ))
        self.fps_combo.setCurrentIndex({"60": 0, "30": 1}.get(
            str(self.settings.get("fps_limit", "60")), 0
        ))
        self.container_combo.setCurrentIndex({"mp4": 0, "mkv": 1, "webm": 2}.get(
            str(self.settings.get("container", "mp4")).lower(), 0
        ))
        self.codec_combo.setCurrentIndex({"h264": 0, "original": 1, "vp9": 2, "av1": 3}.get(
            str(self.settings.get("default_codec", "h264")).lower(), 0
        ))
        self.encoder_combo.setCurrentIndex({
            "auto": 0, "libx264": 1, "h264_nvenc": 2, "h264_qsv": 3, "h264_amf": 4,
        }.get(str(self.settings.get("video_encoder", "auto")), 0))

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выбрать видео для upscale",
            os.path.expanduser("~"),
            "Видео (*.mp4 *.mkv *.webm *.mov *.avi *.m4v *.ts);;Все файлы (*.*)",
        )
        if path:
            self.set_source_file(path)

    def choose_output_folder(self):
        start_dir = self.output_folder or os.path.dirname(self.source_path) or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self, "Выбрать папку для результата Upscale", start_dir
        )
        if folder:
            self.set_output_folder(folder)

    def set_output_folder(self, folder: str) -> bool:
        if not folder:
            return False
        self.output_folder = os.path.abspath(folder)
        self.folder_label.setText(f"Папка результата: {self.output_folder}")
        return True

    def open_output_folder(self):
        folder = self.output_folder or os.path.dirname(self.source_path)
        if folder and os.path.isdir(folder):
            os.startfile(os.path.abspath(folder))

    def set_source_file(self, path: str) -> bool:
        if not os.path.isfile(path):
            self._set_status("Файл не найден.")
            return False
        if not path.lower().endswith(VIDEO_EXTENSIONS) or not has_video_stream(path):
            self._set_status("Выбранный файл не похож на видео.")
            return False
        self.source_path = os.path.abspath(path)
        self.result_path = ""
        if not self.output_folder:
            self.set_output_folder(os.path.dirname(self.source_path))
        self.file_label.setText(self.source_path)
        self.before_preview.set_file(self.source_path, autoplay=True)
        self.after_preview.set_file("")
        self.progress.setValue(0)
        self._set_status("Файл готов к обработке.")
        return True

    def build_processing_settings(self) -> dict:
        target_map = {0: "1440", 1: "2160", 2: "1080"}
        fps_map = {0: "60", 1: "30", 2: "original"}
        container_map = {0: "mp4", 1: "mkv", 2: "webm"}
        codec_map = {0: "h264", 1: "original", 2: "vp9", 3: "av1"}
        encoder_map = {
            0: ("auto", "gpu_auto"),
            1: ("libx264", "cpu_only"),
            2: ("h264_nvenc", "gpu_auto"),
            3: ("h264_qsv", "gpu_auto"),
            4: ("h264_amf", "gpu_auto"),
        }
        encoder, mode = encoder_map.get(self.encoder_combo.currentIndex(), ("auto", "gpu_auto"))
        return {
            **self.settings,
            "download_type": "video",
            "download_quality": target_map.get(self.target_combo.currentIndex(), "1440"),
            "upscale_to_profile": True,
            "upscale_target": target_map.get(self.target_combo.currentIndex(), "1440"),
            "fps_limit": fps_map.get(self.fps_combo.currentIndex(), "60"),
            "container": container_map.get(self.container_combo.currentIndex(), "mp4"),
            "default_codec": codec_map.get(self.codec_combo.currentIndex(), "h264"),
            "encoding_mode": mode,
            "video_encoder": encoder,
            "keep_originals": self.keep_originals_check.isChecked(),
            "output_folder": self.output_folder or os.path.dirname(self.source_path),
            "ask_before_codec_convert": False,
            "auto_convert": True,
        }

    def start_processing(self):
        if not self.source_path:
            QMessageBox.warning(self, "Upscale", "Сначала выберите видеофайл.")
            return False
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "Upscale", "Обработка уже запущена.")
            return False
        settings = self.build_processing_settings()
        self.start_btn.setEnabled(False)
        self.progress.setValue(0)
        self.before_preview.release_file()
        self.after_preview.release_file()
        QApplication.processEvents()
        self._set_status(
            "Обработка запущена: "
            f"{settings['upscale_target']}p · до {settings['fps_limit']} FPS · "
            f"{_codec_label(settings['default_codec'])} · {settings['container'].upper()}"
        )
        self._worker = ConvertWorker(self.source_path, settings, self)
        self._live_processing_threads.add(self._worker)
        connection = QObject.connect(self._worker, SIGNAL('finished()'), self._processing_thread_finished, Qt.QueuedConnection)
        if not connection:
            self._live_processing_threads.discard(self._worker)
            self._worker.deleteLater()
            self._worker = None
            self.start_btn.setEnabled(True)
            self._set_status('Не удалось запустить обработку видео.')
            return False
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()
        return True

    @Slot()
    def _processing_thread_finished(self):
        worker = self.sender()
        if worker is None:
            return
        self._finalize_processing_thread(worker)

    def _finalize_processing_thread(self, worker):
        if not worker.wait(100):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(50, lambda worker=worker: self._finalize_processing_thread(worker))
            return
        self._live_processing_threads.discard(worker)
        if self._worker is worker:
            self._worker = None
        worker.deleteLater()

    def _stop_processing_threads(self, *, wait_ms: int = 750):
        workers = list(self._live_processing_threads)
        still_running = cancel_and_wait_bounded(
            workers, label="upscale", wait_ms=wait_ms
        )
        self._live_processing_threads.intersection_update(still_running)

    def closeEvent(self, event):
        self._stop_processing_threads()
        if self._live_processing_threads:
            event.ignore()
            self._set_status("Отмена обработки выполняется; дождитесь остановки задачи.")
            return
        super().closeEvent(event)

    def _on_progress(self, _path: str, percent: float):
        self.progress.setValue(max(0, min(100, int(percent))))

    def _on_finished(self, src: str, out_path: str, success: bool, error: str):
        self.start_btn.setEnabled(True)
        if success and out_path and os.path.isfile(out_path):
            self.result_path = os.path.abspath(out_path)
            self.progress.setValue(100)
            self.before_preview.set_file(src if os.path.isfile(src) else "", autoplay=True)
            self.after_preview.set_file(self.result_path, autoplay=True)
            info = probe_video_info(self.result_path)
            fps = info.get("fps") or 0
            fps_text = f"{fps:.1f}".rstrip("0").rstrip(".") if fps else "—"
            self._set_status(
                "Готово: "
                f"{info.get('width', 0)}×{info.get('height', 0)} · "
                f"{fps_text} FPS · {probe_codec(self.result_path)}"
            )
        else:
            self.progress.setValue(0)
            self._set_status(f"Ошибка обработки: {error or 'неизвестная ошибка'}")
            QMessageBox.critical(
                self,
                "Ошибка Upscale",
                f"Не удалось обработать видео.\n\n{error or 'Подробностей нет.'}",
            )
        self.finished.emit(out_path or src, success, error or "")

    def _set_status(self, text: str):
        self.status_label.setText(text)
        self.status_changed.emit(text)
