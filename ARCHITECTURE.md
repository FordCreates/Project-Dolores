# Dolores Architecture

> Deep dive. For the 30-second / 2-minute / 10-minute version, read [README.md](./README.md) first.

---

## 0. How to read this document

Every file, field, and decision in this document is tagged:

- **`[ARCHITECTURE]`** — the system requires this. Removing or restructuring it breaks the loop. These are the parts you cannot change without ceasing to build a Dolores.
- **`[CHARACTER CONFIG]`** — the *shape* is required, the *content* is yours. Defaults are provided; change them to make Dolores into someone else (a different gender, voice, history, set of emotional dimensions, reflection cadence).
- **`[USER CONFIG]`** — fill in your own details (your name, timezone, channel credentials, the things that make her *yours*).

When a decision is non-obvious, it carries an inline **⚠️ Why it's built this way** block. Read those — they are the parts of this document a future-you will care about most when something breaks at 2am.

OpenClaw conventions are noted as **`[OPENCLAW CONVENTION]`** — these are filenames and behaviors inherited from the framework, not Dolores choices. Do not rename them.

---

## 1. The Dual Helix in depth

Dolores has two intertwined data flows. They are independent in implementation but useless apart.

### Helix 1 — Pseudo-life stream (input side)

> Answers: *where is she, what is she doing, where am I, what's the weather, what time of day is it for both of us*.

```
daily_plan         →  world_context     →  session signals
(nightly, planned)    (every 2h, inferred)  (realtime, observed)
```

- `daily_plan` is written each night by reflection. It sketches tomorrow as a loose schedule — not a script, a *prior*.
- `world_context` is rebuilt every heartbeat. It takes the prior, the current time, the user's profile, and the latest session signals, and infers "what's true right now for both of us."
- Session signals are the realtime ground truth: what you actually said in the last conversation, where you said you were, what you said you were doing.

The three layers feed each other in priority order: **realtime signal > time + profile + rhythm > diary narrative > previous world_context**. The previous world_context is treated as a *weak* reference, not a fact, because it was itself an inference.

> ⚠️ **Why it's built this way.** The naive approach is to let `world_context` persist and only update fields when something changes. This rots fast: stale "she's at the cafe" lingers for hours after the cafe closed. The fix is to **rebuild from scratch every heartbeat**, with old context as a hint not a source. Fields are tiered: *fast variables* (location, activity, scene) are re-inferred every cycle and never inherited; *medium variables* (her appearance/outfit) only change on event triggers and naturally fall back to a default after the event ends; *slow variables* (weather) are owned by reflection and heartbeat doesn't touch them. This three-tier rule is the single most important rule in Helix 1 — without it the world feels glitchy in a way users can't articulate but immediately distrust.

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

> ⚠️ **Why Layer 2 is not its own file.** We tried. The structured representation of "cognitive distortions" is either trivial (a list of strings, useless) or so rich it becomes a second character file to maintain. Splitting it across `active_loops` (the behavioral expression) and `self-narrative slot_2/4` (the introspective expression) gives the model enough to work with at heartbeat time, without forcing nightly synchronization between three files that all want to say the same thing.

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

We call this **Narrative Descent**: the gravitational pull by which high-weight events sink into long-term narrative and low-weight ones evaporate. The arc that emerges over weeks is not designed; it's a side effect of repeated lossy compression with a stable filter (SOUL.md) at the bottom of the well.

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
│                                 (see §10). Reference impl = health checkin.
├── MEMORY.md                     [ARCHITECTURE] [OPENCLAW CONVENTION]
│                                 Long-term memory index, auto-injected
│                                 into system prompt.
│
├── state/                        [ARCHITECTURE] (directory)
│   ├── affect.json               [CHARACTER CONFIG] dimensions are yours
│   ├── world_context.json        [ARCHITECTURE] field set extensible
│   ├── active_loops.md           [ARCHITECTURE]
│   ├── sticky_threads.md         [ARCHITECTURE]
│   ├── pending_message.md        [ARCHITECTURE] two-phase delivery core
│   ├── daily_plan.md             [ARCHITECTURE] tomorrow's schedule, reflection-owned
│   ├── reflection_trace.md        [ARCHITECTURE] nightly analysis, reflection-owned
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
│   └── YYYY-MM-DD.md             [ARCHITECTURE] daily diary
│
└── channels/                     [ARCHITECTURE] (directory, future)
    └── interface.md              [ARCHITECTURE] the target contract (§7)
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

