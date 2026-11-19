import os, uuid
from PySide6.QtWidgets import QMessageBox
from app.converter import ConvertWorker, normalized_target_codec, target_resolution
from app.conversion_scan import ConversionScanWorker
from app.logger import logger

def _check_and_prompt_conversion(self, filepaths: list, is_playlist: bool = False, *, settings: dict | None = None, item_id: str = ""):
    settings = dict(settings or self.settings)
    if self._conversion_scans_closing:
        return
    worker = ConversionScanWorker(item_id, filepaths, settings, is_playlist)
    self._conversion_scans.add(worker)
    worker.scan_ready.connect(self._on_conversion_scan_ready)
    worker.finished.connect(lambda: self._conversion_scans.discard(worker))
    worker.start()


def _on_conversion_scan_ready(self, item_id: str, needs_conversion: list, settings: dict, is_playlist: bool):
    if self._conversion_scans_closing:
        return
    if not needs_conversion:
        return
    target_codec = normalized_target_codec(settings)
    codec_label = (
        "исходный" if target_codec == "original"
        else ("H.264" if target_codec == "h264" else target_codec.upper())
    )
    profile_label = (
        f"{settings.get('container', 'mp4').upper()} · {codec_label} · "
        f"{target_resolution(settings)}p · "
        f"до {settings.get('fps_limit', '60')} FPS"
    )
    should_convert = True
    if settings.get("ask_before_codec_convert", True):
        if is_playlist:
            msg = (
                f"Плейлист скачан. Обработать файлов по активному профилю: "
                f"{len(needs_conversion)}.\n\nПрофиль: {profile_label}.\n"
                "Исходники будут удалены только после проверки готовых файлов."
            )
        elif len(needs_conversion) == 1:
            msg = (
                f"Видео скачано:\n\n{os.path.basename(needs_conversion[0])}\n\n"
                f"Применить активный профиль: {profile_label}?\n"
                "Исходник будет удалён только после проверки готового файла."
            )
        else:
            names = "\n".join(f"• {os.path.basename(f)}" for f in needs_conversion[:10])
            msg = f"Применить профиль {profile_label} к этим файлам?\n\n{names}"
        reply = QMessageBox.question(
            self,
            "Применение профиля загрузки",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        should_convert = reply == QMessageBox.StandardButton.Yes
    if should_convert:
        for fp in needs_conversion:
            self._start_conversion(fp, settings=settings, source_item_id=item_id)


def _start_conversion(self, filepath: str, *, settings: dict | None = None, source_item_id: str = ""):
    settings = dict(settings or self.settings)
    fake_id = "conv_" + str(uuid.uuid4())[:6]
    self.queue_widget.add_item(fake_id, os.path.basename(filepath))
    target_codec = "original" if settings.get("rotation_only") else normalized_target_codec(settings)
    codec_label = "H.264" if target_codec == "h264" else target_codec.upper()
    status = "Поворот видео..." if settings.get("rotation_only") else f"Перекодирование в {codec_label}..."
    self.queue_widget.update_status(fake_id, status)
    if hasattr(self.queue_widget, "set_target_codec"):
        self.queue_widget.set_target_codec(fake_id, target_codec)
    worker = ConvertWorker(filepath, settings)
    self._track_job_thread(worker)
    worker.progress.connect(lambda fp, pct, fid=fake_id: self.queue_widget.update_progress(fid, pct, "—", "—"))
    worker.finished.connect(lambda fp, out, ok, err, fid=fake_id, sid=source_item_id: self._on_conv_finished(fid, fp, out, ok, err, sid))
    self._conv_workers[filepath] = worker
    worker.start()
    logger.info(f"Started GPU conversion: {filepath}")


def _on_conv_finished(self, fake_id: str, filepath: str, out_path: str, success: bool, error: str, source_item_id: str = ""):
    self._item_paths[fake_id] = out_path or filepath or ""
    self._item_errors[fake_id] = error or ""
    self.queue_widget.set_result(fake_id, out_path or filepath or "", error or "")
    self.queue_widget.set_finished(fake_id, success)
    if success:
        actual_codec = probe_codec(out_path) if out_path else "unknown"
        if hasattr(self.queue_widget, "set_final_codec"):
            self.queue_widget.set_final_codec(fake_id, actual_codec)
            if source_item_id:
                self.queue_widget.set_final_codec(source_item_id, actual_codec)
        if out_path and os.path.isfile(out_path) and hasattr(self.queue_widget, "update_size_bytes"):
            self.queue_widget.update_size_bytes(fake_id, os.path.getsize(out_path))
        self.queue_widget.update_status(fake_id, "Завершено")
        self.status_label.setText(f"Конвертация завершена: {os.path.basename(out_path)}")
        self._update_disk_space()
        if self.settings.get("notify_processing_finished", True):
            self._notify("Обработка завершена", os.path.basename(out_path or filepath or "Файл готов"))
    else:
        self.queue_widget.update_status(fake_id, "Ошибка")
        QMessageBox.critical(self, "Ошибка конвертации", f"Не удалось конвертировать:\n{error}")



from PySide6.QtCore import QObject, SIGNAL, Qt, QTimer
from app.thread_shutdown import cancel_and_wait_bounded

def _stop_conversion_scans(self, *, wait_ms: int = 750):
    self._conversion_scans_closing = True
    workers = list(self._conversion_scans)
    still_running = cancel_and_wait_bounded(
        workers, label="conversion scan", wait_ms=wait_ms
    )
    # Retain live workers: deleting a QThread while it is running can abort
    # the process. Their native finished() signal removes them later.
    self._conversion_scans.intersection_update(still_running)


def _track_job_thread(self, worker):
    """Retain the wrapper until Qt's native, zero-argument finished signal."""
    self._live_job_threads.add(worker)
    connection = QObject.connect(worker, SIGNAL('finished()'), self._job_thread_finished, Qt.QueuedConnection)
    if not connection:
        self._live_job_threads.discard(worker)
        raise RuntimeError('Не удалось подключить завершение рабочего потока')


def _finalize_job_thread(self, worker):
    # QThread.finished() can precede the final native cleanup by a moment.
    # Bound the wait so a broken worker cannot freeze the GUI.
    if not worker.wait(100):
        QTimer.singleShot(50, lambda worker=worker: self._finalize_job_thread(worker))
        return
    self._live_job_threads.discard(worker)
    for path, current in list(self._conv_workers.items()):
        if current is worker:
            self._conv_workers.pop(path, None)


def _stop_job_threads(self, *, wait_ms: int = 750):
    workers = list(self._live_job_threads)
    still_running = cancel_and_wait_bounded(
        workers, label="download/conversion", wait_ms=wait_ms
    )
    # Keep live references until their native finished() callback.  This
    # makes closing bounded without ever destroying a running QThread.
    self._live_job_threads.intersection_update(still_running)
