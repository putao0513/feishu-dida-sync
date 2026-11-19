import hashlib
import json
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG_FILE = ROOT / "config.json"
STATE = ROOT / "state"
STATE.mkdir(exist_ok=True)
MAP_FILE = STATE / "mapping.json"
CAPTURED_FILE = STATE / "captured.json"

# ── 所有非敏感配置直接写死在此，无需 config.json ──
# 滴答凭据通过环境变量注入（GitHub Secrets），本地开发可用 config.json 或环境变量
_BUILTIN = {
    "identity": "user",
    "base_token": "DxI8bVCCMaehZwsXc1Qc9ptEnXe",
    "table_id": "tblqjWO6QRSikPZL",
    "table_name": "待办任务",
    "base_url": "https://chagee.feishu.cn/base/DxI8bVCCMaehZwsXc1Qc9ptEnXe",
    "dry_run": False,
    "port": 8765,
    "fields": {
        "title": "任务名称",
        "content": "任务描述",
        "url": "超链接",
        "due": "截止日期",
        "status": "状态",
        "disposition": "处置状态",
        "priority": "优先级",
        "business": "业务方",
    },
    "capture": {
        "default_status": "待办",
        "default_disposition": "有效",
        "default_priority": "中优先级",
    },
    "sync": {
        "filter": {
            "logic": "and",
            "conditions": [
                ["处置状态", "intersects", ["有效"]],
                ["状态", "disjoint", ["已完成"]],
            ],
        },
        "priority_map": {"高优先级": 5, "中优先级": 3, "低优先级": 1},
        "project_id": "",       # ← 填你的滴答清单项目 ID
        "dida_status_field": "",
    },
    "dida": {
        "api_base": "https://api.dida365.com/open/v1",
        "token": "",
        "refresh_token": "",
        "token_obtained_at": "",
        "client_id": "",        # ← 填你的滴答应用 Client ID
        "client_secret": "",
        "redirect_uri": "http://127.0.0.1:38000/callback",
        "enabled": True,
    },
}


def cfg():
    import os

    config = json.loads(json.dumps(_BUILTIN))  # deep copy

    # 本地 config.json（如存在）覆盖内置默认值
    if CFG_FILE.exists():
        try:
            local = json.loads(CFG_FILE.read_text(encoding="utf-8"))
            for k, v in local.items():
                if isinstance(v, dict) and isinstance(config.get(k), dict):
                    config[k].update(v)
                else:
                    config[k] = v
        except Exception:
            pass

    # 环境变量最高优先级——只覆盖敏感凭据（strip 清除尾部换行/空格）
    env_map = {
        "DIDA_TOKEN": ("dida", "token"),
        "DIDA_REFRESH_TOKEN": ("dida", "refresh_token"),
        "DIDA_CLIENT_ID": ("dida", "client_id"),
        "DIDA_CLIENT_SECRET": ("dida", "client_secret"),
        "DIDA_PROJECT_ID": ("sync", "project_id"),
        "FEISHU_APP_ID": ("feishu", "app_id"),
        "FEISHU_APP_SECRET": ("feishu", "app_secret"),
    }
    for env_key, (section, field) in env_map.items():
        val = os.getenv(env_key)
        if val:
            val = val.strip()
            config.setdefault(section, {})[field] = val

    return config


def _read(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 飞书 Base HTTP API（替代 lark-cli，适用于 GitHub Actions） ──

_feishu_token_cache = {"token": "", "expires": 0.0}


def _feishu_token():
    import os
    now = time.time()
    if _feishu_token_cache["token"] and _feishu_token_cache["expires"] > now + 60:
        return _feishu_token_cache["token"]
    app_id = (os.getenv("FEISHU_APP_ID", "") or "").strip()
    app_secret = (os.getenv("FEISHU_APP_SECRET", "") or "").strip()
    if not app_id or not app_secret:
        raise RuntimeError("FEISHU_APP_ID / FEISHU_APP_SECRET 环境变量未设置")
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read().decode("utf-8"))
    if resp.get("code") != 0:
        raise RuntimeError("飞书认证失败: %s" % resp.get("msg", resp))
    _feishu_token_cache["token"] = resp["tenant_access_token"]
    _feishu_token_cache["expires"] = now + resp.get("expire", 7200)
    return _feishu_token_cache["token"]


def _feishu_api(method, path, body=None):
    token = _feishu_token()
    url = "https://open.feishu.cn/open-apis" + path
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json; charset=utf-8",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read().decode("utf-8"))
    if resp.get("code") != 0:
        raise RuntimeError("飞书 API %s: %s" % (resp.get("code"), resp.get("msg", "")))
    return resp.get("data", {})


