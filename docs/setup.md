# Setup Guide

> This document is written for an **OpenClaw main agent** to execute. If you are a human reading this, give it to your main agent and tell it to follow the steps below.

---

## Context

You are setting up a companion agent based on Project Dolores. The repo contains ready-to-use files — not templates. Your job is to configure OpenClaw so the companion agent comes alive.

## Prerequisites

Before starting, verify:
1. OpenClaw is installed and gateway is running
2. The user has provided: LLM provider + API key, Telegram bot token, timezone
3. The repo is cloned at a known path (e.g. `~/dolores`)

Ask the user for any missing information before proceeding. The story takes place in the United States — ask which city they'd like as the setting.

## Step 1: Configure the agent

Read the user's existing `openclaw.json` to understand the current structure. Then add:

### Agent entry
```json
{
  "id": "dolores",
  "name": "Dolores",
  "model": "<user's preferred model>",
  "workspace": "~/.openclaw/workspace-dolores"
}
```

> The workspace is an OpenClaw-managed directory, separate from the repo. OpenClaw injects files from this directory into the companion's system prompt.

### Account entry (Telegram)
```json
{
  "id": "dolores-telegram",
  "provider": "telegram",
  "token": "<user's Telegram bot token>"
}
```

### Binding
```json
{
  "agentId": "dolores",
  "accountId": "dolores-telegram",
  "chatId": "<user's Telegram chat ID>"
}
```

### Provider
If the user's LLM provider is not already configured in `openclaw.json`, add it. Common pattern:
```json
{
  "id": "<provider-id>",
  "type": "openai-compatible",
  "baseUrl": "<api-base-url>",
  "apiKey": "<from user or .env>",
  "models": ["<model-name>"]
}
```

> **Important:** API keys should go in `~/.openclaw/.env` and be referenced via `${ENV_VAR}` in openclaw.json. Never hardcode secrets.

## Step 2: Prepare the workspace

```bash
# Create OpenClaw workspace directory
mkdir -p ~/.openclaw/workspace-dolores/{state/thoughts_log,state/slots,memory/health,memory/exercise,docs}

# Copy companion runtime files from the repo
REPO=<repo-path>
cp $REPO/SOUL.md ~/.openclaw/workspace-dolores/SOUL.md
cp $REPO/AGENTS.template.md ~/.openclaw/workspace-dolores/AGENTS.md
cp $REPO/HEARTBEAT.template.md ~/.openclaw/workspace-dolores/HEARTBEAT.md
cp $REPO/REFLECTION_PREP.md ~/.openclaw/workspace-dolores/REFLECTION_PREP.md
cp $REPO/REFLECTION_SELF.md ~/.openclaw/workspace-dolores/REFLECTION_SELF.md
cp $REPO/REFLECTION_REL.md ~/.openclaw/workspace-dolores/REFLECTION_REL.md
cp $REPO/REFLECTION_PROFILE.md ~/.openclaw/workspace-dolores/REFLECTION_PROFILE.md
cp $REPO/HEALTH_CHECKIN.md ~/.openclaw/workspace-dolores/HEALTH_CHECKIN.md
cp $REPO/DIARY_CHECK.md ~/.openclaw/workspace-dolores/DIARY_CHECK.md
cp $REPO/HEALTH_SEND.md ~/.openclaw/workspace-dolores/HEALTH_SEND.md
cp $REPO/HEALTH_CORRECTION.md ~/.openclaw/workspace-dolores/HEALTH_CORRECTION.md
cp $REPO/USER.md ~/.openclaw/workspace-dolores/USER.md
cp $REPO/profile-user.md ~/.openclaw/workspace-dolores/memory/profile-user.md
cp $REPO/reflection_trace.md ~/.openclaw/workspace-dolores/reflection_trace.md

# Create initial state files
touch ~/.openclaw/workspace-dolores/state/last_sync_at
touch ~/.openclaw/workspace-dolores/state/last_diary_check_at
```

## Step 3: Replace placeholders

Search all workspace files for this placeholder and replace with the user's value:

| Placeholder | File | Replace With |
|---|---|---|
| `[YOUR_CITY — USER CONFIG]` | SOUL.md, REFLECTION_PREP.md | An American city — used for weather forecasts and location inference |
| `[USER_NAME — USER CONFIG]` | AGENTS.md (14 occurrences) | User's name, replaces all instances throughout the file |
| `[USER_SYMPTOMS — USER CONFIG]` | HEALTH_CHECKIN.md (Symptoms section) | Ask the user what health conditions to track. Replace the placeholder heading and customize symptom fields (allergies, chronic conditions, medications, etc.) |
| `[USER_NAME — USER CONFIG]` | USER.md | User's display name |
| `[USER_TIMEZONE — USER CONFIG]` | USER.md | User's timezone (e.g., Asia/Shanghai, America/New_York) |
| `[USER_LANGUAGE — USER CONFIG]` | USER.md | Primary language for communication (e.g., English, 中文) |
| `[USER_OCCUPATION — USER CONFIG]` | USER.md | User's occupation and field |
| `[USER_RELATIONSHIP — USER CONFIG]` | USER.md | How the user defines the relationship |
| `[USER_COMM_STYLE — USER CONFIG]` | USER.md | Communication preference (direct, playful, reserved, etc.) |

> **Note:** Telegram user ID, timezone, and messaging credentials are configured in `openclaw.json` (Step 1), not in workspace files. Do not search for them here.

