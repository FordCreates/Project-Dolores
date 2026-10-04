#!/usr/bin/env python3
"""Validate world_context.json before it is injected into the live session."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(os.environ.get("DOLORES_WORKSPACE", Path(__file__).resolve().parents[1]))
WORLD_CONTEXT = ROOT / "state/world_context.json"
EXPECTED_FIELDS = {
    "current_time",
    "day_of_week",
    "time_mode",
    "is_quiet_hours",
    "weather",
    "user_location",
    "user_activity",
    "scene",
    "dolores_activity",
    "dolores_appearance",
    "recommended_intensity",
    "hours_since_last_interaction",
    "recent_message_count_24h",
    "context_note",
}
TEXT_FIELDS = {
    "day_of_week",
    "time_mode",
    "weather",
    "user_location",
    "user_activity",
    "scene",
    "dolores_activity",
    "dolores_appearance",
    "recommended_intensity",
    "context_note",
}


def replacement_paths(value: object, prefix: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, str) and "\ufffd" in value:
        paths.append(prefix)
    elif isinstance(value, dict):
        for key, item in value.items():
            paths.extend(replacement_paths(item, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(replacement_paths(item, f"{prefix}[{index}]"))
    return paths


def validate_world_context(value: object) -> list[str]:
    if not isinstance(value, dict):
        return ["root must be an object"]
    errors: list[str] = []
    if set(value) != EXPECTED_FIELDS:
        errors.append(
            f"missing={sorted(EXPECTED_FIELDS - set(value))}; extra={sorted(set(value) - EXPECTED_FIELDS)}"
        )
    for field in TEXT_FIELDS:
        if not isinstance(value.get(field), str):
            errors.append(f"{field} must be a string")
    try:
        datetime.fromisoformat(value.get("current_time", "").replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        errors.append("current_time must be an ISO timestamp")
    if not isinstance(value.get("is_quiet_hours"), bool):
        errors.append("is_quiet_hours must be boolean")
    hours = value.get("hours_since_last_interaction")
    if isinstance(hours, bool) or not isinstance(hours, (int, float)) or hours < 0:
        errors.append("hours_since_last_interaction must be non-negative")
    count = value.get("recent_message_count_24h")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        errors.append("recent_message_count_24h must be a non-negative integer")
    damaged = replacement_paths(value)
    if damaged:
        errors.append("Unicode replacement character U+FFFD is forbidden at: " + ", ".join(damaged))
    return errors


def main() -> int:
    try:
        value = json.loads(WORLD_CONTEXT.read_text(encoding="utf-8"))
    except Exception as exc:
        print(json.dumps({"ok": False, "file": str(WORLD_CONTEXT), "errors": [str(exc)]}))
        return 1
    errors = validate_world_context(value)
    print(json.dumps({"ok": not errors, "file": str(WORLD_CONTEXT), "errors": errors}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