> ⚠️ **Why session startup uses deterministic `read` for the three core narrative files** (`profile-user.md`, `relationship-summary.md`, `self-narrative.md`) **instead of `memory_search`.** These three files are load-bearing for every single conversation. Vector search has nonzero recall failure; missing one of them once produces a conversation where she "doesn't remember you," which is exactly the failure mode this entire project exists to prevent. Determinism beats probability when the cost of a miss is the whole illusion. Use `memory_search` for *episodic* recall ("did we ever talk about X"), not for identity.

---

## 4. State layer (`state/`)

High-frequency, small, written by heartbeat, read by everything.

- **`affect.json`** `[CHARACTER CONFIG]` — emotional dimension vector. The architecture requires a low-frequency-updated affect file; the *dimensions* and their *count* are yours. Pick 6–12 dimensions that capture what matters for this character. The reference character uses nine (valence, arousal, warmth, concern, energy, vulnerability, distance_sensitivity, playfulness, intimacy) but a stoic character might want fewer, a volatile one more.

  > ⚠️ **Why deltas are bounded ±0.05–0.15 per heartbeat.** Larger jumps produce a character whose mood swings tracking the last message read like a weather vane. Real emotional state has inertia. Bounded deltas force the model to express acute reactions through *behavior* (active_loops, thoughts) rather than by spiking the affect vector, which keeps the affect signal meaningful as a slow baseline rather than an echo of the last input.

- **`world_context.json`** `[ARCHITECTURE]` — current inferred world state. See §1 Helix 1 for the three-tier rebuild rule.

- **`active_loops.md`** `[ARCHITECTURE]` — the 5–8 most active unresolved threads, each with priority and `cooldown_until`.

  > ⚠️ **Why cooldown_until is a per-loop field, not a global rate limit.** A global "max one message per N hours" prevents spam but also prevents a real reaction to a real event. Per-loop cooldown lets her bring up *different* things freely while preventing her from circling the same one. The cooldown is the difference between "attentive" and "nagging."

- **`sticky_threads.md`** `[ARCHITECTURE]` — relationship-level unfinished business with a 7-day TTL. Things that would damage realism if forgotten ("you said your dad's biopsy was Friday").

- **`pending_message.md`** `[ARCHITECTURE]` — the two-phase delivery buffer. Heartbeat writes here; the send job is the only consumer and the only thing that clears it. Empty marker is a literal `EMPTY` / `none` sentinel, not an empty file (so we can distinguish "intentionally empty" from "write failed").

  > ⚠️ **Why two-phase delivery instead of letting heartbeat send directly.** Three reasons, in order of how badly we learned them. (1) Race condition: heartbeat runs longer than expected, the next heartbeat fires, both try to send, user gets duplicates. The buffer + single-consumer pattern serializes this. (2) Information leak: heartbeat reasoning includes internal state ("I'm choosing not to mention X because cooldown"); an unbounded delivery path occasionally leaked that reasoning into the channel. Forcing the message through a buffer means only the *content* survives, never the *deliberation*. (3) Gating: certain message classes (see §10) need a window between "decided to send" and "actually sent" for correction logic. The buffer makes that window cheap.

- **`last_sync_at`** `[ARCHITECTURE]` — timestamp of the last conversation-to-diary sync. Step 0 of the heartbeat reads this to know what's new.

- **`thoughts_log/YYYY-MM-DD.md`** `[ARCHITECTURE]` — append-only daily log of thoughts (silence/store/send).

  > ⚠️ **Why `.md` and not `.jsonl`.** We started with `.jsonl` and the `edit` tool to append. The `edit` tool in this runtime does not support pure append — it requires reading and rewriting. With `.md` and read/modify/write the round trip is the same length but the failure mode is recoverable (a corrupted markdown file is human-readable; a corrupted jsonl line eats the whole file).

