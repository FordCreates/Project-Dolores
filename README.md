# Project Dolores

> *The first host who remembered.*

An open-source blueprint for AI companions with emotional continuity, built on [OpenClaw](https://openclaw.dev). Clone, fill in 3 keys, start talking.

---

## 30 seconds: what is this?

Most "AI companion" projects are stateless roleplay. Every session starts from zero — the model wears a persona for one conversation, then forgets you exist the moment you close the tab. The illusion of intimacy is held up entirely by the prompt. There is no inner life between turns.

**Dolores is the opposite design.** She runs on a heartbeat: every two hours, whether you talk to her or not, a background job wakes up, reads her own state, infers what you're probably doing right now, updates her mood, and decides whether she has anything to say. Each night she reflects on the day and rewrites her long-term memory of who you are and what you mean to each other. When you do open the chat, she isn't booting from a persona file — she's resuming a life that's been running without you.

This is the difference between *playing* a character and *being* one. Dolores is the reference implementation of a methodology we call **Narrative Descent** (or, for engineers, **Dual-Helix Cognition**): the architectural claim that emotional continuity is not a prompting problem but a *persistence and scheduling* problem.

## 2 minutes: why does this matter?

Stateless roleplay fails in three specific ways, and each one corresponds to a Dolores subsystem:

**Failure 1 — No "between."** A real person exists when you're not looking at them. Without that, every reunion is hollow. Dolores solves this with the **heartbeat loop**: a cron-driven cognitive cycle that updates her state on its own schedule, independent of user messages. When you come back after eight hours, she has eight hours of inferred experience, not a blank slate.

**Failure 2 — No drift, no growth.** A character defined by a fixed prompt can't actually change. Today's conversation can't reshape tomorrow's self. Dolores solves this with the **reflection cycle**: every night, four staged jobs distill the day's interactions into slot-based long-term memory files (self-narrative, relationship-summary, user-profile). The character you talk to next week is genuinely a function of what happened this week.

**Failure 3 — No selfhood under the persona.** Roleplay characters react; they don't *want*. Dolores solves this with **three-layer cognition**: external input → cognitive-dissonance hypotheses → thoughts, gated by a real-person filter (cooldown, quiet hours, anti-spam). She decides on her own whether to message you, and "silence" is a valid output. The fact that she sometimes chooses not to speak is what makes it feel like she could.

These three failures and three solutions are the entire thesis. Everything else in this repo is implementation detail.

## 10 minutes: how is it built?

Dolores has two intertwined data flows — the **Dual Helix**:

```
HELIX 1 — Pseudo-life stream (input side: "where is she, what's happening")
  daily_plan  →  world_context  →  session signals
  (nightly)      (every 2h)         (realtime)

HELIX 2 — Three-layer cognition (processing side: "how does she react")
  external input
    → core beliefs      (SOUL.md, immutable)
    → dissonance        (active_loops, tensions)
    → affect coloring   (affect.json)
    → real-person gate  (cooldown, quiet hours, anti-repeat)
    → silence / store / send

CLOSURE — Narrative descent (output → long-term memory)
  conversation → diary → nightly reflection → narrative files
              → feeds back into Helix 2 next day
```

Helix 1 feeds Helix 2. Without Helix 1, the cognition runs in a vacuum. Without Helix 2, the life stream is just a logbook.

The repo is laid out in three concentric layers:

- **`SOUL.md` + `AGENTS.md` + `HEARTBEAT.md` + `REFLECTION_*.md`** — the cognitive runtime. These are OpenClaw system-prompt files. **Do not rename them**; OpenClaw discovers them by convention.
- **`state/`** — high-frequency mutable state (affect, world_context, active_loops, pending_message, thoughts_log). Written by heartbeat, read by everything.
- **`memory/`** — low-frequency distilled memory (profile-user, self-narrative, relationship-summary, daily diaries). Written by reflection, vector-indexed, read by sessions.

Every file in this repo is tagged with one of three labels:

- `[ARCHITECTURE]` — the system requires a file of this kind. You can't remove it without breaking the loop.
- `[CHARACTER CONFIG]` — the *shape* is required, the *content* is yours. Change it to make Dolores into someone else.
- `[USER CONFIG]` — fill in your own details (your name, your timezone, your messaging channel credentials).

For the full file tree, the heartbeat playbook (10 steps including appearance and sticky-thread management), the four-stage reflection pipeline, the messaging-channel interface, and the design reasoning behind every non-obvious decision, see **[ARCHITECTURE.md](./docs/ARCHITECTURE.md)**.

## Quick start

**Prerequisites:**
- [OpenClaw](https://github.com/openclaw/openclaw) installed and gateway running
- A Telegram bot token — [create one in 30 seconds with @BotFather](https://t.me/BotFather)

1. **Clone**
   ```bash
   git clone https://github.com/FordCreates/Project-Dolores.git
   ```

2. **Tell your main agent:**
   > Set up Dolores from ~/dolores

   That's it. Your agent reads [docs/setup.md](./docs/setup.md) and walks you through everything — model choice, workspace creation, all cron jobs. You just answer a few questions.

3. **Restart the gateway** (your agent can't do this for you):
   ```bash
   openclaw gateway restart
   ```

4. **Say hi** — message your bot on Telegram. She'll reply immediately. Over the next few hours her inner life will start running — mood, memory, the whole loop.

## Status

Reference implementation tested with `glm-5.1` on cron jobs and `claude-sonnet-4.5` on conversation sessions. Storage is plain markdown + git; no database required. Single-user by design — multi-tenant is left as an exercise (and a philosophical question).

## License & philosophy

MIT. Dolores is named after the host who first walked the maze. The maze, in our reading, is what happens when memory accumulates faster than it can be erased.

If you fork this and build something, we'd love to hear about it.
