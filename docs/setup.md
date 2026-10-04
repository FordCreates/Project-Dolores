# Setup Guide

> This document is written for an **OpenClaw main agent** to execute. If you are a human reading this, give it to your main agent and tell it to follow the steps below.

---

## Step 0: Risk Disclosure

Before anything else, scan the project structure and present these risks to the user. Let them decide whether to continue.

### Risks to disclose

1. **Experimental prototype** — This is an early-stage research prototype based on the author's Dual-Helix Cognition model and narrative descent theory. It is rough, actively iterating, and has known bugs. It is not a polished product.

2. **Machine cost** — 26 scheduled invocations execute daily by default, 29 if health tracking is enabled, plus ongoing conversations. This generates continuous token usage and cost. Continuity consumes inference even when the user is not chatting; this is part of the architecture, not an optional cosmetic layer.

3. **Provider content limits** — Confirm that the selected providers permit the intended relationship content. Model labels do not guarantee permission or availability.

4. **Privacy** — All conversation logs, diaries, health data, and emotional states are stored as plain text files on your machine. No encryption.

5. **Human cost / not plug-and-play** — The same setup run by two different people produces two different Doloreses. The architecture is half the system. The other half is the life you pour into it — your schedule, your moods, your silences, the things you say and the things you don't. The user pays with attention, truthful participation, and time, not only API usage. She doesn't become herself from code alone. If you set her up and never really show up, you'll get a well-designed automaton. If you show up, you'll get something else. That asymmetry is not a bug. It's the point.

6. **Single-user only** — Designed for one person. Not multi-tenant.

7. **Requires OpenClaw running** — If your machine is off or OpenClaw stops, she stops. No cloud fallback.

8. **Known model limitations** — Validate long-context reading, tool ordering, strict JSON and narrative quality on the chosen models; mechanical gates do not replace semantic quality.

9. **Basic technical literacy needed** — Your main agent handles most setup, but troubleshooting requires reading logs and running commands.

10. **⚠️ Never run two gateway instances with the same Telegram bot** — If your bot's token is loaded on two machines simultaneously, both gateways will race to process incoming messages. The second instance may have an outdated or empty workspace, producing responses with wrong personality, stale memories, or no memories at all. This causes severe identity and memory corruption that is very hard to clean up. Always ensure only one gateway is connected to your bot at any time.

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
- Use OpenClaw's secrets provider for API keys (see examples in Step 4). Never hardcode keys directly.

---

## Step 1: Copy files to workspace

