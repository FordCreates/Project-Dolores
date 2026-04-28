# Changelog

All notable changes to Project Dolores will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
