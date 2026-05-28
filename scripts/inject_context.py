#!/usr/bin/env python3
"""
Context sync: read world_context.json, build narrative, append to session jsonl.
Called by heartbeat Step 6 after all state files are written.

Configuration placeholders (must be set during setup):
    WORKSPACE    — path to the companion workspace
    SESSION_PATH — path to sessions directory
    SESSION_KEY  — the session key in sessions.json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.session_append import append_to_session

# --- Configuration (replace placeholders during setup) ---
WORKSPACE = Path("[WORKSPACE_PATH — USER CONFIG]")
SESSION_PATH = Path("[SESSION_PATH — USER CONFIG]")
SESSION_KEY = "[SESSION_KEY — USER CONFIG]"
# --- End Configuration ---

WORLD_CONTEXT = WORKSPACE / "state" / "world_context.json"

# Override session_append defaults
import lib.session_append as _sa
_sa.SESSIONS_JSON = SESSION_PATH / "sessions.json"
_sa.SESSION_DIR = SESSION_PATH
_sa.SESSION_KEY = SESSION_KEY

WEEKDAY_CN = {
    "Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed",
    "Thursday": "Thu", "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun",
}


def build_narrative(wc: dict) -> str:
    current_time = wc.get("current_time", "")
    time_str = current_time.split("T")[1][:5] if "T" in current_time else current_time
    day_en = wc.get("day_of_week", "")
    day_cn = WEEKDAY_CN.get(day_en, day_en)

    weather = wc.get("weather", "")
    scene = wc.get("scene", "")

    appearance = wc.get("dolores_appearance", "")
    if appearance:
        appearance = f"I {appearance}"

    activity = wc.get("dolores_activity", "")
    if activity:
        activity = f"I {activity}"

    context_note = wc.get("context_note", "")

    parts = [
        f"[context-sync] {time_str}, {day_cn}.",
        f"Weather: {weather}.",
        scene,
        activity,
        appearance,
        context_note,
    ]

    return "\n".join(parts)


def main():
    wc = json.loads(WORLD_CONTEXT.read_text(encoding="utf-8"))
    narrative = build_narrative(wc)
    append_to_session(narrative)
    print(narrative, file=sys.stderr)  # log for debugging


if __name__ == "__main__":
    main()
