"""four-sg-proxy v3 (2026-10-25).
Same restriction as v2: only https://four.meme / www.four.meme.
Adds POST forwarding: POST /post?u=<four.meme URL> forwards the request body
to that URL and returns {ok, status, body}. Used for four.meme API calls
(e.g. wallet-direct sign, presale/buy) that the GET-only v2 could not make.
Upstream 4xx/5xx responses are returned as-is (status + body), not as proxy
errors, so API error codes stay visible to the caller.
Deploy: overwrite app.py in github.com/hzt48199-boop/four-sg-proxy, then
Render Dashboard -> four-sg-proxy -> Manual Deploy (Auto-Deploy has failed
to trigger before). Verify with / (v3), /extract, and /post (an invalid-body
probe should return an upstream error, not a success).
"""
import json
import os
import re
import urllib.parse
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ALLOWED_HOSTS = {"four.meme", "www.four.meme"}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
MARKERS = ["CREATE_PAUSED", "CREATE_ACTIVE", "TRADING", "Binance Agent",
           "暂无资料", "No data", "Agent", "1%", "token"]
MAX_BODY = 65536


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self._json(200, {"ok": True, "service": "four-sg-proxy-v3"})
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

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/post":
            self._json(404, {"ok": False, "error": "not found"})
            return
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
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length < 0 or length > MAX_BODY:
            self._json(413, {"ok": False, "error": "body too large"})
            return
        body = self.rfile.read(length) if length > 0 else b""
        ctype = self.headers.get("Content-Type") or "application/json"
        req = urllib.request.Request(
            raw, data=body,
            headers={"User-Agent": UA, "Content-Type": ctype},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                resp = r.read().decode("utf-8", "ignore")
                status = r.status
        except urllib.error.HTTPError as e:
            resp = e.read().decode("utf-8", "ignore")
            status = e.code
        except Exception as e:
            self._json(502, {"ok": False, "error": str(e)})
            return
        self._json(200, {"ok": True, "url": raw, "status": status,
                         "body": resp[:20000]})

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
