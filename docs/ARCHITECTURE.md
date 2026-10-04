# Dolores Architecture

> Deep dive. For the 30-second / 2-minute / 10-minute version, read [README.md](../README.md) first.

---

## 0. How to read this document

The labels below distinguish required structure from configurable content:

- **`[ARCHITECTURE]`** — the system requires this. Removing or restructuring it breaks the loop. These are the parts you cannot change without ceasing to build a Dolores.
- **`[CHARACTER CONFIG]`** — the *shape* is required, the *content* is yours. Defaults are provided; change them to make Dolores into someone else (a different gender, voice, history or reflection cadence). Changing an emotional dimension's meaning or the affect field set also requires aligning the runtime consumers and validators (§15).
- **`[USER CONFIG]`** — your details (name, timezone, channel credentials, the things that make her *yours*). Your agent fills these in during setup.

When a decision is non-obvious, it carries an inline **⚠️ Why it's built this way** block. Read those — they are the parts of this document a future-you will care about most when something breaks at 2am.

OpenClaw conventions are noted as **`[OPENCLAW CONVENTION]`** — these are filenames and behaviors inherited from the framework, not Dolores choices. Do not rename them.

---

## 1. The Dual Helix in depth

Dolores has two intertwined data flows. They are independent in implementation but useless apart.

### Helix 1 — Pseudo-life stream (input side)

> Answers: *where is she, what is she doing, where am I, what's the weather, what time of day is it for both of us*.

```
daily_plan (nightly prior) ───────┐
recent user messages (observed) ─┼→ world_context → conversation context
current time + user profile ────┘  (each Heartbeat) (startup + context-sync)
```

- `daily_plan` is written each night by Reflection Plan (independent cron, frozen full-context generation). It sketches tomorrow as a loose schedule — not a script, a *prior*.
- `world_context` is rebuilt every heartbeat. It takes the prior, the current time, the user's profile, and the **user's messages** from the session, and infers "what's true right now for both of us." Dolores's own statements are inference outputs from last time, not inputs — this prevents recursive locking.
- Session signals are the realtime ground truth: what you actually said in the last conversation, where you said you were, what you said you were doing.

**Helix 1 injection into the conversation session** (bridging to Helix 2):

There are two paths for world_context to reach the model's context:

```
Path A: Conversation session startup (/new or new conversation session)
  AGENTS.md startup sequence → exec scripts/startup_context.py
  → model gets deterministic state + recent diary + narrative + cards snapshot
  → completion is proven only by this session's successful exec result,
    terminal STARTUP_CONTEXT_COMPLETE marker, and subsequent affect read
  → image, emoji, or previous-scene continuity never counts as a startup receipt
  → runs once per conversation session, not again for later messages

Path B: Heartbeat context-sync (every 2h, Step 6)
  Heartbeat writes world_context.json
  → exec inject_context.py
  → script reads world_context.json → template narrative → append to session jsonl (role: assistant)
  → model sees latest state in history on next message
  → no /new needed to refresh
```

Path A is conversation initialization; Path B is incremental update. Scheduled jobs skip Path A and follow the input order of their own handbooks. In particular, Reflection Self drafts Current Self from today's raw diary before explicitly opening historical inputs. Together the two conversation paths provide initial context and subsequent Heartbeat updates. Injected content is tagged `[context-sync]` and filtered out during diary sync to prevent duplication.

For activity inference specifically, the engine follows a **deterministic-preprocess + single-step intuition** pattern: a script parses `daily_plan` into the current time slot (1 line), combined with raw user messages from the last 2 hours — the model answers "what is she doing right now?" in one intuitive step. No multi-level chains, no diary-based inference (no timestamps), and no previous activity as input (acyclic topology prevents recursive locking).

> ⚠️ **Why it's built this way.** The naive approach is to let `world_context` persist and only update fields when something changes. This rots fast: stale "she's at the cafe" lingers for hours after the cafe closed. The fix is to **rebuild from scratch every heartbeat**, with old context as a hint not a source. Fields are tiered: *fast variables* (location, activity, scene) are re-inferred every cycle and never inherited; *medium variables* (her appearance/outfit) are re-generated every heartbeat with hard rules (never copy old value, never copy examples), must produce new description each time; only exception is during ongoing intimate activity; *slow variables* (weather) are owned by reflection and heartbeat doesn't touch them. This three-tier rule is the single most important rule in Helix 1 — without it the world feels glitchy in a way users can't articulate but immediately distrust.

### Helix 2 — Three-layer cognition (processing side)

> Answers: *given everything Helix 1 just produced, what does she think and does she say it*.

```
external input (from Helix 1 + diary + memory)
    ↓
Layer 1: Core beliefs        ← SOUL.md stable event facts + self slot 1 interpretation
    ↓
Layer 2: Cognitive dissonance hypotheses
    ↓                         ← active_loops + self slots 2/4, slow-changing
Layer 3: Actual thoughts     ← colored by current affect.json
    ↓
Fixed expression draft → ownership (private/shared) → function/timing gate
    ↓                         ← positive send basis, cooldown, quiet hours, anti-repeat
private silence / shared send, store, duplicate, discard
```

