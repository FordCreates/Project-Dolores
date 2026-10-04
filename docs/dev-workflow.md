# Dolores Dev Workflow

> Based on a private reference architecture — battle-tested companion template.
> Follow this workflow for any modification to Project Dolores files.

---

## Principles

- Ready to use out of the box, not template parts
- All files written for Dolores in first person ("you")
- Private content marked with `[PLACEHOLDER — USER CONFIG]`; setup.md guides the main agent to replace them
- Reuse proven architecture logic; discard private narratives and independently author public examples

## Checklist (every modification must pass)

1. **Language: English only**
2. **Zero private content:** no private experiences, plots, people or user information. This includes fictional private characters, aliases, relationships and recognizable event combinations.
3. **Zero sensitive data:** no API keys, tokens, chat IDs, absolute paths
4. **Placeholders aligned with setup.md**
5. **Semantic privacy:** review examples, paired calibrations, rules and narrative seeds for translated or renamed private episodes. Check actors, relationship structure, event sequence, places, dates, preferences and distinctive detail combinations; changing names, language or details does not make a private episode public. Intimate/NSFW material needs the same source review. Extract only reusable cognition contracts; discard private examples and write any needed calibration independently. Preserve the established public character setting without importing private biographies. Unresolved provenance blocks publication.
6. **Publication scope:** the same checks apply to all candidate files, comments, images, metadata, Git refs/tags/history, release notes and artifacts. Working-tree checks alone cannot clear a repository with historical private content. Audit reports identify affected paths and categories without quoting private material.

## Per-File Workflow (7 steps)

### 1. Read source + target
- Read the private reference file for the canonical logic
- Read the Dolores current file

### 2. Identify private content
- Private people, biographies, experiences and plots → remove the entire source-derived example or account; never sanitize it by renaming the person to Dolores
- Reusable rules → express without the private episode; independently invent any necessary public example
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
grep -rni "private-name\|real-user-name\|the companion\|the user\|USER\.md\|IDENTITY\.md" ~/project-dolores/
```
Confirm zero residual references. This text scan is only a supporting check.

Then perform the semantic source review in Checklist #5 and the publication-scope check in Checklist #6. Keyword, non-English-character and exact-text scans do not complete either review. Record which public examples and intimate rules were reviewed and their provenance without reproducing private material in the audit or release notes. Any unresolved source or historical finding remains a publication blocker.

### 7. Record + commit; push only with explicit approval

- Record the change and verification result in the project changelog or work log used for that task.
- Stage only the files changed for the task and create a local commit after verification.
- Never fold unrelated dirty files into the commit.
- Push only after the maintainer explicitly approves the exact repository and change set.

### 8. Release notes audit
Before creating a GitHub release, review the changelog / release notes:
- **Never reproduce the leaked content when describing a leak fix.** Write "ungeneralized character name" not the actual name.
- Apply the same zero-private-references rule from Checklist #2 to release notes.
- Treat release notes as public-facing documentation — they are more visible than any individual file.

## Placeholder Reference

Use `[PLACEHOLDER_NAME — USER CONFIG]`. The complete current inventory and per-file replacements are maintained in docs/setup.md Step 6; do not duplicate counts here. Verify the installed workspace with that exact placeholder scan.

## Cross-File Dependencies

| Modified file | Cross-check |
|---|---|
| AGENTS.md | ARCHITECTURE §3 + setup.md Step 2/3 |
| HEARTBEAT.md | ARCHITECTURE §9 + setup.md cron prompts |
| HEALTH_CHECKIN.md | ARCHITECTURE §11 + setup.md cron prompts |
| DIARY_CHECK.md (legacy/manual semantic tool) | AGENTS.md persistence table + ARCHITECTURE §6/§9; it is not a scheduled integrity job |
| DAILY_INTEGRITY_CHECK.md / scripts/daily_integrity_check.py | AGENTS.md persistence table + ARCHITECTURE file/script/responsibility/cron tables + setup.md integrity cron prompts; the public template does not assume automatic Git checkpoints |
| SOUL.md | ARCHITECTURE §2 + setup.md |
| REFLECTION_*.md | ARCHITECTURE §10 + setup.md cron prompts |
| state/ initial files | ARCHITECTURE §4 file tree |
| memory/ initial files | ARCHITECTURE §5 file tree |
| HEARTBEAT_STEPS.md (Phase C exec) | scripts/sticky_sampling.py + state/primed_sticky.md + setup.md §5.5 |
| scripts/sticky_sampling.py | HEARTBEAT_STEPS.md Step 4 + ARCHITECTURE §7 |
| scripts/send_and_append.py / scripts/lib/session_append.py | HEARTBEAT*_STEPS.md pending contract + `.gitignore` runtime receipt/lock paths + ARCHITECTURE send flow/cron table + setup.md command cron; verify acknowledgement-before-clear, receipt recovery, idempotent append, and failure alerts |
| Cron orchestration | ARCHITECTURE cron table + setup.md; distinguish semantic `agentTurn` jobs from deterministic command jobs and do not add a model wrapper around transport-only work |