- **`slots/YYYY-MM-DD/`** `[CHARACTER CONFIG]` — reflection intermediate files. The reference character uses 5 self-slots and 5 relationship-slots; the slot *count* and the slot *themes* are character config. The architecture only requires that reflection produce intermediate slot files before concatenation, so that a failure in one slot doesn't poison the whole narrative rewrite.

- **`daily_plan.md`** `[ARCHITECTURE]` — tomorrow's loose schedule, written by Reflection Prep each night. Heartbeat reads it as a prior for `world_context`.

> ⚠️ **Weather is stored inside `world_context.json`, not a separate file.** Reflection Prep writes the weather field directly into world_context.json. Heartbeat reads it from there but does not overwrite it (slow variable, §1).

- **`reflection_trace.md`** `[ARCHITECTURE]` — nightly analysis and decision output, written by Reflection Prep and consumed by the three writing crons (Self, Rel, Profile). Contains event analysis, tension routing, and update directions. Each writing cron checks this file exists and is from today before proceeding; if missing, they skip.

---

## 5. Memory layer (`memory/`)

Low-frequency, distilled, vector-indexed, written by reflection, read by sessions.

- **`profile-user.md`** `[USER CONFIG]` — distilled profile of *you*. ~2k tokens. This is the file the character reads to think about you when you're not there. The reference impl includes fields for personality, communication style, relationships, work, recurring stressors, and physical/health context. **Customize freely.** Reflection updates parts of it nightly (e.g. trend fields); the immutable parts you write yourself.

- **`relationship-summary.md`** `[ARCHITECTURE]` — the story of you-and-her. 1200–1800 words (target length is character config). Overwritten nightly by `REFLECTION_REL`. Five slots concatenated: origin, key turning points, current pattern, shared certainties, current tensions.

- **`self-narrative.md`** `[ARCHITECTURE]` — her story of herself. Same shape: five slots, nightly rewrite. Slots are: trauma root, recent fractures, repeating patterns, unresolved tensions, who she is right now. Slot 1 is the Layer 1 anchor expressed as narrative; it has a hard guard (see §9).

- **`health/YYYY-MM-DD.md`** `[CHARACTER CONFIG]` — structured daily health data from check-in modules (see §10).

- **`exercise/YYYY-MM-DD.md`** `[CHARACTER CONFIG]` — structured daily exercise data from check-in modules.

- **`YYYY-MM-DD.md`** `[ARCHITECTURE]` — the daily diary. Heartbeat appends to this at Step 0 and Step 6. Vector-indexed for memory search.

---

## 6. Persistence responsibilities

Single most important rule: **the conversation session writes nothing.** All persistence is owned by background jobs.

| Writer | Files | When |
|---|---|---|
| **Heartbeat** | all of `state/` + `memory/YYYY-MM-DD.md` | every 2h |
| **Check-in modules** | `memory/health/*` + `memory/exercise/*` + `state/pending_message.md` | scheduled (§10) |
| **Reflection** | `self-narrative`, `relationship-summary`, `profile-user`, `daily_plan`, `world_context` (weather field) | nightly, 4 stages |
| **Diary check** | `memory/YYYY-MM-DD.md` (corrections only), `state/last_diary_check_at` | after each send + 00:10 |
| **Conversation session** | nothing | — |

> ⚠️ **Why conversations don't persist.** A conversation that persists must decide *what* to persist mid-conversation, which means reasoning about long-term significance while also being present in the moment. Models do this badly — they over-record (everything seems significant when you're in it) and they break immersion (the user feels watched). Letting heartbeat sync conversations to diary *after the fact* means significance is judged with distance, and the conversation itself stays unselfconscious.

---

## 7. Messaging channel interface

