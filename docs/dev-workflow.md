# Dolores 开发规范

> 基于 Akemi 架构的开源 companion 模板
> 每次改造文件必须遵守此流程

---

## 改造原则

- 开箱即用，不是模板零件
- 所有文件面向 Dolores 第一人称（"你"）
- 私有内容用 `[PLACEHOLDER — USER CONFIG]` 标记，setup.md 引导 main agent 替换
- 不删减 Akemi 已验证的架构逻辑，只脱敏通用化

## 检查标准（每步改造必须通过）

1. **语言：必须用英文**
2. **零私有引用：** 无 Papi、Akemi 或任何 Papi 私有信息
3. **零敏感信息：** 无 API key、token、具体 chat ID、具体路径等
4. **user/companion占位符：** user/companion占位符是否修复为对齐setup.md所需/Dolores

## 单文件改造流程（七步）

### 1. 读源 + 读目标
- 读 Akemi 实际运行版本（`~/.openclaw/workspace-companion/<file>`）
- 读 Dolores 当前版本（`~/project-dolores/<file>`）

### 2. 识别私有内容
- Papi / Akemi 硬编码 → Dolores 或 `[PLACEHOLDER — USER CONFIG]`
- 私有脚本路径（akemi-remind、nano-banana-pro skill）→ 删除或标注可选
- 私有 memory_search 关键词 → 通用化

### 3. 语气统一
- 第三人称通用（the companion / the user）→ Dolores 第一人称（"你"）
- 与 SOUL.md 语气保持一致

### 4. 改造文件
- 原地修改 Dolores 文件
- 去 .template 后缀（如适用）

### 5. 联动检查
- **ARCHITECTURE.md** — 对应章节（文件树、流程描述、职责表）是否一致
- **docs/setup.md** — 是否需要新增步骤或占位符
- **README.md** — 是否需要更新

### 6. grep 扫描
```bash
grep -rni "Papi\|Akemi\|the companion\|the user\|USER\.md\|IDENTITY\.md" ~/project-dolores/
```
确认零残留。

### 7. 记录 + push
- 更新 memory/YYYY-MM-DD.md
- git commit + push

## 占位符规范

格式：`[PLACEHOLDER_NAME — USER CONFIG]`

当前占位符：

| 占位符 | 所在文件 | 说明 |
|---|---|---|
| `[YOUR_CITY — USER CONFIG]` | REFLECTION_PREP.md | 天气查询城市 |
| `[USER_NAME — USER CONFIG]` | AGENTS.md（待加） | 用户称呼，替换 "the user" |

## 联动规则

| 改造文件 | 联动检查 |
|---|---|
| AGENTS.md | ARCHITECTURE §3 + setup.md Step 2/3 |
| HEARTBEAT.md | ARCHITECTURE §8 + setup.md cron prompts |
| HEALTH_CHECKIN.md | ARCHITECTURE §10 + setup.md cron prompts |
| DIARY_CHECK.md | ARCHITECTURE §8 + setup.md cron prompts |
| HEALTH_SEND.md | ARCHITECTURE §6 + setup.md cron prompts |
| SOUL.md | ARCHITECTURE §2 + setup.md |
| REFLECTION_*.md | ARCHITECTURE §9 + setup.md cron prompts |
| state/ 初始文件 | ARCHITECTURE §4 文件树 |
| memory/ 初始文件 | ARCHITECTURE §5 文件树 |
