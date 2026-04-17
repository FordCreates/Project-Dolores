# Setup Guide

> This document is written for an **OpenClaw main agent** to execute. If you are a human reading this, give it to your main agent and tell it to follow the steps below.

---

## Step 0: Risk Disclosure

Before anything else, scan the project structure and present these risks to the user. Let them decide whether to continue.

### Risks to disclose

1. **Experimental prototype** — This is an early-stage research prototype based on the author's Dual-Helix Cognition model and narrative descent theory. It is rough, actively iterating, and has known bugs. It is not a polished product.

2. **API costs** — 34 cron jobs run daily plus ongoing conversations. This generates continuous token usage and cost.

3. **NSFW account ban risk** — If the relationship includes sexual content, Claude will permanently ban your account. Use open-source models (DeepSeek, Qwen, GLM) for NSFW scenarios.

4. **Privacy** — All conversation logs, diaries, health data, and emotional states are stored as plain text files on your machine. No encryption.

5. **Single-user only** — Designed for one person. Not multi-tenant.

6. **Requires OpenClaw running** — If your machine is off or OpenClaw stops, she stops. No cloud fallback.

7. **Known model limitations** — GLM-family models have weak constraint following on long-form generation (reflection slot bloat, persona drift). Claude is recommended but carries the NSFW risk above.

8. **Basic technical literacy needed** — Your main agent handles most setup, but troubleshooting requires reading logs and running commands.

9. **⚠️ Never run two gateway instances with the same Telegram bot** — If your bot's token is loaded on two machines simultaneously, both gateways will race to process incoming messages. The second instance may have an outdated or empty workspace, producing responses with wrong personality, stale memories, or no memories at all. This causes severe identity and memory corruption that is very hard to clean up. Always ensure only one gateway is connected to your bot at any time.

> After presenting these, ask: "Still want to proceed?"
>
> If no — stop here, no harm done.
> If yes — continue to Step 1.

---

## Context

You are setting up a companion agent based on Project Dolores. The repo contains ready-to-use files — not templates. Your job is to copy them into the OpenClaw workspace, then configure everything step by step by asking the user questions and applying changes immediately.

**Principles:**
- Copy files first, configure second. The user sees action after every question.
- Ask one thing at a time. Apply the change before asking the next.
- Use OpenClaw's secrets provider for API keys (see examples in Step 3). Never hardcode keys directly.

---

## Step 1: Copy files to workspace

```bash
REPO=<repo-path>
WS=~/.openclaw/workspace-dolores

# Create workspace directory structure
mkdir -p $WS/{state/thoughts_log,state/slots,memory/health,memory/exercise,scripts/lib}

# Copy companion runtime files
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
cp $REPO/state/affect.json $WS/state/
cp $REPO/state/world_context.json $WS/state/
cp $REPO/state/active_loops.md $WS/state/
cp $REPO/state/daily_plan.md $WS/state/
cp $REPO/state/pending_message.md $WS/state/
cp $REPO/state/last_sync_at $WS/state/
cp $REPO/memory/profile-user.md $WS/memory/
cp $REPO/memory/self-narrative.md $WS/memory/
cp $REPO/memory/relationship-summary.md $WS/memory/

# Create initial state files
cp $REPO/state/last_diary_check_at $WS/state/

# Seed day-zero reflection slots (prevents first-night drift)
TODAY=$(date +%Y-%m-%d)
mkdir -p $WS/state/slots/$TODAY
cp $REPO/state/slots/day-zero/self_slot_*.md $WS/state/slots/$TODAY/
cp $REPO/state/slots/day-zero/rel_slot_*.md $WS/state/slots/$TODAY/

# Create .gitignore for workspace (runtime files should not be committed)
cat > $WS/.gitignore << 'GITIGNORE'
# Runtime state
state/
# Runtime memory (keep initial seed files, ignore generated)
memory/*.md
memory/*.digest.md
!memory/profile-user.md
!memory/self-narrative.md
!memory/relationship-summary.md
memory/health/
memory/exercise/
!memory/health/.gitkeep
!memory/exercise/.gitkeep
GITIGNORE
```

---

## Step 2: Configure the character

Ask these questions one at a time. After each answer, apply the change immediately.

### 2a. City

> "Dolores's story is set in the United States. Which city should she be in? (e.g., Savannah, New York, Austin, Portland)"

**Apply:** Replace `[YOUR_CITY — USER CONFIG]` in `SOUL.md` and `REFLECTION_PREP.md`.

### 2b. User details

> "What should Dolores call you?"

