"""four-sg-proxy: minimal Singapore-exit fetch service for four.meme pages.

Stdlib-only (no dependencies). Restricted to https://four.meme on purpose:
it is NOT an open proxy. Endpoints:
  GET /            -> {"ok": true}
  GET /fetch?u=<four.meme URL> -> JSON with status, restricted flag, length, snippet
Render start command: python app.py  (reads $PORT, default 10000)
"""

import json
import os
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ALLOWED_HOSTS = {"four.meme", "www.four.meme"}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self._json(200, {"ok": True, "service": "four-sg-proxy"})
            return
        if parsed.path == "/fetch":
            qs = urllib.parse.parse_qs(parsed.query)
            raw = (qs.get("u") or [""])[0]
            try:
                u = urllib.parse.urlparse(raw)
            except Exception:
                self._json(400, {"ok": False, "error": "bad url"})
                return
            if u.scheme != "https" or u.netloc not in ALLOWED_HOSTS:
                self._json(400, {"ok": False, "error": "only https://four.meme allowed"})
                return
            req = urllib.request.Request(raw, headers={"User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=25) as r:
                    body = r.read().decode("utf-8", "ignore")
                    status = r.status
            except Exception as e:
                self._json(502, {"ok": False, "error": str(e)})
                return
            restricted = "restricted" in body and "current location" in body
            markers = {m: (m in body) for m in
                       ["CREATE_PAUSED", "CREATE_ACTIVE", "TRADING",
                        "Binance Agent", "暂无资料", "No data"]}
            self._json(200, {
                "ok": True,
                "url": raw,
                "status": status,
                "restricted": restricted,
                "length": len(body),
                "markers": markers,
                "snippet": body[:400],
            })
            return
        self._json(404, {"ok": False, "error": "not found"})

    def _json(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
