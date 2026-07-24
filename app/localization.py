"""
localization.py - lightweight runtime translations for visible Qt text.
"""
from PySide6.QtWidgets import QAbstractButton, QComboBox, QGroupBox, QLabel, QLineEdit, QTableWidget, QTabWidget


TRANSLATIONS = {
    "en": {
        "Готов к загрузке": "Ready",
        "Диск: —": "Disk: -",
        "Загрузка": "Downloads",
        "Настройки": "Settings",
        "История": "History",
        "Аккаунты": "Accounts",
        "Загрузка видео, музыки и плейлистов": "Video, Music And Playlist Downloads",
        "Поддержка видео, музыки, плейлистов, каналов и клипов": "Video, music, playlists, channels and clips",
        "Вставить ссылку": "Paste Link",
        "Добавить": "Add",
        "Проверить": "Check",
        "Профиль загрузки": "Download Profile",
        "Качество": "Quality",
        "Контейнер": "Container",
        "Энкодер": "Encoder",
        "Папка:": "Folder:",
        "Изменить": "Change",
        "Открыть": "Open",
        "Очистить": "Clear",
        "Очередь загрузок": "Download Queue",
        "Основные": "General",
        "Формат": "Format",
        "Плейлисты": "Playlists",
        "Соединение": "Connection",
        "Уведомления": "Notifications",
        "Доступ": "Access",
        "Разработчик": "Developer",
        "Сохранить": "Save",
        "Приложение": "Application",
        "Папка": "Folder",
        "Обзор": "Browse",
        "Тема:": "Theme:",
        "Язык:": "Language:",
        "Тип:": "Type:",
        "Кадры:": "FPS:",
        "Режим:": "Mode:",
        "Доступно:": "Available:",
        "Скорость и сеть": "Speed And Network",
        "Одновременно:": "Concurrent:",
        "Лимит:": "Limit:",
        "Сеть:": "Network:",
        "Проверить скорость": "Check Speed",
        "Сервер:": "Server:",
        "Порт:": "Port:",
        "Логин:": "Login:",
        "Пар" + "оль:": "Pass" + "word:",
        "Аккаунты и доступ": "Accounts And Access",
        "Режим разработчика": "Developer Mode",
        "Диагностика": "Diagnostics",
        "Система": "System",
        "Ручной доступ": "Manual Access",
        "Система загрузки": "Download System",
        "Обновить": "Update",
        "Ошибка загрузки": "Download Error",
        "Скопировать отчет": "Copy Report",
        "Открыть GitHub": "Open GitHub",
        "История загрузок": "Download History",
        "Локальная история хранится в AppData и не попадает в GitHub.": "Local history is stored on this computer and is not included in source code.",
        "Дата": "Date",
        "Источник": "Source",
        "Название": "Title",
        "Статус": "Status",
        "Действия": "Actions",
        "Размер": "Size",
        "Прогресс": "Progress",
        "Скорость": "Speed",
        "Ожидание": "Waiting",
        "Получение информации...": "Reading Info...",
        "Загрузка...": "Downloading...",
        "Обработка...": "Processing...",
        "Конвертация...": "Converting...",
        "Пауза": "Paused",
        "Завершено": "Done",
        "Отменено": "Canceled",
        "Ошибка": "Error",
        "Готово": "Done",
        "Активно, данные доступа:": "Active, access data:",
        "Не подключено": "Not Connected",
    },
    "de": {
        "Готов к загрузке": "Bereit",
        "Загрузка": "Downloads",
        "Настройки": "Einstellungen",
        "История": "Verlauf",
        "Аккаунты": "Konten",
        "Загрузка видео, музыки и плейлистов": "Videos, Musik und Playlists herunterladen",
        "Вставить ссылку": "Link einfugen",
        "Добавить": "Hinzufugen",
        "Проверить": "Prufen",
        "Профиль загрузки": "Download-Profil",
        "Качество": "Qualitat",
        "Контейнер": "Container",
        "Энкодер": "Encoder",
        "Папка:": "Ordner:",
        "Изменить": "Andern",
        "Открыть": "Offnen",
        "Очистить": "Leeren",
        "Очередь загрузок": "Download-Warteschlange",
        "Основные": "Allgemein",
        "Формат": "Format",
        "Плейлисты": "Playlists",
        "Соединение": "Verbindung",
        "Уведомления": "Benachrichtigungen",
        "Доступ": "Zugriff",
        "Разработчик": "Entwickler",
        "Сохранить": "Speichern",
        "Проверить скорость": "Tempo prufen",
        "Аккаунты и доступ": "Konten und Zugriff",
        "Режим разработчика": "Entwicklermodus",
        "Диагностика": "Diagnose",
        "Система": "System",
        "Система загрузки": "Download-System",
        "Обновить": "Aktualisieren",
        "История загрузок": "Download-Verlauf",
        "Дата": "Datum",
        "Источник": "Quelle",
        "Название": "Titel",
        "Статус": "Status",
        "Действия": "Aktionen",
        "Размер": "Grosse",
        "Прогресс": "Fortschritt",
        "Скорость": "Tempo",
        "Ожидание": "Warten",
        "Загрузка...": "Laden...",
        "Обработка...": "Verarbeitung...",
        "Пауза": "Pause",
        "Завершено": "Fertig",
        "Отменено": "Abgebrochen",
        "Ошибка": "Fehler",
    },
    "it": {
        "Готов к загрузке": "Pronto",
        "Загрузка": "Download",
        "Настройки": "Impostazioni",
        "История": "Cronologia",
        "Аккаунты": "Account",
        "Загрузка видео, музыки и плейлистов": "Download di video, musica e playlist",
        "Вставить ссылку": "Incolla link",
        "Добавить": "Aggiungi",
        "Проверить": "Controlla",
        "Профиль загрузки": "Profilo download",
        "Качество": "Qualita",
        "Контейнер": "Contenitore",
        "Энкодер": "Encoder",
        "Папка:": "Cartella:",
        "Изменить": "Cambia",
        "Открыть": "Apri",
        "Очистить": "Pulisci",
        "Очередь загрузок": "Coda download",
        "Основные": "Generale",
        "Формат": "Formato",
        "Плейлисты": "Playlist",
        "Соединение": "Connessione",
        "Уведомления": "Notifiche",
        "Доступ": "Accesso",
        "Разработчик": "Sviluppatore",
        "Сохранить": "Salva",
        "Проверить скорость": "Test velocita",
        "Аккаунты и доступ": "Account e accesso",
        "Режим разработчика": "Modalita sviluppatore",
        "Диагностика": "Diagnostica",
        "Система": "Sistema",
        "Система загрузки": "Sistema download",
        "Обновить": "Aggiorna",
        "История загрузок": "Cronologia download",
        "Дата": "Data",
        "Источник": "Fonte",
        "Название": "Titolo",
        "Статус": "Stato",
        "Действия": "Azioni",
        "Размер": "Dimensione",
        "Прогресс": "Avanzamento",
        "Скорость": "Velocita",
        "Ожидание": "In attesa",
        "Загрузка...": "Download...",
        "Обработка...": "Elaborazione...",
        "Пауза": "Pausa",
        "Завершено": "Completato",
        "Отменено": "Annullato",
        "Ошибка": "Errore",
    },
}


