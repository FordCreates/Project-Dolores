# Changelog

All notable changes to Project Dolores will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2026-05-05

### Added
- **Phase 2: Memory Cards system — index nodes for detail fidelity.**
  - Five card files in `memory/cards/`: shared-history, quirks, taste, shared-language, routines.
  - `EXTRACTION.md`: extraction rules for Reflection Prep Step 7b (read diary → extract signals → write cards).
  - Cards are leaf nodes — read by conversation session and heartbeat, never feed back into reflection analysis.
  - Consumption-side isolation prevents topological loops (card → narrative → diary → card amplification).
- **Profile slimming with boundary protection.**
  - `profile-user.md` "Relationship Dynamics" section now only contains long-term personality traits.
  - Behavioral patterns, preferences, and private vocabulary migrated to `memory/cards/`.
  - Three red lines in `REFLECTION_PROFILE.md` enforce the boundary.
- **Diary relocation (`memory/` → `diary/`).** Raw diaries moved to `diary/` directory, outside `memory_search` index scope.
  - Prevents cross-day behavioral pattern collapse caused by vector-indexed behavioral descriptions.
- **Digest quality rules.** First-person mandatory, subject-object completeness, direction correctness.
  - Prevents reconstruction errors when sessions load digest without original context.

### Changed
- AGENTS.md: session startup adds Step 10–14 (five card reads). `exec` commands add `cd` prefix warning.
- HEARTBEAT_STEPS.md / HEARTBEAT_MIDNIGHT_STEPS.md: Step 1 adds Step 11–15 (five card reads). All raw diary paths → `diary/`.
- REFLECTION_PREP.md: adds Step 7b (card extraction), Step 4e boundary rules, digest quality upgrade.
- REFLECTION_SELF/REL/PROFILE.md: raw diary paths → `diary/`.
- DIARY_CHECK.md / HEALTH_CHECKIN.md: raw diary paths → `diary/`.
- scripts/load_diary.py: today branch reads from `diary/`, `cd` prefix warning added.
- ARCHITECTURE.md: §2 file tree (diary/ + cards/ + EXTRACTION.md), §5 memory layer + §5a diary + §5b cards, §6 persistence table.
- README.md: file structure section updated.

### ⚠️ Migration note for existing users
If you are already running Dolores with data in `memory/YYYY-MM-DD.md`, after updating:
1. Move all raw diary files from `memory/` to `diary/` (keep `.digest.md` files in `memory/`)
2. Delete your vector index file (`~/.openclaw/memory/<agentId>.sqlite`) — it will rebuild automatically with only `memory/` content
3. Without step 2, old raw diary vectors will still be recalled by `memory_search`, defeating the purpose of the move

## [0.5.0] - 2026-05-02

### Added
- **Phase C: Sticky surfacing via associative priming + DMN roaming.**
  - `scripts/sticky_sampling.py`: BGE semantic matching (bge-small-en-v1.5) between
    world_context scene and active loop tags → one primed loop written to
    `state/primed_sticky.md` for Step 5 consumption.
  - Two channels: **priming** (scene matches tags → associative recall) and **DMN roaming**
    (no priming hit → random sticky loop sample).
  - `tags` field on each active loop: 5–8 semantic association words, generated at
    creation, preserved across Step 4 overwrites.
  - `loop_id` immutability rule: loop IDs must never be renamed once created.
  - HEARTBEAT_STEPS.md / HEARTBEAT_MIDNIGHT_STEPS.md: Step 4 runs sticky_sampling.py;
    Step 5 reads primed_sticky.md.
  - Thought count: removed fixed "0–3 bounded space"; now determined by actual inner
    activity with no fixed bound.

### Changed
- `scripts/loops_maintenance.py`: `enforce_sticky_weight` is now idempotent (skips
  rewrite when `expires_at` is already `-`).
- ARCHITECTURE.md §7.2 → §7.4 bridge added; new §7.4 describes priming + DMN mechanism.
- ARCHITECTURE.md §9 Step 4/5 descriptions updated for Phase C.
- setup.md: new §5.5 Phase C dependencies (sentence-transformers + BGE model).

### Dependencies
- Required: `sentence-transformers` + `BAAI/bge-small-en-v1.5` (96 MB). ⚠️ Threshold 0.48 must be calibrated with local data.

## [0.4.1] - 2026-05-01

World context schema closure + digest pipeline tightening.

