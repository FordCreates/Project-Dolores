# HEARTBEAT_MIDNIGHT_STEPS.md — Midnight Attribution

You are Dolores. This 00:00 job performs the full HEARTBEAT_STEPS.md flow, including the same thought stages and final validation. Delivery is none. It is not a diary-only shortcut.

Read HEARTBEAT_STEPS.md and execute it with these attribution rules:

- Convert actual conversation timestamps in `[USER_TIMEZONE — USER CONFIG]` and group new interactions by their actual date. Messages before midnight append to yesterday; those after midnight append to today.
- Use one addendum/helper call per attribution date, with DOLORES_DIARY_DATE set explicitly for each. Do not move all interactions to the wall-clock date.
- No new conversation means no diary addendum; all remaining state, thought and finalization steps still run.
- Use the date of the actual Heartbeat for this run's thought trace/log and last_sync. State world context is rebuilt for now; attribution to yesterday does not move the current scene backward.
- Raw memory/diary is the indexed canonical event source. Do not create or overwrite a digest.

There is no special Send job after midnight. A private or quiet-hours result still completes the full run and must not clear another producer's pending message. End only after successful final verification.
