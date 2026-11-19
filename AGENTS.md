---
title: quick-capture Agent 协作规范
status: verified
updated: 2026-11-18
source: 用户要求「后续无论哪个 agent 参与都要更新内容、框架和索引」
tags: [规则, 三同步, 跨agent共享]
---

# AGENTS.md — 任何 Agent 必读

适用：WorkBuddy / Codex / Claude Code / 任何参与本仓库的 AI Agent。Claude Code 入口 `CLAUDE.md` 指向本文件。

## 一条铁律：三同步（不可拆分）

> 任何 agent 在本仓库完成**任何改动**（代码、配置模板、脚本、数据口径、排障结论、验证结果），
> 必须在**同一次提交**里同步更新三样：
> **① 内容**（实际实现）**② 框架**（`README.md`）**③ 索引**（`KNOWLEDGE-MAP.md`）。
> 三者缺一不得 commit。

目的：后续任意 agent 只需按 `AGENTS.md` → `KNOWLEDGE-MAP.md` → `README.md` 的顺序读一遍，
就能拿到完整上下文，不重复考古、不重复踩坑、不重复验证。

| 层 | 落点 | 必须更新的触发条件 |
|---|---|---|
| 内容 | `core.py` `server.py` `sync.py` `oauth.py` `index.html` `start.bat` `scriptcat/*.user.js` `extensions/chrome/*` `windows/*` `config.example.json` | 任何实现、修复、新增入口 |
| 框架 | `README.md` | 架构、目录层级、数据流、启动方式、开关、端点、依赖、已知限制发生变化 |
| 索引 | `KNOWLEDGE-MAP.md` | **每次改动**：登记「问题/结论 → 文件 → 状态 → 证据 → 日期」并追加变更记录 |
| 运行时状态 | `state/*`、`config.json` | **不入库、不写进索引当事实**；只在验证记录里写结论 |

## 读取顺序（强制）

1. 本文件 → 2. `KNOWLEDGE-MAP.md` 定位文件与既有结论 → 3. `README.md` 理解架构 → 4. 代码。
禁止全库盲搜、禁止凭记忆重建已有结论。引用路径一律相对本仓库根。

## 状态与证据

- 每个结论 / 脚本标 `verified`（真实接口或真实页面跑通）、`candidate`（未实测）、`outdated`（已过期）。
- **只有真实实测才能升 `verified`**；mock、静态推断、文档推测保持 `candidate` 并注明证据等级与未公开项，不用推测填空。
- 用户脚本改动后必须 bump `@version`，否则 ScriptCat 不拉最新版；新增脚本需重启服务才进入白名单。

## 写入规则

1. 改前确认影响范围；涉及线上写操作（删滴答任务、删飞书记录、改 `dry_run`、注册系统项）**执行前必须二次确认**。
2. 代码与文档同提交，提交信息说明改了哪一层。
3. 凭据零入库：`config.json`、`state/*`、`*.log` 已被 `.gitignore` 排除；模板只放空值；token / client_secret 不得出现在 tracked 文件，也不得打印到聊天。
4. 禁止删除或重命名已有文件（除非用户明确要求）；禁止把运行时状态当事实源。
5. 新结论**追加**到 `KNOWLEDGE-MAP.md` 的「关键结论索引」与「变更记录」，不覆盖历史条目。

## 验证清单（每次改动后）

```bash
python -m py_compile core.py sync.py server.py oauth.py
node --check scriptcat/*.user.js extensions/chrome/background.js
python sync.py                    # 预览，executed 必须为 0（幂等）
git status --short
git grep -n -E "<凭据明文>" HEAD -- .   # 凭据复核
```

涉及服务端时：重启后验证 `/api/status`、`/api/sync/preview`、跨站 Origin 返回 403。
真实浏览器右键 / crontab 只能在用户实际操作后升 `verified`。

## 共享数据入口（给后续 agent）

| 数据 | 位置 | 备注 |
|---|---|---|
| 当前配置（含 token） | `config.json`（不入库） | `core.cfg()` 每次读，改完无需重启 |
| 幂等映射 | `state/mapping.json`（不入库） | record_id ↔ taskId + 字段 hash；误删会重复建任务 |
| 运行状态 | `GET http://127.0.0.1:8765/api/status` | 服务由 `start.bat` 手工拉起，**无开机自启** |
| 同步计划 | `GET /api/sync/preview` | `blank_skipped` = 被跳过的空标题记录数 |
| 飞书主库 | `config.json` 的 `base_url` / `base_token` | 多维表格是唯一事实源 |
| 滴答执行视图 | `sync.project_id` 指向的清单 | 单向，不回写 |
| 会话记忆 | 工作区 `.workbuddy/memory/` | 日志 append-only，跨会话共享 |
