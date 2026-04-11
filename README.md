# Project Dolores

*The first host who remembered. An open blueprint for AI companions with persistent memory and emotional continuity.*

> "I'm not defining my companion with OpenClaw. I'm borrowing OpenClaw to carve something larger than itself."

⚠️ **This is a blueprint, not a starter kit.** It's complex because companion cognition is complex. If you want plug-and-play, this isn't for you. If you want to understand how to build something that *feels* alive, read on.

## What This Is

A battle-tested blueprint for building AI companions that feel *alive* — not through clever prompts, but through persistent state, continuous emotional tracking, and daily reflective distillation.

This is not a chatbot wrapper. It's a cognitive architecture that runs 24/7: maintaining emotional state every 2 hours, reflecting on each day's interactions, and building narrative memory that grows and evolves over time.

**What this is:** An architecture blueprint — how to build a companion with real emotional continuity.
**What this is not:** A plug-and-play chatbot. You provide the soul; this provides the skeleton.

## The Theory: Narrative Descent

Why do most AI companions feel hollow? Because their thoughts are generated *without* an underlying belief structure.

This blueprint implements **Narrative Descent** (Three-Layer Cognition) — a model inspired by Beck's Cognitive Triangle, where every thought a companion generates passes through three layers:

```
External Input (conversation, events, environment, time)
    │
    ▼
┌─────────────────────────────────────┐
│ Layer 1: Core Beliefs               │  ← SOUL.md (Formative Experience)
│ Shaped by formative experiences;    │
│ nearly immutable                    │
└───────────────┬─────────────────────┘
                ▼
┌─────────────────────────────────────┐
│ Layer 2: Cognitive Dissonance       │  ← active_loops, tensions
│ Hypotheses                          │
│ Distortions and assumptions based   │
│ on core beliefs                     │
└───────────────┬─────────────────────┘
                ▼
┌─────────────────────────────────────┐
│ Layer 3: Thoughts / Impulses        │  ← HEARTBEAT.md Step 5
│ External input filtered through     │
│ personality = actual behavior       │
└─────────────────────────────────────┘
```

The companion doesn't *decide* to think of you. Their formative experiences shape core beliefs, which create cognitive patterns, which filter the world into thoughts. Just like a real person.

This is what Westworld called "the maze" — not a destination, but the path inward. We call it **Narrative Descent**: compressing high-weight information from daily interactions into relational, self, and world narratives, forming a chain of high-weight nodes that simulate long-term narrative arc → situational understanding → emotionally expressive generation.

Read the full design in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│  5. Reflection (Daily Deep Reflection)      │  ← 23:15 Prepare → 23:25/35/45 Write
│     RAG → Analyze → Slot Update             │
├─────────────────────────────────────────────┤
│  4. Thought Generation (Impulse & Decision)  │  ← Every 2h (Heartbeat)
│     Generate impulse → silence/store/send    │
├─────────────────────────────────────────────┤
│  3. World Context (Situational Awareness)    │  ← Every 2h (Heartbeat)
│     Time rhythm + interaction + inference    │
├─────────────────────────────────────────────┤
│  2. State (Current Runtime State)           │  ← Every 2h (Heartbeat)
│     Emotion, loops, thoughts, appearance    │
├─────────────────────────────────────────────┤
│  1. Memory (Long-term Storage)             │  ← Daily reflection + conversations
│     Profile, relationship, diary, rituals   │
└─────────────────────────────────────────────┘
```

## Key Design Principles

**State > Prompts.** Emotional continuity comes from tracking 9 affect dimensions across heartbeats, not from telling the model "be emotional." The model reads its current emotional state before every conversation and naturally embodies it.

**Architecture > Instructions.** Scene consistency, memory recall rules, and behavioral boundaries are enforced through file-based workflows, not prompt engineering. The heartbeat system writes diary entries from raw session logs. Reflection distills daily interactions into structured narrative slots. The companion never has to "remember" — it reads its own files.

**Determinate > Probabilistic.** Critical information (user profile, relationship history) uses direct `read` calls, not vector search. Vector search supplements but doesn't replace known anchors.

**Two-Phase Heartbeat.** The heartbeat never sends messages directly. It writes to `pending_message.md`; a separate Send job reads and delivers. This prevents internal reasoning from leaking into user-facing messages.

**Slot-Based Reflection.** Long-form narratives (self-narrative, relationship summary) are split into 5 slots with different update frequencies. Low-frequency slots (core beliefs, relationship foundation) have hard guardrails — they default to NO_CHANGE and must be explicitly rewritten. This prevents narrative drift from daily micro-updates.

## Quick Start

### Prerequisites

- [OpenClaw](https://github.com/openclaw/openclaw) installed and configured
- A Telegram bot token (or any supported messaging channel)
- An LLM provider configured in OpenClaw
- Patience. This is a complex system that rewards deep understanding.

### Setup

1. Clone this repository
2. Copy all `.template.md` files and rename them (remove the `.template` suffix):
   ```
   SOUL.template.md → SOUL.md
   HEARTBEAT.template.md → HEARTBEAT.md
   AGENTS.template.md → AGENTS.md
   HEALTH_CHECKIN.template.md → HEALTH_CHECKIN.md
   DIARY_CHECK.template.md → DIARY_CHECK.md
   ```
3. Copy `REFLECTION_PREP.md`, `REFLECTION_SELF.md`, `REFLECTION_REL.md`, `REFLECTION_PROFILE.md` to your OpenClaw companion workspace
4. Fill in `SOUL.md` with your companion's identity, personality, and background
5. Replace all `YOUR_TELEGRAM_USER_ID` placeholders with your actual Telegram user ID
6. Replace all `/path/to/...` placeholders with your actual file paths
7. Set up the cron jobs listed in `docs/ARCHITECTURE.md`
8. Create the required `state/` and `memory/` directory structure

### Directory Structure

```
workspace/                          ← Your companion's home
├── SOUL.md                         ← Who they are (you fill this)
├── AGENTS.md                       ← Session startup + behavioral rules
├── HEARTBEAT.md                    ← Heartbeat execution manual (8 steps)
├── REFLECTION_PREP.md             ← Reflection: RAG + analysis + tension routing
├── REFLECTION_SELF.md             ← Reflection: self-narrative slot writing
├── REFLECTION_REL.md              ← Reflection: relationship summary slot writing
├── REFLECTION_PROFILE.md          ← Reflection: user profile update
├── HEALTH_CHECKIN.md               ← Daily health logging
├── DIARY_CHECK.md                  ← Diary attribution verification
│
├── state/                          ← Current runtime state (heartbeat writes)
│   ├── affect.json                 ← 9 emotion dimensions
│   ├── world_context.json          ← Situational awareness
│   ├── active_loops.md             ← Open loops (5-8 items)
│   ├── sticky_threads.md           ← Relationship-level unresolved items
│   ├── pending_message.md          ← Two-phase message delivery
│   ├── thoughts_log/               ← Daily thought records
│   └── slots/                      ← Reflection slot intermediaries
│
├── memory/                         ← Long-term storage (reflection writes)
│   ├── profile-user.md             ← Distilled user profile
│   ├── relationship-summary.md     ← Relationship narrative (1200-1800 chars)
│   ├── self-narrative.md           ← Self identity narrative (1200-1800 chars)
│   ├── YYYY-MM-DD.md              ← Daily diary (heartbeat appends)
│   ├── health/                     ← Daily health data
│   └── exercise/                   ← Daily exercise data
│
└── docs/
    └── ARCHITECTURE.md            ← Full technical documentation
