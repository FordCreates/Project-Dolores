#!/usr/bin/env python3
"""loops_maintenance.py — Update suppressed counters for active loops.

Uses a cursor in thoughts_log to only process entries since the last run,
preventing duplicate accumulation when called multiple times per day.

Cursor: a marker line at the top of each day's thoughts_log:
  <!-- loops_processed: 2025-01-01T12:00:00+00:00 -->

On each run:
  1. Read cursor from today's thoughts_log (if any)
  2. Parse only entries AFTER the cursor timestamp
  3. Compute suppressed delta (send→reset, store/silence→+1)
  4. Add delta to existing suppressed value in active_loops.md
  5. Update cursor to latest processed entry's timestamp

Also enforces: weight >= 4 → sticky: true + expires_at: -

Cross-day accumulation is preserved: suppressed values carry over across days.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

# Resolve relative to script location: scripts/ → workspace root
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
ACTIVE_LOOPS_PATH = WORKSPACE_DIR / "state" / "active_loops.md"
THOUGHTS_LOG_DIR = WORKSPACE_DIR / "state" / "thoughts_log"


CURSOR_RE = re.compile(r"<!-- loops_processed: (.+?) -->")


def parse_thoughts_log(path: Path, after: datetime | None = None) -> list[dict]:
    """Parse a thoughts_log .md file into a list of {loop_id, action, timestamp} dicts.

    If `after` is provided, only return entries with timestamp > after.
    """
    text = path.read_text(encoding="utf-8")
    entries = []
    current = {}

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("<!-- loops_processed:"):
            continue
        if stripped == "---":
            if current.get("loop_id") and current.get("action"):
                if after is None or current.get("ts", datetime.max.replace(tzinfo=timezone.utc)) > after:
                    entries.append(current)
            current = {}
            continue
        if stripped.startswith("loop_id:"):
            current["loop_id"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("action:"):
            current["action"] = stripped.split(":", 1)[1].strip().lower()
        elif stripped.startswith("time:"):
            ts_str = stripped.split(":", 1)[1].strip()
            try:
                current["ts"] = datetime.fromisoformat(ts_str)
            except ValueError:
                pass

    # Handle last entry (no trailing ---)
    if current.get("loop_id") and current.get("action"):
        if after is None or current.get("ts", datetime.max.replace(tzinfo=timezone.utc)) > after:
            entries.append(current)

    return entries


def compute_delta(entries: list[dict]) -> tuple[int, bool]:
    """Compute suppressed delta: send→0 (full reset signal), store/silence→+1 each.

    Returns (delta, had_send). When a send occurs, the suppressed counter
    resets to 0, then any subsequent store/silence adds from there.
    """
    if not entries:
        return 0, False

    last_send_idx = -1
    for i, entry in enumerate(entries):
        if entry["action"] == "send":
            last_send_idx = i

    if last_send_idx >= 0:
        post_send_count = sum(
            1 for e in entries[last_send_idx + 1:]
            if e["action"] in ("store", "silence")
        )
        return post_send_count, True
    else:
        return sum(1 for e in entries if e["action"] in ("store", "silence")), False


def update_cursor(log_path: Path, latest_ts: str):
    """Update or insert the cursor marker in thoughts_log."""
    text = log_path.read_text(encoding="utf-8")
    cursor_line = f"<!-- loops_processed: {latest_ts} -->"

    if CURSOR_RE.search(text):
        text = CURSOR_RE.sub(cursor_line, text)
    else:
        lines = text.splitlines()
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.strip() and not line.strip().startswith("<!--"):
                insert_idx = i
                break
        lines.insert(insert_idx, cursor_line)
        text = "\n".join(lines)

    log_path.write_text(text, encoding="utf-8")


def enforce_sticky_weight(content: str) -> str:
    """Ensure weight >= 4 loops have sticky: true and expires_at: -."""
    lines = content.split("\n")
    result = []
    for line in lines:
        match = re.match(r"^- \*\*(.+?)\*\* \|(.+)$", line)
        if not match:
            result.append(line)
            continue

        loop_id = match.group(1)
        fields = match.group(2)

        weight_match = re.search(r"weight:\s*(\d+)", fields)
        if not weight_match or int(weight_match.group(1)) < 4:
            result.append(line)
            continue

        if "sticky:" in fields:
            fields = re.sub(r"sticky:\s*\w+", "sticky: true", fields)
        else:
            fields = fields.rstrip() + " | sticky: true"

        if "expires_at:" in fields:
            current_val = re.search(r"expires_at:\s*(\S+)", fields)
            if current_val and current_val.group(1).strip() == "-":
                pass  # already correct, skip to avoid git noise
            else:
                fields = re.sub(r"expires_at:\s*\S+", "expires_at: -", fields)

        result.append(f"- **{loop_id}** |{fields}")

    return "\n".join(result)


def main():
    if not ACTIVE_LOOPS_PATH.exists():
        return

    content = ACTIVE_LOOPS_PATH.read_text(encoding="utf-8")
    original_content = content
    content = enforce_sticky_weight(content)

    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    log_path = THOUGHTS_LOG_DIR / f"{today}.md"

    if log_path.exists():
        text = log_path.read_text(encoding="utf-8")
        cursor_match = CURSOR_RE.search(text)
        after = None
        if cursor_match:
            try:
                after = datetime.fromisoformat(cursor_match.group(1))
            except ValueError:
                after = None

        entries = parse_thoughts_log(log_path, after=after)
        if entries:
            by_loop: dict[str, list[dict]] = {}
            latest_ts = None
            for entry in entries:
                by_loop.setdefault(entry.get("loop_id", ""), []).append(entry)
                ts = entry.get("ts")
                if ts and (latest_ts is None or ts > latest_ts):
                    latest_ts = ts

            for loop_id, loop_entries in by_loop.items():
                if not loop_id or loop_id == "spontaneous":
                    continue

                line_pattern = re.compile(
                    rf"^- \*\*{re.escape(loop_id)}\*\* \|.+$", re.MULTILINE
                )
                match = line_pattern.search(content)
                if not match:
                    continue

                line = match.group(0)

                old = 0
                sup_match = re.search(r"\| suppressed: (\d+)", line)
                sup_any = re.search(r"\| suppressed: \S+", line)
                if sup_match:
                    try:
                        old = int(sup_match.group(1))
                    except ValueError:
                        old = 0

                delta, had_send = compute_delta(loop_entries)

                if had_send:
                    new_val = delta
                else:
                    new_val = old + delta

                if new_val == old and sup_match:
                    continue

                if sup_any:
                    base_line = line[:sup_any.start()] + line[sup_any.end():]
                else:
                    base_line = line
                new_line = base_line.rstrip() + f" | suppressed: {new_val}"

                content = content[:match.start()] + new_line + content[match.end():]

            if latest_ts:
                update_cursor(log_path, latest_ts.isoformat())

    if content != original_content:
        ACTIVE_LOOPS_PATH.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