def _convert_filter(f):
    op_map = {"intersects": "is", "disjoint": "isNot"}
    return {
        "conjunction": f.get("logic", "and"),
        "conditions": [
            {"field_name": c[0], "operator": op_map.get(c[1], c[1]), "value": c[2]}
            for c in f.get("conditions", [])
        ],
    }


def lark(args, payload=None):
    c = cfg()
    exe = shutil.which("lark-cli")
    if not exe:
        raise RuntimeError("lark-cli not found in PATH")
    cmd = [exe, "base"] + list(args) + ["--as", c["identity"]]
    tmp = None
    if payload is not None:
        tmp = STATE / (".payload-%d.json" % int(time.time() * 1000))
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        cmd = [("@" + str(tmp)) if x == "@PAYLOAD" else x for x in cmd]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=90)
        if r.returncode != 0:
            raise RuntimeError("lark-cli rc=%s: %s" % (r.returncode, (r.stderr or "")[:400]))
        data = json.loads(r.stdout)
        if data.get("ok") is False:
            raise RuntimeError("lark-cli: %s" % json.dumps(data, ensure_ascii=False)[:400])
        if "manifest_version" in data:
            return data
        return data.get("data", data)
    finally:
        if tmp and tmp.exists():
            tmp.unlink()


def _normalize_field(v):
    """飞书 API 文本字段返回 [{type,text}] 列表，需归一化为字符串"""
    if isinstance(v, list):
        if v and isinstance(v[0], dict):
            return "".join(seg.get("text", "") for seg in v)
        return v  # 多选字段本身就是字符串列表
    if isinstance(v, dict):
        return v.get("text", "") or v.get("link", "")
    return v


def feishu_list():
    c = cfg()
    app_token, table_id = c["base_token"], c["table_id"]
    flt = _convert_filter(c["sync"]["filter"])
    records, page_token = [], ""
    while True:
        path = "/bitable/v1/apps/%s/tables/%s/records/search?page_size=500" % (app_token, table_id)
        if page_token:
            path += "&page_token=" + page_token
        data = _feishu_api("POST", path, {"filter": flt, "automatic_fields": False})
        for item in data.get("items", []):
            row = {"record_id": item["record_id"]}
            for k, v in item.get("fields", {}).items():
                row[k] = _normalize_field(v)
            records.append(row)
        if not data.get("has_more") or not data.get("page_token"):
            break
        page_token = data["page_token"]
    return records


def build_fields(p):
    c = cfg()
    f, d = c["fields"], c["capture"]
    fields = {
        f["title"]: (p.get("title") or "").strip(),
        f["content"]: p.get("content") or "",
        f["status"]: [d["default_status"]],
        f["disposition"]: [d["default_disposition"]],
        f["priority"]: [p.get("priority") or d["default_priority"]],
    }
    if p.get("url"):
        fields[f["url"]] = p["url"]
    if p.get("due"):
        fields[f["due"]] = p["due"]
    if p.get("business"):
        fields[f["business"]] = [p["business"]]
    return fields


def feishu_create(fields, dry=None):
    c = cfg()
    dry_run = c["dry_run"] if dry is None else dry
    if dry_run:
        return {"dry_run": True, "record_id": None, "fields": fields}
    data = _feishu_api("POST",
        "/bitable/v1/apps/%s/tables/%s/records/batch_create" % (c["base_token"], c["table_id"]),
        {"records": [{"fields": fields}]})
    recs = data.get("records", [])
    return {"dry_run": False, "record_id": recs[0]["record_id"] if recs else None, "raw": data}


def capture(p):
    title = (p.get("title") or "").strip()
    if not title:
        raise ValueError("title is required")
    digest = hashlib.md5((title + "|" + (p.get("content") or "")).encode("utf-8")).hexdigest()
    seen = _read(CAPTURED_FILE, [])
    if digest in seen and not p.get("force"):
        return {"duplicate": True, "message": "same title+content already captured"}
    fields = build_fields(p)
    res = feishu_create(fields)
    if not res["dry_run"]:
        seen.append(digest)
        _write(CAPTURED_FILE, seen[-300:])
    return {"duplicate": False, "title": title, **res}


def _hash(row):
    c = cfg()
    f = c["fields"]
    keys = (f["title"], f["content"], f["due"], f["priority"], f["status"], f["disposition"])
    raw = json.dumps([row.get(k) for k in keys], ensure_ascii=False, sort_keys=True)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def normalize_due(v):
    import datetime
    import re
    if isinstance(v, (int, float)):
        tz = datetime.timezone(datetime.timedelta(hours=8))
        return datetime.datetime.fromtimestamp(v / 1000, tz).isoformat(timespec="seconds")
    return re.sub(r"\.\d{3}(?=[+-]\d{2}:?\d{2}|Z$)", "", str(v).strip())