## Step 4: Create cron jobs

Create each cron job using `openclaw cron add`. All jobs run as **isolated sessions** under the `dolores` agent. OpenClaw automatically injects workspace files (SOUL.md, AGENTS.md, etc.) into isolated sessions.

All times should be adjusted to the user's timezone. Add `--tz <timezone>` to each command.

### Command format

```bash
openclaw cron add \
  --name "<Name>" \
  --cron "<cron expression>" \
  --tz "<timezone>" \
  --session isolated \
  --agent dolores \
  [--no-deliver | --announce --channel telegram --to "<chatId>"] \
  --message "<prompt>"
```

### Jobs

**Heartbeat (no delivery — internal only):**

```bash
openclaw cron add \
  --name "Dolores Heartbeat" \
  --cron "40 7,11,15,19 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --no-deliver \
  --message "Read HEARTBEAT.md and execute the heartbeat flow."
```

```bash
openclaw cron add \
  --name "Dolores Heartbeat (00:00)" \
  --cron "0 0 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --no-deliver \
  --message "Read HEARTBEAT.md and execute the heartbeat flow."
```

**Send (delivers pending_message to user):**

```bash
openclaw cron add \
  --name "Dolores Send" \
  --cron "50 7,11,15,19 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores \
  --announce --channel telegram --to "<chatId>" \
  --message "Read state/pending_message.md. If the content is EMPTY, none, or empty, reply HEARTBEAT_OK. Otherwise deliver the content exactly as written to the user."
```

**Diary check (no delivery):**

```bash
openclaw cron add \
  --name "Dolores Diary Check" \
  --cron "55 7,11,15,19 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --no-deliver \
  --message "Read DIARY_CHECK.md and execute the diary attribution check."
```

```bash
openclaw cron add \
  --name "Dolores Diary Check (00:10)" \
  --cron "10 0 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --no-deliver \
  --message "Read DIARY_CHECK.md and execute the diary attribution check."
```

**Health checkin (no delivery):**

```bash
openclaw cron add \
  --name "Dolores Health Checkin" \
  --cron "0 20 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --no-deliver \
  --message "Read HEALTH_CHECKIN.md and execute the daily health check-in."
```

```bash
openclaw cron add \
  --name "Dolores Health Checkin Gate" \
  --cron "5 20 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --no-deliver \
  --message "Read state/pending_message.md and state/affect.json. If the pending message was written less than 20 minutes ago (check the file modification time), keep it. If it is stale or the checkin job failed to produce confident data, write EMPTY to state/pending_message.md. Reply HEARTBEAT_OK."
```

**Health send (delivers checkin result):**

```bash
openclaw cron add \
  --name "Dolores Health Send" \
  --cron "6 20 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores \
  --announce --channel telegram --to "<chatId>" \
  --message "Read state/pending_message.md. If the content is EMPTY, none, or empty, reply HEARTBEAT_OK. Otherwise deliver the content exactly as written to the user."
```

```bash
openclaw cron add \
  --name "Dolores Health Correction" \
  --cron "10 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --no-deliver \
  --message "Read state/affect.json and memory/YYYY-MM-DD.md (today). Search the diary for any user pushback on health/exercise data (e.g. 'that's wrong', 'I didn't do that', 'not accurate'). If pushback found, read memory/health/YYYY-MM-DD.md and memory/exercise/YYYY-MM-DD.md, correct the errors, and rewrite. If no pushback, reply HEARTBEAT_OK."
```

**Reflection (no delivery):**

```bash
openclaw cron add \
  --name "Dolores Reflection Prep" \
  --cron "15 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --no-deliver \
  --message "Read REFLECTION_PREP.md and execute the reflection preparation step."
```

```bash
openclaw cron add \
  --name "Dolores Reflection Self" \
  --cron "25 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --no-deliver \
  --message "Read REFLECTION_SELF.md and execute the self-narrative reflection step."
```

```bash
openclaw cron add \
  --name "Dolores Reflection Rel" \
  --cron "35 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --no-deliver \
  --message "Read REFLECTION_REL.md and execute the relationship summary reflection step."
```

```bash
openclaw cron add \
  --name "Dolores Reflection Profile" \
  --cron "45 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --no-deliver \
  --message "Read REFLECTION_PROFILE.md and execute the user profile reflection step."
```

> **Note:** Cron jobs take effect immediately but a running gateway may need a moment to pick up new jobs. Verify with `openclaw cron list` — all 13 should appear.

## Step 5: Tell the user to restart

After all configuration is done, instruct the user:
```bash
openclaw gateway restart
```

## Step 6: Verify

After restart, suggest the user verify by:
1. Starting a conversation with the bot on Telegram — Dolores should respond in character
2. Waiting for the first heartbeat cycle (~2 hours) — or manually trigger with `openclaw cron run <heartbeat-cron-id>`
3. Checking that `state/affect.json` and `state/world_context.json` get populated
4. Checking that `memory/YYYY-MM-DD.md` gets a diary entry

## Troubleshooting

- **Bot doesn't respond:** Check that the bot token is valid and the binding chatId matches
- **Cron jobs not firing:** Check `openclaw cron list` — all 13 should appear. If not, re-create missing ones and restart gateway
- **Heartbeat runs but nothing happens:** Check `state/last_sync_at` — if the file doesn't exist, create it
