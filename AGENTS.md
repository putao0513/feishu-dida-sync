---
title: feishu-dida-sync Agent 协作规范
status: verified
updated: 2026-11-19
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
| 内容 | `core.py` `sync.py` `oauth.py` `.github/workflows/sync.yml` `config.example.json` | 任何实现、修复、新增入口 |
| 框架 | `README.md` | 架构、数据流、配置、排障、依赖、已知限制发生变化 |
| 索引 | `KNOWLEDGE-MAP.md` | **每次改动**：登记「问题/结论 → 文件 → 状态 → 证据 → 日期」并追加变更记录 |
| 运行时状态 | `state/*`、`config.json` | **不入库、不写进索引当事实**；只在验证记录里写结论 |

## 读取顺序（强制）

1. 本文件 → 2. `KNOWLEDGE-MAP.md` 定位文件与既有结论 → 3. `README.md` 理解架构 → 4. 代码。
禁止全库盲搜、禁止凭记忆重建已有结论。引用路径一律相对本仓库根。

## 当前架构（2026-11-19）

> **架构已从本地服务迁移到 GitHub Actions 云端定时同步。**
> `server.py` / `index.html` / `scriptcat/` / `start.bat` 已废弃，不再维护。

```
飞书多维表格 ──(Feishu Base API)──→ core.py (sync_once) ──(滴答 Open API)──→ 滴答清单 🍵CHAGEE
                                        ↑
                                  GitHub Actions (cron: 每 2 小时)
```

| 组件 | 说明 |
|------|------|
| **GitHub Actions** | 每 2 小时自动同步，`workflow_dispatch` 手动触发 |
| **飞书 API** | HTTP 直连（`_feishu_api()`），需 `FEISHU_APP_ID/SECRET` |
| **滴答 API** | HTTP 直连（`dida_request()`），需 5 个 DIDA Secrets |
| **幂等** | `state/mapping.json` 自动 commit 回仓库（`[skip ci]` 防循环） |

## 状态与证据

- 每个结论 / 脚本标 `verified`（真实接口或真实页面跑通）、`candidate`（未实测）、`outdated`（已过期）。
- **只有真实实测才能升 `verified`**；mock、静态推断、文档推测保持 `candidate` 并注明证据等级与未公开项，不用推测填空。

## 写入规则

1. 改前确认影响范围；涉及线上写操作（删滴答任务、删飞书记录、改 `dry_run`）**执行前必须二次确认**。
2. 代码与文档同提交，提交信息说明改了哪一层。
3. 凭据零入库：`config.json`、`state/*`、`*.log` 已被 `.gitignore` 排除；模板只放空值；token / client_secret 不得出现在 tracked 文件，也不得打印到聊天。
4. 禁止删除或重命名已有文件（除非用户明确要求）；禁止把运行时状态当事实源。
5. 新结论**追加**到 `KNOWLEDGE-MAP.md` 的「关键结论索引」与「变更记录」，不覆盖历史条目。
6. 推送代码到 GitHub 用 Contents API（git push 受代理限制不稳定），脚本模式参考会话记忆。

## 验证清单（每次改动后）

```bash
python -m py_compile core.py sync.py oauth.py
python sync.py                    # 预览，executed 必须为 0（幂等）
git status --short
git grep -n -E "<凭据明文>" HEAD -- .   # 凭据复核
```

真实同步验证：到 GitHub Actions 页面手动触发 workflow，确认 0 错误。

## 共享数据入口（给后续 agent）

| 数据 | 位置 | 备注 |
|---|---|---|
| 当前配置（含 token） | `config.json`（不入库，仅本地开发用） | `core.cfg()` 每次读；生产靠 GitHub Secrets |
| 幂等映射 | `state/mapping.json`（GitHub Actions 自动 commit） | record_id ↔ taskId + 字段 hash；误删会重复建任务 |
| 同步运行日志 | GitHub Actions → 最新 run → Logs | 看 `Run sync` 步骤的 JSON 输出 |
| 飞书主库 | `core.py` 的 `_BUILTIN` 中 `base_url` / `base_token` | 多维表格是唯一事实源 |
| 滴答执行视图 | `DIDA_PROJECT_ID` 指向的清单 🍵CHAGEE | 单向，不回写 |
| 仓库地址 | `https://github.com/putao0513/feishu-dida-sync` | 公开仓库 |
| 会话记忆 | 工作区 `.workbuddy/memory/` | 日志 append-only，跨会话共享 |
