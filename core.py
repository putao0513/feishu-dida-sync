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


def cfg():
    import os
    
    # 第1步：基础 - 读取config.json作为默认配置
    if not CFG_FILE.exists():
        CFG_FILE.write_text((ROOT / "config.example.json").read_text(encoding="utf-8"), encoding="utf-8")
    config = json.loads(CFG_FILE.read_text(encoding="utf-8"))
    
    # 第2步：环境变量覆盖 - 飞书基础信息
    if os.getenv("FEISHU_BASE_TOKEN"):
        config["base_token"] = os.getenv("FEISHU_BASE_TOKEN")
    if os.getenv("FEISHU_TABLE_ID"):
        config["table_id"] = os.getenv("FEISHU_TABLE_ID")
    
    # 第3步：环境变量覆盖 - 滴答OAuth相关
    if os.getenv("DIDA_TOKEN"):
        config.setdefault("dida", {})["token"] = os.getenv("DIDA_TOKEN")
    if os.getenv("DIDA_REFRESH_TOKEN"):
        config.setdefault("dida", {})["refresh_token"] = os.getenv("DIDA_REFRESH_TOKEN")
    if os.getenv("DIDA_CLIENT_ID"):
        config.setdefault("dida", {})["client_id"] = os.getenv("DIDA_CLIENT_ID")
    if os.getenv("DIDA_CLIENT_SECRET"):
        config.setdefault("dida", {})["client_secret"] = os.getenv("DIDA_CLIENT_SECRET")
    if os.getenv("DIDA_PROJECT_ID"):
        config.setdefault("sync", {})["project_id"] = os.getenv("DIDA_PROJECT_ID")
    
    # 第4步：环境变量覆盖 - JSON格式配置
    if os.getenv("FEISHU_FIELD_MAPPING"):
        try:
            config["fields"] = json.loads(os.getenv("FEISHU_FIELD_MAPPING"))
        except Exception:
            pass
    if os.getenv("FEISHU_FILTER_CONDITIONS"):
        try:
            config.setdefault("sync", {})["filter"] = json.loads(os.getenv("FEISHU_FILTER_CONDITIONS"))
        except Exception:
            pass
    if os.getenv("DIDA_PRIORITY_MAP"):
        try:
            config.setdefault("sync", {})["priority_map"] = json.loads(os.getenv("DIDA_PRIORITY_MAP"))
        except Exception:
            pass
    
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


def feishu_list():
    c = cfg()
    out = STATE / (".records-%d.ndjson" % int(time.time() * 1000))
    f = json.dumps(c["sync"]["filter"], ensure_ascii=False, separators=(",", ":"))
    args = ["+record-list", "--base-token", c["base_token"], "--table-id", c["table_id"],
            "--filter-json", f, "--format", "ndjson", "--output", str(out)]
    try:
        lark(args)
        return [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines() if x.strip()]
    finally:
        out.unlink(missing_ok=True)
        out.with_suffix(".manifest.json").unlink(missing_ok=True)


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
    data = lark(["+record-batch-create", "--base-token", c["base_token"],
                 "--table-id", c["table_id"], "--json", "@PAYLOAD"],
                {"create_records": [fields]})
    ids = data.get("record_id_list") or []
    return {"dry_run": False, "record_id": ids[0] if ids else None, "raw": data}


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