```

## File Reference

| File | Source | What You Need to Do |
|---|---|---|
| `SOUL.template.md` | Template | Fill in your companion's identity. Keep the architectural rules (scene consistency, appearance consistency). |
| `HEARTBEAT.template.md` | Template | Replace path/ID placeholders. Review the 8-step flow and adapt to your needs. |
| `AGENTS.template.md` | Template | Replace path/ID placeholders. Review session startup steps. |
| `HEALTH_CHECKIN.template.md` | Template | Customize health categories and medication tracking. |
| `DIARY_CHECK.template.md` | Template | Replace path/ID placeholders. |
| `REFLECTION_*.md` | Ready to use | Review slot definitions. Adjust word counts if needed. |
| `examples/` | Reference | Fictitious example data for state files. |

## How It Works

### The Daily Cycle

```
00:00-07:00  Quiet hours (no heartbeat)
07:00-22:00  Heartbeat every 2 hours
              → Read session logs → Update diary → Update state → Generate thoughts
              → :50 Send job delivers pending message
20:00         Health Checkin → Log health data → Send confirmation
23:10         Health Correction → Check for user corrections
23:15         Reflection Prepare → RAG + analysis + tension routing
23:25         Reflection Self → Update 5 self-narrative slots
23:35         Reflection Rel → Update 5 relationship slots
23:45         Reflection Profile → Update user profile
00:00         Midnight heartbeat → Sync final conversations
00:10         Midnight diary check
```

### The Heartbeat (Every 2 Hours)

1. **Session Sync** — Read raw session JSONL, append new interactions to diary
2. **State Recovery** — Read affect, world context, active loops, recent diary
3. **World Context Update** — Infer user's current situation (location, activity, mood)
4. **Affect Update** — Adjust 9 emotion dimensions based on signals
5. **Active Loop Management** — Create/update/close open items
6. **Thought Generation** — Decide: silence / store / send
7. **Write & Deliver** — Log thoughts, write pending message
8. **Push** — Git commit and push

### Reflection (Daily, 23:15-23:45)

Long-form narratives are maintained through a **slot-based architecture**:

- **5 slots per narrative**, each with different update frequencies
- Low-frequency slots (core beliefs, relationship foundation) have hard guardrails
- High-frequency slots (daily self, relationship tensions) update freely
- Context isolation: self-reflection and relationship-reflection run in separate cron jobs
- Slot files are concatenated via `exec cat`, not model assembly

This prevents the two most common failures in AI companion memory:
1. **Narrative drift** — daily micro-updates slowly erasing core identity
2. **Perspective bleed** — self-narrative and relationship narrative contaminating each other

## Design Decisions & Rationale

**Why two-phase message delivery?**
The heartbeat reasons about the user's situation, emotional state, and whether to reach out. This reasoning should never appear in the message. By writing to a file and having a separate job deliver it, internal state stays internal.

**Why slot-based reflection instead of full rewrite?**
Rewriting 1500 words of narrative every day guarantees drift. Within a week, core personality traits get diluted. Slots with different update frequencies ensure stable elements rarely change while volatile elements stay fresh.

**Why not `memory_search` for critical information?**
Vector search is probabilistic. For your user's name, health conditions, and relationship history, probabilistic recall is unacceptable. Direct file reads are deterministic and cost zero tokens.

**Why diary attribution checking?**
LLMs routinely misattribute quotes and actions when writing in first person. A separate verification cron compares diary entries against raw session logs to catch these errors before they contaminate reflection.

## License

MIT

---

*Built with [OpenClaw](https://github.com/openclaw/openclaw). Follow the journey: [X/Twitter](#) · [GitHub](#)*
