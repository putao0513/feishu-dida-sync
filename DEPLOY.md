---
title: GitHub Actions 后端部署指南
status: verified
updated: 2026-11-19
source: 架构升级：从前台ScriptCat转向后端定时同步
tags: [GitHub Actions, 自动化部署, 定时同步, Secrets配置]
---

# GitHub Actions 后端部署完整指南

本指南说明如何配置 GitHub Actions 工作流，实现**后端定时自动同步**飞书多维表格 → 滴答清单，替代已废弃的本地HTTP服务方案。

---

## 第 0 步｜前置条件检查

### 前置要求

| 项目 | 要求 | 检查方法 |
|---|---|---|
| **GitHub 仓库** | 已推送本项目到远端，分支为 `main`（或自定义） | `git remote -v` 查看仓库地址 |
| **Python 环境** | 3.10+ | `python --version` |
| **依赖包** | `requirements.txt` 已包含全部依赖 | `pip list \| grep -E "requests\|pydantic"` |
| **飞书 API** | `base_token` 已获取，对应多维表格有读权限 | 见第1步配置指引 |
| **滴答 API** | `token` 和 `refresh_token` 已获取 | 见第1步配置指引 |
| **GitHub Actions** | 已启用（Settings > Actions > General > Allow all actions） | 仓库 Settings 确认 |

### 快速验证

```bash
# 验证本地 Python 环境
python --version  # 应为 3.10+

# 验证依赖
pip install -r requirements.txt

# 验证 config.json 格式（可选）
python -c "import json; json.load(open('config.json'))"
```

---

## 第 1 步｜配置 10 个 GitHub Secrets

工作流依赖 10 个环境变量，需通过 GitHub Secrets 注入。访问仓库 Settings → Secrets and variables → Actions，按如下表格逐一配置：

### 飞书相关凭据（2 个）

| Secret 名称 | 取值来源 | 说明 |
|---|---|---|
| `FEISHU_BASE_TOKEN` | 飞书多维表格 API | 格式：`pat_xxxxx...`，需拥有表格读权限 |
| `FEISHU_TABLE_ID` | 多维表格 URL 中 `bid=` 参数 | 示例：`tblxxxxx` |

