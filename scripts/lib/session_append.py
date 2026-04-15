"""Shared session jsonl append utility for companion agent scripts.

Configuration (must be set before use):
    SESSIONS_JSON — path to sessions.json
    SESSION_DIR   — path to sessions directory
    SESSION_KEY   — the session key to look up
"""

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# These must be configured by the calling script or environment.
# Default values are placeholders — must be configured before use.
SESSIONS_JSON = Path("[SESSION_PATH — USER CONFIG]/sessions.json")
SESSION_DIR = Path("[SESSION_PATH — USER CONFIG]")
SESSION_KEY = "[SESSION_KEY — USER CONFIG]"


def append_to_session(text: str):
    """Append an assistant message to the main session jsonl. Silent on failure."""
    try:
        sessions = json.loads(SESSIONS_JSON.read_text())
        session_id = sessions[SESSION_KEY]["sessionId"]
        jsonl_path = SESSION_DIR / f"{session_id}.jsonl"

        if not jsonl_path.exists():
            return

        last_line = jsonl_path.read_text().strip().split("\n")[-1]
        parent_id = json.loads(last_line)["id"]

        entry = {
            "type": "message",
            "id": uuid.uuid4().hex[:8],
            "parentId": parent_id,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": text}],
            },
        }

        line = json.dumps(entry, ensure_ascii=False)
        json.loads(line)  # round-trip validation

        with open(jsonl_path, "a") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"append_to_session failed: {e}", file=sys.stderr)
