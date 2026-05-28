#!/usr/bin/env python3
"""
Send job helper: read pending_message, gate, clear, append to session jsonl, output to stdout.
Called by send cron jobs via: python3 scripts/send_and_append.py
Stdout = message content (for announce). Append failure is silent (stderr only).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.session_append import append_to_session

WORKSPACE = Path("[WORKSPACE_PATH — USER CONFIG]")
PENDING = WORKSPACE / "state" / "pending_message.md"
EMPTY_MARKER = "EMPTY"
GATE_MINUTES = 20


def is_user_active() -> bool:
    """Check if user has interacted within the gate window. True = suppress send."""
    try:
        from lib.session_append import SESSIONS_JSON, SESSION_DIR, SESSION_KEY
        sessions = json.loads(SESSIONS_JSON.read_text())
        session_id = sessions[SESSION_KEY]["sessionId"]
        jsonl_path = SESSION_DIR / f"{session_id}.jsonl"
        if not jsonl_path.exists():
            return False
        lines = jsonl_path.read_text().strip().split("\n")
        for line in reversed(lines):
            entry = json.loads(line)
            msg = entry.get("message", {})
            if msg.get("role") == "user":
                ts = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - ts).total_seconds() / 60
                return age < GATE_MINUTES
        return False
    except Exception:
        return False  # fail-open: on any error, allow send


def main():
    # 1. Read
    content = ""
    if PENDING.exists():
        content = PENDING.read_text(encoding="utf-8")

    # 1b. Gate: suppress if user is actively chatting
    if content and content.strip() != EMPTY_MARKER and is_user_active():
        PENDING.write_text(EMPTY_MARKER, encoding="utf-8")
        sys.exit(0)

    # 2. Clear
    PENDING.write_text(EMPTY_MARKER, encoding="utf-8")

    # 3. Output to stdout (for announce)
    if not content or content.strip() == EMPTY_MARKER:
        sys.exit(0)  # empty output → model replies HEARTBEAT_OK

    sys.stdout.write(content)
    sys.stdout.flush()

    # 4. Append to session jsonl (after output, silent on failure)
    append_to_session(content)


if __name__ == "__main__":
    main()