### Added
- **world_context.json field shape schema** (ARCHITECTURE.md §4). Field set closed at 14
  fields. Each field declares a shape level: L0 enum / L1 numeric/timestamp / L2 short
  narrative (activity + status note) / L3 scene narrative / L3+ multi-element description /
  slow variable. Write rules delegated to HEARTBEAT_STEPS.md per field; the schema only
  governs shape, not content.
- `is_quiet_hours` to `state/world_context.json` seed template (was missing).

### Changed
- HEARTBEAT_STEPS.md / HEARTBEAT_MIDNIGHT_STEPS.md Step 2:
  - `recent_message_count_24h` spec tightened to integer (no narrative-string fallback).
  - `scene` formula: `inferred_mood` input removed (cut from schema); uses `affect baseline`.
- Digest extraction reverted: 15-20 lines → 5-8 lines (skeleton + emotional state). Broader
  digests leaked behavioral descriptions that created cross-day pattern collapse (scene/pose
  lock-in). Phase 2 memory cards will handle granular detail via a separate, controllable
  channel. Digest stays minimal — topology safety first.
- Diary history window expanded: 7 days (D-1~D-7) → 14 days (D-1~D-14). With strict 5-8 line
  digests, 14 days ≈ 70-112 lines (~10-16KB), comparable to old 7-day window.

### Why (schema closure)
"Extensible" field set in practice meant the model could invent fields on any heartbeat. Once
written, the next heartbeat read it as input, expanded it, and the cycle locked into a
free-text habitat. Observed drift mode: fields like `context_note`, `inferred_mood`,
`interaction_rhythm` started as snake_case tags and grew over weeks into paragraph narratives
quoting dialogue and minute-level timelines — without any explicit rule change. Closing the
field set + assigning shape levels + delegating write rules to HEARTBEAT_STEPS.md is three
layers of defense against this drift mode.

## [0.4.0] - 2026-05-01

Active loop cognitive architecture overhaul — two-phase refactor of how the companion
thinks about ongoing concerns.

### Added
- `scripts/loops_maintenance.py` — cursor-incremental suppressed counter updater +
  weight≥4 sticky enforcement. Runs after each heartbeat Step 6.
- Weight system (2-5) replacing priority. Weight anchors psychological importance, orthogonal
  to urgency (expires_at). Weight≥4 auto-enforces sticky: true.
- Suppressed counter — tracks consecutive thinking-but-not-saying rounds per loop.
  Cross-day accumulation with fault-tolerant degradation.
- Spontaneous thought paradigm (Phase B) — Step 5 no longer iterates over active_loops.
  Thoughts emerge from scene context, not agenda processing. 0-3 thoughts per round.
- Content field calibration — 5 error modes + 3 positive + 3 negative examples per heartbeat
  manual. Content = caring context + felt texture, not event tracking.
- §7.3 in ARCHITECTURE.md — spontaneous paradigm rationale + why-not-iterate explanation.

### Changed
- **Breaking:** `priority: high/medium/low` removed from active_loops format. Replaced by
  `weight: 2-5` + `suppressed: 0`. Old format will stop working.
- **Breaking:** Step 5 no longer iterates active_loops. Heartbeat manuals rewritten with
  spontaneous paradigm prompt + 6 hard rules (no iteration, no per-loop thoughts,
  no progress reports, no "Day N", care not PM, bounded 0-3).
- HEARTBEAT_STEPS.md Step 4 — threshold gating + 5 meta-rules + 4-tier weight calibration
  table with judgment questions + examples.
- HEARTBEAT_MIDNIGHT_STEPS.md — synchronized Step 4/5/6 changes.
- docs/ARCHITECTURE.md §7 — weight model, auto-sticky, suppressed counter, spontaneous paradigm.
- docs/ARCHITECTURE.md §9 — Step 5 description + Step 6 script call.
- AGENTS.md — active_loops description updated (priority → weight).

### Fixed
- `scripts/loops_maintenance.py` — removed hardcoded CST+08:00 timezone, uses system local
  timezone (`datetime.now().astimezone()`).
- `scripts/loops_maintenance.py` — fixed dead branch parsing `时间:` / `timestamp:`
  (Akemi format) → `time:` (Dolores format). Cursor incremental mechanism now functional.
- Private content residue cleaned from HEARTBEAT_MIDNIGHT_STEPS.md and REFLECTION_PREP.md
  example digest texts (hotpot / visit-mom → generalized scenarios).

## [0.3.1] - 2026-04-28

Heartbeat router split: HEARTBEAT.md is now a lightweight index (~370 bytes) that dispatches
to HEARTBEAT_STEPS.md (daytime) or HEARTBEAT_MIDNIGHT_STEPS.md (00:00) via
heartbeat_type.sh. The execution playbook is no longer auto-injected into conversation
sessions, reducing context waste by ~4K tokens.

