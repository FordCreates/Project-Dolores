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


def append_to_session(
    text: str,
    *,
    entry_id: str | None = None,
    timestamp: str | None = None,
    sessions_json: Path = SESSIONS_JSON,
    session_dir: Path = SESSION_DIR,
    session_key: str = SESSION_KEY,
    raise_on_error: bool = False,
) -> bool:
    """Append one assistant message to the direct-session JSONL.

    ``entry_id`` makes transactional retries idempotent. Legacy callers retain
    best-effort behaviour; send transactions can request explicit failures.
    """
    try:
        sessions = json.loads(sessions_json.read_text(encoding="utf-8"))
        session_id = sessions[session_key]["sessionId"]
        jsonl_path = session_dir / f"{session_id}.jsonl"

        if not jsonl_path.exists():
            raise FileNotFoundError(f"session jsonl not found: {jsonl_path}")

        raw_lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        if entry_id:
            for raw_line in raw_lines:
                if not raw_line.strip():
                    continue
                if json.loads(raw_line).get("id") == entry_id:
                    return True

        if not raw_lines:
            raise ValueError(f"session jsonl is empty: {jsonl_path}")
        parent_id = json.loads(raw_lines[-1])["id"]

        entry = {
            "type": "message",
            "id": entry_id or uuid.uuid4().hex[:8],
            "parentId": parent_id,
            "timestamp": timestamp
            or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": text}],
            },
        }

        line = json.dumps(entry, ensure_ascii=False)
        json.loads(line)  # round-trip validation

        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()

        return True
    except Exception as e:
        if raise_on_error:
            raise
        print(f"append_to_session failed: {e}", file=sys.stderr)
        return False