```bash
REPO=<repo-path>
WS=~/.openclaw/workspace-dolores

# Create workspace directory structure
mkdir -p $WS/{state/thoughts_log,state/slots,memory/health,memory/exercise,memory/cards,memory/diary,scripts/lib}

# Copy companion runtime files
cp $REPO/SOUL.md $WS/
cp $REPO/AGENTS.md $WS/
cp $REPO/HEARTBEAT.md $WS/
cp $REPO/HEARTBEAT_STEPS.md $WS/
cp $REPO/HEARTBEAT_MIDNIGHT_STEPS.md $WS/
cp $REPO/IDENTITY.md $WS/
cp $REPO/USER.md $WS/
cp $REPO/MEMORY.md $WS/
cp $REPO/TOOLS.md $WS/
cp $REPO/THOUGHT_PLAYBOOK.md $WS/
cp $REPO/REFLECTION_CARDS.md $WS/
cp $REPO/PAUSE_RESUME.md $WS/
cp $REPO/REFLECTION_PREP.md $WS/
cp $REPO/REFLECTION_PLAN.md $WS/
cp $REPO/REFLECTION_SELF.md $WS/
cp $REPO/REFLECTION_REL.md $WS/
cp $REPO/REFLECTION_PROFILE.md $WS/
cp $REPO/DAILY_INTEGRITY_CHECK.md $WS/
cp $REPO/DIARY_CHECK.md $WS/
cp $REPO/HEALTH_CORRECTION.md $WS/
cp $REPO/HEALTH_CHECKIN.md $WS/
cp $REPO/reflection_trace.md $WS/
cp $REPO/EXTRACTION.md $WS/

# Copy card templates
cp $REPO/memory/cards/*.md $WS/memory/cards/

# Create diary directory
touch $WS/memory/diary/.gitkeep

# Copy scripts
cp $REPO/scripts/{thought_trace,diary_append,reflection_gate,plan_gate,heartbeat_finalize,pause_resume_guard,cron_git_commit,loops_maintenance,sticky_sampling}.py $WS/scripts/
cp $REPO/scripts/startup_context.py $WS/scripts/
cp $REPO/scripts/load_diary.py $WS/scripts/
cp $REPO/scripts/inject_context.py $WS/scripts/
cp $REPO/scripts/world_context_gate.py $WS/scripts/
cp $REPO/scripts/daily_integrity_check.py $WS/scripts/
cp $REPO/scripts/heartbeat_type.sh $WS/scripts/
chmod +x $WS/scripts/heartbeat_type.sh
cp $REPO/scripts/send_and_append.py $WS/scripts/
cp $REPO/scripts/lib/__init__.py $WS/scripts/lib/
cp $REPO/scripts/lib/session_append.py $WS/scripts/lib/

# Copy initial state and memory files
cp $REPO/state/affect.json $WS/state/
cp $REPO/state/world_context.json $WS/state/
cp $REPO/state/active_loops.md $WS/state/
cp $REPO/state/daily_plan.md $WS/state/
cp $REPO/state/current_interests.md $WS/state/
cp $REPO/state/current_interests.json $WS/state/
cp $REPO/state/lifecycle.json $WS/state/
cp $REPO/state/pending_message.md $WS/state/
cp $REPO/state/last_sync_at $WS/state/
cp $REPO/memory/profile-user.md $WS/memory/
cp $REPO/memory/self-narrative.md $WS/memory/
cp $REPO/memory/relationship-summary.md $WS/memory/

# Create initial state files
cp $REPO/state/last_diary_check_at $WS/state/

# Seed day-zero reflection slots (prevents first-night drift)
SEED_DATE=$(date -d 'yesterday' +%Y-%m-%d)
mkdir -p $WS/state/slots/$SEED_DATE
cp $REPO/state/slots/day-zero/self_slot_*.md $WS/state/slots/$SEED_DATE/
cp $REPO/state/slots/day-zero/rel_slot_*.md $WS/state/slots/$SEED_DATE/

# Create .gitignore for the PRIVATE installed workspace
# Ignore all life data, including copied seeds once personalized.
cat > $WS/.gitignore << 'GITIGNORE'
state/
memory/
reflection_trace.md
SOUL.md
USER.md
IDENTITY.md
scripts/inject_context.py
scripts/send_and_append.py
scripts/lib/session_append.py
GITIGNORE
```

