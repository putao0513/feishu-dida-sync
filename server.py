"""
[DEPRECATED] 本文件已废弃，请勿使用。
已替换为 GitHub Actions 后端定时同步方案（.github/workflows/sync.yml）。
本地 HTTP 服务不再维护，所有同步任务由 GitHub Actions 自动执行。
保留此文件仅供历史参考。
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import core

ROOT = Path(__file__).resolve().parent
SCRIPTS = {("/scriptcat/" + p.name): p for p in sorted((ROOT / "scriptcat").glob("*.user.js"))}


ALLOWED_ORIGINS = ("http://127.0.0.1:8765", "http://localhost:8765",
                   "chrome-extension://", "moz-extension://")


class Handler(BaseHTTPRequestHandler):
    def _origin_ok(self):
        o = self.headers.get("Origin")
        # 本地进程与 ScriptCat 的 GM_xmlhttpRequest 不携带站点 Origin；
        # 第三方网页的跨站请求一定带真实 Origin，不在白名单即拒绝。
        if not o or o == "null":
            return True
        return o.startswith(ALLOWED_ORIGINS)

    def _send(self, code, obj, ctype="application/json; charset=utf-8"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if self._origin_ok():
            o = self.headers.get("Origin")
            if o and o != "null":
                self.send_header("Access-Control-Allow-Origin", o)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        if not self._origin_ok():
            return self._send(403, {"error": "origin not allowed"})
        return self._send(204, b"")

    def do_GET(self):
        if not self._origin_ok():
            return self._send(403, {"error": "origin not allowed"})
        if self.path in ("/", "/index.html"):
            return self._send(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        path = self.path.split("?", 1)[0]
        if path in ("/scriptcat", "/scriptcat/"):
            return self._send(200, {"scripts": [{"name": p.name, "url": u} for u, p in SCRIPTS.items()]})
        script = SCRIPTS.get(path)
        if script:
            return self._send(200, script.read_bytes(), "application/javascript; charset=utf-8")
        if self.path == "/api/status":
            return self._send(200, core.status())
        if self.path == "/api/sync/preview":
            try:
                return self._send(200, core.sync_once(run=False))
            except Exception as e:
                return self._send(500, {"error": str(e)})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._origin_ok():
            return self._send(403, {"error": "origin not allowed"})
        n = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except Exception:
            body = {}
        if self.path == "/api/capture":
            try:
                return self._send(200, {"ok": True, **core.capture(body)})
            except Exception as e:
                return self._send(400, {"ok": False, "error": str(e)})
        if self.path == "/api/sync/run":
            if not body.get("confirm"):
                return self._send(400, {"ok": False, "error": "confirm:true is required"})
            try:
                return self._send(200, {"ok": True, **core.sync_once(run=True)})
            except Exception as e:
                return self._send(500, {"ok": False, "error": str(e)})
        return self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))


def main():
    port = core.cfg()["port"]
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("quick-capture ready: http://127.0.0.1:%d" % port)
    srv.serve_forever()


if __name__ == "__main__":
    main()
