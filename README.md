---
title: quick-capture 框架说明
status: verified
updated: 2026-11-18
source: 本仓库实现与实测
tags: [架构, 框架, 启动, 开关]
---

# quick-capture — 飞书多维表格 ↔ 滴答清单 + 右键快速录入

## 定位

飞书多维表格「待办任务」是**唯一事实源**；本机枢纽把它**单向**同步到滴答清单 🍵CHAGEE 作为执行视图；浏览器右键把网页 / 选中文字写回主库。不是一次性导出备份。

## 架构（三层）

| 层 | 组件 | 说明 |
|---|---|---|
| 采集层 | `scriptcat/*.user.js`（右键菜单 + `@crontab */15 9-18 * * 1-5`）、`extensions/chrome/`、`windows/` | 只做采集与触发，不持有凭据 |
| 枢纽层 | `server.py` + `core.py` + `sync.py` + `oauth.py`，`127.0.0.1:8765` | 写飞书（经 `lark-cli`）、同步滴答、幂等映射、托管用户脚本、控制台 |
| 数据层 | 飞书多维表格（主库）／滴答清单（执行视图） | 单向：表格 → 滴答 |

```
右键/定时 → HTTP 127.0.0.1:8765 → /api/capture → 飞书主库
                                 → /api/sync/*  → 滴答清单
                        state/mapping.json（不入库）负责幂等
```

枢纽不可省略：`lark-cli` 是本机 CLI 且依赖已授权身份，浏览器沙盒无法调用；滴答 token 不进浏览器。

## 目录层级

| 路径 | 职责 | 入库 |
|---|---|---|
| `core.py` `sync.py` `server.py` `oauth.py` | 配置、飞书/滴答请求、同步计划、HTTP 服务、OAuth | 是 |
| `index.html` | 控制台（录入 + 预览/执行同步 + 状态条） | 是 |
| `start.bat` | 手工启动服务（**无开机自启**） | 是 |
| `scriptcat/` | 浏览器引用层，两个 `.user.js` | 是 |
| `extensions/chrome/` `windows/` | 备选右键入口（MV3 扩展 / 注册表脚本） | 是 |
| `config.example.json` | 入库模板（空凭据） | 是 |
| `config.json` | 实际配置与 token | **否** |
| `state/` | `mapping.json`、`captured.json`、临时 NDJSON、日志 | **否**（仅 `.gitkeep`） |

## 启动与停止

- 双击 `start.bat`（或在本目录执行 `python server.py`），只监听 `127.0.0.1:8765`，窗口可见日志，Ctrl+C / 关窗口即停。
- 用户 2026-11-18 明确**不注册开机自启**；桌面快捷方式：右键 `start.bat` → 发送到 → 桌面快捷方式。
- 端口已占用时先关旧窗口。改 `.py` / `server.py` 后需重启；只改 `index.html` / `.user.js` 无需重启（每次请求读文件）。
- `start.bat` 用 `%USERPROFILE%` 规避中文路径，并自动把 WorkBuddy 的 node bin 加进 PATH 以便找到 `lark-cli`。

## 配置开关（`config.json`，`core.cfg()` 每次读取，改完无需重启）

| 键 | 作用 | 当前 |
|---|---|---|
| `dry_run` | 全局开关，`true` 时录入与同步都不写生产 | `false`（LIVE） |
| `dida.enabled` | 同步开关 | `true` |
| `sync.project_id` | 目标清单 🍵CHAGEE | 已设置 |
| `dida.token` | OAuth 授权写入，**无 refresh_token** | 有效；过期重跑 `python oauth.py auth` |
| `sync.filter` | 口径：处置状态=有效 AND 状态≠已完成 | 已设置 |

文件不存在时由 `core.cfg()` 从模板自动 bootstrap。

## HTTP 端点

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/`、`/index.html` | 控制台 |
| GET | `/api/status` | 配置摘要、token/CLI/映射状态 |
| POST | `/api/capture` | 写飞书主库（受 `dry_run` 控制，带标题去重） |
| GET | `/api/sync/preview` | 只读生成同步计划 |
| POST | `/api/sync/run` | 执行同步，需 `{"confirm":true}` |
| GET | `/scriptcat/`、`/scriptcat/<name>.user.js` | 脚本索引与静态托管（白名单防穿越） |

CORS：Origin 白名单回显（`127.0.0.1` / `localhost` / `chrome-extension://` / `moz-extension://`），无 Origin 与 `null` 放行以兼容 ScriptCat 与本地进程，其它来源 403。

## 同步逻辑

- 幂等：`state/mapping.json` 存 `record_id ↔ taskId + 字段 hash`；hash 变 → update，未变 → skip，无映射 → create。
- **空标题记录直接跳过**，返回 `blank_skipped`，不生成 `(untitled)` 任务。
- 创建 `POST /task`；更新 `POST /task/{taskId}`（**body 必须带 `id`**）；国内版删除是 `DELETE /open/v1/project/{pid}/task/{tid}`。
- `dueDate` 经 `normalize_due()` 去毫秒；滴答转 UTC 存储。请求超时 60s（实测偶发 30.6s 慢响应）。
- 滴答任务描述尾部追加 `[feishu] <base_url>?table=... record_id=...`，便于反查。

## 验证命令

```bash
python -m py_compile core.py sync.py server.py oauth.py
node --check scriptcat/*.user.js extensions/chrome/background.js
python sync.py                 # 预览：executed=0
python sync.py --run           # LIVE 幂等复跑：executed=0
python oauth.py status         # 凭据状态（不打印明文）
```

## 已知限制（2026-11-18）

1. 两个 ScriptCat 脚本仍 `candidate`：真实浏览器右键、`@crontab` 定时触发、`dry_run=false` 下右键真实写飞书，均未端到端实测。
2. 单向同步：表格标完成 / 删记录 → 滴答任务残留；滴答勾完成不回写表格。
3. token 无 `refresh_token`，过期需手动重授权；scheduler 对重复错误只提醒一次，可能静默停摆。
4. `state/mapping.json` 无备份，误删会重复建任务。
5. `config.example.json` 与两个 `@namespace` 含真实 `base_token`；仓库当前无 remote，push 前须脱敏。
