"""User-facing classification of download failures.

Technical text is deliberately kept separate from the short explanation so the UI
can help a non-technical user without losing diagnostics for a support report.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DownloadErrorInfo:
    category: str
    title: str
    message: str
    actions: tuple[str, ...]
    technical_detail: str
    retryable: bool = True

    def user_text(self) -> str:
        actions = "\n".join(f"{index}. {action}" for index, action in enumerate(self.actions, 1))
        return f"{self.title}. {self.message}" + (f"\n\nЧто можно сделать:\n{actions}" if actions else "")


def classify_download_error(raw_message: str) -> DownloadErrorInfo:
    raw = str(raw_message or "Неизвестная ошибка").strip()
    text = raw.lower()

    def result(category: str, title: str, message: str, *actions: str, retryable: bool = True):
        return DownloadErrorInfo(category, title, message, tuple(actions), raw, retryable)

    if "could not copy chrome cookie database" in text or (
        "permission denied" in text and ("network\\cookies" in text or "network/cookies" in text)
    ):
        return result(
            "cookies_locked", "Не удалось прочитать данные входа Chrome",
            "Chrome не дал приложению доступ к файлу cookies.",
            "Закройте все окна Chrome и повторите загрузку.",
            "Либо выберите свежий cookies.txt в настройках доступа.",
        )
    if "failed to load cookies" in text or "failed to decrypt" in text:
        return result(
            "cookies_invalid", "Не удалось использовать данные входа",
            "Файл cookies повреждён, устарел или не может быть расшифрован.",
            "Обновите доступ к аккаунту в приложении.",
            "Либо выберите новый cookies.txt и повторите загрузку.",
        )
    if "sign in to confirm" in text or "not a bot" in text:
        return result(
            "youtube_verification", "YouTube запросил подтверждение",
            "YouTube не разрешил автоматическую загрузку без проверки пользователя.",
            "Обновите доступ к аккаунту в приложении.",
            "Отключите VPN или прокси, если они используются, и повторите попытку.",
        )
    if "http error 403" in text or "403: forbidden" in text or "403 forbidden" in text:
        return result(
            "access_forbidden", "YouTube отказал в доступе (ошибка 403)",
            "Ссылка может быть рабочей, но сервер не разрешил получить данные видео или плейлиста.",
            "Обновите доступ к аккаунту (cookies) и повторите загрузку.",
            "Временно отключите VPN или прокси либо попробуйте другую сеть.",
            "Если ошибка появилась только что, подождите несколько минут и повторите.",
        )
    if "private video" in text or "members-only" in text or "subscriber" in text:
        return result(
            "restricted_video", "Видео доступно не всем",
            "Для просмотра нужен подходящий аккаунт или подписка.",
            "Войдите в аккаунт, у которого есть доступ к видео.",
            "Обновите данные доступа в приложении.", retryable=False,
        )
    if "age-restricted" in text or "confirm your age" in text:
        return result(
            "age_restricted", "Для видео требуется подтверждение возраста",
            "YouTube разрешает загрузку этого видео только после входа в подходящий аккаунт.",
            "Войдите в аккаунт и обновите данные доступа в приложении.", retryable=False,
        )
    if "video unavailable" in text or "has been removed" in text or "is unavailable" in text:
        return result(
            "unavailable", "Видео недоступно",
            "Автор удалил или ограничил видео, либо оно недоступно в вашем регионе.",
            "Откройте ссылку в браузере и проверьте, воспроизводится ли видео.", retryable=False,
        )
    if "timed out" in text or "timeout" in text or "temporary failure" in text or "connection reset" in text:
        return result(
            "network", "Не удалось подключиться к серверу",
            "Соединение прервалось или сервер слишком долго не отвечал.",
            "Проверьте подключение к интернету.", "Повторите загрузку через несколько минут.",
        )
    if "no space left" in text or "disk full" in text:
        return result(
            "disk_full", "Недостаточно места на диске",
            "Для сохранения видео не хватает свободного пространства.",
            "Освободите место или выберите другую папку загрузки.", retryable=False,
        )
    if "permission denied" in text or "access is denied" in text:
        return result(
            "folder_access", "Нет доступа к папке загрузки",
            "Windows не разрешила создать или изменить файл в выбранной папке.",
            "Выберите папку внутри профиля пользователя и повторите загрузку.", retryable=False,
        )
    if "ffmpeg" in text:
        return result(
            "media_processing", "Не удалось обработать видео",
            "Ошибка возникла при объединении дорожек или перекодировании файла.",
            "Повторите загрузку.", "Если ошибка повторится, скопируйте отчёт для разработчика.",
        )
    return result(
        "download", "Не удалось завершить загрузку",
        "Приложение получило непредвиденный ответ при обработке ссылки.",
        "Проверьте ссылку и подключение к интернету.",
        "Повторите попытку; если ошибка сохранится, отправьте отчёт разработчику.",
    )
