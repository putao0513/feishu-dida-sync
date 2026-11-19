#!/usr/bin/env python3
# status: verified | 2026-11-17 已在真实滴答授权页跑通：换 token、列清单、创建任务并读回核对
import base64
import json
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = ROOT / "config.json"
AUTHORIZE = "https://dida365.com/oauth/authorize"
TOKEN_URL = "https://dida365.com/oauth/token"
SCOPE = "tasks:read tasks:write"
TIMEOUT = 3600  # 等待用户在浏览器完成登录与授权；回调服务退出时可用 code 子命令兜底


def load():
    return json.loads(CFG.read_text(encoding="utf-8"))


def save(c):
    CFG.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _form_post(url, form, basic=None):
    data = urllib.parse.urlencode(form).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if basic:
        headers["Authorization"] = "Basic " + base64.b64encode(basic.encode("utf-8")).decode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def api_get(path, token):
    base = load()["dida"]["api_base"].rstrip("/")
    req = urllib.request.Request(base + path,
                                 headers={"Authorization": "Bearer " + token}, method="GET")
    with urllib.request.urlopen(req, timeout=25) as r:
        raw = r.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def refresh_access_token():
    c = load()
    d = c["dida"]
    rt, cid, sec = d.get("refresh_token"), d.get("client_id"), d.get("client_secret")
    if not (rt and cid and sec):
        return None
    try:
        res = _form_post(TOKEN_URL, {"grant_type": "refresh_token",
                                     "refresh_token": rt, "scope": SCOPE},
                         basic=cid + ":" + sec)
    except Exception:
        return None
    if not res.get("access_token"):
        return None
    d["token"] = res["access_token"]
    if res.get("refresh_token"):
        d["refresh_token"] = res["refresh_token"]
    d["token_obtained_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save(c)
    return d["token"]


class _Handler(BaseHTTPRequestHandler):
    code = None
    state = None
    error = None
    error_desc = None

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path != "/callback":
            self.send_error(404)
            return
        q = urllib.parse.parse_qs(u.query)
        _Handler.code = (q.get("code") or [None])[0]
        _Handler.state = (q.get("state") or [None])[0]
        _Handler.error = (q.get("error") or [None])[0]
        _Handler.error_desc = (q.get("error_description") or [None])[0]
        body = "<!doctype html><meta charset=utf-8><body>授权完成，可关闭此窗口并返回终端。</body>"
        raw = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


def projects():
    d = load()["dida"]
    if not d.get("token"):
        print("暂无 access_token，请先运行：python oauth.py auth")
        return 1
    try:
        data = api_get("/project", d["token"])
    except urllib.error.HTTPError as e:
        print("读取清单失败 HTTP %s（401 表示令牌过期，重跑 auth）" % e.code)
        return 1
    except Exception as e:
        print("读取清单失败：%s（若企业网络需代理，请检查 HTTPS_PROXY）" % str(e)[:160])
        return 1
    items = data if isinstance(data, list) else (data.get("projects") or data.get("data") or [])
    if not items:
        print("未返回任何清单")
        return 1
    print("\n可用清单：")
    for i, p in enumerate(items, 1):
        print("  %2d. %-34s %s" % (i, p.get("name") or "(无名)", p.get("id")))
    if not sys.stdin.isatty():
        print("\n非交互环境：把目标 id 手动填入 config.json 的 sync.project_id")
        return 0
    try:
        n = int((input("\n选择目标清单编号（0=跳过）：") or "0").strip())
    except (ValueError, EOFError):
        return 0
    if 1 <= n <= len(items):
        c = load()
        c["sync"]["project_id"] = items[n - 1]["id"]
        save(c)
        print("已写入 sync.project_id = %s" % c["sync"]["project_id"])
    return 0


def auth():
    c = load()
    d = c["dida"]
    cid, sec = d.get("client_id"), d.get("client_secret")
    uri = d.get("redirect_uri") or "http://127.0.0.1:38000/callback"
    if not (cid and sec):
        print("缺少 client_id / client_secret。请先：")
        print("  1) 打开 https://developer.dida365.com/manage 新建应用")
        print("  2) OAuth Redirect URL 填：%s" % uri)
        print("  3) 把 Client ID / Client Secret 填入 config.json 的 dida 段")
        return 1
    state = secrets.token_urlsafe(16)
    url = AUTHORIZE + "?" + urllib.parse.urlencode({
        "client_id": cid, "scope": SCOPE, "state": state,
        "redirect_uri": uri, "response_type": "code"})
    port = urllib.parse.urlparse(uri).port or 80
    srv = HTTPServer(("127.0.0.1", port), _Handler)
    srv.timeout = 3
    print("Redirect URI 必须与开发者中心完全一致：%s\n" % uri)
    print("授权 URL（若浏览器没自动打开，手动复制）：\n%s\n" % url)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    print("等待授权回调（最长 %d 秒）..." % TIMEOUT)
    deadline = time.time() + TIMEOUT
    while time.time() < deadline and _Handler.code is None and _Handler.error is None:
        srv.handle_request()
    srv.server_close()
    if _Handler.error:
        print("授权返回错误：%s %s" % (_Handler.error, _Handler.error_desc or ""))
        return 1
    if not _Handler.code:
        print("未收到有效回调。请确认：① 开发者中心 Redirect URL 与 %s 逐字符一致；"
              "② 授权页已用滴答账号登录并点了同意。" % uri)
        return 1
    if _Handler.state != state:
        print("state 校验失败，已中止（可能存在 CSRF 风险）")
        return 1
    return exchange_code(_Handler.code)


def exchange_code(code):
    """授权码换 token：自动回调与手动粘贴两种入口共用。"""
    d = load()["dida"]
    if not code:
        print("授权码为空")
        return 1
    try:
        res = _form_post(TOKEN_URL, {"code": code,
                                     "grant_type": "authorization_code",
                                     "scope": SCOPE, "redirect_uri": d.get("redirect_uri")},
                         basic=d["client_id"] + ":" + d["client_secret"])
    except urllib.error.HTTPError as e:
        print("换取令牌失败 HTTP %s：%s" % (e.code, e.read().decode("utf-8", "replace")[:300]))
        return 1
    except Exception as e:
        print("换取令牌失败：%s" % str(e)[:200])
        return 1
    tok = res.get("access_token")
    if not tok:
        print("令牌响应缺少 access_token：%s" % json.dumps(res, ensure_ascii=False)[:200])
        return 1
    c = load()
    c["dida"]["token"] = tok
    c["dida"]["refresh_token"] = res.get("refresh_token") or ""
    c["dida"]["token_obtained_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save(c)
    print("access_token 已写入 config.json（%d 字符，不显示明文）" % len(tok))
    print("refresh_token：%s" % ("有" if c["dida"]["refresh_token"] else "无"))
    print("dry_run 与 dida.enabled 未改动，真实写入仍需你确认")
    return projects()


def manual(raw):
    """回调服务已退出时的兜底：接受完整回调 URL 或纯 code。"""
    arg = (raw or "").strip()
    if arg.startswith("http") or "://" in arg:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(arg).query)
        code = (q.get("code") or [None])[0]
        state = (q.get("state") or [None])[0]
    else:
        code, state = arg, None
    if not code:
        print("未能解析出 code。请复制浏览器地址栏的完整 URL（形如 .../callback?code=xxx&state=xxx）")
        return 1
    print("手动模式：code 已解析（不显示明文），state=%s" % ("有" if state else "无"))
    print("提示：回调服务不在监听时无法做 state 校验，请确认该 URL 来自你本人刚才的授权。")
    return exchange_code(code)


def status():
    c = load()
    d = c["dida"]
    print("client_id      :", "已设置" if d.get("client_id") else "未设置")
    print("client_secret  :", "已设置" if d.get("client_secret") else "未设置")
    print("redirect_uri   :", d.get("redirect_uri") or "(未设置)")
    print("access_token   :", ("已设置 %d 字符" % len(d["token"])) if d.get("token") else "未设置")
    print("refresh_token  :", "有" if d.get("refresh_token") else "无")
    print("project_id     :", c["sync"].get("project_id") or "未设置")
    print("dry_run=%s  dida.enabled=%s" % (c["dry_run"], d.get("enabled")))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "auth":
        sys.exit(auth())
    if cmd == "projects":
        sys.exit(projects())
    if cmd == "code":
        if len(sys.argv) < 3:
            print("用法: python oauth.py code '<完整回调URL或code>'")
            sys.exit(1)
        sys.exit(manual(sys.argv[2]))
    if cmd == "status":
        status()
    else:
        print("用法: python oauth.py [status|auth|projects|code]")
