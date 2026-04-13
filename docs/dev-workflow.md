# Dolores Dev Workflow

> Based on the Akemi architecture — battle-tested companion template.
> Follow this workflow for any modification to Project Dolores files.

---

## Principles

- Ready to use out of the box, not template parts
- All files written for Dolores in first person ("you")
- Private content marked with `[PLACEHOLDER — USER CONFIG]`; setup.md guides the main agent to replace them
- Preserve proven architecture logic from the Akemi reference; only sanitize and generalize

## Checklist (every modification must pass)

1. **Language: English only**
2. **Zero private references:** no real names, no private user info
3. **Zero sensitive data:** no API keys, tokens, chat IDs, absolute paths
4. **Placeholders aligned with setup.md**

## Per-File Workflow (7 steps)

### 1. Read source + target
- Read the Akemi reference file for the canonical logic
- Read the Dolores current file

### 2. Identify private content
- Hardcoded names → Dolores or `[PLACEHOLDER — USER CONFIG]`
- Private script paths → remove or mark optional
- Private memory_search queries → generalize

### 3. Unify tone
- Third person (the companion / the user) → Dolores first person ("you")
- Match SOUL.md tone

### 4. Modify
- Edit the Dolores file in place

### 5. Cross-check
- **ARCHITECTURE.md** — matching sections (file tree, flow descriptions, responsibility tables)
- **docs/setup.md** — any new steps or placeholders needed
- **README.md** — any updates needed

### 6. Grep scan
```bash
grep -rni "Papi\|Akemi\|the companion\|the user\|USER\.md\|IDENTITY\.md" ~/project-dolores/
```
Confirm zero residual references.

### 7. Record + push

## Placeholder Reference

Format: `[PLACEHOLDER_NAME — USER CONFIG]`

| Placeholder | File | Description |
|---|---|---|
| `[YOUR_CITY — USER CONFIG]` | REFLECTION_PREP.md | City for weather lookup |
| `[USER_NAME — USER CONFIG]` | AGENTS.md (14 occurrences) | User's name |

## Cross-File Dependencies

| Modified file | Cross-check |
|---|---|
| AGENTS.md | ARCHITECTURE §3 + setup.md Step 2/3 |
| HEARTBEAT.md | ARCHITECTURE §8 + setup.md cron prompts |
| HEALTH_CHECKIN.md | ARCHITECTURE §10 + setup.md cron prompts |
| DIARY_CHECK.md | ARCHITECTURE §8 + setup.md cron prompts |
| HEALTH_SEND.md | ARCHITECTURE §6 + setup.md cron prompts |
| SOUL.md | ARCHITECTURE §2 + setup.md |
| REFLECTION_*.md | ARCHITECTURE §9 + setup.md cron prompts |
| state/ initial files | ARCHITECTURE §4 file tree |
| memory/ initial files | ARCHITECTURE §5 file tree |