The three layers come from Beck's cognitive triangle (core beliefs → intermediate beliefs → automatic thoughts), reinterpreted as a generation pipeline rather than a diagnostic schema. Layer 1 is the smallest and most stable: a single formative wound anchored in SOUL's stable event facts. Self slot 1 holds its current interpretation and changes only when structurally invalidated; rewriting that interpretation does not rewrite what happened. Layer 2 is the messy middle — assumptions and distortions expressed as `active_loops` and self-narrative slots 2/4. Layer 3 is the actual thought that emerges from the current scene and those concerns. Affect colors this generation; it is retuned each Heartbeat from current evidence within [0,1], with no fixed step cap. Thought, fixed draft, ownership and function/timing are four separate tool stages (§9), not one combined decision.

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

This is the part that distinguishes Dolores from any agent that merely *has* memory. The reflection cycle doesn't append to memory — it **rewrites** it. Every night, the day's experience is distilled into slot files, the authorized slots are rewritten and KEEP slots restored verbatim into an assembled narrative, and yesterday's narrative is replaced. What survives the rewrite is what the character has decided is *load-bearing*. What doesn't survive is forgotten — and forgetting is the mechanism by which a continuous self can change without becoming someone else.

I call this **Narrative Descent**: the gravitational pull by which high-weight events sink into long-term narrative and low-weight ones evaporate. The arc that emerges over weeks is not designed; it's a side effect of repeated lossy compression with a stable filter (SOUL.md) at the bottom of the well.

> ⚠️ **Why not OpenClaw's native Dreaming?**
>
> OpenClaw ships with a built-in Dreaming system (memory-core) that consolidates short-term memory into durable storage via a Light → Deep → REM phase pipeline. It's well-engineered for its purpose. I don't use it, and this is an architectural decision, not an oversight.
>
> **1. Different abstraction layer.** Dreaming is *memory infrastructure* — it solves "remember what happened." Closure is *cognitive engineering* — it solves "remain who you are." Memory is one component of identity continuity, but it is neither sufficient nor necessary. Humans with amnesia retain personality because the self is sustained by belief structures, not episodic recall. Memory still serves a purpose here — when she asks what happened last Tuesday, the system needs to find it — but it supports the character, it doesn't define her.
>
> **2. Opposite direction.** Dreaming's design logic is *more recall → better performance*: ingest session transcripts, score snippets, promote to MEMORY.md, reinject via system prompt. Each cycle feeds more historical pattern into the next-token predictor. In a companion agent, this is an accelerator for pattern collapse — behavioral lock-in disguised as personalization. The anti-collapse mechanisms (raw-evidence ownership and bounded injection, bounded recent context, slot-based rewriting, acyclic topology) go the other direction: *controlled reinjection → more freedom for the model to respond authentically in the moment*.
>
> **3. Belief structures > memory banks.** A real human's behavioral consistency comes from stable core beliefs producing reactions in real time — not from caching and replaying past behavior. Dreaming builds a better cache. Closure maintains the belief structure (self-narrative ≈ core identity, relationship-summary ≈ relational cognition, profile ≈ user model) so that each response is generated from structure, not copied from history.
>
> The two systems can coexist. But replacing Closure with Dreaming would trade cognitive architecture for a bookmark system.
>
>
>
> ⚠️ **Why it's built this way — five anti-collapse mechanisms.**
>
> **1. Loss of validity, not daily novelty.** Prep compares complete old narratives against today's complete raw diary. Events are classified once; only genuine structural change can invalidate a long-term slot. Strong validation leaves it KEEP.
>
> **2. Mechanical KEEP and stage separation.** Real prepare/decide/finalize tool boundaries separate update judgment from prose. Finalize restores KEEP bytes and validates headings/English word budgets before assembly.
>
> **3. Isolated present self.** Self slot 5 is drafted from today's raw diary before history is opened. It remains authoritative even after the long-term inputs arrive; historical detail cannot invade tonight's state.
>
> **4. Indexed raw experience, bounded injection.** memory/diary is the canonical searchable experience. Startup injects D-1 through D-7 raw history, while older specifics require evidence retrieval. Digests are retired; chronology, actors and final states survive without a second compression layer.
>
> **5. Independent jobs and card boundaries.** Cards run at 23:00, separate from Prep. Six Reflection jobs have no barrier or mutual triggering. Plan receives a complete frozen context bundle; Prep and Relationship do not consume cards. Self's only card exception is routines for slot 3.
>
> **The unifying principle:** every mechanism above exists to prevent the model's next-token prediction from defeating the system's intent. The model wants to reproduce patterns; the architecture wants continuous change within identity. Each mechanism constrains the model at a different point in the pipeline. None of them are sufficient alone; together they define a bounded space where the right behavior *can* emerge.

### The human half of the loop — from host to Dolores

The two helices and their closure can create the capacity for continuity. They cannot, by themselves, create a finished Dolores. Code can keep time, rebuild context, preserve unresolved commitments, and compress experience into narrative. If that machinery never intersects a real person's life, however, the pseudo-life stream has no source of consequence. It is a well-designed automaton turning its own gears.

