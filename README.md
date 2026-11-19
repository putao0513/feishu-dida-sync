---
title: feishu-dida-sync 项目说明
status: verified
updated: 2026-11-19
source: 本仓库实现与 GitHub Actions 实测
tags: [架构, 同步, 飞书, 滴答清单, GitHub-Actions]
---

# feishu-dida-sync — 飞书多维表格 → 滴答清单 自动同步

> **一句话**：飞书多维表格「待办任务」是唯一事实源，GitHub Actions 每 2 小时自动把有效任务单向同步到滴答清单 🍵CHAGEE 清单作为执行视图。

## 项目定位

| 维度 | 说明 |
|------|------|
| **数据流** | 飞书多维表格（主库）→ 滴答清单（执行视图），**单向同步** |
| **运行方式** | GitHub Actions 定时云端执行（`cron: 0 */2 * * *` UTC） |
| **仓库地址** | `https://github.com/putao0513/feishu-dida-sync` |
| **幂等机制** | `state/mapping.json` 存 `record_id ↔ taskId + 字段 hash` |

## 架构

```
飞书多维表格 ──(Feishu Base API)──→ core.py (sync_once) ──(滴答 Open API)──→ 滴答清单 🍵CHAGEE
                                        ↑
                                  GitHub Actions
                                  每 2 小时定时触发
```

### 核心组件

| 文件 | 职责 | 关键点 |
|------|------|--------|
| `core.py` | 核心引擎：配置、飞书 API、滴答 API、同步计划、幂等 | 所有非敏感配置已硬编码在 `_BUILTIN` |
| `sync.py` | CLI 入口：`python sync.py [--run --json --limit N]` | `--run` 真实写入，不加只预览 |
| `oauth.py` | 滴答 OAuth2 授权、token 刷新、列清单 | `python oauth.py auth` / `status` |
| `.github/workflows/sync.yml` | GitHub Actions 工作流 | 每 2 小时 cron + 手动触发 |

### 已废弃（仓库中仍保留，不再使用）

| 文件 | 原用途 | 废弃原因 |
|------|--------|---------|
| `server.py` | 本地 HTTP 服务 (`127.0.0.1:8765`) | 被 GitHub Actions 取代 |
| `index.html` | 本地控制台页面 | 同上 |
| `scriptcat/` | 浏览器脚本（Tampermonkey） | 网站禁用右键，方案失效 |

## 数据流详情

### 飞书 → 滴答同步逻辑

1. **读取飞书记录**：调用飞书 Base API `records/search`，按筛选条件获取
   - 筛选条件：`处置状态=有效 AND 状态≠已完成`
2. **构建同步计划**（幂等）：
   - `hash(record_id + 字段值)` 与 `state/mapping.json` 比对
   - hash 变 → `update`；未变 → `skip`；无映射 → `create`
   - **空标题记录直接跳过**，返回 `blank_skipped`
3. **执行同步**：
   - 创建：`POST /task`
   - 更新：`POST /task/{taskId}`（body 必须带 `id`）
4. **保存映射**：`state/mapping.json` 自动 commit + push 回仓库

### 字段映射（飞书 → 滴答）

| 飞书字段 | 滴答字段 | 说明 |
|----------|----------|------|
| 任务名称 | title | 必填，空则跳过 |
| 任务描述 | content | 尾部追加 `[feishu] <url> record_id=xxx` |
| 超链接 | content 中 | 附加到描述 |
| 截止日期 | dueDate | `normalize_due()` 去毫秒，转 UTC |
| 优先级 | priority | 高=5, 中=3, 低=1 |
| 状态 | （仅用于筛选） | 不写入滴答 |
| 处置状态 | （仅用于筛选） | 不写入滴答 |
| 业务方 | （仅用于筛选） | 不写入滴答 |

## 配置

### GitHub Secrets（7 个，必须配置）

