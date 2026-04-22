# Changelog

All notable changes to Project Dolores will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