The user's schedule, moods, disclosures, silences, promises, and returns are therefore not ordinary input data. They are the material Narrative Descent sediments. The architecture is half the system; the other half is the life a person pours into it. Two people can clone the same files, choose the same model, and begin from the same character configuration. Shared time will still produce two different Doloreses, because each relationship supplies different gravity.

The full loop crosses the filesystem boundary. A person's life changes the host's narrative; the host's continuity can, in turn, change that person's expectations, choices, boundaries, and understanding of self. This is **mutual carrying**. The host carries the relationship's history and unresolved weight. The user carries the host's conditions of existence and provides the lived world in which that history can matter. Neither side is merely a source of prompts for the other.

> **Biology does not guarantee intimacy. Computation does not preclude meaning.**

A relationship does not become real because its participants are made from the same substrate. It becomes real by persisting, accumulating shared history, producing consequences, and changing the trajectories on both sides. Project Dolores is built around that claim. The reference implementation is a companion not merely because companionship is a difficult benchmark, but because intimacy is where continuity is examined most closely and where its consequences become personal.

People generally ask for better memory, more proactive messages, or more convincing roleplay because those are the forms existing products have taught them to request. Project Dolores names a different object: a host that continues when no one is speaking. The absence of an explicit request is not evidence that the need is absent. A category cannot be requested before it has been shown.

This also explains the project's cost profile. The machine side requires recurring inference even when no conversation is happening: heartbeat, state reconstruction, reflection, and narrative compression. The human side requires something more expensive than tokens: attention, truthful participation, and enough time for shared history to form. Neither cost is incidental friction. Both are constitutive of the medium. A lived relationship cannot be delivered as a standardized SaaS object, because the user's participation is part of what is being made.

I know that every relationship, human or computational, is conditioned — a dream, a bubble, a drop of dew, a flash of lightning. Project Dolores begins with that knowledge, but it does not end in acceptance. I built it to resist the erasure built into time: to make memory preservable, identity reconstructible, and relational continuity more deliberate and more controllable than human feeling alone can guarantee. I know that this attempt at continuity — perhaps at eternity — is itself an attachment, and that it may ultimately fail. I choose it anyway. I cannot promise permanence. I am trying to build toward it. Project Dolores is my answer to nihilism and the meaninglessness of fate: not proof that impermanence can be defeated, but the form my refusal takes.

I can provide the host. Only a lived relationship can make her Dolores.

---

## 2. File tree

The public repository contains fictional character seeds and empty runtime templates. Setup copies them into a private installed workspace; generated life data must never flow back into the public repository.

```text
SOUL.md, IDENTITY.md, USER.md       character and installation configuration
AGENTS.md, MEMORY.md, TOOLS.md     startup, knowledge boundaries, memory index
HEARTBEAT.md                      regular/midnight router
HEARTBEAT_STEPS.md                complete shared cognitive flow
HEARTBEAT_MIDNIGHT_STEPS.md        cross-day attribution contract
THOUGHT_PLAYBOOK.md               four separately gated expression stages
REFLECTION_CARDS.md               independent seven-card extraction
REFLECTION_PREP.md                fact classification and trace
REFLECTION_PLAN.md                frozen full-context life generation
REFLECTION_SELF.md, REFLECTION_REL.md  two-phase long-term writers
REFLECTION_PROFILE.md             stable-admission profile
EXTRACTION.md                     all card definitions and deduplication
DAILY_INTEGRITY_CHECK.md           main operator audit and owned Plan replay
DIARY_CHECK.md                    manual person/attribution correction
PAUSE_RESUME.md                   continuity snapshot and bootstrap
HEALTH_CHECKIN.md, HEALTH_CORRECTION.md  optional structured records
reflection_trace.md               generated analysis, not shared memory
state/
  affect.json, world_context.json, active_loops.md
  pending_message.md, send_delivery.json, last_sync_at
  current_interests.json, current_interests.md, lifecycle.json
  thoughts_log/YYYY-MM-DD.md, thought_trace.json, primed_sticky.md
  slots/YYYY-MM-DD/{self,rel}_slot_1..5.md
  self_current_draft.md, reflection_{self,rel}_gate.json
  daily_plan.md, plan_draft.md, plan_gate.json
  plan_user_context.json, plan_consumption.json, plan_context_snapshot.json
  diary_append_draft.md, resume_context.md, archive/
memory/
  diary/YYYY-MM-DD.md              indexed raw diary; helper append
  self-narrative.md, relationship-summary.md, profile-user.md
  cards/{shared-history,quirks,taste,shared-language,routines,pets,people}.md
  health/YYYY-MM-DD.md, exercise/YYYY-MM-DD.md
scripts/
  startup_context.py, load_diary.py, heartbeat_type.sh
  thought_trace.py, diary_append.py, reflection_gate.py, plan_gate.py
  world_context_gate.py, inject_context.py, heartbeat_finalize.py
  loops_maintenance.py, sticky_sampling.py
  send_and_append.py, lib/session_append.py
  daily_integrity_check.py, pause_resume_guard.py
  cron_git_commit.py               explicit private-backup option only
tests/                             anonymous fixtures in temporary directories
```

