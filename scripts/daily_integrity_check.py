#!/usr/bin/env python3
"""Deterministic integrity checks and lossless repairs for a Dolores workspace."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
WORLD_FIELDS = {
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
AFFECT_FIELDS = {
    "valence",
    "arousal",
    "warmth",
    "concern",
    "energy",
    "vulnerability",
    "distance_sensitivity",
    "playfulness",
    "horny",
}
CARD_FILES = ("shared-history.md", "quirks.md", "taste.md", "shared-language.md", "routines.md")
SELF_HEADER = "# Self-Narrative — My Story\n\n*The voice in my head after the lights go out.*\n\n---\n"
REL_HEADER = "# Relationship Summary — Our Story\n"


@dataclass
class Finding:
    code: str
    path: str
    detail: str
    model_repairable: bool = False


@dataclass
class Repair:
    code: str
    path: str
    detail: str


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


def parse_time(raw: str, zone: ZoneInfo) -> datetime:
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=zone)
    return value.astimezone(zone)


class Auditor:
    def __init__(self, root: Path, mode: str, now: datetime, repair: bool, health_enabled: bool):
        self.root = root.resolve()
        self.mode = mode
        self.now = now
        self.zone = now.tzinfo
        self.repair_enabled = repair
        self.health_enabled = health_enabled
        self.findings: list[Finding] = []
        self.repairs: list[Repair] = []
        self.checked: list[str] = []

    def label(self, path: Path) -> str:
        return str(path.resolve().relative_to(self.root))

    def finding(self, code: str, path: Path, detail: str, *, model_repairable: bool = False) -> None:
        item = Finding(code, self.label(path), detail, model_repairable)
        if item not in self.findings:
            self.findings.append(item)

    def text(self, relative: str, *, required: bool = True, newline: bool = True) -> str | None:
        path = self.root / relative
        if not path.is_file():
            if required:
                self.finding("missing_file", path, "required artifact is missing")
            return None
        self.checked.append(relative)
        try:
            raw = path.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                if self.repair_enabled:
                    raw = raw[3:]
                    atomic_write(path, raw.decode("utf-8"))
                    self.repairs.append(Repair("utf8_bom_removed", relative, "removed UTF-8 BOM"))
                else:
                    self.finding("utf8_bom", path, "UTF-8 BOM should be removed")
            content = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            self.finding("unreadable_text", path, str(exc))
            return None
        if "\ufffd" in content:
            self.finding(
                "replacement_character",
                path,
                f"contains {content.count(chr(0xfffd))} Unicode replacement character(s)",
                model_repairable=True,
            )
        if newline and content and not content.endswith("\n"):
            if self.repair_enabled:
                content += "\n"
                atomic_write(path, content)
                self.repairs.append(Repair("terminal_newline_added", relative, "added missing terminal newline"))
            else:
                self.finding("missing_terminal_newline", path, "text file must end with a newline")
        return content

    def json_file(self, relative: str) -> Any:
        content = self.text(relative)
        if content is None:
            return None
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            self.finding("invalid_json", self.root / relative, str(exc), model_repairable=True)
            return None

    def check_world(self, *, require_weather: bool) -> None:
        path = self.root / "state/world_context.json"
        value = self.json_file("state/world_context.json")
        if not isinstance(value, dict):
            if value is not None:
                self.finding("world_root_type", path, "world_context root must be an object")
            return
        if set(value) != WORLD_FIELDS:
            self.finding(
                "world_schema",
                path,
                f"missing={sorted(WORLD_FIELDS - set(value))}; extra={sorted(set(value) - WORLD_FIELDS)}",
            )
        for field in ("day_of_week", "time_mode", "weather", "user_location", "user_activity", "scene", "dolores_activity", "dolores_appearance", "recommended_intensity", "context_note"):
            if not isinstance(value.get(field), str):
                self.finding("world_type", path, f"{field} must be a string")
        if not isinstance(value.get("is_quiet_hours"), bool):
            self.finding("world_type", path, "is_quiet_hours must be boolean")
        hours = value.get("hours_since_last_interaction")
        if isinstance(hours, bool) or not isinstance(hours, (int, float)) or hours < 0:
            self.finding("world_type", path, "hours_since_last_interaction must be non-negative")
        count = value.get("recent_message_count_24h")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            self.finding("world_type", path, "recent_message_count_24h must be a non-negative integer")
        try:
            current = parse_time(value.get("current_time", ""), self.zone)
            if self.mode == "close" and current.date() != self.now.date():
                self.finding("world_date_mismatch", path, f"current_time date is {current.date()}, expected {self.now.date()}")
        except (TypeError, ValueError):
            self.finding("world_time", path, "current_time must be an ISO timestamp")
        if require_weather and not str(value.get("weather", "")).strip():
            self.finding("missing_weather", path, "nightly Reflection completed but weather is empty")

    def check_affect(self) -> None:
        path = self.root / "state/affect.json"
        value = self.json_file("state/affect.json")
        if not isinstance(value, dict):
            if value is not None:
                self.finding("affect_root_type", path, "affect root must be an object")
            return
        if set(value) != AFFECT_FIELDS:
            self.finding("affect_schema", path, "affect fields do not match the reference schema")
        for field in AFFECT_FIELDS:
            number = value.get(field)
            if isinstance(number, bool) or not isinstance(number, (int, float)) or not 0 <= number <= 1:
                self.finding("affect_value", path, f"{field} must be a number from 0 to 1")

    def check_timestamp(self, day: date | None = None) -> None:
        path = self.root / "state/last_sync_at"
        content = self.text("state/last_sync_at", newline=False)
        if content is None:
            return
        try:
            value = parse_time(content.strip(), self.zone)
        except ValueError:
            self.finding("invalid_timestamp", path, "expected one ISO timestamp")
            return
        if day and value.date() != day:
            self.finding("timestamp_date_mismatch", path, f"timestamp date is {value.date()}, expected {day}")

    def check_thought_log(self, day: date) -> None:
        relative = f"state/thoughts_log/{day.isoformat()}.md"
        content = self.text(relative, required=False)
        if content is None:
            return
        path = self.root / relative
        repaired = re.sub(r"([^\n])(?=---\n(?:time|时间):)", r"\1\n", content)
        if repaired != content:
            if self.repair_enabled:
                atomic_write(path, repaired)
                self.repairs.append(Repair("thought_record_separated", relative, "moved glued record delimiter to its own line"))
            else:
                self.finding("thought_record_glued", path, "thought record delimiter is glued to previous content")

    def check_plan(self, day: date, *, required_date: bool) -> None:
        path = self.root / "state/daily_plan.md"
        content = self.text("state/daily_plan.md")
        if content is None:
            return
        first = content.splitlines()[0] if content.splitlines() else ""
        if not required_date and first == "# Daily Plan — Dolores's Day":
            return
        if not re.fullmatch(rf"# {day.isoformat()} \(.+\) Schedule", first):
            self.finding("plan_date", path, f"first line must be the {day.isoformat()} schedule title")

    def check_health(self, day: date) -> None:
        relative = f"memory/health/{day.isoformat()}.md"
        content = self.text(relative)
        if content is None:
            return
        path = self.root / relative
        if not content.startswith(f"## {day.isoformat()}\n"):
            self.finding("health_date", path, f"first line must be ## {day.isoformat()}")
        for heading in ("Sleep", "Exercise", "Diet", "Medication", "Symptoms"):
            if len(re.findall(rf"(?m)^### {heading}\s*$", content)) != 1:
                self.finding("health_section", path, f"expected exactly one ### {heading} section")
        self.text(f"memory/exercise/{day.isoformat()}.md", required=False)

    def check_trace(self, day: date) -> None:
        path = self.root / "reflection_trace.md"
        content = self.text("reflection_trace.md")
        if content is None:
            return
        dates = re.findall(r"(?m)^generated_at:\s*(\d{4}-\d{2}-\d{2})", content)
        if not dates or dates[-1] != day.isoformat():
            self.finding("reflection_trace_date", path, f"latest generated_at must belong to {day}")

    def check_reflection(self, day: date, kind: str) -> None:
        prefix = "self" if kind == "self" else "rel"
        parts: list[str] = []
        for number in range(1, 6):
            relative = f"state/slots/{day.isoformat()}/{prefix}_slot_{number}.md"
            content = self.text(relative)
            if content is not None:
                if not content.strip():
                    self.finding("reflection_slot_empty", self.root / relative, "slot must not be empty")
                parts.append(content)
        final_relative = "memory/self-narrative.md" if kind == "self" else "memory/relationship-summary.md"
        final = self.text(final_relative)
        if len(parts) != 5 or final is None:
            return
        expected = (SELF_HEADER if kind == "self" else REL_HEADER) + "".join(parts)
        if final != expected:
            path = self.root / final_relative
            if self.repair_enabled:
                atomic_write(path, expected)
                self.repairs.append(Repair("reflection_final_reassembled", final_relative, f"rebuilt {kind} final from existing slots"))
            else:
                self.finding("reflection_final_mismatch", path, f"{kind} final does not match its five slots")

    def common(self, *, require_weather: bool, sync_day: date | None = None) -> None:
        self.check_world(require_weather=require_weather)
        self.check_affect()
        self.text("state/active_loops.md")
        pending = self.text("state/pending_message.md", newline=False)
        if pending is not None and not pending.strip():
            self.finding("pending_empty", self.root / "state/pending_message.md", "use EMPTY or a message")
        self.check_timestamp(sync_day)

    def run(self) -> dict[str, Any]:
        current = self.now.date()
        if self.mode == "incremental":
            self.common(require_weather=False)
            self.text(f"diary/{current.isoformat()}.md", required=False)
            self.check_thought_log(current)
            self.check_plan(current, required_date=False)
            if self.health_enabled and self.now.timetz().replace(tzinfo=None) >= time(20, 10):
                self.check_health(current)
            closed_day = None
        else:
            closed = current - timedelta(days=1)
            closed_day = closed.isoformat()
            self.common(require_weather=True, sync_day=current)
            self.text(f"diary/{closed.isoformat()}.md")
            self.text(f"memory/{closed.isoformat()}.digest.md")
            self.check_thought_log(closed)
            self.check_thought_log(current)
            if self.health_enabled:
                self.check_health(closed)
            self.check_trace(closed)
            self.text("state/current_interests.md")
            self.check_plan(current, required_date=True)
            self.check_reflection(closed, "self")
            self.check_reflection(closed, "rel")
            self.text("memory/profile-user.md")
            for card in CARD_FILES:
                self.text(f"memory/cards/{card}")
        return {
            "ok": not self.findings,
            "mode": self.mode,
            "run_at": self.now.isoformat(timespec="seconds"),
            "closed_day": closed_day,
            "health_enabled": self.health_enabled,
            "checked": sorted(set(self.checked)),
            "repairs": [asdict(item) for item in self.repairs],
            "findings": [asdict(item) for item in self.findings],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("incremental", "close"))
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--timezone", default="UTC", help="IANA timezone used for date ownership")
    parser.add_argument("--now", help="ISO timestamp override for testing")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--health-enabled", action="store_true")
    args = parser.parse_args()
    zone = ZoneInfo(args.timezone)
    now = parse_time(args.now, zone) if args.now else datetime.now(zone)
    report = Auditor(args.root, args.mode, now, args.repair, args.health_enabled).run()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
