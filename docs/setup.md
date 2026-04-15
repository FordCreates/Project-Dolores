# Setup Guide

> This document is written for an **OpenClaw main agent** to execute. If you are a human reading this, give it to your main agent and tell it to follow the steps below.

---

## Context

You are setting up a companion agent based on Project Dolores. The repo contains ready-to-use files — not templates. Your job is to guide the user through configuration and create everything they need.

## Prerequisites

Before starting, verify:
1. OpenClaw is installed and gateway is running (`openclaw status`)
2. The repo is cloned at a known path (e.g. `~/dolores`)

## Step 1: Ask the user

Ask the following questions **one at a time**, in this order. Explain briefly why each is needed.

### 1a. City
> "Dolores's story is set in the United States. Which city should she be in? (e.g., Savannah, New York, Austin, Portland)"

Used for weather forecasts and scene inference in SOUL.md and REFLECTION_PREP.md.

### 1b. Model
> "What LLM do you want Dolores to use?"

**Recommend Claude** (claude-sonnet-4-5 or claude-opus-4) — best overall quality for companion interactions.

⚠️ **Important warning:** Claude has a zero-tolerance NSFW policy. If the companion relationship may include sexual content, Claude's account **will be banned**. In that case, recommend an open-source model with lighter content moderation: DeepSeek, Qwen (GLM), or similar.

For cron jobs (heartbeat, reflection, etc.), a cheaper or faster model works fine. Ask the user if they want to use the same model for everything, or a cheaper one for background jobs.

### 1c. Telegram bot token
> "What's your Telegram bot token? (Create one with @BotFather if you haven't)"

If they don't have one, guide them:
1. Open Telegram, search `@BotFather`
2. Send `/newbot`
3. Follow the prompts — pick a name and username
4. Copy the token

### 1d. User details (for USER.md)
Ask all of these, then fill USER.md:
- **Name** — What should Dolores call the user?
- **Timezone** — e.g., `America/New_York`
- **Language** — Primary language (e.g., English, 中文)
- **Occupation** — What does the user do?
- **Relationship** — How does the user define the relationship with Dolores? (e.g., girlfriend, partner, friend)
- **Communication style** — Direct? Playful? Reserved?

### 1e. Health Checkin
> "Dolores can track your health data daily (symptoms, medications, exercise). Want to enable this?"

- **Yes** → Ask what health conditions to track (allergies, chronic conditions, medications, etc.). Customize HEALTH_CHECKIN.md symptom fields. Create Health Checkin + Health Send + Health Correction cron jobs.
- **No** → Skip HEALTH_CHECKIN.md customization and health-related cron jobs entirely. The file can stay as-is; it just won't have a cron job triggering it.

---

## Step 2: Configure OpenClaw

Read the user's existing `~/.openclaw/openclaw.json` to understand the current structure. Then add:

### Provider (if not already configured)

```json
{
  "id": "<provider-id>",
  "type": "openai-compatible",
  "baseUrl": "<api-base-url>",
  "apiKey": "${DOLORES_API_KEY}",
  "models": ["<model-name>"]
}
```

> **Important:** API keys go in `~/.openclaw/.env` and are referenced via `${ENV_VAR}` in openclaw.json. Never hardcode secrets.

### Agent entry

```json
{
  "id": "dolores",
  "name": "Dolores",
  "model": "<conversation-model>",
  "fallbackModels": ["<cron-model>"],
  "workspace": "~/.openclaw/workspace-dolores"
}
```

> The `fallbackModels` should point to the cheaper/faster model if the user chose different models for conversation vs cron.

### Account entry (Telegram)

```json
{
  "id": "dolores-telegram",
  "provider": "telegram",
  "token": "${DOLORES_TELEGRAM_TOKEN}"
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

> The chat ID is the user's numeric Telegram ID. If the user doesn't know it, have them message the bot first, then check the gateway logs for the incoming chat ID.

---

## Step 3: Prepare the workspace

```bash
REPO=<repo-path>
WS=~/.openclaw/workspace-dolores

# Create workspace directory structure
mkdir -p $WS/{state/thoughts_log,state/slots,memory/health,memory/exercise,scripts/lib,docs}