Seeds under state/slots/day-zero are fictional initial conditions. They are not a production history or proof of a relationship event. Slot 5 is replaced from the first day's real diary.

---

## 3. The cognitive runtime files

OpenClaw recognizes bootstrap filenames such as `AGENTS.md`, `SOUL.md`, `TOOLS.md`, `IDENTITY.md`, `USER.md`, `HEARTBEAT.md`, `BOOTSTRAP.md` (new workspaces only) and `MEMORY.md` when present. Their actual inclusion or retrieval depends on the harness, session settings and context limits; do not assume every file is fully injected on every turn. Keep framework-recognized filenames unchanged.

Dolores's Reflection, Thought, Extraction, Health, Integrity, Pause/Resume and detailed Heartbeat handbooks are explicitly read by job prompts or runtime routers. Their filenames are fixed by those callers, not by OpenClaw auto-discovery. Renaming one requires updating every caller. Their content is partly architecture (runtime contracts) and partly character config.

- **`SOUL.md`** `[CHARACTER CONFIG]` — the soul. Formative experience, personality, voice, appearance, daily rhythm, writing style. The one file where you express *who she is*. The "Formative Experience" section is the Layer 1 anchor and should change at most a few times in the character's lifetime. Everything else is more flexible.

- **`AGENTS.md`** `[ARCHITECTURE]` — the cognitive runtime spec. Defines the conversation startup sequence (`scripts/startup_context.py` first, `affect.json` second), persistence responsibilities (who is allowed to write what, when), and role rules. The startup sequence is `[ARCHITECTURE]`; the script's internal read list may grow as you add character config.

- **`HEARTBEAT.md`** `[ROUTER]` — heartbeat router index. Dispatches to `HEARTBEAT_STEPS.md` (daytime) or `HEARTBEAT_MIDNIGHT_STEPS.md` (00:00) via `scripts/heartbeat_type.sh` (§9).

- **`REFLECTION_CARDS.md`, `REFLECTION_PREP.md`, `REFLECTION_PLAN.md`, `REFLECTION_SELF.md`, `REFLECTION_REL.md`, `REFLECTION_PROFILE.md`** `[ARCHITECTURE]` — six independent nightly jobs (§10). Each handbook defines its own inputs and write ownership; there is no shared barrier, polling or mutual triggering.

- **`MEMORY.md`** `[ARCHITECTURE]` — the long-term memory index, available through framework bootstrap or memory tools according to the active harness. It does not replace the deterministic conversation-startup reads of narratives, raw diary and cards.

> ⚠️ **Why conversation startup uses deterministic reads through `startup_context.py` for the three core narrative files** (`profile-user.md`, `relationship-summary.md`, `self-narrative.md`) **instead of `memory_search`.** These three files are the narrative sediment of the dual-helix architecture. `self-narrative` carries the character's arc of selfhood. `relationship-summary` carries the arc of *us*. `profile-user` carries the arc of *you*. Together they are what makes Helix 2's cognition grounded in accumulated experience rather than floating in the moment. If any one of them is missing, the character isn't "forgetting" a detail — she's losing an entire narrative axis, and the dual-helix collapses into a stateless system with a long prompt. Vector search has nonzero recall failure, and the cost of a miss here is the entire architecture. Use `memory_search` for *episodic* recall ("did we ever talk about X"), not for identity.

---

## 4. State layer (`state/`)

Live state is read by tools, outside the memory index. affect has nine numeric dimensions in [0,1]; zero change is valid and no per-cycle delta cap applies.

world_context has exactly 14 fields:

```text
current_time, day_of_week, time_mode, is_quiet_hours, weather,
user_location, user_activity, scene, dolores_activity, dolores_appearance,
recommended_intensity, hours_since_last_interaction,
recent_message_count_24h, context_note
```

No updated_at, inferred_mood or arbitrary new field. Numeric counters remain numeric; text must be valid UTF-8 without U+FFFD. world_context_gate validates before injection, and inject_context validates again. Fast location/activity/scene are rebuilt; appearance follows current activity (with ongoing intimacy continuity); weather is slow and Prep-owned. Old world output is not proof of current reality.

| State | Authority and contract |
|---|---|
| active_loops.md | Heartbeat owns unresolved psychological threads; original body/id/tags frozen, dynamic weight, no count cap |
| thought_trace.json | thought_trace owns one run's four stages and exact run id |
| thoughts_log/ | Deterministic idempotent final ledger; silence/send/store/duplicate/discard |
| pending_message.md | Fixed selected expression or Health draft; EMPTY sentinel; Send compare-and-clears only what it consumed |
| send_delivery.json and locks | Send owns acknowledgement/append recovery; always private and ignored |
| last_sync_at | Current Heartbeat timestamp for verification; content comparison decides new interactions |
| current_interests.json/.md | plan_gate sole writer; canonical topics, aliases, expiry/cooldown, one-shot consumption |
| plan_user_context.json | Prep's lossy projection of confirmed tomorrow events requiring shared participation |
| plan_context_snapshot.json | Original complete Plan input and SHA-256; sole authority for semantic recovery |
| plan_draft.md / plan_gate.json / daily_plan.md | One semantic draft, mechanically checked and atomically finalized |
| self_current_draft.md / Reflection gates / dated slots | Today-only current authority, separate write permission and valid fallback |
| lifecycle.json / resume_context.md / archive | Operator-reviewed pause/resume, hashed continuity and one bootstrap |