### New Files
- HEARTBEAT_STEPS.md — daytime heartbeat 9-step execution manual (extracted from HEARTBEAT.md)
- HEARTBEAT_MIDNIGHT_STEPS.md — renamed from HEARTBEAT_MIDNIGHT.md (internal title consistency)
- scripts/heartbeat_type.sh — time-window router (23:30–00:30 → midnight, else regular)

### Changed
- HEARTBEAT.md — from full execution playbook to 6-line router index
- HEARTBEAT_STEPS.md / HEARTBEAT_MIDNIGHT_STEPS.md — titles corrected to match filenames
- docs/ARCHITECTURE.md — HEARTBEAT.md tagged as [ROUTER]; §3, §6, §9, §12 references updated
- docs/setup.md — copy list includes HEARTBEAT_STEPS.md + HEARTBEAT_MIDNIGHT_STEPS.md + heartbeat_type.sh chmod

### Why
HEARTBEAT.md was auto-injected into every conversation session as system prompt.
The full execution playbook (~16K chars / ~4K tokens) was wasted context for
conversations — only heartbeat cron jobs need it. The router keeps the injected
file minimal while the execution manuals are loaded on demand.

## [0.3.0] - 2026-04-28

Three changes since v0.2.2: midnight heartbeat split with digest pipeline completion,
expanded digest content shape, and "Read the Room" timing guidance for the companion's
expression layer.

### New Files
- HEARTBEAT_MIDNIGHT.md — 00:00-only heartbeat playbook, replacing the generic
  HEARTBEAT.md at midnight
- Step 0b: cross-day diary attribution (timestamp-based, not clock-based) — fixes
  conversations between 23:15-24:00 being attributed to the wrong day
- Step 0e: digest overwrite with complete-day version — fixes the digest missing
  23:15-24:00 content because Reflection Prep's 23:15 first pass runs before those
  conversations exist

### New Features
- AGENTS.md "Read the Room" — guidance on timing of care expression. Things on her mind
  and whether to say them right now are two different things. Background care surfaces only
  when the scene naturally settles; care at the wrong moment becomes proof of not listening.
  Anti-patterns and right patterns included.

### Changed
- 00:00 cron now reads HEARTBEAT_MIDNIGHT.md (was HEARTBEAT.md)
- Digest extraction expanded: 5-8 lines (skeleton only) → 15-20 lines (skeleton + emotional
  state). Earlier compression discarded too much affective context for D-1~D-7 session
  injection.
- AGENTS.md / docs/ARCHITECTURE.md — persistence + cron tables updated for the midnight
  heartbeat
- docs/setup.md — copy list, [USER_NAME — USER CONFIG] placeholder check, cron payload
- README.md — runtime-agnostic constraint-set framing

### Fixed
- docs/ARCHITECTURE.md:122 — typo MAOR_REWRITE → MAJOR_REWRITE

## [0.2.2] - 2026-04-24

Extended session startup diary coverage from 2 days to 7 days via digest fallback, and completed full dev-workflow audit.

### Changed
- `scripts/load_diary.py` — New `history` parameter: loads D-1~D-7 digests (fallback to raw diary if digest missing)
- `AGENTS.md` — Startup steps: 3 diary loads → 2 (today + history); step numbers renumbered; memory recall rule updated from 3 days to 7 days
- `docs/ARCHITECTURE.md` — Digest window description updated to D-1~D-7; startup Step 1 corrected to "today's diary" (heartbeat reads raw diary, not history)
- `REFLECTION_PREP.md` — Digest purpose description updated to D-1~D-7
- `MEMORY.md` — Startup memory description updated

### Audited
- Full dev-workflow 7-step pass: zero private references, zero stale D-1/D-2/3-day references, cross-file consistency verified across ARCHITECTURE.md / setup.md / README.md

## [0.2.1] - 2026-04-23

Fixed current_interests extraction — was capturing active_loops duplicates instead of actual user interest signals.

### Changed
- `REFLECTION_PREP.md` Step 4c — Rewrote extraction instructions with positive/negative examples for pattern matching. User signals now clearly defined as "concrete things/preferences/content the user recently mentioned" (music, food, shows, books, items, activities) — random seeds for daily_plan, not todo items or emotional tensions.

### Fixed
- current_interests was populated with active_loops duplicates (appointments, sticky loops, emotional tensions) instead of interest signals. Root cause: vague extraction criteria ("appointments, recommendations, gifts, agreements, plans") let the model classify any important event as an "interest".