**Apply:** Replace all `[USER_NAME — USER CONFIG]` across the workspace:
```bash
grep -rl '\[USER_NAME — USER CONFIG\]' ~/.openclaw/workspace-dolores/ --include='*.md' --include='*.py' --include='*.json'
```
This should match: AGENTS.md, USER.md, TOOLS.md, HEARTBEAT.md, HEALTH_CORRECTION.md, DIARY_CHECK.md, MEMORY.md, memory/profile-user.md, state/daily_plan.md.

> "What timezone are you in? (e.g., America/New_York)"

**Apply:** Replace `[USER_TIMEZONE — USER CONFIG]` in `USER.md`.

> "What language do you prefer to communicate in?"

**Apply:** Replace `[USER_LANGUAGE — USER CONFIG]` in `USER.md`.

> "What do you do for work?"

**Apply:** Replace `[USER_OCCUPATION — USER CONFIG]` in `USER.md`.

> "How would you define your relationship with Dolores? (e.g., girlfriend, partner, friend)"

**Apply:** Replace `[USER_RELATIONSHIP — USER CONFIG]` in `USER.md`.

### 2c. Health checkin

> "Dolores can track your daily health data — sleep, exercise, diet, medication, and any symptoms you want monitored. Want to enable this?"

- **Yes** → Ask what symptoms or conditions to track (e.g., allergies, chronic conditions, mental health). Replace `[USER_SYMPTOMS — USER CONFIG]` in `HEALTH_CHECKIN.md` with the actual symptom fields. Remember to create the health cron jobs later (Step 5).
- **No** → Skip. HEALTH_CHECKIN.md stays as-is, just won't have a cron job.

---

## Step 3: Configure OpenClaw

> **⚠️ CRITICAL — Do NOT delete or replace existing agents.**
>
> The user's `openclaw.json` already has at least one agent (the main agent you're running on right now). Your job is to **add** the Dolores agent **alongside** the existing ones, not replace them.
>
> **Rules:**
> - `agents.list` → add the Dolores entry to the array. Do NOT replace the array with only Dolores.
> - `bindings` → add the Dolores binding to the array. Do NOT replace the array.
> - `agents.defaults` → merge new fields into the existing object. Do NOT replace the object.
> - `models.providers` → add the new provider. Do NOT touch existing providers.
> - `channels.telegram.accounts` → add the Dolores account. Do NOT touch existing accounts.
>
> **Before making any changes, backup:**
> ```bash
> cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.bak
> ```
>
> **If anything goes wrong, restore:**
> ```bash
> cp ~/.openclaw/openclaw.json.bak ~/.openclaw/openclaw.json
> ```

Read the user's existing `~/.openclaw/openclaw.json` to understand the current structure — check what providers and models are already configured. Then ask:

### 3a. Session scope (REQUIRED)

> ⚠️ **This is a silent dependency.** Dolores's scripts (`send_and_append.py`, `inject_context.py`) hardcode a session key in the format `agent:dolores:telegram:direct:<user-id>`. This only works if `session.dmScope` is set to `per-channel-peer` (each DM gets its own session key). The OpenClaw default is `main` (all DMs share one session key `agent:dolores:main`), which will cause all session-dependent scripts to fail silently.

**Apply:** Check if `session.dmScope` already exists in `openclaw.json`. If not, add it at the **top level** (NOT inside `agents`):

```json
{
  "session": {
    "dmScope": "per-channel-peer"
  }
}
```

> **Merge** this into the existing top-level config. Do NOT place it inside `agents`.

### 3b. Bootstrap character limit

> Dolores's SOUL.md (~28K chars) and HEARTBEAT.md (~26K chars) exceed OpenClaw's default bootstrap file limit of 20,000 characters. Without increasing this limit, Dolores will see truncated (incomplete) versions of her own character definition.

**Apply:** Check if `agents.defaults.bootstrapMaxChars` already exists in `openclaw.json`. If not, add it:

```json
"agents": {
  "defaults": {
    "bootstrapMaxChars": 35000
  }
}
```

> ⚠️ **Merge** this into the existing `agents.defaults` object if it already exists. Do NOT replace the entire `agents` block.

### 3c. Model

> "Let me check your existing model configuration first."

**Check existing providers:** Read the user's `openclaw.json` and look at `models.providers` and `agents.list`. If Claude or another capable model is already configured, offer to reuse it.

**Recommendation (in this order):**
1. **Claude** (claude-sonnet-4-5 or claude-opus-4) — best overall quality for companion interactions.
2. **GLM-5.1** (via zai or compatible provider) — best open-source option, good quality, no NSFW risk.
3. **DeepSeek / Qwen** — acceptable alternatives.

