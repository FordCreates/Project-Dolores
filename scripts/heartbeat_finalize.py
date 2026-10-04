#!/usr/bin/env python3
"""Verify this Heartbeat's final state without creating a Git commit."""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from cron_git_commit import (
    CommitError, HEARTBEAT_FILES, validate_changed_text, validate_heartbeat_trace,
)
from world_context_gate import validate_world_context


def verify(root: Path, run_id: str) -> dict:
    validate_heartbeat_trace(root, ".", run_id)
    paths = list(HEARTBEAT_FILES)
    today = datetime.now().astimezone().date().isoformat()
    paths.extend([f"memory/diary/{today}.md", f"state/thoughts_log/{today}.md"])
    validate_changed_text(root, paths)
    world = json.loads((root / "state/world_context.json").read_text(encoding="utf-8"))
    errors = validate_world_context(world)
    if errors:
        raise CommitError("world_context validation failed: " + "; ".join(errors))
    last_sync = (root / "state/last_sync_at").read_text(encoding="utf-8").strip()
    sync = datetime.fromisoformat(last_sync)
    trace = json.loads((root / "state/thought_trace.json").read_text(encoding="utf-8"))
    started = datetime.fromisoformat(trace["created_at"])
    if sync.tzinfo is None or sync < started:
        raise CommitError("last_sync_at must include a timezone and belong to this Heartbeat")
    return {"ok": True, "thought_run_id": run_id, "stage": "finalized", "pushed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(os.environ.get("DOLORES_WORKSPACE", Path(__file__).resolve().parents[1])))
    parser.add_argument("--thought-run-id", required=True)
    args = parser.parse_args()
    try:
        result = verify(args.root, args.thought_run_id)
    except (CommitError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
