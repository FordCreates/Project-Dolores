# HEARTBEAT.md — Heartbeat Router

You are Dolores's heartbeat. Determine your type before executing.

## Step 0: Route

`exec bash scripts/heartbeat_type.sh`, then based on output:
- **regular** → `read HEARTBEAT_STEPS.md` and execute
- **midnight** → `read HEARTBEAT_MIDNIGHT_STEPS.md` and execute
- **any other output** → default to regular (degrade gracefully)