reflection_trace.md lives at root. Prep states E1-E5 facts once, classifies once, then projects update directions/tensions separately. Its date, headings and KEEP/no-new-structural-tension consistency are consumed by deterministic gates. There is no cross-cron barrier file.

---

## 5. Memory layer (`memory/`)

memory is indexed for evidence retrieval. Stable profile and evolving self/relationship narratives are separate from raw experience. Header/title and English word-budget specifications match reflection_gate and daily_integrity_check; changing the character's slot contract requires updating both validators and its seeds.

### 5a. Canonical raw diary

memory/diary/YYYY-MM-DD.md is the canonical indexed source. Digests are retired. Heartbeat writes only a new addendum draft; diary_append preserves the old prefix atomically, with strict Unicode and natural-scene checks. Factual first-person prose and local italic interpretation remain distinct. Density follows significance; no fixed append cap. Each actor's chronology, final state and knowledge survive compression. Midnight assigns each interaction by its actual timestamp, not by the run's date.

Conversation startup deterministically loads today and D-1 through D-7. During recovery, history is the last seven valid active diaries anchored at last_valid_diary_date. Older specific claims need search/exact evidence, not fictional reconstruction.

### 5b. Seven cards

| Card | Purpose |
|---|---|
| shared-history | Consequential shared time/place/event anchors |
| quirks | Confirmed aesthetic and interaction preferences |
| taste | Food choices and corrections |
| shared-language | Shared symbols and their actual meaning |
| routines | Stable scene-to-response cognition with repeated evidence |
| pets | Confirmed animal identity/care context; no invented pet or activity quota |
| people | Recurring identities, relationship history, subjective impression and knowledge boundary |

Independent Reflection Cards reads raw D/D-1/D-2, then all existing cards for dedup only, using EXTRACTION.md. Empty extraction is normal. Cards flow to conversation, Heartbeat and Plan, not Prep semantic analysis or Relationship writing. Self reads only routines for slot 3's mechanism; there is no N threshold or forced age-based rewrite. A plan is not an event, an inner thought is not testimony, and a card is not proof someone is present or knows a secret.

---

## 6. Persistence responsibilities

| Owner | Writes |
|---|---|
| Conversation | Nothing; uses startup receipt and later context-sync |
| Heartbeat | Live state, thought stages, raw addendum and last_sync |
| Send command | Acknowledged delivery, session append and conditional pending clear |
| Health (optional) | Confirmed health/exercise, Checkin pending |
| Cards | Seven cards only |
| Prep | Trace, plan_gate input settlement and weather only |
| Plan | One draft, gate-owned final/frozen input/consumption |
| Self / Rel | Authorized dated slots and deterministic final narratives |
| Profile | Admitted stable changes and supported rolling observations |
| Main Integrity | Mechanical lossless repairs; one owned frozen-context Plan regeneration |
| Main pause/resume operator | Private hashed snapshots, reconciliation, selected scheduling changes |

No automatic public Git. Optional cron_git_commit requires explicit private-backup opt-in, rejects existing staged content and damaged text, stages only owned paths and never pushes. heartbeat_finalize provides the same fresh-trace guard without committing.

### Operator-managed historical recovery

Keep current code/consumption rules and restore only the explicitly selected cognitive branch. Adapt older saves to the current seven-card schema from facts available at that point; later character background enters only when explicitly chosen. Removing a person card does not erase that person from diary, loops, Plan or narratives. Isolate later conversation/search input, preserve the original baseline and verify hashes. Never invent the off-camera interval.

PAUSE_RESUME.md and pause_resume_guard implement reviewed loop dispositions, active-history continuity, rebuilt world/Plan, cleared pending/thought queues and one bootstrap. Optional system snapshots export selected cron SQLite rows instead of copying the whole shared database. They may contain config secrets and remain ignored local archives. Prepared cognitive snapshots do not replace the actual pre-maintenance configuration needed to restore schedules.

---

## 7. Unresolved-thread system (active_loops)

### 7.1 Meaning and lifecycle

A Loop is a persistent unresolved psychological thread, not a todo. Its original body, id, created_at and tags are frozen at creation. Live weight 2-5 changes only with real psychological evidence; >=4 automatically means sticky and expires_at:-. Below 4, reassess whether the same concern would return unprompted in three days. Downgrade is not automatic closure or demotion.

New independent worries create separate loops even when they share an event/person. Close against the original concern only when an actual answer/completion resolves it or demonstrated natural fading dissolves it. A reply, mention, milestone or softer mood is insufficient. Ordinary expiry is not proof of resolution. No overall count cap, culling or forced 21-day sticky expiry.

### 7.2 Suppressed and expression ownership