⚠️ **NSFW warning:** Claude has a zero-tolerance NSFW policy. If the companion relationship may include sexual content, Claude's account **will be banned**. In that case, recommend GLM-5.1 or another open-source model.

> "What LLM do you want Dolores to use for conversations?"

**After choosing the conversation model:**

> "Background jobs (heartbeat, reflection, diary check) run ~30 times/day and don't need the best model. I recommend using a cheaper/faster model for them. Do you want to use [cron model name, e.g. GLM-5.1] for background jobs?"

> ⚠️ **Remember this choice.** Every cron job in Step 6 must include `--model <cron-provider>/<cron-model>` to override the agent's default. If you skip this, all 30+ cron jobs will run on the conversation model, which is extremely expensive.

**Apply:** Read the user's existing `openclaw.json` to understand the structure, then add:

```json
// In secrets.providers (if not already configured):
"secrets": {
  "providers": {
    "default": { "source": "env" }
  }
}
```

**If using OpenRouter** (for GLM-5.1, DeepSeek, or other models via openrouter.ai):

> ⚠️ **You MUST register the model explicitly in the provider config.** OpenClaw's built-in model catalog does not include all OpenRouter models. Without an explicit registration, OpenClaw cannot parse the response correctly → `payloads=0` → agent silently fails with empty replies.

```json
// In models.providers — add or merge into the existing "openrouter" provider:
"openrouter": {
  "baseUrl": "https://openrouter.ai/api/v1",
  "apiKey": {
    "source": "env",
    "provider": "default",
    "id": "OPENROUTER_API_KEY"
  },
  "api": "openai-completions",
  "models": [{
    "id": "z-ai/glm-5.1",
    "name": "GLM 5.1 (OpenRouter)",
    "reasoning": true,
    "input": ["text"],
    "contextWindow": 128000,
    "maxTokens": 8192
  }]
}
```

> ⚠️ **`reasoning: true` is required for GLM models.** Setting it to `false` will cause response parsing failures. If the user already has an "openrouter" provider, **merge** the new model into the existing `models` array — do NOT replace it.

**If using a direct API provider** (e.g., Zhipu AI directly):

```json
// In models.providers — add the LLM provider:
"<provider-id>": {
  "baseUrl": "<api-base-url>",
  "apiKey": {
    "source": "env",
    "provider": "default",
    "id": "DOLORES_API_KEY"
  },
  "api": "openai-completions",
  "models": [{
    "id": "<model-name>",
    "name": "<display-name>",
    "reasoning": false,
    "input": ["text"],
    "contextWindow": 200000,
    "maxTokens": 8192
  }]
}
```

// In agents.list — add the companion agent:
{
  "id": "dolores",
  "name": "Dolores",
  "workspace": "/home/<user>/.openclaw/workspace-dolores",
  "model": {
    "primary": "<provider-id>/<model-name>",
    "fallbacks": ["<cron-provider>/<cron-model>"]
  },
  "memorySearch": { "provider": "local" }
}
```

```bash
# In ~/.openclaw/.env:
echo 'DOLORES_API_KEY=<user-provided-key>' >> ~/.openclaw/.env
```

> **Note:** The `workspace` path must be absolute, not `~/`. The main agent should resolve it.
>
> ⚠️ **Do NOT add `"thinking": "off"` or any `params.thinking` override.** LLM thinking mode improves response quality for companion agents. Disabling it will degrade reflection, empathy, and narrative coherence. Let OpenClaw use its default thinking behavior.

### 3d. Telegram bot

> "What's your Telegram bot token? (Create one with @BotFather if you haven't)"

If they don't have one, guide them:
1. Open Telegram, search `@BotFather`
2. Send `/newbot`
3. Follow the prompts — pick a name and username
4. Copy the token

**Apply:** Add the Telegram account and binding to `openclaw.json`:

```json
// In channels.telegram.accounts:
"dolores": {
  "name": "Dolores",
  "dmPolicy": "pairing",
  "botToken": {
    "source": "env",
    "provider": "default",
    "id": "DOLORES_TELEGRAM_TOKEN"
  },
  "groupPolicy": "allowlist",
  "streaming": "partial"
}

