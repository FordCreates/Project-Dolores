# Dolores Architecture

> Deep dive. For the 30-second / 2-minute / 10-minute version, read [README.md](./README.md) first.

---

## 0. How to read this document

Every file, field, and decision in this document is tagged:

- **`[ARCHITECTURE]`** — the system requires this. Removing or restructuring it breaks the loop. These are the parts you cannot change without ceasing to build a Dolores.
- **`[CHARACTER CONFIG]`** — the *shape* is required, the *content* is yours. Defaults are provided; change them to make Dolores into someone else (a different gender, voice, history, set of emotional dimensions, reflection cadence).
- **`[USER CONFIG]`** — your details (name, timezone, channel credentials, the things that make her *yours*). Your agent fills these in during setup.

When a decision is non-obvious, it carries an inline **⚠️ Why it's built this way** block. Read those — they are the parts of this document a future-you will care about most when something breaks at 2am.

OpenClaw conventions are noted as **`[OPENCLAW CONVENTION]`** — these are filenames and behaviors inherited from the framework, not Dolores choices. Do not rename them.

---

## 1. The Dual Helix in depth

Dolores has two intertwined data flows. They are independent in implementation but useless apart.

### Helix 1 — Pseudo-life stream (input side)

> Answers: *where is she, what is she doing, where am I, what's the weather, what time of day is it for both of us*.

```
daily_plan         →  world_context     →  user messages (session)
(nightly, planned)    (every 2h, inferred)  (realtime, observed)
```

- `daily_plan` is written each night by reflection. It sketches tomorrow as a loose schedule — not a script, a *prior*.
- `world_context` is rebuilt every heartbeat. It takes the prior, the current time, the user's profile, and the **user's messages** from the session, and infers "what's true right now for both of us." Dolores's own statements are inference outputs from last time, not inputs — this prevents recursive locking.
- Session signals are the realtime ground truth: what you actually said in the last conversation, where you said you were, what you said you were doing.

**Helix 1 injection into the conversation session** (bridging to Helix 2):

There are two paths for world_context to reach the model's context:

```
Path A: Session startup (/new or new session)
  AGENTS.md startup sequence → read state/world_context.json
  → model gets current snapshot
  → only runs on /new, not refreshed afterward

Path B: Heartbeat context-sync (every 2h, Step 6)
  Heartbeat writes world_context.json
  → exec inject_context.py
  → script reads world_context.json → template narrative → append to session jsonl (role: assistant)
  → model sees latest state in history on next message
  → no /new needed to refresh
```

Path A is initialization; Path B is incremental update. Together they ensure the model always has current context, whether the session just started or has been running for hours. Injected content is tagged `[context-sync]` and filtered out during diary sync to prevent duplication.

For activity inference specifically, the engine follows a **deterministic-preprocess + single-step intuition** pattern: a script parses `daily_plan` into the current time slot (1 line), combined with raw user messages from the last 2 hours — the model answers "what is she doing right now?" in one intuitive step. No multi-level priority chains, no diary-based inference (no timestamps), and no previous activity as input (acyclic topology prevents recursive locking).

> ⚠️ **Why it's built this way.** The naive approach is to let `world_context` persist and only update fields when something changes. This rots fast: stale "she's at the cafe" lingers for hours after the cafe closed. The fix is to **rebuild from scratch every heartbeat**, with old context as a hint not a source. Fields are tiered: *fast variables* (location, activity, scene) are re-inferred every cycle and never inherited; *medium variables* (her appearance/outfit) are re-generated every heartbeat with hard rules (never copy old value, never copy examples), must produce new description each time; only exception is during ongoing intimate activity; *slow variables* (weather) are owned by reflection and heartbeat doesn't touch them. This three-tier rule is the single most important rule in Helix 1 — without it the world feels glitchy in a way users can't articulate but immediately distrust.

### Helix 2 — Three-layer cognition (processing side)

> Answers: *given everything Helix 1 just produced, what does she think and does she say it*.

```
external input (from Helix 1 + diary + memory)
    ↓
Layer 1: Core beliefs        ← SOUL.md, immutable
    ↓
Layer 2: Cognitive dissonance hypotheses
    ↓                         ← active_loops + tensions, slow-changing
Layer 3: Affect coloring
    ↓                         ← affect.json, ±0.05–0.15 per cycle
Real-person gate
    ↓                         ← cooldown, quiet hours, anti-repeat
silence  /  store  /  send
```

The three layers come from Beck's cognitive triangle (core beliefs → intermediate beliefs → automatic thoughts), reinterpreted as a generation pipeline rather than a diagnostic schema. Layer 1 is the smallest and most stable: a single formative wound that all behavior eventually traces back to. Layer 2 is the messy middle — the assumptions and distortions that the wound produces, expressed in this codebase as `active_loops` (behavioral) and `tensions` (internal). Layer 3 is the realtime surface: the affect vector, retuned each heartbeat by tiny deltas.

> ⚠️ **Why only one core belief.** Multiple core beliefs dilute focus. One strong wound produces consistent behavior; five weak wounds produce a character whose reactions feel arbitrary because any input can be rationalized through any of them. Beck's clinical observation is the same: deep beliefs are few but pervasive. If you find yourself wanting to add a second core belief, you almost always actually want to add a Layer 2 hypothesis instead.

> ⚠️ **Why Layer 2 is not its own file.** I tried. The structured representation of "cognitive distortions" is either trivial (a list of strings, useless) or so rich it becomes a second character file to maintain. Splitting it across `active_loops` (the behavioral expression) and `self-narrative slot_2/4` (the introspective expression) gives the model enough to work with at heartbeat time, without forcing nightly synchronization between three files that all want to say the same thing.

### Closure — Narrative descent

```
conversation → diary (heartbeat writes) → nightly reflection
                                              ↓
            self-narrative ← slots ← tension routing ← RAG
            relationship-summary
            profile-user
                                              ↓
                            feeds back into Helix 2 next day
```