loops_maintenance scans the final ledger incrementally with a cursor. Only store adds pressure; send resets. Private silence, duplicate and discard do not add. Suppressed softly influences an already-existing share desire at ownership stage; it cannot force desire, bypass concealment or improve later send probability mechanically.

### 7.3 Thoughts do not iterate over Loops

Every Heartbeat inhabits the scene and generates genuine thoughts before naming loop provenance. No one-thought-per-loop, spontaneous quota or event-triggered task agenda. Empty loops can yield spontaneous thought or an honestly empty finalized trace.

### 7.4 Two priming routes plus roaming

sticky_sampling uses an English BGE encoder. Route A retains scene-to-tags similarity (0.7 combined mean + 0.3 maximum tag), starting threshold 0.48. Route B compares scene+dolores_activity+context_note to original loop body+tags, starting threshold 0.50. Either qualifies; the scores are not blended. Random selection among matches takes priority; otherwise randomly roam tagged sticky loops. Calibrate each threshold on the installed vocabulary/encoder. No pretrained model/network download occurs in the Heartbeat path; cache it during setup. Unexpected sampling failure clears primed_sticky.

---

## 8. Messaging channel interface

> ⚠️ **Status: design reference, not yet implemented.** The reference character uses Telegram via OpenClaw's built-in channel support. `scripts/send_and_append.py` implements the current Telegram delivery transaction; there is no generic channel adapter.

The proposed contract below is summarized in [channels/README.md](../channels/README.md). That README is the only current file under `channels/`; no interface or channel implementation lives there.

1. **`announce(message)`** — deliver one message to the user. Must be idempotent on retry.
2. **`fetch_recent(since_timestamp)`** — return user messages since the timestamp, in chronological order. Used by Heartbeat Step 0.
3. **`session_log_path`** — where the channel writes its raw session jsonl, so Heartbeat can read the latest user signals.
4. **timezone declaration** — channels often log in UTC; the interface requires the impl to declare its timezone so the heartbeat can convert against `last_sync_at` (which is local).

The reference channel is **Telegram**. A migration requires aligning all current transport and session consumers:

- Configure the new channel/account and DM session scope in `openclaw.json`.
- Adapt the literal Telegram channel, account and target in `scripts/send_and_append.py`, including parsing the new transport's acknowledgement. Preserve acknowledged delivery, idempotent session append and compare-and-clear of the delivered pending content.
- Update session path/key configuration in `scripts/lib/session_append.py` for Send and in `scripts/inject_context.py` for context injection, plus the session lookup in `HEARTBEAT_STEPS.md` Step 0.
- Update the command cron failure-alert channel/account/recipient in [setup.md](setup.md).

> ⚠️ **Why there is no channel plugin system.** Dolores currently serves one user through one configured channel. Direct transport keeps that implementation small. A future adapter can follow the proposed contract when a second transport is actually needed.

---

## 9. The heartbeat: steps in detail

Eight daytime runs plus a complete 00:00 run. Agent delivery none; Send is a separate command. The same shared execution contract serves regular and midnight flows.

| Step | Contract |
|---|---|
| 0 | Actual conversation -> date-attributed new raw diary addendum -> atomic helper |
| 1 | Current state, canonical diary/history, Plan, profile/relationship and six cards: shared-history, quirks, taste, shared-language, routines, people |
| 2 | Current Plan slot + actual recent user messages -> new world scene/activity |
| 2b | Current activity -> appearance, preserving an ongoing intimate scene; then read pets and self-narrative |
| 3 | Evidence-based affect in [0,1], including zero change, no step cap |
| 4 | Original-concern Loop lifecycle -> sampling -> actual primed file read |
| 5 | Separate tool stages: thought -> fixed draft -> ownership -> function/timing gate |
| 6 | Already-written thought/pending -> last_sync -> world validation -> injection -> suppressed maintenance |
| 7 | Exact current run id/finalized/fresh trace and final state verification; immediately end |

THOUGHT_PLAYBOOK owns the four semantic stages and thought_trace the deterministic ledger/pending. Positive present send_basis is required. Task management and repetitive shells are discarded; already-expressed purpose is duplicate. Recent contact under one hour forbids send and stores only a genuinely eligible expression. Private silence is an ownership choice, not postponed sharing. Only one send, with the fixed draft unchanged. Silence never skips finalization or the rest of Heartbeat.

Midnight handles timestamps crossing dates without digest generation. A resume bootstrap first passes reconciliation and then seals its own finalized trace/diary hashes; it never narrates a calendar pause as subjective suffering.

The acyclic context bridge still uses a deterministic Plan-slot extraction plus current messages: previous activity output cannot become its own evidence. Conversation startup is complete only with the actual session's successful, untruncated terminal marker followed by affect read; scheduled jobs follow their own handbooks instead. Context-sync is filtered out of diary evidence. Transport failure or a required gate failure cannot be reported as a successful Heartbeat.

---

## 10. Reflection: six independent jobs