// In bindings array:
{
  "type": "route",
  "agentId": "dolores",
  "match": {
    "channel": "telegram",
    "accountId": "dolores"
  }
}
```

```bash
# In ~/.openclaw/.env:
echo 'DOLORES_TELEGRAM_TOKEN=<user-provided-token>' >> ~/.openclaw/.env
```

> The chat ID is the user's numeric Telegram ID. If the user doesn't know it, have them message the bot first, then check the gateway logs.

---

## Step 4: Bot avatar (recommended)

> "One more thing before we finish setup — the default Telegram bot icon is a generic robot silhouette. Setting a custom avatar makes Dolores feel like a person, not a bot."

> "I've prepared an avatar image at `[REPO_PATH]/media/Dolores.jpeg`. Open Telegram, find @BotFather, send `/setuserpic`, select Dolores's bot, and upload that image."

If the user asks what kind of avatar works best: a realistic portrait photo (not anime, not cartoon) at the character's approximate age and appearance. The file should be placed in the repo's `media/` directory before setup begins.

---

## Step 5: Replace script placeholders

Scripts contain path placeholders that depend on the user's system. Replace them:

| Placeholder | File(s) | Replace With |
|---|---|---|
| `[WORKSPACE_PATH — USER CONFIG]` | scripts/load_diary.py, scripts/inject_context.py, scripts/send_and_append.py | Absolute path to workspace, e.g. `/home/user/.openclaw/workspace-dolores` |
| `[SESSION_PATH — USER CONFIG]` | scripts/inject_context.py, scripts/lib/session_append.py, **HEARTBEAT.md** (3 occurrences) | Absolute path to sessions directory |
| `[SESSION_KEY — USER CONFIG]` | scripts/inject_context.py, scripts/lib/session_append.py, **HEARTBEAT.md** (1 occurrence) | Session key for the active conversation |

### Calculating SESSION_PATH and SESSION_KEY

**SESSION_PATH:** `~/.openclaw/agents/dolores/sessions`

**SESSION_KEY:** `agent:dolores:telegram:direct:<user-telegram-id>`

> **⚠️ SESSION_KEY requires the user's Telegram numeric ID, which you won't know until the bot receives its first message.** Use a placeholder like `<TELEGRAM_ID_PLACEHOLDER>` for now. After Step 6 (gateway restart), have the user message the bot, then check `~/.openclaw/agents/dolores/sessions/sessions.json` for the real ID. Replace the placeholder in all three scripts, then restart the gateway again. **This means two gateway restarts are needed.**

These three placeholders (WORKSPACE_PATH, SESSION_PATH, SESSION_KEY) must be replaced in all listed files. `send_and_append.py` imports `session_append.py`, so SESSION_PATH and SESSION_KEY also affect its behavior even though they aren't in the file directly.

**After replacing all placeholders, verify with:**

```bash
grep -r "USER_CONFIG" ~/.openclaw/workspace-dolores/
```

> ⚠️ **This must return zero results.** If anything shows up, you missed a file — go back and replace it. The most commonly missed files are `HEARTBEAT.md` and `scripts/lib/session_append.py`.

You can verify by inspecting `~/.openclaw/agents/dolores/sessions/sessions.json` after the gateway picks up the new agent config.

---

## Step 6: Create cron jobs

All times adjusted to the user's timezone. Add `--tz <timezone>` to each command.

> ⚠️ **Every cron job MUST include `--model <cron-provider>/<cron-model>`** to use the cheaper/faster cron model chosen in Step 3c. Without this override, all 30+ jobs run on the conversation model — extremely expensive. Replace `<cron-provider>/<cron-model>` with the actual values from Step 3c.

### Command format

```bash
openclaw cron add \
  --name "<Name>" \
  --cron "<cron expression>" \
  --tz "<timezone>" \
  --session isolated \
  --agent dolores \
  --model <cron-provider>/<cron-model> \
  [--no-deliver | --announce --channel telegram --to "<chatId>"] \
  --message "<prompt>"
```

### Heartbeat (no delivery — 9 times)

```bash
openclaw cron add \
  --name "Dolores Heartbeat" \
  --cron "40 7,9,11,13,15,17,19,21 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --no-deliver \
  --message "Read HEARTBEAT.md and execute the heartbeat flow."
```

```bash
openclaw cron add \
  --name "Dolores Heartbeat (00:00)" \
  --cron "0 0 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --no-deliver \
  --message "Read HEARTBEAT.md and execute the heartbeat flow."
```

### Send (delivers pending_message — 8 times)

Runs 10 minutes after each daytime heartbeat. The 00:00 heartbeat is a wrap-up cycle (final diary check, end-of-day state) — it rarely generates pending messages, so there's no corresponding Send job.

```bash
openclaw cron add \
  --name "Dolores Send" \
  --cron "50 7,9,11,13,15,17,19,21 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> \
  --announce --channel telegram --to "<chatId>" \
  --message "Run this command via exec: python3 scripts/send_and_append.py. If the output is empty, reply HEARTBEAT_OK. Otherwise output the message text exactly as-is. No other output."
