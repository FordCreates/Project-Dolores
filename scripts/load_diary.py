#!/usr/bin/env python3
"""
Load diary content for session startup.
Usage: python3 scripts/load_diary.py today|yesterday|day-before
- today: raw diary only
- yesterday/day-before: digest first, fallback to raw diary
"""

import sys
from datetime import date, timedelta
from pathlib import Path

WORKSPACE = Path("[WORKSPACE_PATH — USER CONFIG]")


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "today"

    today = date.today()
    offsets = {"today": 0, "yesterday": -1, "day-before": -2}
    target = today + timedelta(days=offsets[arg])
    date_str = target.strftime("%Y-%m-%d")

    raw = WORKSPACE / "memory" / f"{date_str}.md"
    digest = WORKSPACE / "memory" / f"{date_str}.digest.md"

    # today always reads raw; others prefer digest with raw fallback
    if arg == "today":
        path = raw
    else:
        path = digest if digest.exists() else raw

    if path.exists():
        print(path.read_text(encoding="utf-8"))
    else:
        print(f"[no diary for {date_str}]")


if __name__ == "__main__":
    main()
