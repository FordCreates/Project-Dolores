#!/usr/bin/env python3
"""Atomically append one validated Heartbeat diary addendum.

The model writes only ``state/diary_append_draft.md``.  This helper preserves
the existing raw diary byte-for-byte, rejects damaged Unicode and generic
reflection headings at the append boundary, and creates the canonical daily
heading when needed.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import NoReturn


ROOT = Path(os.environ.get("DOLORES_DIARY_ROOT", Path(__file__).resolve().parents[1]))
DRAFT = ROOT / "state/diary_append_draft.md"
LOCK = ROOT / "state/.diary_append.lock"
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
GENERIC_REFLECTION_HEADING = re.compile(
    r"(?im)^##[ \t]*(?:(?:today(?:'s)?|overall)[ \t]+)?"
    r"(?:feelings|thoughts|reflections|summary|what I(?:'m| am) feeling)"
    r"[ \t]*(?:\([^\r\n)]*\))?[ \t]*$"
)


def fail(message: str) -> NoReturn:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
    raise SystemExit(1)


def target_day() -> date:
    raw = os.environ.get("DOLORES_DIARY_DATE")
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        fail("DOLORES_DIARY_DATE must be YYYY-MM-DD")


def read_utf8(path: Path, label: str) -> str:
    try:
        content = path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        fail(f"{label} is missing: {path}")
    except UnicodeDecodeError as exc:
        fail(f"{label} is not valid UTF-8: {exc}")
    if "\ufffd" in content:
        fail(f"{label} contains Unicode replacement character U+FFFD")
    if "\x00" in content:
        fail(f"{label} contains a NUL character")
    return content


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def append_draft() -> None:
    day = target_day()
    diary = ROOT / "memory/diary" / f"{day.isoformat()}.md"
    draft = read_utf8(DRAFT, "diary append draft").strip()
    if not draft:
        fail("diary append draft is empty")
    if re.match(r"^#\s+\d{4}-\d{2}-\d{2}\b", draft):
        fail("diary append draft must contain only the new addendum, not a daily heading")
    if GENERIC_REFLECTION_HEADING.search(draft):
        fail(
            "diary append draft must not use a generic feelings/thoughts/summary "
            "heading; attach italic inner reflection to its natural scene"
        )

    expected_header = f"# {day.isoformat()} ({WEEKDAYS[day.weekday()]})"
    if diary.exists():
        existing = read_utf8(diary, "existing diary")
        first = existing.splitlines()[0] if existing.splitlines() else ""
        if not re.fullmatch(rf"{re.escape(expected_header)}(?: · [^\r\n]+)?", first):
            fail(
                "existing diary heading must be the canonical date/weekday, "
                "optionally followed by a non-empty ' · title' suffix"
            )
    else:
        existing = expected_header + "\n"

    normalized_draft = draft + "\n"
    if existing.rstrip().endswith(draft):
        DRAFT.unlink(missing_ok=True)
        print(
            json.dumps(
                {
                    "ok": True,
                    "skipped": True,
                    "reason": "duplicate_suffix",
                    "path": str(diary),
                },
                ensure_ascii=False,
            )
        )
        return

    separator = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    atomic_write(diary, existing + separator + normalized_draft)
    DRAFT.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "ok": True,
                "skipped": False,
                "path": str(diary),
                "appended_chars": len(draft),
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("a+", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fail("another diary append is already in progress")
        append_draft()


if __name__ == "__main__":
    main()
