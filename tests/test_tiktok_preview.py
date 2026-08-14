import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen

from app.tiktok_preview import TikTokPreviewProxy


class TikTokPreviewProxyTests(unittest.TestCase):
    def test_proxy_forwards_auth_headers_and_byte_range(self):
        received = {}

        class RemoteHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                received["cookie"] = self.headers.get("Cookie")
                received["proxy_auth"] = self.headers.get("Proxy-Authorization")
                received["range"] = self.headers.get("Range")
                received["referer"] = self.headers.get("Referer")
                body = b"preview-bytes"
                self.send_response(206)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Range", f"bytes 0-{len(body) - 1}/{len(body)}")
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                return

        remote = ThreadingHTTPServer(("127.0.0.1", 0), RemoteHandler)
        remote_thread = threading.Thread(target=remote.serve_forever, daemon=True)
        remote_thread.start()
        proxy = TikTokPreviewProxy()
        try:
            remote_url = f"http://127.0.0.1:{remote.server_address[1]}/video.mp4"
            local_url = proxy.register(remote_url, {
                "Cookie": "sid_tt=authenticated",
                "Proxy-Authorization": "Basic secret",
                "Referer": "https://www.tiktok.com/",
            })
            request = Request(local_url, headers={"Range": "bytes=0-12"})
            with urlopen(request, timeout=5) as response:
                self.assertEqual(response.status, 206)
                self.assertEqual(response.read(), b"preview-bytes")
            self.assertEqual(received, {
                "cookie": "sid_tt=authenticated",
                "proxy_auth": None,
                "range": "bytes=0-12",
                "referer": "https://www.tiktok.com/",
            })
        finally:
            proxy.close()
            remote.shutdown()
            remote.server_close()
            remote_thread.join(timeout=2)

    def test_proxy_rejects_non_http_preview_urls(self):
        proxy = TikTokPreviewProxy()
        try:
            with self.assertRaises(ValueError):
                proxy.register("file:///C:/secret.mp4", {})
            with self.assertRaises(ValueError):
                proxy.register("ftp://example.invalid/video.mp4", {})
        finally:
            proxy.close()


if __name__ == "__main__":
    unittest.main()