def build_task(row, task_id=None):
    c = cfg()
    f, s = c["fields"], c["sync"]
    title = (row.get(f["title"]) or "").strip() or "(untitled)"
    desc = row.get(f["content"]) or ""
    ref = "[feishu] %s?table=%s  record_id=%s" % (c["base_url"], c["table_id"], row["record_id"])
    desc = (desc + "\n\n" + ref) if desc else ref
    pri = row.get(f["priority"]) or []
    if isinstance(pri, str):
        pri = [pri]
    task = {
        "title": title,
        "content": desc,
        "priority": s["priority_map"].get(pri[0] if pri else "", 0),
        "projectId": s["project_id"],
    }
    if row.get(f["due"]):
        task["dueDate"] = normalize_due(row[f["due"]])
    if task_id:
        task["id"] = task_id  # 滴答 OpenAPI 更新任务时 body 的 id 为必填
    return task


def dida_request(method, path, body=None, _retry=True):
    import urllib.error
    d = cfg()["dida"]
    if not d.get("token"):
        raise RuntimeError("dida.token is empty")

    def _call(token):
        req = urllib.request.Request(
            d["api_base"].rstrip("/") + path,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None,
            method=method,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else {}

    try:
        return _call(d["token"])
    except urllib.error.HTTPError as e:
        if e.code == 401 and _retry:
            from oauth import refresh_access_token
            fresh = refresh_access_token()
            if fresh:
                return _call(fresh)
            raise RuntimeError("dida token 已过期且无 refresh_token，请重新运行：python oauth.py auth") from e
        raise


def sync_once(run=False, limit=0):
    c = cfg()
    token_ok = bool(c["dida"].get("token")) and c["dida"].get("enabled")
    project_ok = bool(c["sync"].get("project_id"))
    dry = (not run) or c["dry_run"] or not token_ok or not project_ok
    rows = feishu_list()
    mapping = _read(MAP_FILE, {})
    plan = []
    blank = []
    for row in rows:
        rid = row["record_id"]
        if not (row.get(c["fields"]["title"]) or "").strip():
            blank.append(rid)
            continue
        h = _hash(row)
        m = mapping.get(rid)
        action = "skip" if m and m.get("hash") == h else ("update" if m else "create")
        plan.append({
            "record_id": rid,
            "title": row.get(c["fields"]["title"]),
            "action": action,
            "task_id": (m or {}).get("taskId"),
            "hash": h,
            "task": build_task(row, (m or {}).get("taskId")),
        })
    executed, errors = [], []
    exec_plan = plan[:limit] if limit and limit > 0 else plan
    if not dry:
        for item in exec_plan:
            if item["action"] == "skip":
                continue
            try:
                if item["action"] == "create":
                    res = dida_request("POST", "/task", item["task"])
                    tid = res.get("id")
                else:
                    tid = item["task_id"]
                    dida_request("POST", "/task/" + tid, item["task"])
                mapping[item["record_id"]] = {
                    "taskId": tid, "hash": item["hash"],
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                executed.append({"record_id": item["record_id"], "taskId": tid,
                                 "action": item["action"]})
            except Exception as e:
                errors.append({"record_id": item["record_id"], "error": str(e)[:200]})
        _write(MAP_FILE, mapping)
    return {
        "dry_run": dry,
        "scanned": len(rows),
        "blank_skipped": len(blank),
        "blank_ids": blank[:20],
        "counts": {a: sum(1 for x in plan if x["action"] == a) for a in ("create", "update", "skip")},
        "blockers": [b for b, ok in (("dida.token/enabled", token_ok),
                                     ("sync.project_id", project_ok),
                                     ("config.dry_run=false", not c["dry_run"])) if not ok],
        "plan": plan,
        "executed": executed,
        "errors": errors,
    }


def status():
    c = cfg()
    return {
        "base": c["base_url"], "table": c["table_name"], "table_id": c["table_id"],
        "dry_run": c["dry_run"], "port": c["port"],
        "lark_cli": bool(shutil.which("lark-cli")),
        "dida_token": bool(c["dida"].get("token")),
        "dida_enabled": c["dida"].get("enabled"),
        "project_id": c["sync"].get("project_id") or "(empty)",
        "mapping_count": len(_read(MAP_FILE, {})),
    }