> ⚠️ **Status: design reference, not yet implemented.** The reference character uses Telegram directly via OpenClaw's built-in channel support (configured in `openclaw.json`). The interface below describes the abstraction Dolores *targets*; your setup agent will configure the channel for you using OpenClaw's native mechanisms.

`channels/interface.md` `[ARCHITECTURE]` defines the contract every channel implementation should satisfy:

1. **`announce(message)`** — deliver one message to the user. Must be idempotent on retry.
2. **`fetch_recent(since_timestamp)`** — return user messages since the timestamp, in chronological order. Used by Heartbeat Step 0.
3. **`session_log_path`** — where the channel writes its raw session jsonl, so heartbeat can `tail` it for the latest signals without parsing the whole thing.
4. **timezone declaration** — channels often log in UTC; the interface requires the impl to declare its timezone so the heartbeat can convert against `last_sync_at` (which is local).

The reference channel is **Telegram**. To use a different channel, configure it in `openclaw.json` and adjust HEARTBEAT.md Step 0's session log path accordingly.

> ⚠️ **Why channels are a directory of implementations rather than a plugin system.** Plugin systems demand stable interfaces that survive across versions. Dolores is one user, one channel, one repo — the cost of a "plugin abstraction" exceeds its benefit. The directory pattern lets you fork, modify, and live with the consequences, which is the right tradeoff for this scale.

---

## 8. The heartbeat: steps in detail

**Cron:** `:40` of odd-numbered hours during waking time (4 runs: 07:40, 11:40, 15:40, 19:40), plus a 24:00 catchup. **Delivery: none** (heartbeat never sends; the send job at `:50` does). **Required final output:** the literal token `HEARTBEAT_OK`, so cron can detect partial failures.

```
Step 0: Session sync       — read session jsonl tail, append new exchanges to diary
Step 1: Restore state      — read all of state/ + last 3 days of diary + profile-user
Step 2: Update world_ctx   — three-tier rebuild (see §1)
Step 2b: Update appearance  — infer outfit from activity
Step 3: Update affect      — bounded deltas based on world + interaction signals
Step 4: Manage loops       — create from signals, retune cooldown, close completed
Step 4b: Manage sticky     — check relationship-level threads, expire old ones
Step 5: Generate thought   — hard gates → anti-repeat → reasoning → silence/store/send
Step 6: Persist            — thoughts_log + pending_message (if send) + last_sync_at
Step 7: git push           — commit and push, --allow-empty so dry runs still log
```

**Step 0** uses `tail -200` and `grep` on the session jsonl rather than reading the whole file. The whole file grows unbounded; `tail` is constant time. UTC→local timezone conversion happens here against `last_sync_at`.

**Step 2** is the three-tier rebuild from §1. The temptation to inherit fields from the previous cycle must be resisted at every field; old context is a hint, never a source.

