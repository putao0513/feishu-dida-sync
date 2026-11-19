---
title: quick-capture 知识索引
status: verified
updated: 2026-11-18
source: 本仓库实现与实测记录
tags: [索引, 知识图谱, 跨agent共享]
---

# KNOWLEDGE-MAP.md — 先读这里再找文件

任何 agent 改完东西，必须**追加**登记到下方「关键结论索引」与「变更记录」（规则见 `AGENTS.md`）。
状态：`verified` = 真实接口/页面跑通；`candidate` = 未实测；`outdated` = 已过期。

## 快速检索

| 意图 | 入口 |
|---|---|
| 协作规则 / 三同步 | `AGENTS.md`（Claude Code 看 `CLAUDE.md`） |
| 架构、目录、启动、开关、限制 | `README.md` |
| 改同步计划 / 幂等 / 字段映射 | `core.py` → `sync.py` |
| 改本地服务 / CORS / 端点 | `server.py` |
| 改控制台页面 | `index.html` |
| 改右键录入或定时触发 | `scriptcat/workbench-quick-capture.user.js`、`scriptcat/workbench-sync-scheduler.user.js` |
| 改浏览器扩展 / Windows 右键 | `extensions/chrome/`、`windows/` |
| 授权、换 token、列清单 | `oauth.py` |
| 查当前配置与运行状态 | `GET /api/status`、`GET /api/sync/preview` |
| 查历史排障结论 | 下方「关键结论索引」、工作区 `.workbuddy/memory/*.md` |

## 文件清单

| 路径 | 职责 | 状态 | 证据 |
|---|---|---|---|
| `AGENTS.md` | 跨 agent 三同步铁律与验证清单 | verified | 用户 2026-11-18 要求并落地 |
| `CLAUDE.md` | Claude Code 入口，指向 AGENTS.md | verified | 新建 |
| `README.md` | 框架：架构/目录/启动/开关/端点/限制 | verified | 与当前代码逐项核对 |
| `KNOWLEDGE-MAP.md` | 本索引 | verified | 新建 |
| `core.py` | 配置、`lark-cli` 适配、字段构造、滴答请求、`sync_once`、状态 | verified | 真实飞书/滴答读写 + 幂等复跑 |
| `sync.py` | CLI 预览/执行、`--limit` | verified | `python sync.py --run` executed=0 |
| `server.py` | HTTP 服务、CORS 白名单、脚本托管 | verified | 7 端点 + 跨站 403 实测 |
| `oauth.py` | OAuth2 授权、手动 code 兜底、刷新、列清单 | verified | 真实授权页跑通（无 refresh_token 返回） |
| `index.html` | 控制台 | verified | 页面 200，状态条随 config 变化 |
| `start.bat` | 手工启动（无自启） | candidate | 已核对路径与内容，**未双击实测** |
| `config.example.json` | 入库模板 | verified | clone bootstrap 模拟通过 |
| `scriptcat/*.user.js` | 浏览器右键 + 定时触发 | candidate | Node vm 模拟通过，**未真实浏览器实测** |
| `extensions/chrome/` | MV3 右键扩展 | candidate | `node --check` 通过，未加载实测 |
| `windows/` | 文件右键注册表脚本 | candidate | 未执行安装 |

## 关键结论索引（append-only）

| 日期 | 问题 / 坑 | 结论 | 证据 | 状态 |
|---|---|---|---|---|
| 11-17 | `lark-cli base +record-list --format ndjson --output` 的 stdout | 是 manifest，不是 `{"ok":true,...}` 包装；`core.lark()` 需单独适配，临时文件用 `finally` 回收 | 实测 | verified |
| 11-17 | 飞书 datetime 带毫秒 `.000+08:00` | `normalize_due()` 去毫秒；滴答按 UTC 存 `+0000`，北京 00:00 → 前日 16:00 UTC，换算正确 | 真实创建并读回 | verified |
| 11-17 | 飞书单选字段 | 写入用数组（如 `["中优先级"]`），`业务方` 是多选 select（5 个选项，含 `docusign`） | `+field-list` | verified |
| 11-17 | OAuth 报 `At least one redirect_uri must be registered` | 开发者中心必须登记 `http://127.0.0.1:38000/callback`，与 `config.json` 逐字符一致 | 用户实报 + 修复后授权成功 | verified |
| 11-17 | 官方未返回 `refresh_token` | 401 时明确提示重跑 `python oauth.py auth`，不做静默失败 | 真实授权响应 | verified |
| 11-17 | 飞书「存档」按钮 | 绑定动作实际把「状态」改为「已完成」，未改「处置状态」；而「已存档」视图筛的是处置状态=已存档 → 记录从常规视图消失且不进已存档视图 | 工作流静态推断，**未点按钮验证** | candidate |
| 11-17 | 幂等 | `state/mapping.json` 存 record_id ↔ taskId + 字段 hash；复跑 skip 全量、executed=0 | 真实全量 LIVE + 复跑 | verified |
| 11-17 | ScriptCat `@updateURL` 指向本地服务 | 改脚本必须 bump `@version`，否则不拉新版；新增脚本需重启服务进白名单 | 官方机制 + 自建白名单 | verified |
| 11-18 | 滴答更新任务 `POST /task/{taskId}` | body 的 `id` 与 `projectId` **均必填**；补 `id` 后完整载荷实测 200、字段未变 | 官方文档 + 真实 POST | verified |
| 11-18 | 滴答国内版删除端点 | `DELETE /open/v1/project/{pid}/task/{tid}` → 200；文档里的 `/task/{pid}/{tid}` → 404；`DELETE /task/{tid}` → 405 | 真实探查 | verified |
| 11-18 | 滴答接口慢响应 | 更新接口偶发 30.6s 返回（另一次 0.3s）；原 25s 超时必失败 → 改 60s，scheduler 20s → 60s；**不加自动重试**，避免 `POST /task` 重复建任务 | 真实计时 | verified |
| 11-18 | 空标题记录 | 飞书两条空记录曾生成滴答 `(untitled)` 脏任务；`sync_once` 现直接跳过并返回 `blank_skipped` | 三方对账 + 清理后复跑 | verified |
| 11-18 | 跨站写接口 | `ACAO: *` 改为 Origin 白名单回显；`evil.example` 403 / 本机 200 / 合法预检 204 | 真实预检与 GET | verified |
| 11-18 | 三同步规则 | 任何 agent 改动必须同提交更新内容 / `README.md` / 本索引 | 用户要求 | verified |

## 变更记录（append-only）

| 日期 | 提交 | 内容 | 框架 | 索引 |
|---|---|---|---|---|
| 11-17 | `39e684f`…`f35e67b` | 仓库基线、日期归一化、OAuth 兜底、授权成功 + 全量 LIVE | （当时无 README） | （当时无索引） |
| 11-18 | `d87b826` | 更新补 `id`、空标题过滤、CORS 白名单、超时 60s、控制台文案、`start.bat` | 本次补建 `README.md` | 本次补建本文件 |
| 11-18 | 本次 | 新增 `AGENTS.md`、`CLAUDE.md` 落地三同步铁律 | `README.md` 同步 | 本文件同步 |
