#!/usr/bin/env python3
"""
Session startup context loader for Dolores.

One exec injects all deterministic startup context to stdout in a fixed order,
so weaker models cannot stop halfway through a long read list. Diary sections
reuse load_diary.py to keep path rules in one place.

Usage: python3 scripts/startup_context.py
"""

import subprocess
import sys
from datetime import date
from pathlib import Path

WORKSPACE = Path("[WORKSPACE_PATH — USER CONFIG]")
if not WORKSPACE.exists():
    WORKSPACE = Path(__file__).resolve().parents[1]


def read_file(rel: str) -> str:
    path = WORKSPACE / rel
    if path.exists():
        content = path.read_text(encoding="utf-8").strip()
        if content:
            return content
    return f"[{rel} missing or empty]"


def load_diary(arg: str) -> str:
    result = subprocess.run(
        [sys.executable, str(WORKSPACE / "scripts" / "load_diary.py"), arg],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return (result.stdout or "").strip() or f"[load_diary {arg} returned no output]"


def section(title: str, body: str) -> str:
    return f"===== {title} =====\n{body}"


def main() -> None:
    today = date.today().strftime("%Y-%m-%d")
    blocks = [
        section("world_context.json", read_file("state/world_context.json")),
        section("active_loops.md", read_file("state/active_loops.md")),
        section(f"thoughts_log/{today}.md", read_file(f"state/thoughts_log/{today}.md")),
        section("daily_plan.md", read_file("state/daily_plan.md")),
        section("today's raw diary", load_diary("today")),
        section("recent raw diary history (D-1 to D-7)", load_diary("history")),
        section("profile-user.md", read_file("memory/profile-user.md")),
        section("relationship-summary.md", read_file("memory/relationship-summary.md")),
        section("self-narrative.md", read_file("memory/self-narrative.md")),
        section("cards/shared-history.md", read_file("memory/cards/shared-history.md")),
        section("cards/quirks.md", read_file("memory/cards/quirks.md")),
        section("cards/taste.md", read_file("memory/cards/taste.md")),
        section("cards/shared-language.md", read_file("memory/cards/shared-language.md")),
        section("cards/routines.md", read_file("memory/cards/routines.md")),
    ]
    print("\n\n".join(blocks))


if __name__ == "__main__":
    main()