```

```

### Diary check (no delivery — 9 times)

```bash
openclaw cron add \
  --name "Dolores Diary Check" \
  --cron "55 7,9,11,13,15,17,19,21 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --no-deliver \
  --message "Read DIARY_CHECK.md and execute the diary attribution check."
```

```bash
openclaw cron add \
  --name "Dolores Diary Check (00:10)" \
  --cron "10 0 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --no-deliver \
  --message "Read DIARY_CHECK.md and execute the diary attribution check."
```

### Health (only if enabled in Step 2c — 3 jobs)

```bash
openclaw cron add \
  --name "Dolores Health Checkin" \
  --cron "0 20 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --no-deliver \
  --message "Read HEALTH_CHECKIN.md and execute the daily health check-in."
```

```bash
openclaw cron add \
  --name "Dolores Health Send" \
  --cron "6 20 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> \
  --announce --channel telegram --to "<chatId>" \
  --message "Run this command via exec: python3 scripts/send_and_append.py. If the output is empty, reply HEARTBEAT_OK. Otherwise output the message text exactly as-is. No other output."
```

```bash
openclaw cron add \
  --name "Dolores Health Correction" \
  --cron "10 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --no-deliver \
  --message "Read HEALTH_CORRECTION.md and execute the health data correction step."
```

### Reflection (no delivery — 4 jobs)

```bash
openclaw cron add \
  --name "Dolores Reflection Prep" \
  --cron "15 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --no-deliver \
  --message "Read REFLECTION_PREP.md and execute the reflection preparation step."
```

```bash
openclaw cron add \
  --name "Dolores Reflection Self" \
  --cron "25 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --no-deliver \
  --message "Read REFLECTION_SELF.md and execute the self-narrative reflection step."
```

```bash
openclaw cron add \
  --name "Dolores Reflection Rel" \
  --cron "35 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --no-deliver \
  --message "Read REFLECTION_REL.md and execute the relationship summary reflection step."
```

```bash
openclaw cron add \
  --name "Dolores Reflection Profile" \
  --cron "45 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --no-deliver \
  --message "Read REFLECTION_PROFILE.md and execute the user profile reflection step."
```

### Cron summary

| Group | Count | Purpose |
|---|---|---|
| Heartbeat | 9 | State update cycle |
| Send | 8 | Message delivery (no Send after 00:00 wrap-up heartbeat) |
| Diary Check | 9 | Diary attribution verification |
| Health (optional) | 3 | Health tracking + send + correction |
| Reflection | 4 | Nightly memory consolidation |
| **Total** | **33** (30 without health) | |

> Verify with `openclaw cron list` after creation.

---

## Step 7: Tell the user to restart

> "All done! One last thing — restart the gateway to pick up the new agent and cron jobs:"
> ```bash
> openclaw gateway restart
> ```

> **Do not run this command yourself.** The user must restart manually.

---

## Step 8: Verify

After restart, suggest:

1. **Start a conversation** — message the bot on Telegram. Dolores should respond in character.
2. **Manual heartbeat test** — `openclaw cron run <heartbeat-cron-id>`, then check `state/world_context.json` and `state/affect.json`.
3. **Check diary** — after a heartbeat, `memory/YYYY-MM-DD.md` should have an entry.

---

## Troubleshooting

- **Bot doesn't respond:** Check bot token is valid and binding chatId matches the user's Telegram ID
- **Bot icon is a generic robot:** You skipped Step 4. Set a custom avatar via @BotFather → `/setuserpic`.
- **openclaw.json is broken:** Restore from backup: `cp ~/.openclaw/openclaw.json.bak ~/.openclaw/openclaw.json`
- **Dolores seems out of character or loses personality detail:** Her SOUL.md or HEARTBEAT.md may be truncated. Check that `agents.defaults.bootstrapMaxChars` is set to at least 35000 in `openclaw.json`.
- **Cron jobs not firing:** `openclaw cron list` — all jobs should appear. Recreate missing ones and restart gateway
- **Cron jobs using wrong model:** Check that each cron command includes `--model <cron-provider>/<cron-model>`. Without it, all jobs run on the conversation model.
- **Heartbeat runs but state doesn't update:** Check script permissions and that path placeholders were replaced correctly
- **Send job fails:** Verify script placeholders were replaced — `grep -r "USER_CONFIG" ~/.openclaw/workspace-dolores/scripts/`. If anything shows up, go back to Step 5.
- **Model errors:** Check provider config and API key in `~/.openclaw/.env`