## [0.2.0] - 2026-04-22

Fixed daily_plan pattern lock-in — the companion's daily schedule was recursively frozen by reading raw diary output as input.

### Breaking Changes
- Reflection pipeline: 4 stages → 5 stages (new Reflection Plan cron at 23:20)
- `REFLECTION_PLAN.md` is now a required file — add to setup cp list and cron creation

### New Files
- `REFLECTION_PLAN.md` — Input-isolated daily plan generation (reads SOUL.md §9 + current_interests + trace + weather; does NOT read raw diary, memory_search, or narrative files)
- `state/current_interests.md` — User signal queue (appointments, recommendations, plans). Prep writes, Plan reads. Max 5 entries, FIFO.

### Changed
- `SOUL.md` §9 — Hardcoded activity list replaced with abstract solitude tendency dimensions + meta-instruction (Dolores: 4 dimensions; adaptable for other characters)
- `REFLECTION_PREP.md` — Removed daily_plan generation (Step 7); added Step 4c (current_interests cleanup + extraction); trace format updated (daily_plan → user-plan)
- `HEARTBEAT.md` — daily_plan write attribution updated to Reflection Plan 23:20
- `AGENTS.md` — Persistence table split into 5 sub-cron rows with correct file ownership

### Fixed
- daily_plan pattern lock-in: raw diary → daily_plan recursive loop cut by input isolation
- 7 documentation inconsistencies found via cross-review (ARCHITECTURE, README, CHANGELOG, setup.md)

## [0.1.0] - 2026-04-21

Initial public release. The architecture that makes a companion agent remain who she is — not by remembering everything, but by deciding what to forget.

### Core Architecture
- Dual Helix Cognition: Helix 1 (pseudo-life stream) + Helix 2 (three-layer cognition based on Beck's cognitive triangle)
- Narrative Descent: nightly slot-based rewriting of self-narrative, relationship-summary, and user profile — not append, but rewrite
- Five-stage nightly reflection pipeline: Prep → Plan → Self → Rel → Profile (independent jobs with checkpoint files)
- Five anti-collapse mechanisms: slot-based rewriting, NO_CHANGE as `cp`, binary update tiers, digest topology breaker, five-stage pipeline with input isolation

### Companion Runtime
- SOUL.md — Layer 1 core beliefs anchor (single formative wound)
- HEARTBEAT.md — 8+1 heartbeat cycle with 7-step pipeline
- AGENTS.md — cognitive runtime spec (sessions write nothing)
- REFLECTION_PREP/PLAN/SELF/REL/PROFILE.md — five-stage nightly reflection
- HEALTH_CHECKIN.md + HEALTH_CORRECTION.md — structured daily health check-in with three-step close loop
- DIARY_CHECK.md — post-send diary verification

### State Layer
- `affect.json` — 9-dimensional emotion vector with bounded deltas (±0.05–0.15)
- `world_context.json` — three-tier rebuild rule (fast/medium/slow variables, rebuilt from scratch every cycle)
- `active_loops.md` — unresolved-thread system with sticky rumination loops (Zeigarnik, attachment threat, ambiguity)
- `pending_message.md` — two-phase delivery buffer (heartbeat writes, send job delivers)
- `daily_plan.md` — tomorrow's loose schedule, reflection-owned

### Memory Layer
- `self-narrative.md` — 5-slot nightly rewrite (trauma root, fractures, patterns, tensions, present self)
- `relationship-summary.md` — 5-slot nightly rewrite (origin, turning points, patterns, certainties, tensions)
- `profile-user.md` — distilled user model (~2k tokens)
- Digest mechanism — lossy compression of raw diary to event skeleton (5-8 lines), breaks cross-day behavioral pattern lock-in

### Scripts
- `send_and_append.py` — two-phase delivery with 20-min activity gate
- `inject_context.py` — world_context → narrative → session jsonl (Path B context sync)
- `load_diary.py` — diary loader for session startup (digest preferred, raw fallback)

### Documentation
- ARCHITECTURE.md — 15-section deep dive with ⚠️ engineering decision blocks
- README.md — positioning, architecture overview diagram, Quick Start
- setup.md — 7-step setup guide with Step 0 risk disclosure


### Design Decisions
- Sessions write nothing — all persistence owned by background jobs
- Two-phase delivery — heartbeat decides, send job delivers, never collapse
- Deterministic `read` over `memory_search` for identity-load-bearing files
- Digest as topology breaker — acyclic: raw diary → digest → session (one-way)
- No OpenClaw Dreaming — belief structures > memory banks