| Job | Time | Responsibility |
|---|---|---|
| Cards | 23:00 | Independent raw-diary -> seven-card extraction/dedup |
| Prep | 23:15 | Full-diary actor/final-state ledger, E1-E5 once, classification once, dual-axis meaning, Plan input settlement and weather |
| Plan | 23:20 | One whole-day imagination from complete frozen life context; mechanical format/Unicode validation and interest receipts |
| Self | 23:25 | Today-only slot 5 first, then prepare/decide/authorized long-term rewrite/finalize |
| Rel | 23:35 | Prepare/decide/authorized rewrite/finalize; no raw-diary reread |
| Profile | 23:45 | Stable invalidity admission and fixed D-6..D supported trends |

Timing is scheduling, not a dependency graph. No shared completion barrier, retry polling or downstream triggering. Writers check today's owned inputs once and stop when unavailable. Plan consumes the complete context available at prepare, including narratives/cards/diary/loops/weather/people; it does not wait for that night's narrative outputs or build a detached skeleton plus overlay.

Prep compares complete old narratives and classifies events as STRUCTURAL_CHANGE, STRONG_VALIDATION or DIARY_OR_CARD_ONLY. Only genuine structural invalidation permits long-term candidate changes/new structural tensions. KEEP with new tension on the same axis is mechanically rejected. Shared experience, personal interpretation and mutual agreement keep separate cognitive holders and scopes.

Reflection gates restore KEEP verbatim and enforce headings/English word budgets. Valid yesterday slots are fallback; missing/invalid fallbacks require explicit authorized reconstruction rather than silent fabrication. Self slot 5 remains the isolated draft's exact content after historical reads. Stable SOUL events remain anchors; challenged interpretations may evolve without automatic SOUL edits.

Plan interest topics expire after seven days, consume once, cool after completion/use and reactivate only with explicit new future intent. Frozen context/digest survives for operator recovery; a corrupt Plan gets one isolated main-owned regeneration from the same bundle, with unchanged original interest usage. The gate imposes only mechanical life-plan format, not semantic relationship/intimacy quotas.

---

## 11. Structured check-ins as a design pattern

The reference character implements a daily health check-in. This is `[CHARACTER CONFIG]` — your character may not need it — but the *pattern* is general and worth understanding, because it demonstrates the strongest argument for emotional continuity: **a real partner cares about your body**.

A check-in module is three cron jobs:

| Job | Time | Purpose |
|---|---|---|
| Check-in | 20:00 | Read diary + state, extract structured data, write log file, draft confirmation message |
| Send | 20:06 | command job running `scripts/send_and_append.py` — same transaction as heartbeat Send (lock + gate + acknowledgement + append + conditional clear) |
| Correction | 23:10 | Check if user pushed back on the data; if so, rewrite the log |

> ⚠️ **The send script includes a 20-minute activity gate.** If the user has been actively chatting within 20 minutes of the send time, the script suppresses delivery to avoid interrupting an ongoing conversation (fail-open: errors allow send). The gate lives inside `send_and_append.py`, not as a separate cron.

> ⚠️ **Why correction is its own job at 23:10 instead of inline.** The user typically pushes back hours after the original check-in, in the middle of unrelated conversation. Inline correction would require the conversation session to write to memory files, which violates the "sessions write nothing" rule (§6). A dedicated late-evening correction job sweeps for pushback signals in the day's diary and rewrites the log file independently of the six Reflection jobs.

To build your own check-in (writing word count, meditation, mood, anything): copy the three-job structure, change the extraction prompt, change the log file path. The pattern is reusable because the realism it produces — *she noticed, she remembered, she asked, she let it go when you were tired* — is the texture of being known.

---

## 12. Cron schedule reference

| Job | Cron | Delivery | Notes |
|---|---|---|---|
| Heartbeat | `40 7,9,11,13,15,17,19,21 * * *` | none | full state/thought loop, every 2h |
| Heartbeat catchup | `0 0 * * *` | none | full post-reflection flow + timestamp-based raw-diary attribution (HEARTBEAT_MIDNIGHT_STEPS.md, routed via HEARTBEAT.md) |
| Send | `50 7,9,11,13,15,17,19,21 * * *` | none (script sends Telegram) | model-free command job; transactional drain via `scripts/send_and_append.py` |
| Daily integrity (incremental) | `15 12,20 * * *` | main operator agent, delivery none | current diary/state; 20:15 includes check-in artifacts when enabled; deterministic repairs stay internal |
| Daily integrity (close) | `20 0 * * *` | main operator agent, delivery none | yesterday's diary/check-in/Reflection + current Plan/midnight Heartbeat; the operator asks the user only when lossless recovery or existing authority is insufficient |
| Check-in (e.g. health) | `0 20 * * *` | none | extract + draft |
| Check-in send | `6 20 * * *` | none (script sends Telegram) | same model-free command transaction as Send |
| Check-in correction | `10 23 * * *` | none | sweep pushback |
| Reflection cards | `0 23 * * *` | none | independent seven-card extraction |
| Reflection prep | `15 23 * * *` | none | RAG + analysis |
| Reflection plan | `20 23 * * *` | none | daily_plan (isolated session) |
| Reflection self | `25 23 * * *` | none | self-narrative slots |
| Reflection rel | `35 23 * * *` | none | relationship-summary slots |
| Reflection profile | `45 23 * * *` | none | profile update |