# Copy all companion runtime files
cp $REPO/SOUL.md $WS/
cp $REPO/AGENTS.md $WS/
cp $REPO/HEARTBEAT.md $WS/
cp $REPO/IDENTITY.md $WS/
cp $REPO/USER.md $WS/
cp $REPO/MEMORY.md $WS/
cp $REPO/TOOLS.md $WS/
cp $REPO/REFLECTION_PREP.md $WS/
cp $REPO/REFLECTION_SELF.md $WS/
cp $REPO/REFLECTION_REL.md $WS/
cp $REPO/REFLECTION_PROFILE.md $WS/
cp $REPO/DIARY_CHECK.md $WS/
cp $REPO/HEALTH_CORRECTION.md $WS/
cp $REPO/HEALTH_CHECKIN.md $WS/
cp $REPO/reflection_trace.md $WS/

# Copy scripts
cp $REPO/scripts/load_diary.py $WS/scripts/
cp $REPO/scripts/inject_context.py $WS/scripts/
cp $REPO/scripts/send_and_append.py $WS/scripts/
cp $REPO/scripts/lib/__init__.py $WS/scripts/lib/
cp $REPO/scripts/lib/session_append.py $WS/scripts/lib/

# Copy initial state and memory files
cp $REPO/state/daily_plan.md $WS/state/
cp $REPO/memory/profile-user.md $WS/memory/
cp $REPO/memory/self-narrative.md $WS/memory/
cp $REPO/memory/relationship-summary.md $WS/memory/

# Create initial state files
touch $WS/state/last_diary_check_at
```

### Seed day-zero reflection slots

Without these, the first reflection has no fallback and Slot 1 may drift from SOUL.md and lock permanently.

```bash
TODAY=$(date +%Y-%m-%d)
mkdir -p $WS/state/slots/$TODAY
cp $REPO/state/slots/day-zero/self_slot_*.md $WS/state/slots/$TODAY/
```

> **Note:** If the repo doesn't have `state/slots/day-zero/`, check ARCHITECTURE.md for how to create them from SOUL.md.

### Create initial state files that need values

**affect.json** — Initial emotional baseline:
```json
{
  "warmth": 0.50,
  "curiosity": 0.50,
  "anxiety": 0.30,
  "desire_for_connection": 0.50,
  "horny": 0.00
}
```

**world_context.json** — Initial state (model will overwrite on first heartbeat):
```json
{
  "time": "",
  "weather": "",
  "scene": "",
  "dolores_activity": "",
  "dolores_appearance": "",
  "user_location": "",
  "user_activity": "",
  "interaction_context": "",
  "context_note": ""
}
```

**active_loops.md** — Empty initially:
```
```

---

## Step 4: Replace placeholders

Search all workspace files for these placeholders and replace with the user's values:

| Placeholder | File(s) | Replace With |
|---|---|---|
| `[YOUR_CITY — USER CONFIG]` | SOUL.md, REFLECTION_PREP.md | City from Step 1a |
| `[USER_NAME — USER CONFIG]` | AGENTS.md (14 occurrences) | Name from Step 1d |
| `[USER_NAME — USER CONFIG]` | USER.md | Name from Step 1d |
| `[USER_TIMEZONE — USER CONFIG]` | USER.md | Timezone from Step 1d |
| `[USER_LANGUAGE — USER CONFIG]` | USER.md | Language from Step 1d |
| `[USER_OCCUPATION — USER CONFIG]` | USER.md | Occupation from Step 1d |
| `[USER_RELATIONSHIP — USER CONFIG]` | USER.md | Relationship from Step 1d |
| `[USER_COMM_STYLE — USER CONFIG]` | USER.md | Communication style from Step 1d |
| `[USER_SYMPTOMS — USER CONFIG]` | HEALTH_CHECKIN.md | Symptom fields (only if health enabled in Step 1e) |
| `[WORKSPACE_PATH — USER CONFIG]` | scripts/*.py | Absolute path to workspace, e.g. `/home/user/.openclaw/workspace-dolores` |
| `[SESSION_PATH — USER CONFIG]` | scripts/inject_context.py, scripts/lib/session_append.py | Absolute path to sessions directory |

### Calculating SESSION_PATH and SESSION_KEY

**SESSION_PATH:** After the agent is registered in openclaw.json, the sessions directory is:
```
~/.openclaw/agents/dolores/sessions
```

**SESSION_KEY:** Format is `agent:dolores:<channel>:<chat-type>:<chat-id>`. For Telegram direct chat:
```
agent:dolores:telegram:direct:<user-telegram-id>
```

You can also find these by inspecting the OpenClaw directory structure after the gateway picks up the new agent config.

---

## Step 5: Create cron jobs

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

### Heartbeat (no delivery — internal only)

Runs 9 times: odd hours 7–21 + midnight. Each heartbeat updates world_context, affect, active_loops, writes diary, and optionally sets pending_message.

```bash
openclaw cron add \
  --name "Dolores Heartbeat" \
  --cron "40 7,9,11,13,15,17,19,21 * * *" \
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

