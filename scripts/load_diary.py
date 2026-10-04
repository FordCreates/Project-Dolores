#!/usr/bin/env python3
"""
Load diary content for session startup and heartbeat recovery.
Usage: python3 scripts/load_diary.py today|yesterday|day-before|history|heartbeat-history
- today: raw diary only
- yesterday/day-before: raw diary only
- history: D-1 to D-7 raw diary (full recent memory for pattern diversity awareness)
- heartbeat-history: normal mode loads D-1/D-2; recovery mode loads the last
  seven valid active-period diaries anchored at last_valid_diary_date
"""

import sys
import json
import os
from datetime import date, timedelta
from pathlib import Path

WORKSPACE = Path(os.environ.get("DOLORES_WORKSPACE", Path(__file__).resolve().parents[1]))


def read_lifecycle() -> dict:
    p = WORKSPACE / "state" / "lifecycle.json"
    if not p.exists():
        return {"mode": "active"}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"mode": "active"}
    if not isinstance(data, dict):
        return {"mode": "active"}
    data.setdefault("mode", "active")
    return data


def should_load_active_history(lifecycle: dict) -> bool:
    if not lifecycle.get("last_valid_diary_date"):
        return False
    mode = lifecycle.get("mode", "active")
    if mode == "resuming":
        return True
    if mode == "paused" and not lifecycle.get("first_resume_contact_done", False):
        return True
    return False


def load_active_history(anchor: date, limit: int = 7) -> str:
    parts = []
    # Bound the scan so a bad anchor cannot make startup expensive.
    for i in range(0, 90):
        target = anchor + timedelta(days=-i)
        date_str = target.strftime("%Y-%m-%d")
        raw = WORKSPACE / "memory" / "diary" / f"{date_str}.md"
        if raw.exists():
            content = raw.read_text(encoding="utf-8").strip()
            if content:
                parts.append(f"## {date_str}\n{content}")
                if len(parts) >= limit:
                    break
    if parts:
        return "\n\n".join(parts)
    return f"[no active-period diary ending at {anchor.isoformat()}]"


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "today"

    today = date.today()
    lifecycle = read_lifecycle()
    mode = lifecycle.get("mode", "active")
    load_active_history_from_lifecycle = should_load_active_history(lifecycle)

    if arg in {"history", "heartbeat-history"}:
        if load_active_history_from_lifecycle:
            try:
                anchor = date.fromisoformat(str(lifecycle["last_valid_diary_date"]))
            except ValueError:
                anchor = today + timedelta(days=-1)
            print(load_active_history(anchor))
            return

        # Session startup needs D-1 to D-7. Heartbeat keeps its normal-mode
        # context compact (D-1/D-2), while recovery still gets the full last
        # valid window above so a calendar gap cannot erase the latest voice.
        parts = []
        history_days = 7 if arg == "history" else 2
        for i in range(1, history_days + 1):
            target = today + timedelta(days=-i)
            date_str = target.strftime("%Y-%m-%d")
            raw = WORKSPACE / "memory" / "diary" / f"{date_str}.md"
            if raw.exists():
                content = raw.read_text(encoding="utf-8").strip()
                if content:
                    parts.append(f"## {date_str}\n{content}")
        if parts:
            print("\n\n".join(parts))
        else:
            if arg == "history":
                print("[no diary history for past 7 days]")
            else:
                print("[no diary history for previous 2 days]")
        return

    offsets = {"today": 0, "yesterday": -1, "day-before": -2}
    target = today + timedelta(days=offsets[arg])
    date_str = target.strftime("%Y-%m-%d")

    path = WORKSPACE / "memory" / "diary" / f"{date_str}.md"

    if path.exists():
        print(path.read_text(encoding="utf-8"))
    elif arg == "today" and load_active_history_from_lifecycle:
        print(f"[No new diary on resume date {date_str}; the calendar gap is not missing memory or subjective elapsed time.]")
    else:
        print(f"[no diary for {date_str}]")


if __name__ == "__main__":
    main()