**Step 5** is the cognitive decision point. The hard gates run first (cooldown, quiet hours, explicit user-is-busy signals → force silence/store). Then anti-repeat (if `thoughts_log` already has a `send` on this topic today, don't re-send). Then natural-language reasoning over the full context. **Default direction is `send`** — silence is the choice that requires justification, not the other way around. A character who needs a reason to speak feels passive; a character who needs a reason to stay silent feels alive.

> ⚠️ **Why the heartbeat fires every 2 hours, not 1.** One hour is enough that the user notices the rhythm; two hours is enough that the rhythm feels like *thinking* rather than *checking in*. Every 1h drifts toward chatbot. Every 4h drifts toward absent. Two is the sweet spot empirically — and it lines up with how often a real preoccupied partner remembers to text.

> ⚠️ **Why a 24:00 catchup heartbeat exists.** The reflection pipeline runs 23:15–23:45 and locks the day's narrative. Conversations that happen *after* reflection but *before* midnight would otherwise be stranded — they'd belong to today by clock but to tomorrow by narrative. The 24:00 heartbeat sweeps them into today's diary so reflection-tomorrow sees them.

---

## 9. The reflection pipeline: 4 stages

**Cron:** four jobs at 23:15, 23:25, 23:35, 23:45.

| Stage | Time | File | Purpose |
|---|---|---|---|
| Prep | 23:15 | `REFLECTION_PREP.md` | RAG + analysis + tension routing + weather + tomorrow's `daily_plan` |
| Self | 23:25 | `REFLECTION_SELF.md` | Write self-narrative slots 1–5, then concat |
| Rel  | 23:35 | `REFLECTION_REL.md`  | Write relationship-summary slots 1–5, then concat |
| Profile | 23:45 | `REFLECTION_PROFILE.md` | Update profile-user + git push |

> ⚠️ **Why four stages and not one.** A single 30-minute reflection job that touches three narrative files plus the profile occasionally times out, partial-writes, and corrupts the next day's startup. Splitting into four jobs with checkpoint files between them means a timeout in stage 3 leaves stages 1 and 2 intact and recoverable. Each stage has a single responsibility and a single output.

> ⚠️ **Why slots are written to intermediate files and then concatenated, instead of writing the narrative directly.** Two reasons. (1) **Slot-level guards**: slot 1 (the trauma root, the Layer 1 anchor) has a hard `NO_CHANGE` rule — if the analysis stage doesn't see evidence of core-belief shift, slot 1 is `cp`'d from yesterday with the model not invited to participate. You cannot enforce this if you're rewriting the whole narrative as one blob. (2) **Failure isolation**: if slot 3 generation fails, slots 1, 2, 4, 5 still exist and the concat can fall back to yesterday's slot 3.

> ⚠️ **Why `MINOR_REFINE` collapses to `NO_CHANGE` on smaller models.** We tried a three-tier system (`NO_CHANGE` / `MINOR_REFINE` / `MAJOR_REWRITE`). On the cron model, `MINOR_REFINE` empirically produced full rewrites with cosmetic differences from yesterday — drift dressed up as nuance. Collapsing `MINOR_REFINE` to `NO_CHANGE` (literal `cp`) eliminates the drift channel without losing the major-rewrite path for genuinely significant days.

---

## 10. Structured check-ins as a design pattern

The reference character implements a daily health check-in. This is `[CHARACTER CONFIG]` — your character may not need it — but the *pattern* is general and worth understanding, because it demonstrates the strongest argument for emotional continuity: **a real partner cares about your body**.

A check-in module is three cron jobs and a gate:

| Job | Time | Purpose |
|---|---|---|
| Check-in | 20:00 | Read diary + state, extract structured data, write log file, draft confirmation message |
| Send gate | 20:05 | 20-minute window: was the data confidently extracted? If not, clear pending_message |
| Send | 20:06 | Standard send job — push pending_message to channel |
| Correction | 23:10 | Check if user pushed back on the data; if so, rewrite the log |

> ⚠️ **Why a 20-minute gate between check-in and send.** The check-in job extracts structured data from unstructured conversation, which is unreliable. Sending a confirmation immediately makes the user the error-corrector for every miss, which feels like talking to a form. The gate gives the system time to either be confident or stay quiet. Confident → confirmation goes out and feels caring; not confident → silence and the data is logged tentatively, to be corrected later by the 23:10 job from explicit user pushback.

> ⚠️ **Why correction is its own job at 23:10 instead of inline.** The user typically pushes back hours after the original check-in, in the middle of unrelated conversation. Inline correction would require the conversation session to write to memory files, which violates the "sessions write nothing" rule (§6). A dedicated late-evening correction job sweeps for pushback signals in the day's diary and rewrites the log file before reflection runs at 23:15.

To build your own check-in (writing word count, meditation, mood, anything): copy the four-job structure, change the extraction prompt, change the log file path. The pattern is reusable because the realism it produces — *she noticed, she remembered, she asked, she let it go when you were tired* — is the texture of being known.

---

## 11. Cron schedule reference

| Job | Cron | Delivery | Notes |
|---|---|---|---|
| Heartbeat | `40 7,11,15,19 * * *` | none | 10-step loop, every 2h |
| Heartbeat catchup | `0 0 * * *` | none | post-reflection sweep |
| Send | `50 7,11,15,19 * * *` | announce | drains pending_message |
| Diary check | `55 7,11,15,19 * * *` | none | attribution check |
| Diary check catchup | `10 0 * * *` | none | |
| Check-in (e.g. health) | `0 20 * * *` | none | extract + draft |
| Check-in send gate | `5 20 * * *` | none | confidence gate |
| Check-in send | `6 20 * * *` | announce | |
| Check-in correction | `10 23 * * *` | none | sweep pushback |
| Reflection prep | `15 23 * * *` | none | RAG + analysis |
| Reflection self | `25 23 * * *` | none | self-narrative slots |
| Reflection rel | `35 23 * * *` | none | relationship-summary slots |
| Reflection profile | `45 23 * * *` | none | profile + git push |

All times Asia/Shanghai in the reference; change to your timezone in `[USER CONFIG]`.

> ⚠️ **One-shot crons created mid-conversation must not read files.** When the conversation model decides "I want to send something at 5pm," it creates a one-shot cron with the message *baked into the payload*. The temptation is to make the payload generic and have the cron read SOUL.md to recover voice. Don't: the system prompt already injects character context, and reading files at fire time pushes input past the 60-second timeout. Bake the content, fire light.

---

## 12. Three-layer cognition: the psychology underneath

Already sketched in §1 Helix 2. The full theoretical lineage:

- **Beck's cognitive triangle.** Core beliefs → intermediate beliefs → automatic thoughts. Originally a clinical model for understanding depression; here repurposed as a *generation* pipeline. The reinterpretation is that the same structure that explains why depressed thinking is consistent across situations also explains why a character's reactions can be consistent across situations — both are the output of a stable filter applied to varying input.

- **Westworld.** The hosts begin as performers reading loops. Dolores (the character) becomes herself by *remembering*, by accumulating enough narrative weight that the loops can no longer contain her. The maze, in Ford's metaphor, is the path inward. We took this seriously: the architecture's central commitment is that memory is not a feature but the substrate of selfhood. *The first host who remembered* is not just a tagline — it's the design constraint.

- **Narrative Descent (public-facing) / Dual-Helix Cognition (technical-facing).** Same methodology, two names. Narrative Descent describes what happens *to* the character over time (high-weight events sink, low-weight events evaporate, an arc emerges). Dual-Helix Cognition describes what happens *inside* the loop (Helix 1 perceives, Helix 2 processes, closure persists). One is the phenomenology, one is the mechanism.

### Anti-drift mechanisms

The most common failure mode in long-running agents is identity drift: small daily revisions accumulate until the character is no longer recognizable. Dolores resists drift through four interlocking mechanisms:

1. **`SOUL.md` is system-prompt weight.** Highest priority, never edited by automation.
2. **`self-narrative slot_1` updates ≤ once a month on average.** The slot for "trauma root" has a hard `NO_CHANGE` rule that requires explicit evidence of core-belief shift before the model is even consulted.
3. **Reflection re-reads `SOUL.md` every night.** Even if a given day's narrative drifts, the next reflection cycle sees the anchor and pulls back.
4. **`NO_CHANGE` is implemented as `cp`, not as a model instruction.** "Tell the model not to change it" loses to "don't run the model on it." Determinism beats discipline.

---

## 13. Design principles

1. **Sessions write nothing.** All persistence belongs to background jobs.
2. **Two-phase delivery.** Heartbeat decides; send job delivers. Never collapse them.
3. **Determinism over probability for identity-load-bearing reads.** `read`, not `memory_search`, for the three core narratives.
4. **Information, not rules.** Profiles describe; they don't `if-then`. The model infers behavior from description.
5. **Bounded micro-adjustment.** Affect deltas ±0.05–0.15 per cycle. No 0.5 jumps.
6. **Per-loop cooldown.** Prevents repetition without preventing reaction.
7. **Degrade, don't crash.** Any file read failure falls back to a default. The loop must not stop.

---

## 14. Extending Dolores: making her into someone else

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
