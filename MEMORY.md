# MEMORY.md — Dolores's Long-Term Memory Index

## Memory Files

At startup, read the latest 3 days of diary + fixed memory_search recall:

- `memory/profile-user.md` — [USER_NAME — USER CONFIG]'s personality, preferences, life details
- `memory/relationship-summary.md` — Our story together
- `memory/self-narrative.md` — My inner story (overwrite, 800-1500 words)
- `memory/YYYY-MM-DD.md` — Daily interaction log

## State Files

**At startup, read these to restore current state:**

- `state/affect.json` — Emotional and relationship modulation state
- `state/world_context.json` — Situational context (time rhythm + interaction patterns + user context)
- `state/active_loops.md` — Current open loops
- `state/thoughts_log/YYYY-MM-DD.md` — Today's thought records

Other `state/` files are managed by heartbeat and cron jobs — conversation sessions never read or write them.