**飞书 base_token 获取步骤**：
1. 登录 [飞书开发者后台](https://open.feishu.cn/app)
2. 创建 or 选择应用 → 凭证与基础信息 → 获取 App ID / App Secret
3. 在本地运行飞书 OAuth 流程获取 `base_token`（若已有，直接使用）
4. 获取多维表格 ID：打开多维表格 → URL 查看 `bid=` 参数

### 滴答相关凭据（4 个）

| Secret 名称 | 取值来源 | 说明 |
|---|---|---|
| `DIDA_TOKEN` | 滴答清单 API 令牌 | 长期令牌，可在滴答账户设置获取 |
| `DIDA_REFRESH_TOKEN` | 滴答刷新令牌 | 需要时自动刷新短期 token |
| `DIDA_CLIENT_ID` | 滴答应用 ID | OAuth 客户端 ID |
| `DIDA_CLIENT_SECRET` | 滴答应用密钥 | OAuth 客户端密钥，**勿泄露** |
| `DIDA_PROJECT_ID` | 滴答目标项目 ID | 同步到此项目，可在滴答Web查看 |

**滴答凭据获取步骤**：
1. 访问 [滴答清单开发者平台](https://dida365.com/oauth/authorize)
2. 创建 OAuth 应用 → 获取 `client_id` / `client_secret`
3. 本地运行 `python oauth.py auth` 完成授权 → 生成 `token` / `refresh_token`
4. 在 `config.json` 中查看已保存的值，复制到 GitHub Secrets

### 字段映射与过滤（3 个）

| Secret 名称 | 格式 | 示例 |
|---|---|---|
| `FEISHU_FIELD_MAPPING` | JSON 字符串 | `{"title": "field_1", "priority": "field_2"}` |
| `FEISHU_FILTER_CONDITIONS` | JSON 字符串 | `{"field": "status", "value": "进行中"}` |
| `PRIORITY_MAP` | JSON 字符串 | `{"高": 5, "中": 3, "低": 1}` |

**如何生成 JSON Secrets**：
```bash
# 在本地生成紧凑 JSON（无空格）
python3 -c "
import json
mapping = {'title': 'field_1', 'priority': 'field_2'}
print(json.dumps(mapping, ensure_ascii=False, separators=(',', ':')))"
# 输出：{\"title\":\"field_1\",\"priority\":\"field_2\"}
# 复制到 GitHub Secrets
```

### 配置步骤

1. **打开 GitHub 仓库**，点击 Settings
2. **左侧菜单** → Secrets and variables → Actions
3. **点击 "New repository secret"**，逐一添加上述 10 个 Secret：
   - 输入 Secret 名称（严格匹配表格中的大写名称）
   - 输入 Secret 值
   - 点 "Add secret"
4. **验证**: 页面应显示 10 个 Secret（值显示为 `●●●●●` 隐蔽）

---

## 第 2 步｜验证工作流配置

### 工作流文件位置

工作流已在 `.github/workflows/sync.yml` 创建，核心配置如下：

```yaml
name: Feishu → Dida Auto Sync
on:
  schedule:
    - cron: "0 */2 * * *"   # UTC 每 2 小时整点触发
  workflow_dispatch:         # 手动触发
```

**Cron 说明**：
- `0` — 分钟（第 0 分）
- `*/2` — 小时（每 2 小时）
- `*` — 日期（每天）
- `*` — 月份（每月）
- `*` — 周几（每周）

→ 结果：**UTC 时区每 2 小时整点**（如 00:00, 02:00, 04:00...）

### 首次手动触发（推荐）

1. **进入 GitHub 仓库** → Actions 标签页
2. **左侧菜单** → 选择 "Feishu → Dida Auto Sync" 工作流
3. **点击 "Run workflow"** → 选择分支（通常为 `main`）
4. **点击绿色 "Run workflow"** 按钮
5. **等待执行**（通常 30-60 秒）

### 检查执行日志

1. 工作流执行后，点击最新的 **run 记录**
2. 展开 **"Sync Data"** job，查看完整日志
3. **成功标志**：
   - 日志末尾显示 `✓ Sync completed` 或类似消息
   - `state/mapping.json` 已自动提交
4. **失败排查**：见第 4 步「常见问题排查」

---

## 第 3 步｜监控定时运行

### 查看工作流执行历史

1. **GitHub 仓库** → Actions 标签页
2. **左侧菜单** → "Feishu → Dida Auto Sync"
3. 列表显示所有历史运行，最新的排在最上方
4. 点击任一条记录，查看详细日志

### 理解时区转换

工作流使用 **UTC 时区**，配置 `"0 */2 * * *"` 表示：

| UTC 时间 | 中国时间（UTC+8） | 状态 |
|---|---|---|
| 00:00 UTC | 08:00 CST | 触发 |
| 02:00 UTC | 10:00 CST | 触发 |
| 04:00 UTC | 12:00 CST | 触发 |
| 06:00 UTC | 14:00 CST | 触发 |
| 08:00 UTC | 16:00 CST | 触发 |
| 10:00 UTC | 18:00 CST | 触发 |
| 12:00 UTC | 20:00 CST | 触发 |
| 14:00 UTC | 22:00 CST | 触发 |
| 16:00 UTC | 次日 00:00 CST | 触发 |
| 18:00 UTC | 次日 02:00 CST | 触发 |
| 20:00 UTC | 次日 04:00 CST | 触发 |
| 22:00 UTC | 次日 06:00 CST | 触发 |

**若需调整触发时间**，编辑 `.github/workflows/sync.yml`：

```yaml
# 改为每 6 小时触发（UTC）
schedule:
  - cron: "0 0,6,12,18 * * *"

# 改为工作日 09:00-17:00 每小时触发（UTC 对应 17:00-01:00 CST）
schedule:
  - cron: "0 1,2,3,4,5,6,7,8,9 * * 1-5"
```

### 监控最佳实践

- **周一首次运行**：验证定时触发是否生效
- **每周检查日志**：确保无异常错误
- **月度审计**：检查 `state/mapping.json` 的提交历史

---

## 第 4 步｜常见问题排查

### 工作流未触发

**现象**：Actions 页面无新运行记录

**排查**：

| 步骤 | 检查项 | 解决方法 |
|---|---|---|
| 1 | Settings > Actions > General > Allow all actions | 确保 Actions 已启用 |
| 2 | `.github/workflows/sync.yml` 是否已提交到 `main` 分支 | 运行 `git log --oneline -- .github/workflows/` 查看 |
| 3 | Cron 语法是否正确 | 访问 [crontab.guru](https://crontab.guru/) 验证表达式 |
| 4 | 当前 UTC 时间是否已过触发时刻 | 运行 `date -u` 或在线查看 UTC 时间 |

### 工作流运行失败

**现象**：Actions 页面显示红色 ✗，日志有错误信息

**常见错误及解决**：

| 错误信息 | 原因 | 解决方法 |
|---|---|---|
| `secret not found` | GitHub Secret 配置不完整或名称错误 | 重新检查 Settings > Secrets，确保 10 个 Secret 都已配置 |
| `401 Unauthorized` | 飞书 or 滴答凭据过期 | 重跑 `python oauth.py auth` 获取新 token，更新 Secret |
| `Connection timeout` | 网络问题（GitHub 无法连接飞书 / 滴答 API） | 检查本地网络，确保能正常访问外网 API |
| `KeyError: 'field_x'` | `FEISHU_FIELD_MAPPING` JSON 格式错误 | 验证 JSON 格式，使用 `python -m json.tool` 检查 |
| `Sync failed: 0 records` | 飞书表格无符合条件的记录 | 检查 `FEISHU_FILTER_CONDITIONS` 是否过于严格 |

### 同步后数据未更新

**现象**：工作流显示成功，但滴答清单没看到新任务

**排查**：

1. 检查 `state/mapping.json` 提交日志
   ```bash
   git log --oneline -- state/mapping.json | head -5
   ```
   若无新提交，说明同步未执行任何操作

2. 验证 `FEISHU_FILTER_CONDITIONS` 是否过滤掉了所有记录
   ```bash
   # 本地测试（若需）
   python core.py  # 查看是否读取到飞书数据
   ```

3. 确认滴答 `DIDA_PROJECT_ID` 正确
   - 登录滴答清单 Web → 项目列表 → 查看 URL 中的项目 ID
   - 更新 GitHub Secret

### 禁用临时同步

若需临时停止定时运行（不删除工作流）：

1. 编辑 `.github/workflows/sync.yml`
2. 注释掉 `schedule` 部分：
   ```yaml
   # schedule:
   #   - cron: "0 */2 * * *"
   ```
3. 提交更改
4. 需要恢复时，反注释即可

---

## 第 5 步｜手动测试与验证

### 单步测试流程

**目标**：验证整个同步链路端到端正常

```
Step 1: 在飞书多维表格新增一条测试记录
        标题："【测试】GitHub Actions 同步验证"
        优先级：高
        状态：进行中
        ↓
Step 2: 手动触发 GitHub Actions 工作流（Actions > Run workflow）
        ↓
Step 3: 等待工作流执行完毕（查看日志确认成功）
        ↓
Step 4: 登录滴答清单，查看目标项目
        应出现新任务，标题、优先级、到期日期与飞书一致
        ↓
Step 5: （可选）在滴答完成任务，等待下一次定时同步
        飞书表格中该记录的"已同步"状态应更新
```

### 验证清单

- [ ] 飞书表格新增记录成功
- [ ] GitHub Actions 手动运行成功（无红色错误）
- [ ] 日志中显示 "Synced X records"
- [ ] 滴答清单目标项目出现新任务
- [ ] 任务标题、优先级、到期日期完全匹配
- [ ] `state/mapping.json` 已自动提交到 Git

---

## 第 6 步｜自定义调整

### 修改同步频率

编辑 `.github/workflows/sync.yml`，修改 `cron` 表达式。**常见场景**：

| 需求 | Cron 表达式 | 说明 |
|---|---|---|
| 每小时整点 | `"0 * * * *"` | `*` 表示每小时 |
| 每 30 分钟 | `"*/30 * * * *"` | 首个 `*` 是分钟 |
| 工作日 09:00 | `"0 1 * * 1-5"` | UTC 01:00 = CST 09:00（周一至五） |
| 每周一 00:00 | `"0 0 * * 1"` | UTC 每周一午夜 |
| 每天 12:00（CST） | `"0 4 * * *"` | UTC 04:00 = CST 12:00 |

验证工具：[crontab.guru](https://crontab.guru/)

### 调整字段映射

若飞书或滴答表字段变更，更新 GitHub Secrets：

1. 本地运行 `python core.py` 查看当前字段映射
2. 更新 `FEISHU_FIELD_MAPPING`（如有变更）
3. 在 GitHub Settings > Secrets 中更新对应 Secret
4. 工作流下次运行自动读取新映射

### 关闭 dry_run

工作流默认在 **dry_run=true** 模式下运行（仅预览不写入）。要启用实际同步：

在 `.github/workflows/sync.yml` 中设置：
```yaml
env:
  DRY_RUN: "false"
```

（注意：环境变量优先级低于 GitHub Secrets 中的 `FEISHU_BASE_TOKEN` 等，不会冲突）

---

## 附录 A｜Git 自动提交说明

工作流每次运行后，自动执行：
```bash
git add state/mapping.json
git commit -m "Auto sync: $(date)"
git push
```

**作用**：
- 持久化上次同步的状态和映射关系
- 支持多机协作时的同步位置恢复

**若想禁用自动提交**，编辑工作流删除最后的提交步骤。

---

## 附录 B｜环境变量优先级

工作流环境变量读取顺序（高到低）：

1. **GitHub Secrets**（最高优先级）
2. **`.env` 文件**（若存在，本地开发时）
3. **`config.json`**（默认配置）
4. **`config.example.json`**（内置默认值）

→ **GitHub Actions 中**，10 个 Secrets 会自动覆盖本地 `config.json` 中的对应值。

---

## 附录 C｜故障诊断快速表

| 症状 | 第一步检查 | 第二步检查 | 解决方案 |
|---|---|---|---|
| **Actions 无运行** | 仓库 Settings 是否启用 Actions | `.github/workflows/sync.yml` 是否在 main 分支 | 启用 Actions，push 工作流文件 |
| **运行失败（红色✗）** | 日志中错误信息 | 对应错误是否在上文表格中 | 按表格对应解决方案操作 |
| **同步 0 条记录** | `FEISHU_FILTER_CONDITIONS` 是否过严 | 飞书表格是否有符合条件的记录 | 放宽过滤条件或新增测试记录 |
| **滴答未收到任务** | `DIDA_PROJECT_ID` 是否正确 | 滴答 token 是否过期 | 验证 ID，重跑 `oauth.py auth` |
| **Git 提交失败** | 工作流是否有 push 权限 | 仓库是否保护 main 分支 | 检查分支保护规则，允许 Actions 推送 |

---

## 后续维护清单

- [ ] 每周一检查 Actions 运行日志，确保无异常
- [ ] 每月审计 `state/mapping.json` 提交历史
- [ ] 飞书 / 滴答 API 凭据有效期临近时，提前更新 GitHub Secrets
- [ ] 若需修改同步规则，先在本地 `config.json` 测试，再同步到 Secrets

---

**部署完成！** 工作流现已就绪，将在设定时刻自动执行同步任务。
