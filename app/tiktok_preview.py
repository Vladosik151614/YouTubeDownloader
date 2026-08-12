"""Authenticated localhost proxy used by the muted TikTok hover preview."""
from __future__ import annotations

import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from curl_cffi import requests


class TikTokPreviewProxy:
    """Relay media ranges while keeping TikTok headers and cookies off the UI URL."""

    def __init__(self):
        self._routes: dict[str, tuple[str, dict[str, str]]] = {}
        self._lock = threading.Lock()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_HEAD(self):
                self._relay(head_only=True)

            def do_GET(self):
                self._relay(head_only=False)

            def _relay(self, *, head_only: bool):
                token = self.path.partition("?")[0].removeprefix("/preview/")
                with owner._lock:
                    route = owner._routes.get(token)
                if not route:
                    self.send_error(404)
                    return
                remote_url, saved_headers = route
                headers = dict(saved_headers)
                if self.headers.get("Range"):
                    headers["Range"] = self.headers["Range"]
                headers.setdefault("Accept", "*/*")
                try:
                    method = requests.head if head_only else requests.get
                    response = method(
                        remote_url,
                        headers=headers,
                        timeout=25,
                        impersonate="chrome131",
                        stream=not head_only,
                    )
                    try:
                        if response.status_code >= 400:
                            raise RuntimeError(f"preview HTTP {response.status_code}")
                        self.send_response(response.status_code)
                        for name in (
                            "Content-Type", "Content-Length", "Content-Range",
                            "Accept-Ranges", "ETag", "Last-Modified",
                        ):
                            value = response.headers.get(name)
                            if value:
                                self.send_header(name, value)
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        if head_only:
                            return
                        for chunk in response.iter_content():
                            if chunk:
                                self.wfile.write(chunk)
                    finally:
                        response.close()
                except (BrokenPipeError, ConnectionResetError):
                    return
                except Exception:
                    if not self.wfile.closed:
                        try:
                            self.send_error(502)
                        except (BrokenPipeError, ConnectionResetError):
                            pass

            def log_message(self, *_args):
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def register(self, remote_url: str, headers: dict[str, str]) -> str:
        token = uuid.uuid4().hex
        safe_headers = {
            str(key): str(value) for key, value in headers.items()
            if value is not None and str(key).lower() not in {"host", "content-length", "connection"}
        }
        with self._lock:
            self._routes = {token: (remote_url, safe_headers)}
        host, port = self._server.server_address
        return f"http://{host}:{port}/preview/{token}"

    def close(self):
        with self._lock:
            self._routes.clear()
        self._server.shutdown()
        self._server.server_close()
        if self._thread.is_alive():
            self._thread.join(timeout=2)
