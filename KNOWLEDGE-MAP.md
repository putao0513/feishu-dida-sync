---
title: feishu-dida-sync 知识索引
status: candidate
updated: 2026-11-26
source: 本仓库实现与 GitHub Actions 实测记录
tags: [索引, 知识图谱, 跨agent共享]
---

# KNOWLEDGE-MAP.md — 先读这里再找文件

任何 agent 改完东西，必须**追加**登记到下方「关键结论索引」与「变更记录」（规则见 `AGENTS.md`）。
状态：`verified` = 真实接口/页面跑通；`candidate` = 未实测；`outdated` = 已过期。

## 快速检索

| 意图 | 入口 |
|---|---|
| 协作规则 / 三同步 | `AGENTS.md`（Claude Code 看 `CLAUDE.md`） |
| 架构、配置、排障、验证 | `README.md` |
| 改同步逻辑 / 字段映射 / 幂等 | `core.py` → `sync.py` |
| 改飞书 API 调用 | `core.py` → `_feishu_token()` / `_feishu_api()` / `_normalize_field()` |
| 改滴答 API 调用 | `core.py` → `dida_request()` / `build_task()` |
| 改 GitHub Actions 工作流 | `.github/workflows/sync.yml` |
| 授权、换 token、列清单 | `oauth.py` |
| 部署指南（历史） | `DEPLOY.md`（部分已过时，架构已转 GitHub Actions） |
| 查历史排障结论 | 下方「关键结论索引」、工作区 `.workbuddy/memory/*.md` |

## 文件清单

| 路径 | 职责 | 状态 | 证据 |
|---|---|---|---|
| `AGENTS.md` | 跨 agent 三同步铁律与验证清单 | verified | 用户 2026-11-18 要求并落地 |
| `CLAUDE.md` | Claude Code 入口，指向 AGENTS.md | verified | 新建 |
| `README.md` | 项目说明：架构/配置/排障/验证 | candidate | 2026-11-26 增补状态同步与源记录清理，待实测 |
| `KNOWLEDGE-MAP.md` | 本索引 | candidate | 2026-11-26 更新 |
| `core.py` | 核心引擎：飞书 API、滴答 API、同步计划、幂等 | candidate | 2026-11-26 完成状态与删除清理逻辑待实测 |
| `sync.py` | CLI 入口：`--run --json --limit` | verified | `python sync.py --run` 实测 |
| `oauth.py` | 滴答 OAuth2 授权、刷新、列清单 | verified | 真实授权页跑通（localhost redirect） |
| `.github/workflows/sync.yml` | GitHub Actions 工作流 | verified | 手动触发 + 自动 commit 实测 |
| `config.example.json` | 入库模板（空凭据） | verified | 保留参考 |
| `config.json` | 本地开发配置 | verified | 不入库，生产全靠 Secrets |
| `server.py` | **已废弃**：本地 HTTP 服务 | outdated | 被 GitHub Actions 取代 |
| `index.html` | **已废弃**：本地控制台 | outdated | 同上 |
| `scriptcat/` | **已废弃**：浏览器脚本 | outdated | 网站禁用右键，方案失效 |
| `DEPLOY.md` | 历史部署指南 | outdated | 架构已转 GitHub Actions |

## 关键结论索引（append-only）

| 日期 | 问题 / 坑 | 结论 | 证据 | 状态 |
|---|---|---|---|---|
| 11-17 | `lark-cli base +record-list --format ndjson` 的 stdout | 是 manifest，不是 `{"ok":true,...}` 包装；临时文件用 `finally` 回收 | 实测 | verified |
| 11-17 | 飞书 datetime 带毫秒 `.000+08:00` | `normalize_due()` 去毫秒；滴答按 UTC 存 | 真实创建并读回 | verified |
| 11-17 | 飞书单选字段 | 写入用数组（如 `["中优先级"]`） | `+field-list` | verified |
| 11-17 | OAuth 报 `redirect_uri must be registered` | 开发者中心登记的 URL 与 config 逐字符一致 | 用户实报 + 修复 | verified |
| 11-17 | 官方未返回 `refresh_token` | 401 时提示重跑 `python oauth.py auth` | 真实授权响应 | verified |
| 11-17 | 幂等 | `mapping.json` 存 record_id ↔ taskId + hash；复跑 skip 全量 | 真实 LIVE + 复跑 | verified |
| 11-18 | 滴答更新任务 `POST /task/{taskId}` | body 的 `id` 与 `projectId` **均必填** | 官方文档 + 真实 POST | verified |
| 11-18 | 滴答国内版删除端点 | `DELETE /open/v1/project/{pid}/task/{tid}` → 200 | 真实探查 | verified |
| 11-18 | 滴答接口慢响应 | 偶发 30.6s；超时改 60s；不加自动重试防重复建任务 | 真实计时 | verified |
| 11-18 | 空标题记录 | 直接跳过返回 `blank_skipped`，不生成 `(untitled)` | 三方对账 | verified |
| 11-18 | 跨站写接口 | Origin 白名单回显，其它来源 403 | 真实预检 | verified |
| 11-18 | 三同步规则 | 任何 agent 改动必须同提交更新内容 / README / 索引 | 用户要求 | verified |
| 11-19 | `lark-cli not found in PATH`（GitHub Actions） | 改用飞书 HTTP API 直连（`_feishu_api()`），需 `FEISHU_APP_ID/SECRET` | Actions 日志 | verified |
| 11-19 | 飞书 API 文本字段格式 | 返回 `[{type:"text",text:"..."}]` 列表，需 `_normalize_field()` 归一化 | Actions 日志 | verified |
| 11-19 | 滴答 token 含换行符致 `Invalid header value` | `cfg()` 环境变量读取加 `.strip()` | Actions 日志 | verified |
| 11-19 | 滴答 OAuth 403 Forbidden | WAF 拦截 `127.0.0.1`，redirect_uri 改用 `http://localhost:38000/callback` | curl 逐端点测试 | verified |
| 11-19 | 滴答 OAuth `invalid_client`（ticktick.com） | 应用注册在 dida365.com，端点必须用 `dida365.com` | 真实授权页 | verified |
| 11-19 | `Permission denied to github-actions[bot]` | workflow 加 `permissions: contents: write` | Actions 日志 | verified |
| 11-19 | GitHub Actions 首次同步 | 12 条飞书记录 → 12 条滴答更新，0 错误，mapping 自动 commit | Actions 日志 | verified |
| 11-26 | 完成状态与源记录删除 | 有效项状态映射到滴答；无效或源记录缺失时删除映射任务 | 代码实现；需 Actions 实测 | candidate |

## 变更记录（append-only）

| 日期 | 提交 | 内容 | 框架 | 索引 |
|---|---|---|---|---|
| 11-17 | `39e684f`…`f35e67b` | 仓库基线、日期归一化、OAuth 兜底、授权成功 + 全量 LIVE | （当时无 README） | （当时无索引） |
| 11-18 | `d87b826` | 更新补 `id`、空标题过滤、CORS 白名单、超时 60s、控制台文案 | 补建 `README.md` | 补建本文件 |
| 11-18 | 一次 | 新增 `AGENTS.md`、`CLAUDE.md` 落地三同步铁律 | `README.md` 同步 | 本文件同步 |
| 11-19 | 多次 | **架构迁移**：lark-cli→飞书 HTTP API、本地服务→GitHub Actions、OAuth 403/invalid_client 修复、token strip | **全面重写** | **本次更新** |
| 2026-11-26 | 本次 | 完成状态同步；删除飞书中已删除或无效记录对应的滴答任务 | `core.py`、`README.md` | 本次更新 |
