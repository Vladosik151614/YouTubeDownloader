import os
from PySide6.QtWidgets import QFileDialog, QMessageBox
from app.logger import logger
from app.settings_manager import save_settings

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
