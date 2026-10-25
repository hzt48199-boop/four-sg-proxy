"""four-sg-proxy v2 (UNDEPLOYED DRAFT, 2026-10-25).
Same restriction as v1: only https://four.meme / www.four.meme.
Adds /extract: returns a slice of the fetched body (default 20000 chars),
keyword hit positions, and script srcs, so the mode page's token list and
embedded JSON can be read without a browser.
Deploy: overwrite app.py in github.com/hzt48199-boop/four-sg-proxy, then
Render Dashboard -> four-sg-proxy -> Manual Deploy (Auto-Deploy has failed
to trigger before). Verify with /extract on the mode page.
"""
import json
import os
import re
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ALLOWED_HOSTS = {"four.meme", "www.four.meme"}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
MARKERS = ["CREATE_PAUSED", "CREATE_ACTIVE", "TRADING", "Binance Agent",
           "暂无资料", "No data", "Agent", "1%", "token"]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self._json(200, {"ok": True, "service": "four-sg-proxy-v2"})
            return
        if parsed.path in ("/fetch", "/extract"):
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
            markers = {m: (m in body) for m in MARKERS}
            out = {"ok": True, "url": raw, "status": status,
                   "restricted": restricted, "length": len(body),
                   "markers": markers}
            if parsed.path == "/extract":
                try:
                    offset = int((qs.get("offset") or ["0"])[0])
                except ValueError:
                    offset = 0
                out["offset"] = offset
                out["slice"] = body[offset:offset + 20000]
                q = (qs.get("q") or [""])[0]
                if q:
                    out["query"] = q
                    out["hits"] = [m.start() for m in
                                   re.finditer(re.escape(q), body)][:20]
                out["scripts"] = re.findall(
                    r'src="([^"]+\.js[^"]*)"', body)[:50]
            else:
                out["snippet"] = body[:400]
            self._json(200, out)
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