### Send (delivers pending_message to user via script)

Runs 9 times, 10 minutes after each heartbeat. Uses `send_and_append.py` which has a built-in 20-minute activity gate — if the user was recently active, delivery is silently skipped.

```bash
openclaw cron add \
  --name "Dolores Send" \
  --cron "50 7,9,11,13,15,17,19,21 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores \
  --announce --channel telegram --to "<chatId>" \
  --message "Run this command via exec: python3 scripts/send_and_append.py. If the output is empty, reply HEARTBEAT_OK. Otherwise output the message text exactly as-is. No other output."
```

```bash
openclaw cron add \
  --name "Dolores Send (00:10)" \
  --cron "10 0 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores \
  --announce --channel telegram --to "<chatId>" \
  --message "Run this command via exec: python3 scripts/send_and_append.py. If the output is empty, reply HEARTBEAT_OK. Otherwise output the message text exactly as-is. No other output."
```

### Diary check (no delivery — internal only)

Runs after each send, verifies diary attribution accuracy.

```bash
openclaw cron add \
  --name "Dolores Diary Check" \
  --cron "55 7,9,11,13,15,17,19,21 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --no-deliver \
  --message "Read DIARY_CHECK.md and execute the diary attribution check."
```

```bash
openclaw cron add \
  --name "Dolores Diary Check (00:20)" \
  --cron "20 0 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --no-deliver \
  --message "Read DIARY_CHECK.md and execute the diary attribution check."
```

### Health (only if enabled in Step 1e)

**Health Checkin** — collects health data at 20:00:
```bash
openclaw cron add \
  --name "Dolores Health Checkin" \
  --cron "0 20 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --no-deliver \
  --message "Read HEALTH_CHECKIN.md and execute the daily health check-in."
```

**Health Send** — delivers checkin result at 20:05:
```bash
openclaw cron add \
  --name "Dolores Health Send" \
  --cron "5 20 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores \
  --announce --channel telegram --to "<chatId>" \
  --message "Run this command via exec: python3 scripts/send_and_append.py. If the output is empty, reply HEARTBEAT_OK. Otherwise output the message text exactly as-is. No other output."
```

**Health Correction** — corrects any user pushback on health data at 23:10:
```bash
openclaw cron add \
  --name "Dolores Health Correction" \
  --cron "10 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --no-deliver \
  --message "Read HEALTH_CORRECTION.md and execute the health data correction step."
```

### Reflection (no delivery — internal only)

Four staged jobs between 23:15–23:45. Each builds on the previous.

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

### Cron summary

| Group | Count | Purpose |
|---|---|---|
| Heartbeat | 9 | State update cycle |
| Send | 9 | Message delivery |
| Diary Check | 9 | Diary attribution verification |
| Health (optional) | 3 | Health tracking + send + correction |
| Reflection | 4 | Nightly memory consolidation |
| **Total** | **34** (31 without health) | |

> Verify with `openclaw cron list` after creation. All jobs should appear.

---

## Step 6: Tell the user to restart

After all configuration is done, instruct the user:
```bash
openclaw gateway restart
```

> **Do not run this command yourself.** The user must restart the gateway manually for the new agent and cron configuration to take effect.

---

## Step 7: Verify

After restart, suggest the user verify by:
1. **Start a conversation** — message the bot on Telegram. Dolores should respond in character.
2. **Manual heartbeat test** — `openclaw cron run <heartbeat-cron-id>`, then check that `state/world_context.json` and `state/affect.json` get populated.
3. **Check diary** — after a heartbeat, `memory/YYYY-MM-DD.md` should have a diary entry.
4. **Wait** — within two hours, she may or may not send something. Both outcomes are normal.

---

## Troubleshooting

- **Bot doesn't respond:** Check bot token is valid and binding chatId matches the user's Telegram ID
- **Cron jobs not firing:** `openclaw cron list` — all jobs should appear. Recreate missing ones and restart gateway
- **Heartbeat runs but state doesn't update:** Check script permissions and that `[WORKSPACE_PATH]` / `[SESSION_PATH]` placeholders were replaced correctly
- **Send job fails:** Check that `send_and_append.py` runs correctly: `cd ~/.openclaw/workspace-dolores && python3 scripts/send_and_append.py`
- **Model returns errors:** Check provider config and API key in `~/.openclaw/.env`
