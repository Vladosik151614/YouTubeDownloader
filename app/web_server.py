"""
web_server.py — локальный браузерный интерфейс для YouTube Downloader.
"""
import json
import os
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import yt_dlp

from app.binary_manager import get_binary_path
from app.auth_manager import cookie_file_for_url, ensure_cookie_file_for_url, refresh_cookie_file_for_url
from app.downloader import YtDlpLogCollector, format_bytes, is_playlist
from app.history_store import add_history_entry
from app.logger import logger
from app.path_manager import service_output_folder
from app.proxy_config import proxy_url_from_settings
from app.settings_manager import APP_DATA_DIR, load_settings


TASKS = {}
TASKS_LOCK = threading.Lock()


HTML = r"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>YouTube Downloader</title>
  <style>
    :root { color-scheme: dark; font-family: "Segoe UI", Arial, sans-serif; }
    body { margin: 0; background: #15172a; color: #e8edf6; }
    .app { max-width: 1120px; margin: 0 auto; padding: 28px; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 22px; }
    h1 { font-size: 24px; margin: 0; color: #fff; }
    .badge { color: #65d6ff; font-weight: 700; }
    .panel { background: #1b213b; border: 1px solid #123b63; border-radius: 8px; padding: 18px; }
    textarea { width: 100%; min-height: 96px; box-sizing: border-box; resize: vertical; border: 1px solid #124d84; border-radius: 8px; background: #14213d; color: #fff; padding: 14px; font-size: 15px; outline: none; }
    textarea:focus { border-color: #ec4565; }
    .row { display: flex; gap: 12px; align-items: center; margin-top: 14px; flex-wrap: wrap; }
    button { border: 0; border-radius: 8px; background: #0d4a80; color: #fff; padding: 12px 18px; font-weight: 700; cursor: pointer; }
    button.primary { background: linear-gradient(90deg, #ef4768, #cb2f4d); min-width: 150px; }
    button:hover { filter: brightness(1.08); }
    .path { color: #65d6ff; word-break: break-all; }
    table { width: 100%; border-collapse: collapse; margin-top: 18px; overflow: hidden; border-radius: 8px; }
    th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #253455; font-size: 14px; vertical-align: top; }
    th { background: #0f3d6f; color: #aebbd2; }
    tr { background: #172444; }
    tr:nth-child(even) { background: #1b2b51; }
    .ok { color: #55d678; font-weight: 700; }
    .err { color: #ff5b6e; font-weight: 700; }
    .muted { color: #9aa9c5; }
    progress { width: 160px; accent-color: #ef4768; }
  </style>
</head>
<body>
  <main class="app">
    <header>
      <h1>▶ YouTube Downloader</h1>
      <div class="badge">Browser mode</div>
    </header>

    <section class="panel">
      <textarea id="urls" placeholder="Вставь одну или несколько поддерживаемых ссылок, каждую с новой строки"></textarea>
      <div class="row">
        <button class="primary" onclick="startDownload()">Добавить</button>
        <button onclick="clearDone()">Очистить завершённые</button>
        <span class="muted">Папка:</span>
        <span class="path" id="folder">...</span>
      </div>
    </section>

    <table>
      <thead>
        <tr>
          <th>Название</th>
          <th>Статус</th>
          <th>Прогресс</th>
          <th>Размер</th>
          <th>Скорость</th>
          <th>Ошибка</th>
        </tr>
      </thead>
      <tbody id="tasks"></tbody>
    </table>
  </main>
  <script>
    async function api(path, options) {
      const res = await fetch(path, options);
      if (!res.ok) throw new Error(await res.text());
      return await res.json();
    }
    async function startDownload() {
      const text = document.getElementById('urls').value.trim();
      if (!text) return;
      await api('/api/download', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({urls: text.split(/\n+/).map(x => x.trim()).filter(Boolean)})
      });
      document.getElementById('urls').value = '';
      await refresh();
    }
    async function clearDone() {
      await api('/api/clear', {method: 'POST'});
      await refresh();
    }
    function row(t) {
      const cls = t.status === 'Завершено' ? 'ok' : (t.status === 'Ошибка' ? 'err' : '');
      const pct = Math.max(0, Math.min(100, t.percent || 0));
      return `<tr>
        <td>${escapeHtml(t.title || t.url || '')}</td>
        <td class="${cls}">${escapeHtml(t.status || '')}</td>
        <td><progress max="100" value="${pct}"></progress> ${pct.toFixed(1)}%</td>
        <td>${escapeHtml(t.size || '—')}</td>
        <td>${escapeHtml(t.speed || '—')}</td>
        <td class="err">${escapeHtml(t.error || '')}</td>
      </tr>`;
    }
    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    }
    async function refresh() {
      const data = await api('/api/tasks');
      document.getElementById('folder').textContent = data.download_folder;
      document.getElementById('tasks').innerHTML = data.tasks.map(row).join('');
    }
    refresh();
    setInterval(refresh, 1500);
  </script>
</body>
</html>"""


def _task_update(task_id: str, **changes):
    with TASKS_LOCK:
        TASKS.setdefault(task_id, {}).update(changes)


def _snapshot_files(folder: str) -> set[str]:
    try:
        return {
            os.path.join(folder, name)
            for name in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, name))
        }
    except Exception:
        return set()


def _media_files(paths: set[str]) -> list[str]:
    exts = {".mp4", ".mkv", ".webm", ".m4a", ".mp3", ".opus", ".jpg", ".jpeg", ".png", ".webp", ".json", ".description", ".vtt", ".srt"}
    return sorted(
        path for path in paths
        if os.path.splitext(path)[1].lower() in exts and os.path.getsize(path) > 0
    )


def _rate_limit_bytes(value: str) -> int | None:
    limits = {
        "50m": 50 * 1024 * 1024 // 8,
        "25m": 25 * 1024 * 1024 // 8,
        "10m": 10 * 1024 * 1024 // 8,
        "4m": 4 * 1024 * 1024 // 8,
        "2m": 2 * 1024 * 1024 // 8,
    }
    return limits.get(value)


def _build_opts(task_id: str, url: str, folder: str, settings: dict, collector: YtDlpLogCollector):
    ffmpeg_bin = get_binary_path("ffmpeg")
    deno_bin = get_binary_path("deno")
    container = settings.get("container", "mp4")
    quality = str(settings.get("download_quality", "1080"))
    fps = str(settings.get("fps_limit", "best"))
    download_type = settings.get("download_type", "video")
    if download_type == "audio":
        fmt = "bestaudio/best"
    elif download_type in {"pictures", "documents"}:
        fmt = "best"
    else:
        height_filter = "" if quality == "best" else f"[height<={quality}]"
        fps_filter = "" if fps == "best" else f"[fps<={fps}]"
        media_filter = f"{height_filter}{fps_filter}"
        if container == "webm":
            fmt = (
                f"bestvideo[ext=webm]{media_filter}+bestaudio[ext=webm]/"
                f"bestvideo{media_filter}+bestaudio/"
                "best"
            )
        else:
            fmt = (
                f"bestvideo[ext=mp4]{media_filter}+bestaudio[ext=m4a]/"
                f"bestvideo[ext=mp4][vcodec^=avc]{media_filter}+bestaudio[ext=m4a]/"
                f"bestvideo{media_filter}+bestaudio/"
                "best[ext=mp4]/best"
            )

    if is_playlist(url) and settings.get("playlist_subfolders", True):
        filename = "%(playlist_index)03d - %(title)s.%(ext)s" if settings.get("playlist_numbering", True) else "%(title)s.%(ext)s"
        outtmpl = os.path.join(folder, "%(playlist_title)s", filename)
    else:
        outtmpl = os.path.join(folder, "%(title)s.%(ext)s")

    def progress_hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            percent = (done / total * 100) if total else 0
            _task_update(
                task_id,
                status="Загрузка...",
                percent=percent,
                speed=d.get("_speed_str") or "—",
                eta=d.get("_eta_str") or "—",
            )
        elif d.get("status") == "finished":
            _task_update(task_id, status="Обработка...")

    opts = {
        "format": fmt,
        "outtmpl": outtmpl,
        "progress_hooks": [progress_hook],
        "logger": collector,
        "merge_output_format": container,
        "skip_download": download_type in {"pictures", "documents"},
        "noplaylist": False,
        "ignoreerrors": True,
        "skip_unavailable_fragments": True,
        "fragment_retries": 10,
        "retries": 5,
        "extractor_retries": 3,
        "continuedl": True,
        "quiet": True,
        "no_warnings": False,
        "no_color": True,
        "source_address": "0.0.0.0",
        "ffmpeg_location": os.path.dirname(ffmpeg_bin) if os.path.isfile(ffmpeg_bin) else None,
    }
    if download_type == "pictures":
        opts.update({"writethumbnail": True, "writeinfojson": False})
    elif download_type == "documents":
        opts.update({"writedescription": True, "writeinfojson": True, "writesubtitles": True})
    rate_limit = _rate_limit_bytes(settings.get("speed_limit", "unlimited"))
    if rate_limit:
        opts["ratelimit"] = rate_limit
    proxy_url = proxy_url_from_settings(settings)
    if proxy_url:
        opts["proxy"] = proxy_url
    if settings.get("skip_duplicates", True):
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        opts["download_archive"] = os.path.join(APP_DATA_DIR, "download_archive.txt")
    if settings.get("embed_subtitles", False):
        opts.update({
            "writesubtitles": True,
            "writeautomaticsub": False,
            "subtitleslangs": ["all"],
            "embedsubtitles": True,
        })
    if os.path.isfile(deno_bin):
        opts["js_runtimes"] = {"deno": {"path": deno_bin}}
    cookies_file = cookie_file_for_url(url)
    if not cookies_file and settings.get("auto_export_cookies", True):
        cookies_file, auth_message = ensure_cookie_file_for_url(url)
        if auth_message:
            logger.info(f"[{task_id}] Auto cookie export: {auth_message}")
    if not cookies_file:
        cookies_file = settings.get("cookies_file", "")
    if cookies_file and os.path.isfile(cookies_file):
        opts["cookiefile"] = cookies_file
    cookies_browser = settings.get("cookies_from_browser", "")
    if cookies_browser:
        opts["cookiesfrombrowser"] = (cookies_browser, None, None, None)
    return opts


def _looks_like_auth_error(message: str, collector: YtDlpLogCollector) -> bool:
    text = " ".join([message] + collector.messages).lower()
    markers = [
        "sign in",
        "login",
        "not a bot",
        "confirm your age",
        "age-restricted",
        "private video",
        "members-only",
        "subscriber",
        "cookies",
        "forbidden",
        "http error 403",
        "your ip address is blocked",
    ]
    return any(marker in text for marker in markers)


def _download_task(task_id: str):
    task = TASKS[task_id]
    url = task["url"]
    settings = load_settings()
    folder = settings.get("download_folder") or os.path.join(os.path.expanduser("~"), "Videos", "youtube")
    if settings.get("auto_route_folders", True):
        folder = service_output_folder(folder, url, settings.get("download_type", "video"))
    os.makedirs(folder, exist_ok=True)

    for attempt in range(2):
        collector = YtDlpLogCollector(task_id)
        opts = _build_opts(task_id, url, folder, settings, collector)
        try:
            _task_update(task_id, status="Получение информации...")
            before = _snapshot_files(folder)
            playlist = False
            expected_files = []
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise RuntimeError("Ссылка недоступна или заблокирована")
                playlist = is_playlist(url) or info.get("_type") == "playlist"
                entries = [e for e in info.get("entries", []) if e] if playlist else []
                size = sum((e.get("filesize") or e.get("filesize_approx") or 0) for e in entries) if playlist else (info.get("filesize") or info.get("filesize_approx") or 0)
                _task_update(
                    task_id,
                    title=info.get("title") or url,
                    size=format_bytes(size),
                    status="Загрузка...",
                )
                if not playlist:
                    filename = ydl.prepare_filename(info)
                    base = os.path.splitext(filename)[0]
                    expected_files = [base + ".mp4", filename, base + ".mkv", base + ".webm"]
                result = ydl.download([url])
                if result not in (None, 0):
                    raise RuntimeError(f"yt-dlp вернул код ошибки: {result}")
                if collector.errors:
                    raise RuntimeError(collector.errors[-1])

            new_files = _media_files(_snapshot_files(folder) - before)
            existing_expected = [path for path in expected_files if os.path.isfile(path) and os.path.getsize(path) > 0]
            if collector.errors and not new_files:
                raise RuntimeError(collector.errors[-1])
            if not playlist and not new_files and not existing_expected:
                raise RuntimeError("Загрузка закончилась без готового файла")
            files = new_files or existing_expected
            first_path = files[0] if files else folder
            add_history_entry(url, TASKS[task_id].get("title", url), first_path, True, "")
            _task_update(task_id, status="Завершено", percent=100.0, error="", files=files)
            return
        except Exception as exc:
            message = str(exc)
            if (
                attempt == 0
                and settings.get("auto_export_cookies", True)
                and _looks_like_auth_error(message, collector)
            ):
                _task_update(task_id, status="Обновление доступа...")
                cookies_file, auth_message = refresh_cookie_file_for_url(url)
                if auth_message:
                    logger.info(f"[{task_id}] Auth refresh: {auth_message}")
                if cookies_file:
                    continue
            logger.error(f"[{task_id}] Browser download failed: {message}")
            add_history_entry(url, TASKS[task_id].get("title", url), "", False, message)
            _task_update(task_id, status="Ошибка", error=message)
            return


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data):
        self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/tasks":
            settings = load_settings()
            with TASKS_LOCK:
                tasks = list(TASKS.values())
            self._json(200, {"download_folder": settings.get("download_folder"), "tasks": tasks})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length) or b"{}")
        if path == "/api/download":
            urls = payload.get("urls") or []
            created = []
            for url in urls:
                if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                    continue
                task_id = str(uuid.uuid4())[:8]
                with TASKS_LOCK:
                    TASKS[task_id] = {
                        "id": task_id,
                        "url": url,
                        "title": url,
                        "status": "Ожидание",
                        "percent": 0.0,
                        "size": "—",
                        "speed": "—",
                        "eta": "—",
                        "error": "",
                    }
                thread = threading.Thread(target=_download_task, args=(task_id,), daemon=True)
                thread.start()
                created.append(task_id)
            self._json(200, {"created": created})
            return
        if path == "/api/clear":
            with TASKS_LOCK:
                for task_id in [
                    task_id for task_id, task in TASKS.items()
                    if task.get("status") in {"Завершено", "Ошибка"}
                ]:
                    TASKS.pop(task_id, None)
            self._json(200, {"ok": True})
            return
        self._json(404, {"error": "not found"})

    def log_message(self, format, *args):
        logger.debug("Browser UI: " + format % args)


def run_browser_server(host="127.0.0.1", port=8765, open_browser=True):
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    logger.info(f"Browser UI started: {url}")
    print(f"YouTube Downloader browser mode: {url}")
    server.serve_forever()