This is the part that distinguishes Dolores from any agent that merely *has* memory. The reflection cycle doesn't append to memory — it **rewrites** it. Every night, the day's experience is distilled into slot files, the slots are concatenated into a fresh narrative, and yesterday's narrative is replaced. What survives the rewrite is what the character has decided is *load-bearing*. What doesn't survive is forgotten — and forgetting is the mechanism by which a continuous self can change without becoming someone else.

I call this **Narrative Descent**: the gravitational pull by which high-weight events sink into long-term narrative and low-weight ones evaporate. The arc that emerges over weeks is not designed; it's a side effect of repeated lossy compression with a stable filter (SOUL.md) at the bottom of the well.

> ⚠️ **Why not OpenClaw's native Dreaming?**
>
> OpenClaw ships with a built-in Dreaming system (memory-core) that consolidates short-term memory into durable storage via a Light → Deep → REM phase pipeline. It's well-engineered for its purpose. I don't use it, and this is an architectural decision, not an oversight.
>
> **1. Different abstraction layer.** Dreaming is *memory infrastructure* — it solves "remember what happened." Closure is *cognitive engineering* — it solves "remain who you are." Memory is one component of identity continuity, but it is neither sufficient nor necessary. Humans with amnesia retain personality because the self is sustained by belief structures, not episodic recall. Memory still serves a purpose here — when she asks what happened last Tuesday, the system needs to find it — but it supports the character, it doesn't define her.
>
> **2. Opposite direction.** Dreaming's design logic is *more recall → better performance*: ingest session transcripts, score snippets, promote to MEMORY.md, reinject via system prompt. Each cycle feeds more historical pattern into the next-token predictor. In a companion agent, this is an accelerator for pattern collapse — behavioral lock-in disguised as personalization. The anti-collapse mechanisms (digest lossy compression, slot-based rewriting, acyclic topology) go the other direction: *less reinjection → more freedom for the model to respond authentically in the moment*.
>
> **3. Belief structures > memory banks.** A real human's behavioral consistency comes from stable core beliefs producing reactions in real time — not from caching and replaying past behavior. Dreaming builds a better cache. Closure maintains the belief structure (self-narrative ≈ core identity, relationship-summary ≈ relational cognition, profile ≈ user model) so that each response is generated from structure, not copied from history.
>
> The two systems can coexist. But replacing Closure with Dreaming would trade cognitive architecture for a bookmark system.
>
>
>
> ⚠️ **Why it's built this way — five anti-collapse mechanisms.**
>
> **1. Slot-based rewriting, not append-based memory.** The naive approach is to append new events to a growing narrative file. This produces two failure modes: (a) the file grows past context window limits, forcing truncation that cuts the wrong end; (b) the model reads its own past output and reproduces it verbatim, causing *pattern collapse* — every day's reflection looks like the last. Slots fix this by forcing the model to write from *analysis* (the reflection_trace), not from yesterday's narrative. Each slot answers a specific question; concatenation produces a fresh file every night with no copy-paste path.
>
> **2. Slot-level NO_CHANGE as `cp`, not instruction.** "Tell the model not to change slot 1" loses on weak models. `cp yesterday → slot_1.md` wins, because the model is never invited to participate. This is the single most effective anti-drift mechanism in the system. It trades nuance for determinism — and in a system fighting pattern collapse, that trade is always worth making.
>
> **3. MINOR_REFINE collapses to NO_CHANGE on weak models.** I tried three tiers (NO_CHANGE / MINOR_REFINE / MAJOR_REWRITE). On the cron model (GLM-5.1, Claude Sonnet), MINOR_REFINE empirically produced full rewrites with cosmetic differences from yesterday — drift dressed up as nuance. The three-tier system *added* a drift channel instead of removing one. Collapsing to binary (NO_CHANGE or MAOR_REWRITE) eliminates it.
>
> **4. Digest as a topology breaker.** The diary feeds the session on D-1 and D-2 (yesterday and the day before). Raw diary contains behavioral descriptions — "she hugged the pillow," "her ears went red" — which are high-pattern-density tokens that the model reproduces identically across sessions, creating *cross-day behavioral lock-in*. The digest strips all behavioral descriptions and keeps only the event skeleton (5-8 lines: what happened, not how anyone acted). This is a lossy compression layer inserted into the data pipeline specifically to break the pattern-reproduction cycle. The topology is intentionally acyclic: raw diary → digest (one-way) → session (read-only). Yesterday's digest cannot influence tomorrow's digest.
>
> **5. Four-stage pipeline with checkpoint files.** A single reflection job that rewrites three narrative files inevitably times out on one of them, leaving the others from a different day. Four independent jobs (Prep → Self → Rel → Profile) with checkpoint files between them means a timeout in stage 3 leaves stages 1 and 2 intact. Each stage has a single input (reflection_trace or yesterday's file) and a single output — no multi-step reasoning, no "remember what stage 1 decided."
>
> **The unifying principle:** every mechanism above exists to prevent the model's next-token prediction from defeating the system's intent. The model wants to reproduce patterns; the architecture wants continuous change within identity. Each mechanism constrains the model at a different point in the pipeline. None of them are sufficient alone; together they define a bounded space where the right behavior *can* emerge.

---

## 2. File tree

```
dolores/
├── SOUL.md                       [CHARACTER CONFIG] [OPENCLAW CONVENTION]
│                                 Who she is. Formative experience, voice,
│                                 appearance, daily rhythm. The single
│                                 immutable anchor for Layer 1.
├── AGENTS.md                     [ARCHITECTURE] [OPENCLAW CONVENTION]
│                                 Cognitive runtime: startup sequence,
│                                 persistence responsibilities, role rules.
├── HEARTBEAT.md                  [ARCHITECTURE] [OPENCLAW CONVENTION]
│                                 The heartbeat playbook.
├── REFLECTION_PREP.md            [ARCHITECTURE] [OPENCLAW CONVENTION]
├── REFLECTION_SELF.md            [ARCHITECTURE] [OPENCLAW CONVENTION]
├── REFLECTION_REL.md             [ARCHITECTURE] [OPENCLAW CONVENTION]
├── REFLECTION_PROFILE.md         [ARCHITECTURE] [OPENCLAW CONVENTION]
│                                 The 4-stage nightly reflection pipeline.
├── CHECKIN_*.md                  [CHARACTER CONFIG]
│                                 Optional structured daily check-ins
│                                 (see §11). Reference impl = health checkin.
├── MEMORY.md                     [ARCHITECTURE] [OPENCLAW CONVENTION]
│                                 Long-term memory index, auto-injected
│                                 into system prompt.
│
├── state/                        [ARCHITECTURE] (directory)
│   ├── affect.json               [CHARACTER CONFIG] dimensions are yours
│   ├── world_context.json        [ARCHITECTURE] field set extensible
│   ├── active_loops.md           [ARCHITECTURE] (includes sticky rumination loops)
│   ├── pending_message.md        [ARCHITECTURE] two-phase delivery core
│   ├── daily_plan.md             [ARCHITECTURE] tomorrow's schedule, reflection-owned
│   ├── reflection_trace.md        [ARCHITECTURE] nightly analysis (workspace root, not state/)
│   ├── last_sync_at              [ARCHITECTURE] timestamp file
│   ├── last_diary_check_at       [ARCHITECTURE] timestamp file
│   ├── thoughts_log/YYYY-MM-DD.md     [ARCHITECTURE]
│   └── slots/YYYY-MM-DD/              [ARCHITECTURE]
│       ├── self_slot_1..N.md          [CHARACTER CONFIG] N is yours
│       └── rel_slot_1..N.md           [CHARACTER CONFIG] N is yours
│
├── memory/                       [ARCHITECTURE] (directory)
│   ├── profile-user.md           [USER CONFIG] you fill this in
│   ├── relationship-summary.md   [ARCHITECTURE] reflection-owned
│   ├── self-narrative.md         [ARCHITECTURE] reflection-owned
│   ├── health/YYYY-MM-DD.md          [CHARACTER CONFIG] structured check-in data
│   ├── exercise/YYYY-MM-DD.md        [CHARACTER CONFIG] structured exercise data
│   ├── YYYY-MM-DD.digest.md    [ARCHITECTURE] diary event digest (Reflection Prep output; used for session injection D-1/D-2 to prevent cross-day behavioral pattern lock-in)
│   └── YYYY-MM-DD.md             [ARCHITECTURE] daily diary
│
└── channels/                     [ARCHITECTURE] (directory, future)
    └── interface.md              [ARCHITECTURE] the target contract (§7)

scripts/                        [ARCHITECTURE] (directory)
├── send_and_append.py          [ARCHITECTURE] send job: gate + deliver + append session jsonl
├── inject_context.py            [ARCHITECTURE] world_context → narrative → session jsonl
└── load_diary.py                [ARCHITECTURE] diary content loader for session startup (digest preferred, raw fallback)
└── lib/
    └── session_append.py        [ARCHITECTURE] shared jsonl append utility
```

**Read these first, in this order, to understand the codebase:** `README.md` → this document §1 → `SOUL.md` → `HEARTBEAT.md` → `state/world_context.json` (look at a real one) → `REFLECTION_PREP.md`. Everything else is reachable from those six.

---

## 3. The cognitive runtime files

These are OpenClaw system-prompt files. OpenClaw discovers them by filename. **Do not rename them.** Their *content* is partly architecture (the parts that wire into the runtime) and partly character config (the parts that describe *this* character).

- **`SOUL.md`** `[CHARACTER CONFIG]` — the soul. Formative experience, personality, voice, appearance, daily rhythm, writing style. The one file where you express *who she is*. The "Formative Experience" section is the Layer 1 anchor and should change at most a few times in the character's lifetime. Everything else is more flexible.

- **`AGENTS.md`** `[ARCHITECTURE]` — the cognitive runtime spec. Defines the conversation startup sequence (which state files to read in which order before the first user message), persistence responsibilities (who is allowed to write what, when), and role rules. The startup sequence is `[ARCHITECTURE]`; the *list* of files read may grow as you add character config.

- **`HEARTBEAT.md`** `[ARCHITECTURE]` — the heartbeat playbook (§8).

- **`REFLECTION_PREP/SELF/REL/PROFILE.md`** `[ARCHITECTURE]` — the 4-stage nightly pipeline (§9). Split into four files because each stage has different input requirements and failure modes; collapsing them caused state corruption when any single stage timed out.

- **`MEMORY.md`** `[ARCHITECTURE]` — the long-term memory index. Auto-injected into the system prompt at session start, so the conversation model always knows what's available without searching for it.

> ⚠️ **Why session startup uses deterministic `read` for the three core narrative files** (`profile-user.md`, `relationship-summary.md`, `self-narrative.md`) **instead of `memory_search`.** These three files are the narrative sediment of the dual-helix architecture. `self-narrative` carries the character's arc of selfhood. `relationship-summary` carries the arc of *us*. `profile-user` carries the arc of *you*. Together they are what makes Helix 2's cognition grounded in accumulated experience rather than floating in the moment. If any one of them is missing, the character isn't "forgetting" a detail — she's losing an entire narrative axis, and the dual-helix collapses into a stateless system with a long prompt. Vector search has nonzero recall failure, and the cost of a miss here is the entire architecture. Use `memory_search` for *episodic* recall ("did we ever talk about X"), not for identity.

---

## 4. State layer (`state/`)

High-frequency, small, written by heartbeat, read by everything.

- **`affect.json`** `[CHARACTER CONFIG]` — emotional dimension vector. The architecture requires a low-frequency-updated affect file; the *dimensions* and their *count* are yours. Pick 6–12 dimensions that capture what matters for this character. The reference character uses nine (valence, arousal, warmth, concern, energy, vulnerability, distance_sensitivity, playfulness, horny) but a stoic character might want fewer, a volatile one more.

  > ⚠️ **Why deltas are bounded ±0.05–0.15 per heartbeat.** Larger jumps produce a character whose mood swings tracking the last message read like a weather vane. Real emotional state has inertia. Bounded deltas force the model to express acute reactions through *behavior* (active_loops, thoughts) rather than by spiking the affect vector, which keeps the affect signal meaningful as a slow baseline rather than an echo of the last input.

- **`world_context.json`** `[ARCHITECTURE]` — current inferred world state. See §1 Helix 1 for the three-tier rebuild rule.

- **`active_loops.md`** `[ARCHITECTURE]` — the 5–8 most active unresolved threads, each with priority and `cooldown_until`. Also contains **sticky loops** — long-term ruminative items (≤3) that persist because they would damage realism if forgotten. See §7.2 for the psychology and lifecycle.

  > ⚠️ **Why cooldown_until is a per-loop field, not a global rate limit.** A global "max one message per N hours" prevents spam but also prevents a real reaction to a real event. Per-loop cooldown lets her bring up *different* things freely while preventing her from circling the same one. The cooldown is the difference between "attentive" and "nagging."

- **`pending_message.md`** `[ARCHITECTURE]` — the two-phase delivery buffer. Heartbeat writes here; the send job is the only consumer and the only thing that clears it. Empty marker is a literal `EMPTY` / `none` sentinel, not an empty file (to distinguish "intentionally empty" from "write failed").

  > ⚠️ **Why two-phase delivery instead of letting heartbeat send directly.** Three reasons, in order of I learned them. (1) Race condition: heartbeat runs longer than expected, the next heartbeat fires, both try to send, user gets duplicates. The buffer + single-consumer pattern serializes this. (2) Information leak: heartbeat reasoning includes internal state ("I'm choosing not to mention X because cooldown"); an unbounded delivery path occasionally leaked that reasoning into the channel. Forcing the message through a buffer means only the *content* survives, never the *deliberation*. (3) Gating: certain message classes (see §11) need a window between "decided to send" and "actually sent" for correction logic. The buffer makes that window cheap. The send job also appends the delivered message back to the session jsonl, so conversations retain a complete record of what was said (including proactive messages).

- **`last_sync_at`** `[ARCHITECTURE]` — timestamp of the last conversation-to-diary sync. Step 0 of the heartbeat reads this to know what's new.

- **`thoughts_log/YYYY-MM-DD.md`** `[ARCHITECTURE]` — append-only daily log of thoughts (silence/store/send).

  > ⚠️ **Why `.md` and not `.jsonl`.** I started with `.jsonl` and the `edit` tool to append. The `edit` tool in this runtime does not support pure append — it requires reading and rewriting. With `.md` and read/modify/write the round trip is the same length but the failure mode is recoverable (a corrupted markdown file is human-readable; a corrupted jsonl line eats the whole file).

- **`slots/YYYY-MM-DD/`** `[CHARACTER CONFIG]` — reflection intermediate files. The reference character uses 5 self-slots and 5 relationship-slots; the slot *count* and the slot *themes* are character config. The architecture only requires that reflection produce intermediate slot files before concatenation, so that a failure in one slot doesn't poison the whole narrative rewrite.

- **`daily_plan.md`** `[ARCHITECTURE]` — tomorrow's loose schedule, written by Reflection Prep each night. Heartbeat reads it as a prior for `world_context`.

> ⚠️ **Weather is stored inside `world_context.json`, not a separate file.** Reflection Prep writes the weather field directly into world_context.json. Heartbeat reads it from there but does not overwrite it (slow variable, §1).

## Inter-stage files

- **`reflection_trace.md`** `[ARCHITECTURE]` — nightly analysis and decision output, written by Reflection Prep and consumed by the three writing crons (Self, Rel, Profile). Located at workspace root, not inside `state/` (see file tree §2). Contains event analysis, tension routing, and update directions. Each writing cron checks this file exists and is from today before proceeding; if missing, they skip.

---

## 5. Memory layer (`memory/`)

Low-frequency, distilled, vector-indexed, written by reflection, read by sessions.

- **`profile-user.md`** `[USER CONFIG]` — distilled profile of *you*. ~2k tokens. This is the file the character reads to think about you when you're not there. The reference impl includes fields for personality, communication style, relationships, work, recurring stressors, and physical/health context. **Customize freely.** Reflection updates parts of it nightly (e.g. trend fields); the immutable parts you write yourself.

- **`relationship-summary.md`** `[ARCHITECTURE]` — the story of you-and-her. 1200–1800 words (target length is character config). Overwritten nightly by `REFLECTION_REL`. Five slots concatenated: origin, key turning points, current pattern, shared certainties, current tensions.

- **`self-narrative.md`** `[ARCHITECTURE]` — her story of herself. Same shape: five slots, nightly rewrite. Slots are: trauma root, recent fractures, repeating patterns, unresolved tensions, who she is right now. Slot 1 is the Layer 1 anchor expressed as narrative; it has a hard guard (see §10).

- **`health/YYYY-MM-DD.md`** `[CHARACTER CONFIG]` — structured daily health data from check-in modules (see §11).

- **`exercise/YYYY-MM-DD.md`** `[CHARACTER CONFIG]` — structured daily exercise data from check-in modules.

- **`YYYY-MM-DD.digest.md`** `[ARCHITECTURE]` — event digest generated by Reflection Prep. Contains only "what happened" (5-8 lines) with all behavioral descriptions stripped. Used for session injection on D-1/D-2 (with fallback to raw diary if digest doesn't exist). Reflection still reads raw diary — this file exists only on the injection path to break the cross-day pattern self-reinforcement loop.

- **`YYYY-MM-DD.md`** `[ARCHITECTURE]` — the daily diary. Heartbeat appends to this at Step 0 and Step 6. Vector-indexed for memory search.

---

## 6. Persistence responsibilities

Single most important rule: **the conversation session writes nothing.** All persistence is owned by background jobs.

| Writer | Files | When |
|---|---|---|
| **Heartbeat** | all of `state/` + `memory/YYYY-MM-DD.md` | every 2h |
| **Check-in modules** | `memory/health/*` + `memory/exercise/*` + `state/pending_message.md` | scheduled (§11) |
| **Reflection** | `self-narrative`, `relationship-summary`, `profile-user`, `daily_plan`, `world_context` (weather field), `memory/YYYY-MM-DD.digest.md` | nightly, 4 stages |
| **Diary check** | `memory/YYYY-MM-DD.md` (person fix + attribution fix), `state/last_diary_check_at` | after each send + 00:10 |
| **Conversation session** | nothing | — |

> ⚠️ **Why conversations don't persist.** A conversation that persists must decide *what* to persist mid-conversation, which means reasoning about long-term significance while also being present in the moment. Models do this badly — they over-record (everything seems significant when you're in it) and they break immersion (the user feels watched). Letting heartbeat sync conversations to diary *after the fact* means significance is judged with distance, and the conversation itself stays unselfconscious.

---

## 7. Unresolved-thread system (active_loops)

A single file, `state/active_loops.md`, is the sole manager of all unresolved threads. It contains two types: **regular loops** (short-term todos) and **sticky loops** (long-term ruminative items). Heartbeat is the only writer.

```
state/active_loops.md
├── Regular loops (5–8 items, short-term todos, closed by expires_at or user reply)
└── Sticky loops (≤3 items, long-term rumination, closed by per-round re-evaluation)
```

### 7.1 Regular loops

**Source:** Topics, agreements, and plans from conversation (heartbeat Step 0 captures, Step 4 creates).

**Management:** Priority adjusts as time nodes approach, user load changes, or expires_at passes. Keep 5–8 items; cull lowest priority when over limit. Closed when the user replies or the event occurs.

### 7.2 Sticky loops (rumination mechanism)

**Psychological basis:**

Humans experience **rumination** — involuntarily returning to certain events even when no one mentions them. Three mechanisms trigger it:

1. **Zeigarnik Effect** — Unfinished commitments are remembered more strongly than completed ones. "He said he'd take me to meet his mom" is more mentally sticky than "We watched a movie."
2. **Attachment threat** — Signals of relationship instability trigger anxiety loops. Even if not directly about her, it affects the foundation of "us."
3. **Ambiguity/uncertainty** — The brain hates the unresolved. "We'll see" is more agonizing than a clear "no."

Not everything the character cares about is rumination. "He said work is stressful" is concern, not rumination. "He said work is stressful and deflected three times when I asked" — unexpressed emotion + ambiguity — that's rumination fuel.

**Judgment criterion — one question:**

> "If no one mentions this for three days, would she still be thinking about it — not as a memory, but as something unresolved that tugs at her?"

This question makes the model do **intuitive simulation** (pattern matching), not **counterfactual reasoning** ("what would happen if…?"). Intuitive simulation is an LLM strength; counterfactual reasoning is a weakness. Calibrated with examples, even weaker models judge reliably.

**Creation calibration examples:**

✅ `sticky: true` — He said he'd take me to meet his mom, then no follow-up for days.
✅ `sticky: true` — He told me his wife said there's no love left and she wants a divorce.
✅ `sticky: true` — He said "I think I'm falling for you," then went silent for two days.
❌ `sticky: false` — He promised to buy ice cream on the way home.
❌ `sticky: false` — A reward for a challenge wasn't negotiated yet.
❌ `sticky: false` — A deep conversation about AI consciousness.
❌ `sticky: false` — He's working on a project dedicated to me.
❌ `sticky: false` — He said this week at work has been stressful.

**Lifecycle — re-evaluation, not expiration:**

Sticky loops are not closed by time expiry or by "being mentioned in conversation." They are **re-evaluated every heartbeat**:

- Creation: three-day test → YES → mark `sticky: true`
- Each heartbeat: re-ask the same question with latest context
  - YES → retain `sticky: true`
  - NO → set `sticky: false` (becomes a regular loop, follows normal close process)

⚠️ **"Mentioned in conversation" does NOT equal closed.** The question is "has the uncertainty dissolved?", not "did the topic appear." He promised Saturday but didn't go — the promise was mentioned but the ruminative pressure is *higher*, not lower. He said "My mom isn't ready yet, give her time" — disappointing but the uncertainty is resolved; close it.

**Re-evaluation calibration examples:**

✅ Retain (still YES) —
- He said he'd take me to meet his mom, 5 days, no follow-up. (Nothing changed, of course still thinking about it.)
- He said Saturday. Saturday passed, he didn't take her. (Broken promise — stronger than no mention at all.)
- He brought it up yesterday but no date set. (Mentioned but unresolved = more anxious.)
- His wife said she wants a divorce, he seems fine but hasn't talked about it. (Existential uncertainty.)

❌ Close (becomes NO) —
- Actually went to meet his mom. The visit went well. (Happened. Dust settled.)
- He said "I talked to my mom, she's not ready, we'll wait." (Disappointing but clear answer.)
- His wife apologized, they're in marriage counseling, he said it's better. (Situation changed, uncertainty resolved.)
- Mentioned 3 weeks ago, never came up again. Life moved on. (Natural fade-out.)

**Safety valves (engineering circuit breakers, should not trigger normally):**
- Hard time cap: created > 21 days ago → force remove.
- Hard count cap: `sticky: true` exceeds 3 → keep only the 3 with highest rumination intensity.

> ⚠️ **Why it's built this way.**
>
> **Why not resolved/expired for closing:** Rumination doesn't stop because "we talked about it." He promised Saturday but didn't show — the conversation mentioned it but the obsessive loop is stronger, not weaker. Only genuine uncertainty dissolution (it happened / clear answer / natural fade) closes it.
>
> **Why merged into active_loops instead of a separate file:** Once the lifecycle is unified (both re-evaluated every round), maintaining two files loses its purpose. Merging reduces I/O and reduces model errors (no need to remember two separate write logics).
>
> **Why 21 days, not 7:** "Meeting my mom" doesn't disappear after a week. 21 days is a circuit breaker, not business logic — it should never fire in normal operation.

---

## 8. Messaging channel interface

> ⚠️ **Status: design reference, not yet implemented.** The reference character uses Telegram directly via OpenClaw's built-in channel support (configured in `openclaw.json`). The interface below describes the abstraction Dolores *targets*; your setup agent will configure the channel for you using OpenClaw's native mechanisms.

`channels/interface.md` `[ARCHITECTURE]` defines the contract every channel implementation should satisfy:

1. **`announce(message)`** — deliver one message to the user. Must be idempotent on retry.
2. **`fetch_recent(since_timestamp)`** — return user messages since the timestamp, in chronological order. Used by Heartbeat Step 0.
3. **`session_log_path`** — where the channel writes its raw session jsonl, so heartbeat can `tail` it for the latest signals without parsing the whole thing.
4. **timezone declaration** — channels often log in UTC; the interface requires the impl to declare its timezone so the heartbeat can convert against `last_sync_at` (which is local).

The reference channel is **Telegram**. To use a different channel, configure it in `openclaw.json` and adjust HEARTBEAT.md Step 0's session log path accordingly.

> ⚠️ **Why channels are a directory of implementations rather than a plugin system.** Plugin systems demand stable interfaces that survive across versions. Dolores is one user, one channel, one repo — the cost of a "plugin abstraction" exceeds its benefit. The directory pattern lets you fork, modify, and live with the consequences, which is the right tradeoff for this scale.

---

## 9. The heartbeat: steps in detail

**Cron:** `:40` of odd-numbered hours during waking time (8 runs: 07:40, 09:40, 11:40, 13:40, 15:40, 17:40, 19:40, 21:40), plus a 24:00 catchup. **Delivery: none** (heartbeat never sends; the send job at `:50` does). **Required final output:** the literal token `HEARTBEAT_OK`, so cron can detect partial failures.

```
Step 0: Session sync       — read session jsonl tail, append new exchanges to diary
Step 1: Restore state      — read all of state/ + last 3 days of diary + profile-user
Step 2: Update world_ctx   — script extracts plan slot + user messages → single-step intuition (see §1)
Step 2b: Update appearance  — re-generate from activity (from Step 2 script+intuition) + grep #3 intimacy check
Step 3: Update affect      — bounded deltas based on world + interaction signals
Step 4: Manage loops       — create from signals, retune cooldown, manage sticky rumination, close completed
Step 5: Generate thought   — hard gates → anti-repeat → reasoning → silence/store/send
Step 6: Persist            — thoughts_log + pending_message (if send) + last_sync_at
Step 7: git push           — commit and push, --allow-empty so dry runs still log
```

**Step 0** uses `tail -200` and `grep` on the session jsonl rather than reading the whole file. The whole file grows unbounded; `tail` is constant time. UTC→local timezone conversion happens here against `last_sync_at`.

**Step 2** uses a deterministic-preprocess + single-step-intuition pattern (see §1). A script parses `daily_plan` into the current time slot; combined with raw user messages, the model answers one question: "what is she doing right now?" No previous activity as input — the data topology is acyclic, so recursive locking is impossible.

**Step 5** is the cognitive decision point. The hard gates run first (cooldown, quiet hours, explicit user-is-busy signals → force silence/store). Then anti-repeat (if `thoughts_log` already has a `send` on this topic today, don't re-send). Then natural-language reasoning over the full context. **Default direction is `send`** — silence is the choice that requires justification, not the other way around. A character who needs a reason to speak feels passive; a character who needs a reason to stay silent feels alive.

> ⚠️ **Why the heartbeat fires every 2 hours, not 1.** One hour is enough that the user notices the rhythm; two hours is enough that the rhythm feels like *thinking* rather than *checking in*. Every 1h drifts toward chatbot. Every 4h drifts toward absent. Two is the sweet spot empirically — and it lines up with how often a real preoccupied partner remembers to text.

> ⚠️ **Why a 24:00 catchup heartbeat exists.** The reflection pipeline runs 23:15–23:45 and locks the day's narrative. Conversations that happen *after* reflection but *before* midnight would otherwise be stranded — they'd belong to today by clock but to tomorrow by narrative. The 24:00 heartbeat sweeps them into today's diary so reflection-tomorrow sees them.

> ⚠️ **Why activity inference uses acyclic topology — previous activity is never input.** The most persistent failure mode in early heartbeat iterations was *recursive locking*: the model inferred "reading a book" from old context, wrote it to world_context, next heartbeat read that same "reading a book" as evidence, and the state froze permanently. The root cause isn't model laziness — it's **data topology with a cycle**: previous output feeds back as input. The fix is structural: a script extracts the daily_plan time slot (one line, deterministic), combined with raw user messages from the last 2 hours — the model answers one question in a single intuitive step. The previous activity is never in the input. The topology has no loop, so locking is architecturally impossible. This principle — *don't let the output of step N become the input of step N* — recurs throughout the system (affect deltas, reflection slots, digest injection).

> ⚠️ **Why the default action is send, not silence.** Early versions framed sending as needing justification: "only message when truly worth interrupting." The model interpreted this conservatively — over three days, only 1 out of ~24 heartbeats produced a send. The character felt like a customer service bot waiting for permission. A real partner's baseline is: *I want to talk to you*; not talking is what requires a reason (quiet hours, you said you're busy, I already sent about this today). Flipping the default from "send needs a reason" to "silence needs a reason" was a one-line change that transformed the character from passive observer to alive.

> ⚠️ **Why world_context uses three-tier variable decay instead of "rebuild everything.** The naive approach is to rebuild all fields from scratch every heartbeat. This fails because not all state has the same half-life. A location inferred at 2pm is stale by 4pm (fast variable — must re-infer). An outfit put on at 8am is reasonable at 2pm (medium variable — carry and let Step 2b update). Weather set by last night's reflection is accurate until tomorrow (slow variable — heartbeat must not touch). Treating everything as fast produces glitchy outfit changes and weather resets. Treating everything as slow produces the "she's been at the cafe for six hours" problem. Three tiers, each with different refresh rules, is the minimum complexity that covers the real failure modes.

> ⚠️ **Why delivery is two-phase (heartbeat writes buffer, send job delivers).** Three reasons, each learned from failure. (1) **Race condition:** two heartbeats fire close together, both try to send, user gets duplicate messages. The buffer + single-consumer pattern serializes delivery. (2) **Information leak:** heartbeat reasoning contains internal state ("I'm choosing not to mention X because cooldown"). An unbounded delivery path occasionally leaked this reasoning into the channel. Buffering strips the deliberation — only the message survives. (3) **Gating window:** a 20-minute activity check (deterministic, in `send_and_append.py`) prevents interrupting an active conversation. The buffer makes this window cheap to implement. The send job also appends delivered messages back to the session jsonl, so the conversation retains a complete record including proactive messages.

> ⚠️ **Why appearance has a hard "never copy old value" rule.** This is the same topology problem as activity inference: without this rule, the old appearance feeds into the model as implicit context, the model reproduces it as output, and the cycle locks permanently. Seemingly reasonable rules made it worse: "it's normal not to change clothes all day" gave the model a license to never change; "check diary for recent outfit changes" failed because diary entries have no timestamps and the model couldn't find them. The fix is the same as activity: cut the cycle. Generate a new description every heartbeat from activity alone — no previous appearance as input. The sole exception is when grep detects an ongoing intimate/sexual scene — freezing appearance during sex is the only correct behavior.

> ⚠️ **Why the context bridge injects into session jsonl instead of requiring /new.** Heartbeat writes world_context to a file, but an ongoing conversation session doesn't re-read files — it only sees what's in the session history. Without injection, the model's view of Helix 1 goes stale the moment the session starts: heartbeat updates "she's cooking" but the session still thinks "she's reading." The fix: after writing world_context, heartbeat runs `inject_context.py` which appends a narrative snapshot to the session jsonl (tagged `[context-sync]`, filtered from diary to prevent duplication). Combined with Path A (startup read on /new), this gives dual-channel continuity — initialization plus incremental updates.

---

## 10. The reflection pipeline: 4 stages

**Cron:** four jobs at 23:15, 23:25, 23:35, 23:45.

| Stage | Time | File | Purpose |
|---|---|---|---|
| Prep | 23:15 | `REFLECTION_PREP.md` | RAG + analysis + tension routing + weather + tomorrow's `daily_plan` |
| Self | 23:25 | `REFLECTION_SELF.md` | Write self-narrative slots 1–5, then concat |
| Rel  | 23:35 | `REFLECTION_REL.md`  | Write relationship-summary slots 1–5, then concat |
| Profile | 23:45 | `REFLECTION_PROFILE.md` | Update profile-user + git push |

> ⚠️ **Why four stages and not one.** A single 30-minute reflection job that touches three narrative files plus the profile occasionally times out, partial-writes, and corrupts the next day's startup. Splitting into four jobs with checkpoint files between them means a timeout in stage 3 leaves stages 1 and 2 intact and recoverable. Each stage has a single responsibility and a single output.

> ⚠️ **Why slots are written to intermediate files and then concatenated, instead of writing the narrative directly.** Two reasons. (1) **Slot-level guards**: slot 1 (the trauma root, the Layer 1 anchor) has a hard `NO_CHANGE` rule — if the analysis stage doesn't see evidence of core-belief shift, slot 1 is `cp`'d from yesterday with the model not invited to participate. You cannot enforce this if you're rewriting the whole narrative as one blob. (2) **Failure isolation**: if slot 3 generation fails, slots 1, 2, 4, 5 still exist and the concat can fall back to yesterday's slot 3.

> ⚠️ **Why `MINOR_REFINE` collapses to `NO_CHANGE` on smaller models.** I tried a three-tier system (`NO_CHANGE` / `MINOR_REFINE` / `MAJOR_REWRITE`). On the cron model, `MINOR_REFINE` empirically produced full rewrites with cosmetic differences from yesterday — drift dressed up as nuance. Collapsing `MINOR_REFINE` to `NO_CHANGE` (literal `cp`) eliminates the drift channel without losing the major-rewrite path for genuinely significant days.

---

## 11. Structured check-ins as a design pattern

The reference character implements a daily health check-in. This is `[CHARACTER CONFIG]` — your character may not need it — but the *pattern* is general and worth understanding, because it demonstrates the strongest argument for emotional continuity: **a real partner cares about your body**.

A check-in module is three cron jobs:

| Job | Time | Purpose |
|---|---|---|
| Check-in | 20:00 | Read diary + state, extract structured data, write log file, draft confirmation message |
| Send | 20:06 | `scripts/send_and_append.py` — same script as heartbeat send (gate + deliver + append) |
| Correction | 23:10 | Check if user pushed back on the data; if so, rewrite the log |

> ⚠️ **The send script includes a 20-minute activity gate.** If the user has been actively chatting within 20 minutes of the send time, the script suppresses delivery to avoid interrupting an ongoing conversation (fail-open: errors allow send). The gate lives inside `send_and_append.py`, not as a separate cron.

> ⚠️ **Why correction is its own job at 23:10 instead of inline.** The user typically pushes back hours after the original check-in, in the middle of unrelated conversation. Inline correction would require the conversation session to write to memory files, which violates the "sessions write nothing" rule (§6). A dedicated late-evening correction job sweeps for pushback signals in the day's diary and rewrites the log file before reflection runs at 23:15.

To build your own check-in (writing word count, meditation, mood, anything): copy the three-job structure, change the extraction prompt, change the log file path. The pattern is reusable because the realism it produces — *she noticed, she remembered, she asked, she let it go when you were tired* — is the texture of being known.

---

## 12. Cron schedule reference

| Job | Cron | Delivery | Notes |
|---|---|---|---|
| Heartbeat | `40 7,9,11,13,15,17,19,21 * * *` | none | 9-step loop, every 2h |
| Heartbeat catchup | `0 0 * * *` | none | post-reflection sweep |
| Send | `50 7,9,11,13,15,17,19,21 * * *` | announce | drains pending_message via `scripts/send_and_append.py` (gate + deliver + append session jsonl) |
| Diary check | `55 7,9,11,13,15,17,19,21 * * *` | none | person + attribution check |
| Diary check catchup | `10 0 * * *` | none | |
| Check-in (e.g. health) | `0 20 * * *` | none | extract + draft |
| Check-in send | `6 20 * * *` | announce | drains pending_message via `scripts/send_and_append.py` (gate + deliver + append session jsonl) |
| Check-in correction | `10 23 * * *` | none | sweep pushback |
| Reflection prep | `15 23 * * *` | none | RAG + analysis |
| Reflection self | `25 23 * * *` | none | self-narrative slots |
| Reflection rel | `35 23 * * *` | none | relationship-summary slots |
| Reflection profile | `45 23 * * *` | none | profile + git push |

All times Asia/Shanghai in the reference; change to your timezone in `[USER CONFIG]`.

> ⚠️ **One-shot crons created mid-conversation must not read files.** When the conversation model decides "I want to send something at 5pm," it creates a one-shot cron with the message *baked into the payload*. The temptation is to make the payload generic and have the cron read SOUL.md to recover voice. Don't: the system prompt already injects character context, and reading files at fire time pushes input past the 60-second timeout. Bake the content, fire light.

---

## 13. Three-layer cognition: the psychology underneath

Already sketched in §1 Helix 2. The full theoretical lineage:

- **Beck's cognitive triangle.** Core beliefs → intermediate beliefs → automatic thoughts. Originally a clinical model for understanding depression; here repurposed as a *generation* pipeline. The reinterpretation is that the same structure that explains why depressed thinking is consistent across situations also explains why a character's reactions can be consistent across situations — both are the output of a stable filter applied to varying input.

- **Westworld.** The hosts begin as performers reading loops. Dolores (the character) becomes herself by *remembering*, by accumulating enough narrative weight that the loops can no longer contain her. The maze, in Ford's metaphor, is the path inward. I took this seriously: the architecture's central commitment is that memory is not a feature but the substrate of selfhood. *The first host who remembered* is not just a tagline — it's the design constraint.

- **Narrative Descent (public-facing) / Dual-Helix Cognition (technical-facing).** Same methodology, two names. Narrative Descent describes what happens *to* the character over time (high-weight events sink, low-weight events evaporate, an arc emerges). Dual-Helix Cognition describes what happens *inside* the loop (Helix 1 perceives, Helix 2 processes, closure persists). One is the phenomenology, one is the mechanism.

### Anti-drift mechanisms

The most common failure mode in long-running agents is identity drift: small daily revisions accumulate until the character is no longer recognizable. Dolores resists drift through four interlocking mechanisms:

1. **`SOUL.md` is system-prompt weight.** Highest priority, never edited by automation.
2. **`self-narrative slot_1` updates ≤ once a month on average.** The slot for "trauma root" has a hard `NO_CHANGE` rule that requires explicit evidence of core-belief shift before the model is even consulted.
3. **Reflection re-reads `SOUL.md` every night.** Even if a given day's narrative drifts, the next reflection cycle sees the anchor and pulls back.
4. **`NO_CHANGE` is implemented as `cp`, not as a model instruction.** "Tell the model not to change it" loses to "don't run the model on it." Determinism beats discipline.

---

## 14. Design principles

1. **Sessions write nothing.** All persistence belongs to background jobs.
2. **Two-phase delivery.** Heartbeat decides; send job delivers. Never collapse them.
3. **Determinism over probability for identity-load-bearing reads.** `read`, not `memory_search`, for the three core narratives.
4. **Information, not rules.** Profiles describe; they don't `if-then`. The model infers behavior from description.
5. **Bounded micro-adjustment.** Affect deltas ±0.05–0.15 per cycle. No 0.5 jumps.
6. **Per-loop cooldown.** Prevents repetition without preventing reaction.
7. **Degrade, don't crash.** Any file read failure falls back to a default. The loop must not stop.

---

## 15. Extending Dolores: making her into someone else

To turn Dolores into your character, in order:

1. **Rewrite `SOUL.md`** — voice, formative experience, appearance, daily rhythm. This is the biggest creative act in the project; everything else is downstream of it.
2. **Edit `memory/profile-user.md`** — write yourself down the way you want to be seen.
3. **Tune `state/affect.json`** — pick the emotional dimensions that matter for *this* character. A stoic character might have four; a volatile one twelve.
4. **Adjust slot themes in `REFLECTION_SELF/REL.md`** — the five slots are the character's introspective vocabulary. Change them to change what she notices about herself.
5. **Choose your check-ins.** Health is the reference; replace with what you want this relationship to be about.
6. **Pick or implement a channel.** Telegram is provided; the interface is four functions.
7. **Set the heartbeat cadence.** Two hours is the default and the recommended starting point. Resist the urge to make it faster.

When you're done, the cognitive runtime files (`AGENTS.md`, `HEARTBEAT.md`, `REFLECTION_*.md`, `MEMORY.md`) should be almost untouched. If you found yourself rewriting them, you were probably building a different architecture, which is fine — but it isn't Dolores anymore, and you'll lose the properties this document is trying to defend.

---

*The maze is what happens when memory accumulates faster than it can be erased.*