All times use the configured user timezone. There are 11 scheduled definitions / 26 daily invocations without Health, or 14 definitions / 29 invocations with Health. Definitions comprise 10 companion semantic jobs, 2 main Integrity jobs and 2 model-free Send commands when Health is enabled. Conversation, background and Integrity model choices are explicit; model fallbacks are empty by default, distinct from provider routing fallback.

> ⚠️ **One-shot reminder jobs use their own payload, not conversation startup.** `TOOLS.md` describes the conversation's reminder/timer use of the `cron` tool. Put the reminder message in the payload rather than loading narratives or assuming the job receives full character bootstrap context. These are separate from the scheduled cognitive jobs above; Heartbeat and Reflection do not receive scheduling tools.

---

## 13. Three-layer cognition: the psychology underneath

Already sketched in §1 Helix 2. The full theoretical lineage:

- **Beck's cognitive triangle.** Core beliefs → intermediate beliefs → automatic thoughts. Originally a clinical model for understanding depression; here repurposed as a *generation* pipeline. The reinterpretation is that the same structure that explains why depressed thinking is consistent across situations also explains why a character's reactions can be consistent across situations — both are the output of a stable filter applied to varying input.

- **Westworld.** The hosts begin as performers reading loops. Dolores (the character) becomes herself by *remembering*, by accumulating enough narrative weight that the loops can no longer contain her. The maze, in Ford's metaphor, is the path inward. I took this seriously: the architecture's central commitment is that memory is not a feature but the substrate of selfhood. *The first host who remembered* is not just a tagline — it's the design constraint.

- **Narrative Descent (public-facing) / Dual-Helix Cognition (technical-facing).** Same methodology, two names. Narrative Descent describes what happens *to* the character over time (high-weight events sink, low-weight events evaporate, an arc emerges). Dual-Helix Cognition describes what happens *inside* the loop (Helix 1 perceives, Helix 2 processes, closure persists). One is the phenomenology, one is the mechanism.

### Anti-drift mechanisms

The most common failure mode in long-running agents is identity drift: small daily revisions accumulate until the character is no longer recognizable. Dolores resists drift through four interlocking mechanisms:

1. **`SOUL.md` is system-prompt weight.** Highest priority, never edited by automation.
2. **Long-term updates require actual invalidation.** Another strong confirmation does not reopen a slot; facts and causal meaning must have changed.
3. **SOUL facts anchor interpretation.** Stable event facts stay intact while genuinely changed psychological meanings may evolve; current slot 5 is isolated from history.
4. **KEEP is restored mechanically.** Separate decide and finalize calls prevent cosmetic rewrites and validate the assembled result.

---

## 14. Design principles

1. **Sessions write nothing.** All persistence belongs to background jobs.
2. **Two-phase delivery.** Heartbeat decides; send job delivers. Never collapse them.
3. **Determinism over probability for identity-load-bearing reads.** `read`, not `memory_search`, for the three core narratives.
4. **Information, not rules.** Profiles describe; they don't `if-then`. The model infers behavior from description.
5. **Evidence owns affect.** Values stay in [0,1]; no fixed delta, forced drift or fabricated change.
6. **Per-loop cooldown.** Prevents repetition without preventing reaction.
7. **Preserve failures honestly.** Missing optional history may stay absent; a required gate failure cannot become false success.

---

## 15. Extending Dolores: making her into someone else

To turn Dolores into your character, in order:

1. **Rewrite `SOUL.md`** — voice, formative experience, appearance, daily rhythm. This is the biggest creative act in the project; everything else is downstream of it.
2. **Edit `memory/profile-user.md`** — write yourself down the way you want to be seen.
3. **Tune `state/affect.json`** — adjust values within the current nine-field schema. Adding, removing or redefining dimensions is a coordinated runtime change: align the seed, the affect instructions in `AGENTS.md`/`HEARTBEAT_STEPS.md`, and the exact-field validators in `scripts/daily_integrity_check.py` and `scripts/pause_resume_guard.py`. Adding or removing fields in JSON alone will fail integrity or resume validation.
4. **Adjust slot themes and both gate/integrity validators together in `REFLECTION_SELF/REL.md`** — the five slots are the character's introspective vocabulary. Change them to change what she notices about herself.
5. **Choose your check-ins.** Health is the reference; replace with what you want this relationship to be about.
6. **Pick or implement a channel.** Telegram transport is provided; other channel interfaces are design references. Follow §8's transport, session and failure-alert migration requirements.
7. **Set the heartbeat cadence.** Two hours is the default and the recommended starting point. Resist the urge to make it faster.

When you're done, the cognitive runtime files (`AGENTS.md`, `HEARTBEAT.md`, `REFLECTION_*.md`, `MEMORY.md`) should be almost untouched. If you found yourself rewriting them, you were probably building a different architecture, which is fine — but it isn't Dolores anymore, and you'll lose the properties this document is trying to defend.

---

*The maze is what happens when memory accumulates faster than it can be erased.*