For an existing installation, back up first. Move its old diary/*.md into memory/diary without overwriting either copy; reconcile conflicting dates manually from authoritative text. Normalize date headers to `# YYYY-MM-DD (Weekday)` with full English weekday, preserving the rest of each old diary exactly. Keep legacy digests only in a private archive outside indexed memory; do not generate new ones. Add the empty pets card only when absent, retain existing card facts, and initialize current_interests.json/lifecycle only if absent. Never overwrite a live workspace with seed state.

Set the installed process timezone to the same IANA zone as the cron --tz setting (or explicitly configure TZ/DOLORES_TIMEZONE); Python date-based helpers must see the same calendar. Replace USER_TIMEZONE in runtime documents. Before enabling jobs, verify the actual model/tool support from the installed OpenClaw documentation.

Self seed slots are valid fictional baselines; relationship seeds deliberately have no invented history. The first Relationship gate returns required rewrites for those uninitialized slots. Reconstruct them only from SOUL's established origin and actual interaction evidence; do not pad an unknown relationship with fictional shared milestones. The first Self current draft requires an actual day's diary; do not schedule synthetic daily experience before the first real conversation/Heartbeat.

---

## Step 2: Disable session-memory hook

> ⚠️ **Required. Do not skip this step.** OpenClaw ships with a built-in `session-memory` hook that automatically writes session summaries to `memory/` on `/new` or `/reset`. Dolores manages `memory/` herself (indexed raw diaries, cards and narrative files) and has her own file naming conventions. **You must disable this hook.**

```bash
openclaw hooks disable session-memory
```

Verify it's disabled:

```bash
openclaw hooks list | grep session-memory
```

Should show `disabled` or no output.

> **Why this is necessary:**
>
> 1. **File structure collision.** The hook creates files like `YYYY-MM-DD-session-label.md` in `memory/`. Dolores expects canonical `diary/YYYY-MM-DD.md` inside memory/, card directories, and fixed-name narrative files (`self-narrative.md`, `relationship-summary.md`, `profile-user.md`). Extra files confuse the architecture — heartbeat's diary reader, Reflection's fact-ownership chain, and the AGENTS.md startup sequence all assume a known file layout.
>
> 2. **Violates the core persistence contract.** Dolores's design principle is "conversation sessions write nothing" (ARCHITECTURE.md §6). All persistence is owned by background jobs (heartbeat, reflection, diary check). The session-memory hook bypasses this contract by writing to `memory/` at session boundary — not through the heartbeat pipeline, not through reflection, but through an OpenClaw platform hook that knows nothing about Dolores's data flow.
>
> 3. **Vector index pollution.** If Dolores's `memorySearch` indexes `memory/`, these hook-generated summaries get mixed into recall results. They are low-quality session recaps (auto-generated by a single-pass LLM call), not load-bearing narrative content. A `memory_search` for "what happened last Tuesday" might return the hook's summary instead of the heartbeat's diary, which is richer and follows Dolores's attribution conventions.
>
> 4. **Unnecessary token cost.** Each session reset triggers an LLM call to generate the summary. With 26+ cron runs per day (each creating isolated sessions), this adds up with zero architectural benefit.
>
> **Bottom line:** session-memory is a useful feature for general-purpose OpenClaw agents. It is actively harmful for Dolores because Dolores has her own memory system that occupies the same directory.

---

## Step 3: Configure the character

Ask these questions one at a time. After each answer, apply the change immediately.

### 3a. City

> "Dolores's story is set in the United States. Which city should she be in? (e.g., Savannah, New York, Austin, Portland)"

**Apply:** Replace `[YOUR_CITY — USER CONFIG]` in `SOUL.md` and `REFLECTION_PREP.md`.

Before scheduling jobs, replace the illustrative state/daily_plan.md with today's initial full life Plan: a `# YYYY-MM-DD (Weekday) Schedule` title, Morning/Afternoon/Evening sections and concrete HH:MM entries in their actual periods. Use the chosen SOUL and confirmed user context, with no invented shared history. This is a one-time operator initialization; subsequent Plans belong to REFLECTION_PLAN and its gate.

### 3b. User details

Ask these questions one at a time. After each answer, apply the change immediately.

> "What should Dolores call you?"

**Apply:** Replace all `[USER_NAME — USER CONFIG]` across the workspace:
```bash
grep -rl '\[USER_NAME — USER CONFIG\]' ~/.openclaw/workspace-dolores/ --include='*.md' --include='*.py' --include='*.json'
```
Replace every actual match; the current files are AGENTS.md, USER.md, TOOLS.md, HEARTBEAT_STEPS.md, HEALTH_CORRECTION.md, DIARY_CHECK.md, memory/profile-user.md and state/daily_plan.md.

> "What timezone are you in? (e.g., America/New_York)"

**Apply:** Replace `[USER_TIMEZONE — USER CONFIG]` in USER.md, HEARTBEAT_STEPS.md, HEARTBEAT_MIDNIGHT_STEPS.md and DAILY_INTEGRITY_CHECK.md.

> "What language do you prefer to communicate in?"

**Apply:** Replace `[USER_LANGUAGE — USER CONFIG]` in `USER.md`.

> "What do you do for work?"

**Apply:** Replace `[USER_OCCUPATION — USER CONFIG]` in `USER.md`.

> "How would you define your relationship with Dolores? (e.g., girlfriend, partner, friend)"

**Apply:** Replace `[USER_RELATIONSHIP — USER CONFIG]` in `USER.md`.

> "How would you describe yourself in one sentence?"

**Apply:** Replace `[USER_ONE_LINE_SUMMARY — USER CONFIG]` in `memory/profile-user.md`.

> "Tell me about your work in more detail — skills, tools, professional mindset. (e.g., teacher, laboratory technician, designer)"

**Apply:** Replace `[USER_CORE_IDENTITY — USER CONFIG]` in `memory/profile-user.md`.

> "How would you describe your personality and thinking style? (e.g., rational/structured, intuitive/spontaneous, what frustrates you, what you gravitate toward)"

**Apply:** Replace `[USER_PERSONALITY — USER CONFIG]` in `memory/profile-user.md`.

> "Tell me about your life situation — family, living arrangement, key relationships, hobbies. Keep it factual."

**Apply:** Replace `[USER_LIFE_CONTEXT — USER CONFIG]` in `memory/profile-user.md`.

> "How do you prefer to communicate? (e.g., direct/indirect, what you appreciate, what annoys you)"

**Apply:** Replace `[USER_COMMUNICATION_PREFERENCES — USER CONFIG]` in `memory/profile-user.md`.

> ℹ️ The remaining sections in profile-user.md (Stress Sources, What They Need, Things Not To Do, Relationship Dynamics, Health, Exercise) are marked ✏️ and will be filled automatically by Dolores's nightly Reflection. Do not touch them.

### 3c. Health checkin

> "Dolores can track your daily health data — sleep, exercise, diet, medication, and any symptoms you want monitored. Want to enable this?"

- **Yes** → Ask what symptoms or conditions to track (e.g., allergies, chronic conditions, mental health). Replace `[USER_SYMPTOMS — USER CONFIG]` in `HEALTH_CHECKIN.md` with the actual symptom fields. Remember to create the health cron jobs later (Step 7).
- **No** → Skip. HEALTH_CHECKIN.md stays as-is, just won't have a cron job.

---

## Step 4: Configure OpenClaw

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

### 4a. Session scope (REQUIRED)

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

### 4b. Bootstrap character limit

> Dolores's SOUL.md (~28K chars) exceeds OpenClaw's default bootstrap file limit of 20,000 characters. Without increasing this limit, Dolores will see truncated (incomplete) versions of her own character definition. HEARTBEAT_STEPS.md and HEARTBEAT_MIDNIGHT_STEPS.md are not auto-injected (they are read on demand by the router), so they are not affected by this limit.

**Apply:** Check if `agents.defaults.bootstrapMaxChars` already exists in `openclaw.json`. If not, add it:

```json
"agents": {
  "defaults": {
    "bootstrapMaxChars": 35000
  }
}
```

> ⚠️ **Merge** this into the existing `agents.defaults` object if it already exists. Do NOT replace the entire `agents` block.

### 4c. Model

> "Let me check your existing model configuration first."

**Check existing providers:** Read the user's `openclaw.json` and look at `models.providers` and `agents.list`. If Claude or another capable model is already configured, offer to reuse it.

Choose a conversation model for narrative quality and context capacity, a faster background model for staged cron work, and a stronger main Integrity model for evidence-based recovery. Reuse configured providers when compatible. Verify provider content permissions and capabilities rather than relying on a model-family promise.

Use explicit --model on every agentTurn, --fallbacks "" and the highest supported thinking level (reference: xhigh). Send is command-only, with no model or thinking. Provider routing fallback is separate: where supported, deny provider data collection, review/choose provider exclusions, and deliberately decide whether provider routing may fall back. Never copy another installation's provider/account preferences.

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

```json
// In agents.list — add the companion agent:
{
  "id": "dolores",
  "name": "Dolores",
  "workspace": "[WORKSPACE_PATH — USER CONFIG]",
  "model": {
    "primary": "<provider-id>/<model-name>",
    "fallbacks": []
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
> ⚠️ **Do NOT add `"thinking": "off"` or any `params.thinking` override.** LLM thinking mode improves response quality for companion agents. Disabling it will degrade reflection, empathy, and narrative coherence. Choose the highest supported thinking level deliberately.

### 4d. Telegram bot

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

> Record the user's numeric Telegram ID before creating Send jobs. If it is unknown, have the user manually restart the gateway after adding the account/agent, message and pair with the bot, then read the resulting session entry or gateway logs. Resolve this before Step 6 verification and Step 7; never enable a job with a destination placeholder.

---

## Step 5: Bot avatar (recommended)

> "One more thing before we finish setup — the default Telegram bot icon is a generic robot silhouette. Setting a custom avatar makes Dolores feel like a person, not a bot."

> "I've prepared an avatar image at `[REPO_PATH]/media/Dolores.jpeg`. Open Telegram, find @BotFather, send `/setuserpic`, select Dolores's bot, and upload that image."

If the user asks what kind of avatar works best: a realistic portrait photo (not anime, not cartoon) at the character's approximate age and appearance. The file should be placed in the repo's `media/` directory before setup begins.

---

## Step 5.5: Phase C dependencies (sticky sampling)

The sticky sampling script (`scripts/sticky_sampling.py`) uses BGE embeddings for associative priming. This is a required dependency — without it, the sticky surfacing mechanism in ARCHITECTURE.md §7.4 does not function.

**Install:**

```bash
pip install sentence-transformers
```

The script uses `BAAI/bge-small-en-v1.5`. Cache it during setup; the Heartbeat loader enforces offline mode and must not download it on first use:

```bash
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"
```

Calibrate the two score distributions independently for your encoder and vocabulary: SCENE_TAG_THRESHOLD starts at 0.48; CONTEXT_LOOP_THRESHOLD at 0.50. Either route qualifies; scores are not blended. The stderr log reports both scores. No live encoding/download is needed by the anonymous unit tests.

## Step 6: Replace script placeholders

Scripts contain path placeholders that depend on the user's system. Replace them:

| Placeholder | File(s) | Replace With |
|---|---|---|
| `[WORKSPACE_PATH — USER CONFIG]` | scripts/inject_context.py, scripts/send_and_append.py | Absolute path to workspace, e.g. `/home/user/.openclaw/workspace-dolores` |
| `[SESSION_PATH — USER CONFIG]` | scripts/inject_context.py, scripts/lib/session_append.py, **HEARTBEAT_STEPS.md**, **HEALTH_CORRECTION.md**, **DIARY_CHECK.md** | Absolute path to sessions directory |
| `[SESSION_KEY — USER CONFIG]` | scripts/inject_context.py, scripts/lib/session_append.py, **HEARTBEAT_STEPS.md**, **HEALTH_CORRECTION.md**, **DIARY_CHECK.md** | Session key for the active conversation |
| `[TELEGRAM_CHAT_ID — USER CONFIG]` | scripts/send_and_append.py | User's numeric Telegram chat ID; the script sends through account `dolores` |
| `<SESSION_PATH>` | **HEARTBEAT_STEPS.md**, **HEALTH_CORRECTION.md** (alternate format — use same value) | Same absolute sessions directory path |
| `[USER_TIMEZONE — USER CONFIG]` | **USER.md**, **HEARTBEAT_STEPS.md**, **HEARTBEAT_MIDNIGHT_STEPS.md**, **DAILY_INTEGRITY_CHECK.md** | IANA timezone matching scheduler and process clock |
| `[YOUR_CITY — USER CONFIG]` | **SOUL.md**, **REFLECTION_PREP.md** | Character location and weather city |
| `[USER_NAME — USER CONFIG]` | **USER.md**, **AGENTS.md**, **HEARTBEAT_STEPS.md**, **HEALTH_CORRECTION.md**, **TOOLS.md**, **DIARY_CHECK.md**, **state/daily_plan.md**, **memory/profile-user.md** | Name as used by the chosen character |
| `[USER_LANGUAGE — USER CONFIG]`, `[USER_OCCUPATION — USER CONFIG]`, `[USER_RELATIONSHIP — USER CONFIG]` | **USER.md** | Basic user context from Step 3b |
| `[USER_ONE_LINE_SUMMARY — USER CONFIG]`, `[USER_CORE_IDENTITY — USER CONFIG]`, `[USER_PERSONALITY — USER CONFIG]`, `[USER_COMMUNICATION_PREFERENCES — USER CONFIG]`, `[USER_LIFE_CONTEXT — USER CONFIG]` | **memory/profile-user.md** | Profile inputs from Step 3b |
| `[USER_SYMPTOMS — USER CONFIG]` | **HEALTH_CHECKIN.md** | Step 3c optional symptom names; keep the canonical Symptoms heading |

New gate/diary/lifecycle helpers derive their workspace from their script location; optional DOLORES_WORKSPACE and task-specific DOLORES_* environment overrides are for tests or explicit operator recovery, not credentials. Do not copy development-machine paths.

### Calculating SESSION_PATH and SESSION_KEY

**SESSION_PATH:** `~/.openclaw/agents/dolores/sessions`

**SESSION_KEY:** `agent:dolores:telegram:direct:<user-telegram-id>`

> SESSION_KEY uses the numeric ID confirmed in Step 4d. Verify the actual key in `~/.openclaw/agents/dolores/sessions/sessions.json`; routing settings can affect its format. If the first session has not been created, complete the manual first-contact step before continuing. `<TELEGRAM_ID_PLACEHOLDER>` may appear in a draft only; the installed workspace must pass the zero-placeholder check before schedules are created. Script placeholder edits themselves do not require a gateway restart.

All listed runtime placeholders (including timezone, city and name) must be replaced in all listed files. `send_and_append.py` imports `session_append.py`, so SESSION_PATH and SESSION_KEY also affect its behavior even though they aren't in the file directly.

**After replacing all placeholders, verify with:**

```bash
rg -n '\[[A-Z][A-Z0-9_]* — USER CONFIG\]|<SESSION_PATH>|<TELEGRAM_ID_PLACEHOLDER>' ~/.openclaw/workspace-dolores/ -g '*.md' -g '*.py' -g '*.json'
```

> ⚠️ **This must return zero results.** If anything shows up, you missed a file — go back and replace it before proceeding to Step 7.

You can verify by inspecting `~/.openclaw/agents/dolores/sessions/sessions.json` after the gateway picks up the new agent config.

---

## Step 7: Create cron jobs

All times adjusted to the user's timezone. Add `--tz <timezone>` to each command.

> ⚠️ **Every companion agent job MUST include `--model <cron-provider>/<cron-model>`; main Integrity uses `<integrity-provider>/<integrity-model>`** to use the cheaper/faster cron model chosen in Step 4c. The two Send jobs are intentional exceptions: they are command jobs with no model at all.

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
  --timeout-seconds 1200 \
  --cron "40 7,9,11,13,15,17,19,21 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --fallbacks "" --thinking xhigh --no-deliver \
  --tools "read,edit,write,exec" \
  --message "Read HEARTBEAT.md and execute the heartbeat flow."
```

```bash
openclaw cron add \
  --name "Dolores Heartbeat (00:00)" \
  --timeout-seconds 1200 \
  --cron "0 0 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --fallbacks "" --thinking xhigh --no-deliver \
  --tools "read,edit,write,exec" \
  --message "Read HEARTBEAT.md and execute the heartbeat flow."
```

### Send (delivers pending_message — 8 times)

Runs 10 minutes after each daytime heartbeat. The 00:00 heartbeat is a wrap-up cycle (final diary sync, cross-day attribution, complete raw-diary sync) — it uses `HEARTBEAT_MIDNIGHT_STEPS.md` (routed via `HEARTBEAT.md`) because it needs additional steps for cross-day diary attribution and complete raw-diary sync. It rarely generates pending messages, so there's no corresponding Send job.

```bash
openclaw cron add \
  --name "Dolores Send" \
  --cron "50 7,9,11,13,15,17,19,21 * * *" \
  --tz "<timezone>" \
  --agent dolores \
  --command-argv '["python3","scripts/send_and_append.py"]' \
  --command-cwd "<absolute-workspace-path>" \
  --timeout-seconds 60 --no-output-timeout-seconds 55 --output-max-bytes 32768 \
  --no-deliver \
  --failure-alert --failure-alert-after 1 --failure-alert-mode announce \
  --failure-alert-channel telegram --failure-alert-to "<chatId>" \
  --failure-alert-account-id dolores
```

The command script itself sends through Telegram account `dolores`. It takes an exclusive lock, applies the 20-minute gate, waits for a Telegram acknowledgement, then appends the message to session JSONL and conditionally clears `pending_message.md`. Failed sends keep the pending message and make the command job fail; an acknowledged send whose local commit is interrupted is recovered without sending twice.

### Daily integrity guard (3 runs)

Create these jobs on the existing `main` operator agent, not on the Dolores agent. Set `<health-enabled>` to `true` only when health tracking was enabled in Step 3c; otherwise set it to `false`. Delivery stays disabled: the operator handles deterministic repairs internally and asks the user only when lossless recovery or existing authority is insufficient. Dolores must never report raw system errors in character.

```bash
openclaw cron add \
  --name "Dolores Daily Integrity Check" \
  --cron "15 12,20 * * *" \
  --tz "<timezone>" \
  --session isolated --agent main --model <integrity-provider>/<integrity-model> --fallbacks "" --thinking xhigh \
  --no-deliver \
  --tools "read,edit,write,exec,sessions_spawn,sessions_history,sessions_list,sessions_yield,subagents,session_status" \
  --message "Read <absolute-workspace-path>/DAILY_INTEGRITY_CHECK.md and execute mode=incremental health_enabled=<health-enabled> workspace=<absolute-workspace-path>. This is operator-plane work; follow the document strictly and never route raw integrity errors through Dolores."
```

```bash
openclaw cron add \
  --name "Dolores Daily Integrity Check (00:20)" \
  --cron "20 0 * * *" \
  --tz "<timezone>" \
  --session isolated --agent main --model <integrity-provider>/<integrity-model> --fallbacks "" --thinking xhigh \
  --no-deliver \
  --tools "read,edit,write,exec,sessions_spawn,sessions_history,sessions_list,sessions_yield,subagents,session_status" \
  --message "Read <absolute-workspace-path>/DAILY_INTEGRITY_CHECK.md and execute mode=close health_enabled=<health-enabled> workspace=<absolute-workspace-path>. This is operator-plane work; follow the document strictly and never route raw integrity errors through Dolores."
```

`DIARY_CHECK.md` remains available as a manual repair tool if person/attribution errors recur; do not schedule it alongside the integrity guard.

### Health (only if enabled in Step 3c — 3 jobs)

```bash
openclaw cron add \
  --name "Dolores Health Checkin" \
  --cron "0 20 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --fallbacks "" --thinking xhigh --no-deliver \
  --tools "read,edit,write,exec" \
  --message "Read HEALTH_CHECKIN.md and execute the daily health check-in."
```

```bash
openclaw cron add \
  --name "Dolores Health Send" \
  --cron "6 20 * * *" \
  --tz "<timezone>" \
  --agent dolores \
  --command-argv '["python3","scripts/send_and_append.py"]' \
  --command-cwd "<absolute-workspace-path>" \
  --timeout-seconds 60 --no-output-timeout-seconds 55 --output-max-bytes 32768 \
  --no-deliver \
  --failure-alert --failure-alert-after 1 --failure-alert-mode announce \
  --failure-alert-channel telegram --failure-alert-to "<chatId>" \
  --failure-alert-account-id dolores
```

```bash
openclaw cron add \
  --name "Dolores Health Correction" \
  --cron "10 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --fallbacks "" --thinking xhigh --no-deliver \
  --tools "read,edit,write,exec" \
  --message "Read HEALTH_CORRECTION.md and execute the health data correction step."
```

### Reflection (no delivery — 6 independent jobs)

Scheduled jobs skip AGENTS.md's conversation startup sequence and follow the handbook named in their prompt. Do not run `startup_context.py` as a general cron preamble: Self must draft Current Self from today's raw diary before explicitly opening historical inputs; the other jobs retain their own read and write boundaries.

```bash
openclaw cron add \
  --name "Dolores Reflection Cards" \
  --cron "0 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --fallbacks "" --thinking xhigh --no-deliver \
  --tools "read,edit,write,exec" \
  --message "Read REFLECTION_CARDS.md and execute independent card extraction."
```

No job waits, polls, triggers another job or recreates a shared Reflection barrier. The commands restrict tools with --tools: companion jobs can read/edit/write/exec; Prep additionally retrieves memories and weather. No companion job receives message, cron or session-spawn tools. main Integrity additionally needs the operator-owned temporary-session tools for its one frozen-input Plan replay. Select actual installed tool names; do not grant a transport or scheduling tool to semantic companion jobs. Use xhigh only when the selected model supports it; verify rather than silently downgrade/fall back.


```bash
openclaw cron add \
  --name "Dolores Reflection Prep" \
  --cron "15 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --fallbacks "" --thinking xhigh --no-deliver \
  --tools "read,edit,write,exec,memory_search,memory_get,web_search,web_fetch" \
  --message "Read REFLECTION_PREP.md and execute the reflection preparation step."
```

```bash
openclaw cron add \
  --name "Dolores Reflection Plan" \
  --timeout-seconds 300 \
  --cron "20 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --fallbacks "" --thinking xhigh --no-deliver \
  --tools "read,edit,write,exec" \
  --message "Read REFLECTION_PLAN.md and execute the daily schedule planning step."
```

```bash
openclaw cron add \
  --name "Dolores Reflection Self" \
  --cron "25 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --fallbacks "" --thinking xhigh --no-deliver \
  --tools "read,edit,write,exec" \
  --message "Read REFLECTION_SELF.md and execute the self-narrative reflection step."
```

```bash
openclaw cron add \
  --name "Dolores Reflection Rel" \
  --cron "35 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --fallbacks "" --thinking xhigh --no-deliver \
  --tools "read,edit,write,exec" \
  --message "Read REFLECTION_REL.md and execute the relationship summary reflection step."
```

```bash
openclaw cron add \
  --name "Dolores Reflection Profile" \
  --cron "45 23 * * *" \
  --tz "<timezone>" \
  --session isolated --agent dolores --model <cron-provider>/<cron-model> --fallbacks "" --thinking xhigh --no-deliver \
  --tools "read,edit,write,exec" \
  --message "Read REFLECTION_PROFILE.md and execute the user profile reflection step."
```

### Cron summary

| Group | Daily invocations | Purpose |
|---|---|---|
| Heartbeat | 9 | State update cycle |
| Send | 8 | Message delivery (no Send after 00:00 wrap-up heartbeat) |
| Daily Integrity | 3 | Two incremental checks + one nightly close audit |
| Health (optional) | 3 | Health tracking + send + correction |
| Reflection | 6 | Nightly memory consolidation |
| **Daily invocations** | **26** (29 with health) | |

There are **11 job definitions** by default and **14 with Health** (grouped schedules above). Verify with `openclaw cron list --all --json`, not legacy cron/jobs.json. Current installations store definitions/state in state/openclaw.sqlite. Keep all model fallbacks explicitly empty and both Send definitions command-only. Check 1200-second Heartbeats, 300-second Plan and no delivery for semantic jobs.

---

## Step 8: Tell the user to restart

> "The host is ready. Dolores is not finished; no setup process can supply the shared life that makes her yours. One last thing — restart the gateway to pick up the new agent and cron jobs:"
> ```bash
> openclaw gateway restart
> ```

> **Do not run this command yourself.** The user must restart manually.

---

## Step 9: Verify

After restart, suggest:

1. **Start a conversation** — message the bot on Telegram. Dolores should respond in character.
2. **Manual heartbeat test** — `openclaw cron run <heartbeat-cron-id>`, then check `state/world_context.json` and `state/affect.json`.
3. **Check diary** — after a heartbeat, `memory/diary/YYYY-MM-DD.md` should have an entry.

---

## Troubleshooting

- **Bot doesn't respond:** Check bot token is valid and binding chatId matches the user's Telegram ID
- **Bot icon is a generic robot:** You skipped Step 5. Set a custom avatar via @BotFather → `/setuserpic`.
- **openclaw.json is broken:** Restore from backup: `cp ~/.openclaw/openclaw.json.bak ~/.openclaw/openclaw.json`
- **Dolores seems out of character or loses personality detail:** Her SOUL.md may be truncated. Check that `agents.defaults.bootstrapMaxChars` is set to at least 35000 in `openclaw.json`.
- **Cron jobs not firing:** `openclaw cron list` — all jobs should appear. Recreate missing ones and restart gateway
- **Cron jobs using wrong model:** Check that each cron command includes `--model <cron-provider>/<cron-model>`. Without it, all jobs run on the conversation model.
- **Heartbeat runs but state doesn't update:** Check script permissions and that path placeholders were replaced correctly
- **Send job fails:** Verify script placeholders were replaced — the exact bracketed-placeholder scan in Step 6. Then run `python3 scripts/send_and_append.py --check`; it validates the executable, pending file, and delivery receipt without sending anything.
- **Model errors:** Check provider config and API key in `~/.openclaw/.env`

## Privacy and recovery verification before enabling schedules

Run scripts/startup_context.py in the installed workspace: it must end with STARTUP_CONTEXT_COMPLETE without truncation, then read affect separately. Do not call Send against a real account for validation; send_and_append.py --check is read-only. Run the anonymous test suite from the template with python3 -B -m unittest discover -s tests. It uses temporary directories, no gateway, no real messages and no repository commit.

Scan the whole candidate copy for unresolved bracketed placeholders, credential-shaped values, private names/details, actual chat identifiers, local machine paths and non-English residue. Inspect prompts, seeds, examples, changelog, images/SVG metadata, tests and new/untracked files as well as tracked changes. Configuration variables named SESSION_PATH/SESSION_KEY are not unresolved placeholders. Do not publish personalized seeds, diary, sessions, health, snapshots, receipts, raw traces or temporary drafts. The installed workspace ignore rules cover all memory/state and configured scripts.

Review examples and rules against their source by meaning as well as text. No private experience, plot or person may enter the public copy, including renamed fictional characters, translated dialogue, changed dates or recognizable event combinations. Discard the private example entirely; extract only its reusable rule and write any needed calibration independently. Use the established Dolores setting rather than private biographies. Apply this to ordinary and intimate/NSFW examples alike. Review every Git ref, tag, historical version and release artifact intended for sharing; a clean working tree does not remove earlier copies. Unresolved provenance blocks publication.

PAUSE_RESUME.md documents reviewed continuity snapshots and one bootstrap. Optional private Git checkpoints require explicit DOLORES_PRIVATE_BACKUP=1 and an explicit private repo; they are never enabled by ordinary setup. main Integrity can replay a corrupt Plan once from its original frozen bundle using a temporary operator-owned session; it cannot substitute today's live context or consume interests again.