def _source_text(text: str) -> str:
    for mapping in TRANSLATIONS.values():
        for source, translated in mapping.items():
            if text == translated:
                return source
    return text


def translate(text: str, language: str) -> str:
    source = _source_text(text)
    return TRANSLATIONS.get(language, {}).get(source, source)


def apply_translations(root, language: str) -> None:
    for label in root.findChildren(QLabel):
        label.setText(translate(label.text(), language))
    for button in root.findChildren(QAbstractButton):
        button.setText(translate(button.text(), language))
        button.setToolTip(translate(button.toolTip(), language))
    for group in root.findChildren(QGroupBox):
        group.setTitle(translate(group.title(), language))
    for edit in root.findChildren(QLineEdit):
        edit.setPlaceholderText(translate(edit.placeholderText(), language))
    for tabs in root.findChildren(QTabWidget):
        for index in range(tabs.count()):
            tabs.setTabText(index, translate(tabs.tabText(index), language))
    for combo in root.findChildren(QComboBox):
        for index in range(combo.count()):
            combo.setItemText(index, translate(combo.itemText(index), language))
    for table in root.findChildren(QTableWidget):
        for index in range(table.columnCount()):
            item = table.horizontalHeaderItem(index)
            if item:
                item.setText(translate(item.text(), language))