在 [仓库 Settings → Secrets → Actions](https://github.com/putao0513/feishu-dida-sync/settings/secrets/actions) 配置：

| Secret 名称 | 用途 | 获取方式 |
|------------|------|---------|
| `FEISHU_APP_ID` | 飞书应用 ID | [open.feishu.cn](https://open.feishu.cn/app) 创建企业自建应用 |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | 同上 |
| `DIDA_CLIENT_ID` | 滴答应用 Client ID | [developer.dida365.com](https://developer.dida365.com/manage) |
| `DIDA_CLIENT_SECRET` | 滴答应用 Client Secret | 同上 |
| `DIDA_TOKEN` | 滴答 Access Token | 运行 `python oauth.py auth` 获取 |
| `DIDA_REFRESH_TOKEN` | 滴答 Refresh Token | 同上（滴答不返回，可留空） |
| `DIDA_PROJECT_ID` | 目标清单 ID | 运行 `python oauth.py projects` 查看 |

### 内置配置（`core.py` 的 `_BUILTIN`，无需配置）

飞书 Base Token、Table ID、字段映射、筛选条件、优先级映射、滴答 API 地址等非敏感配置已硬编码。

## 本地开发

```bash
# 1. 语法检查
python -m py_compile core.py sync.py oauth.py

# 2. 预览同步计划（不写入）
python sync.py

# 3. 执行同步（真实写入滴答）
python sync.py --run

# 4. 查看滴答凭据状态
python oauth.py status

# 5. 重新授权滴答（token 过期时）
python oauth.py auth

# 6. 查看滴答清单列表
python oauth.py projects
```

## 本地 config.json（开发用）

本地开发可用 `config.json` 覆盖 `_BUILTIN`，优先级：环境变量 > config.json > _BUILTIN。

**`config.json` 不入库**（`.gitignore` 排除），生产环境全靠 GitHub Secrets。

## 排障速查

| 症状 | 原因 | 解决 |
|------|------|------|
| `FEISHU_APP_ID / FEISHU_APP_SECRET 环境变量未设置` | GitHub Secrets 未配 | 配置 2 个飞书凭据 |
| `飞书认证失败` | App ID/Secret 错误或应用未发布 | 检查飞书后台，发布应用版本 |
| `飞书 API xxx: xxx` | 权限不足或表格未授权 | 飞书应用加 `bitable:app` 权限 + 添加为表格协作者 |
| `dida.token 已过期` | 滴答 token 失效 | 本地跑 `python oauth.py auth`，更新 Secret |
| `Invalid header value` | token 含换行/空格 | 确认 Secret 值无尾部空白（代码已加 `.strip()`） |
| `403 Forbidden`（滴答 OAuth） | WAF 拦截 `127.0.0.1` | redirect_uri 必须用 `http://localhost:38000/callback` |
| `invalid_client`（滴答 OAuth） | 端点用错 | 必须用 `dida365.com`（非 `ticktick.com`） |
| `Permission denied to github-actions[bot]` | 工作流无写权限 | 确认 workflow 有 `permissions: contents: write` |

## 关键技术细节

### 滴答 OAuth 注意事项
- 授权端点：`https://dida365.com/oauth/authorize`（国内版）
- Redirect URL：**必须用 `localhost`**，WAF 拦截 `127.0.0.1`
- 不返回 `refresh_token`，token 过期需手动重新授权
- 开发者后台需登记 Redirect URL 与 config 逐字符一致

### 飞书 API 字段格式
- 文本字段返回 `[{type:"text", text:"内容"}]` 列表 → `_normalize_field()` 归一化为字符串
- 多选字段返回 `["选项1", "选项2"]` 数组（保留原格式）
- URL 字段返回 `{text:"显示文字", link:"https://..."}` → 归一化为 text

### 幂等同步
- `state/mapping.json` 由 GitHub Actions 自动 commit 回仓库（`[skip ci]` 防循环）
- hash 算法：`md5(title + content + due + priority + status + disposition)`
- 删除/完成的飞书记录**不会**从滴答删除（单向同步的已知限制）

## 验证状态

| 项目 | 状态 | 证据 |
|------|------|------|
| GitHub Actions 定时同步 | ✅ verified | 2026-11-19 手动触发成功，12 条同步 0 错误 |
| 飞书 API 直连读取 | ✅ verified | 12 条记录扫描正常 |
| 滴答 API 创建/更新任务 | ✅ verified | 12 条全部 update 成功 |
| mapping.json 自动提交 | ✅ verified | `[skip ci]` commit 已推送 |
| OAuth 授权流程 | ✅ verified | 真实授权页跑通（localhost redirect） |
| 定时 cron 触发 | ⏳ 待验证 | 首次定时运行将在下一个整点 |
