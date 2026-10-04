#!/usr/bin/env python3
"""Deterministic integrity audit and safe repair for Dolores runtime artifacts.

Two modes are intentionally separate:

* ``incremental`` checks the current day's Heartbeat/state outputs and, after
  20:00, the Health Checkin outputs.
* ``close`` treats yesterday as the closed diary/health/reflection day while
  checking today's midnight Heartbeat state and today's newly generated plan.

Only lossless mechanical repairs are performed: UTF-8 BOM removal, missing
terminal newlines, thought-trace marker separation, deterministic interests
rendering, and deterministic Self/Relationship reassembly from already-valid
slots.  Missing or malformed content is reported and never invented here.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo


TZ = datetime.now().astimezone().tzinfo
DEFAULT_ROOT = Path(os.environ.get("DOLORES_WORKSPACE", Path(__file__).resolve().parents[1]))
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
PERIODS = ("Morning", "Afternoon", "Evening")
PERIOD_RANGES = {
    "Morning": (5 * 60, 12 * 60),
    "Afternoon": (12 * 60, 18 * 60),
    "Evening": (18 * 60, 24 * 60),
}

WORLD_FIELDS = {
    "current_time",
    "time_mode",
    "day_of_week",
    "is_quiet_hours",
    "hours_since_last_interaction",
    "recent_message_count_24h",
    "recommended_intensity",
    "user_location",
    "user_activity",
    "scene",
    "weather",
    "dolores_activity",
    "dolores_appearance",
    "context_note",
}
WORLD_ENUMS = {
    "time_mode": {"early_morning", "morning", "afternoon", "evening", "late_evening", "deep_night"},
    "day_of_week": {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"},
    "recommended_intensity": {"gentle_checkin", "soft_low_pressure", "normal", "warm", "flirty"},
    "user_location": {"home", "office", "cafe", "commuting", "outdoor", "restaurant", "other", "unknown"},
    "user_activity": {
        "working",
        "gaming",
        "creative_work",
        "meeting",
        "exercising",
        "resting",
        "eating",
        "commuting",
        "socializing",
        "family_time",
        "other",
        "unknown",
    },
}
WORLD_TEXT_FIELDS = {"scene", "weather", "dolores_activity", "dolores_appearance", "context_note"}
AFFECT_FIELDS = {
    "valence",
    "arousal",
    "energy",
    "warmth",
    "concern",
    "playfulness",
    "horny",
    "vulnerability",
    "distance_sensitivity",
}
THOUGHT_FIELDS = {
    "time",
    "loop_id",
    "thought",
    "expression_draft",
    "visibility",
    "expression_candidate",
    "candidate_kind",
    "send_basis",
    "action",
    "reason",
}
CARD_FILES = (
    "shared-history.md",
    "quirks.md",
    "taste.md",
    "shared-language.md",
    "routines.md",
    "pets.md",
    "people.md",
)
REFLECTION_SPECS: dict[str, dict[str, Any]] = {
    "self": {
        "prefix": "self_slot_",
        "final": "memory/self-narrative.md",
        "document_header": "# Self-Narrative — My Story\n\n*The voice in my head after the lights go out.*\n\n---\n",
        "titles": {1: None, 2: "## Recent Fractures", 3: "## Recurring Patterns", 4: "## Unresolved Tensions", 5: "## Current Self"},
        "budgets": {1: (250, 350), 2: (250, 350), 3: (200, 300), 4: (200, 300), 5: (250, 350)},
    },
    "rel": {
        "prefix": "rel_slot_",
        "final": "memory/relationship-summary.md",
        "document_header": "# Relationship Summary — Our Story\n",
        "titles": {1: "## Relationship Foundation", 2: "## Key Turning Points", 3: "## Current Patterns", 4: "## Mutual Confirmations", 5: "## Relational Tensions"},
        "budgets": {1: (200, 250), 2: (300, 400), 3: (250, 350), 4: (200, 300), 5: (250, 350)},
    },
}


@dataclass
class Finding:
    code: str
    path: str
    detail: str
    severity: str = "error"
    model_repairable: bool = False


@dataclass
class Repair:
    code: str
    path: str
    detail: str


def parse_datetime(raw: str) -> datetime:
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=TZ)
    return value.astimezone(TZ)


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


class Auditor:
    def __init__(self, root: Path, mode: str, now: datetime, repair: bool, verify_checkpoints: bool):
        self.root = root.resolve()
        self.mode = mode
        self.now = now
        self.repair_enabled = repair
        self.verify_checkpoints = verify_checkpoints
        self.health_enabled = False
        self.findings: list[Finding] = []
        self.repairs: list[Repair] = []
        self.checked: list[str] = []
        self.skipped_reason: str | None = None

    def relative(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.root))
        except ValueError:
            return str(path)

    def finding(
        self,
        code: str,
        path: Path | str,
        detail: str,
        *,
        severity: str = "error",
        model_repairable: bool = False,
    ) -> None:
        label = path if isinstance(path, str) else self.relative(path)
        item = Finding(code, label, detail, severity, model_repairable)
        if item not in self.findings:
            self.findings.append(item)

    def repaired(self, code: str, path: Path, detail: str) -> None:
        self.repairs.append(Repair(code, self.relative(path), detail))

    def text(
        self,
        relative: str,
        *,
        required: bool = True,
        terminal_newline: bool = True,
    ) -> str | None:
        path = self.root / relative
        if not path.exists():
            if required:
                self.finding("missing_file", path, "required artifact is missing")
            return None
        if not path.is_file():
            self.finding("not_a_file", path, "artifact path is not a regular file")
            return None
        self.checked.append(relative)
        try:
            raw = path.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                if self.repair_enabled:
                    raw = raw[3:]
                    try:
                        decoded = raw.decode("utf-8")
                    except UnicodeDecodeError as exc:
                        self.finding("invalid_utf8", path, str(exc), model_repairable=False)
                        return None
                    atomic_write(path, decoded)
                    self.repaired("utf8_bom_removed", path, "removed UTF-8 BOM")
                else:
                    self.finding("utf8_bom", path, "UTF-8 BOM should be removed")
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                self.finding("invalid_utf8", path, str(exc), model_repairable=False)
                return None
        except OSError as exc:
            self.finding("read_failed", path, str(exc))
            return None

        if "\ufffd" in content:
            count = content.count("\ufffd")
            self.finding(
                "replacement_character",
                path,
                f"contains {count} Unicode replacement character(s)",
                model_repairable=True,
            )

        if terminal_newline and content and not content.endswith("\n"):
            if self.repair_enabled:
                content += "\n"
                atomic_write(path, content)
                self.repaired("terminal_newline_added", path, "added missing terminal newline")
            else:
                self.finding("missing_terminal_newline", path, "text file must end with a newline")
        return content

    def json_file(
        self,
        relative: str,
        *,
        required: bool = True,
        validator: Callable[[Any, Path], None] | None = None,
    ) -> Any:
        content = self.text(relative, required=required, terminal_newline=True)
        if content is None:
            return None
        path = self.root / relative
        try:
            value = json.loads(content)
        except json.JSONDecodeError as exc:
            self.finding("invalid_json", path, str(exc), model_repairable=True)
            return None
        if validator:
            validator(value, path)
        return value

    def validate_world(self, value: Any, path: Path, *, require_weather: bool = False) -> None:
        if not isinstance(value, dict):
            self.finding("world_root_type", path, "world_context root must be an object")
            return
        actual = set(value)
        if actual != WORLD_FIELDS:
            missing = sorted(WORLD_FIELDS - actual)
            extra = sorted(actual - WORLD_FIELDS)
            self.finding("world_schema", path, f"missing={missing}; extra={extra}")
        for field, allowed in WORLD_ENUMS.items():
            if value.get(field) not in allowed:
                self.finding("world_enum", path, f"{field} has invalid value {value.get(field)!r}")
        try:
            parse_datetime(value.get("current_time", ""))
        except (TypeError, ValueError):
            self.finding("world_time", path, "current_time must be an ISO timestamp")
        if not isinstance(value.get("is_quiet_hours"), bool):
            self.finding("world_type", path, "is_quiet_hours must be boolean")
        hours = value.get("hours_since_last_interaction")
        if isinstance(hours, bool) or not isinstance(hours, (int, float)) or hours < 0:
            self.finding("world_type", path, "hours_since_last_interaction must be non-negative")
        count = value.get("recent_message_count_24h")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            self.finding("world_type", path, "recent_message_count_24h must be a non-negative integer")
        for field in WORLD_TEXT_FIELDS:
            if not isinstance(value.get(field), str):
                self.finding("world_type", path, f"{field} must be a string")
        if require_weather and not str(value.get("weather", "")).strip():
            self.finding(
                "missing_weather",
                path,
                "nightly Reflection completed but world_context.weather is empty",
                model_repairable=False,
            )

    def validate_affect(self, value: Any, path: Path) -> None:
        if not isinstance(value, dict):
            self.finding("affect_root_type", path, "affect root must be an object")
            return
        actual = set(value)
        if actual != AFFECT_FIELDS:
            self.finding(
                "affect_schema",
                path,
                f"missing={sorted(AFFECT_FIELDS - actual)}; extra={sorted(actual - AFFECT_FIELDS)}",
            )
        for field in AFFECT_FIELDS:
            number = value.get(field)
            if isinstance(number, bool) or not isinstance(number, (int, float)) or not 0 <= number <= 1:
                self.finding("affect_value", path, f"{field} must be a number from 0 to 1")

    def validate_lifecycle(self, value: Any, path: Path) -> None:
        if not isinstance(value, dict) or value.get("mode") not in {"active", "paused", "resuming"}:
            self.finding("lifecycle_schema", path, "lifecycle.mode must be active, paused, or resuming")

    def validate_thought_trace(self, value: Any, path: Path) -> None:
        if not isinstance(value, dict):
            self.finding("thought_trace_schema", path, "thought trace root must be an object")
            return
        if value.get("stage") != "finalized":
            self.finding("thought_trace_incomplete", path, f"stage is {value.get('stage')!r}, expected finalized")
        try:
            parse_datetime(value.get("created_at", ""))
        except (TypeError, ValueError):
            self.finding("thought_trace_time", path, "created_at must be an ISO timestamp")
        if not isinstance(value.get("slots"), dict):
            self.finding("thought_trace_schema", path, "slots must be an object")

    def check_timestamp(self, relative: str, *, expected_date: date | None = None) -> datetime | None:
        content = self.text(relative, terminal_newline=False)
        if content is None:
            return None
        path = self.root / relative
        try:
            value = parse_datetime(content.strip())
        except (TypeError, ValueError):
            self.finding("invalid_timestamp", path, "expected one ISO-8601 timestamp")
            return None
        if expected_date and value.date() != expected_date:
            self.finding("timestamp_date_mismatch", path, f"timestamp date is {value.date()}, expected {expected_date}")
        if value > self.now + timedelta(minutes=5):
            self.finding("future_timestamp", path, f"timestamp {value.isoformat()} is in the future")
        return value

    def check_diary(self, day: date, *, required: bool) -> None:
        relative = f"memory/diary/{day.isoformat()}.md"
        content = self.text(relative, required=required)
        if content is None:
            return
        expected = f"# {day.isoformat()} ({WEEKDAYS[day.weekday()]})"
        first = content.splitlines()[0] if content.splitlines() else ""
        if not re.fullmatch(rf"{re.escape(expected)}(?: · [^\r\n]+)?", first):
            self.finding(
                "diary_header",
                self.root / relative,
                f"first line must be {expected!r}, optionally followed by a non-empty ' · title' suffix",
            )

    def check_thought_log(self, day: date, *, required: bool = False) -> None:
        relative = f"state/thoughts_log/{day.isoformat()}.md"
        content = self.text(relative, required=required)
        if content is None:
            return
        path = self.root / relative
        glued = re.search(r"[^\n]<!-- thought_trace_run_id:", content)
        if glued:
            if self.repair_enabled:
                repaired = re.sub(r"([^\n])(?=<!-- thought_trace_run_id:)", r"\1\n", content)
                atomic_write(path, repaired)
                content = repaired
                self.repaired("thought_marker_separated", path, "moved glued thought_trace marker to its own line")
            else:
                self.finding("thought_marker_glued", path, "thought_trace marker is glued to the previous record")
        for line_number, line in enumerate(content.splitlines(), start=1):
            if "<!-- thought_trace_run_id:" in line and not re.fullmatch(
                r"<!-- thought_trace_run_id: .+ -->", line
            ):
                self.finding("thought_marker_format", path, f"malformed marker on line {line_number}")
        for raw_record in re.split(r"(?m)^---\s*$", content):
            if not re.search(r"(?m)^time:\s*", raw_record):
                continue
            present = {
                match.group(1)
                for match in re.finditer(r"(?m)^([^:\n]+):\s*", raw_record)
                if match.group(1) in THOUGHT_FIELDS
            }
            missing = sorted(THOUGHT_FIELDS - present)
            if missing:
                self.finding("thought_record_fields", path, f"record is missing fields: {missing}")
            match = re.search(r"(?m)^time:\s*(\d{4}-\d{2}-\d{2})T", raw_record)
            if match and match.group(1) != day.isoformat():
                self.finding(
                    "thought_record_date",
                    path,
                    f"record date {match.group(1)} does not match filename date {day.isoformat()}",
                )

    def check_health(self, day: date, *, required: bool) -> None:
        relative = f"memory/health/{day.isoformat()}.md"
        content = self.text(relative, required=required)
        if content is None:
            return
        path = self.root / relative
        lines = content.splitlines()
        expected = f"## {day.isoformat()}"
        if not lines or lines[0] != expected:
            self.finding("health_header", path, f"first line must be {expected!r}")
        completeness = re.search(r"(?m)^\*\*completeness:\*\*\s*(\S+)\s*$", content)
        if not completeness or completeness.group(1) not in {"full", "partial", "empty"}:
            self.finding("health_completeness", path, "completeness must be full, partial, or empty")
        source = re.search(r"(?m)^\*\*data_source:\*\*\s*(\S+)\s*$", content)
        allowed_sources = {"conversation", "diary_inference", "mixed", "diary_inference/mixed"}
        if not source or source.group(1) not in allowed_sources:
            self.finding(
                "health_data_source",
                path,
                "data_source must be conversation, diary_inference, mixed, or diary_inference/mixed",
            )
        for heading in ("Sleep", "Exercise", "Diet", "Medication", "Symptoms"):
            if len(re.findall(rf"(?m)^### {re.escape(heading)}\s*$", content)) != 1:
                self.finding("health_section", path, f"expected exactly one ### {heading} section")

    def check_exercise(self, day: date) -> None:
        relative = f"memory/exercise/{day.isoformat()}.md"
        content = self.text(relative, required=False)
        if content is None:
            return
        path = self.root / relative
        lines = content.splitlines()
        expected = f"## {day.isoformat()}"
        if not lines or lines[0] != expected:
            self.finding("exercise_header", path, f"first line must be {expected!r}")
        if not any(line.startswith("- ") for line in lines[1:]):
            self.finding("exercise_entries", path, "exercise file must contain at least one bullet")

    def check_plan(self, day: date, *, require_all_periods: bool) -> str | None:
        relative = "state/daily_plan.md"
        content = self.text(relative)
        if content is None:
            return None
        repaired = self.rebucket_plan_entries(content, day)
        if repaired is not None and repaired != content:
            path = self.root / relative
            if self.repair_enabled:
                atomic_write(path, repaired)
                content = repaired
                self.repaired(
                    "plan_entries_rebucketed",
                    path,
                    "moved timestamped entries to their deterministic time periods",
                )
        self.validate_plan_content(content, self.root / relative, day, require_all_periods=require_all_periods)
        return content

    @staticmethod
    def rebucket_plan_entries(content: str, day: date) -> str | None:
        lines = content.replace("\r\n", "\n").strip().split("\n")
        expected_title = f"# {day.isoformat()} ({WEEKDAYS[day.weekday()]}) Schedule"
        if not lines or lines[0].strip() != expected_title:
            return None
        headings: list[str] = []
        current: str | None = None
        entries: list[tuple[str, int, str]] = []
        needs_repair = False
        for raw_line in lines[1:]:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("## "):
                period = line[3:].strip()
                if period not in PERIODS or period in headings:
                    return None
                if headings and PERIODS.index(period) <= PERIODS.index(headings[-1]):
                    return None
                headings.append(period)
                current = period
                continue
            match = re.fullmatch(r"-\s+([0-2]\d:[0-5]\d)\s+(.+)", line)
            if current is None or not match:
                return None
            raw_time, description = match.groups()
            hour, minute = map(int, raw_time.split(":"))
            value = hour * 60 + minute
            target = next(
                (period for period, (lower, upper) in PERIOD_RANGES.items() if lower <= value < upper),
                None,
            )
            if target is None:
                return None
            if target != current:
                needs_repair = True
            entries.append((target or "", value, f"- {raw_time} {description}"))
        if not needs_repair:
            return content
        if any(not target or target not in headings for target, _, _ in entries):
            return None
        grouped = {period: [] for period in headings}
        for target, value, line in entries:
            grouped[target].append((value, line))
        if any(not grouped[period] for period in headings):
            return None
        output = [expected_title, ""]
        for period in headings:
            output.extend([f"## {period}", ""])
            output.extend(line for _, line in sorted(grouped[period], key=lambda item: item[0]))
            output.append("")
        return "\n".join(output).rstrip() + "\n"

    def validate_plan_content(self, content: str, path: Path, day: date, *, require_all_periods: bool) -> None:
        raw = content.replace("\r\n", "\n").strip()
        expected_title = f"# {day.isoformat()} ({WEEKDAYS[day.weekday()]}) Schedule"
        lines = raw.split("\n") if raw else []
        if not lines or lines[0].strip() != expected_title:
            self.finding("plan_title", path, f"title must be exactly {expected_title!r}")
            return
        seen_periods: list[str] = []
        current: str | None = None
        seen_times: set[str] = set()
        period_times: dict[str, list[int]] = {period: [] for period in PERIODS}
        for line_number, raw_line in enumerate(lines[1:], start=2):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("## "):
                period = line[3:].strip()
                if period not in PERIODS:
                    self.finding("plan_period", path, f"unknown period {period!r} on line {line_number}")
                    current = None
                    continue
                if period in seen_periods or (seen_periods and PERIODS.index(period) <= PERIODS.index(seen_periods[-1])):
                    self.finding("plan_period_order", path, "period headings must be unique and chronological")
                seen_periods.append(period)
                current = period
                continue
            if current is None:
                self.finding("plan_entry_position", path, f"content before a period heading on line {line_number}")
                continue
            match = re.fullmatch(r"-\s+([0-2]\d:[0-5]\d)\s+(.+)", line)
            if not match:
                self.finding("plan_entry_format", path, f"invalid entry on line {line_number}")
                continue
            raw_time, description = match.groups()
            hour, minute = map(int, raw_time.split(":"))
            value = hour * 60 + minute
            lower, upper = PERIOD_RANGES[current]
            if not lower <= value < upper:
                self.finding("plan_entry_period", path, f"{raw_time} does not belong to {current}")
            if raw_time in seen_times:
                self.finding("plan_duplicate_time", path, f"duplicate time {raw_time}")
            if not description.strip():
                self.finding("plan_empty_entry", path, f"empty activity on line {line_number}")
            seen_times.add(raw_time)
            period_times[current].append(value)
        if require_all_periods and tuple(seen_periods) != PERIODS:
            self.finding("plan_periods_missing", path, "close mode requires Morning, Afternoon, Evening in order")
        for period in seen_periods:
            values = period_times[period]
            if not values:
                self.finding("plan_empty_period", path, f"{period} has no entries")
            if values != sorted(values):
                self.finding("plan_time_order", path, f"{period} entries are not chronological")

    def validate_interests(self, value: Any, path: Path) -> None:
        if not isinstance(value, dict) or set(value) != {"version", "updated_at", "active", "cooldowns"}:
            self.finding("interests_schema", path, "current_interests.json has an unexpected schema")
            return
        if value.get("version") != 1 or not isinstance(value.get("active"), list) or not isinstance(value.get("cooldowns"), list):
            self.finding("interests_schema", path, "unsupported interests version or list fields")

    @staticmethod
    def render_interests(value: dict[str, Any]) -> str:
        lines = [
            "# Current Interests — Recent Sparks",
            "",
            "> `scripts/plan_gate.py` is the sole writer. Plan receives seeds in its frozen context bundle.",
            "> Seeds are consumed once. Completed or scheduled topics cool down until explicit new future intent.",
            "",
            "## Available Seeds",
            "",
        ]
        active = value.get("active", [])
        if active:
            for item in active:
                lines.append(
                    f"- `{item['id']}` · `{item['topic']}` · [{item['source_date']}] "
                    f"{item['label']} — {item['summary']}"
                )
        else:
            lines.append("- None")
        lines.extend(["", "## Cooldown Topics (Prep deduplication only)", ""])
        cooldowns = value.get("cooldowns", [])
        if cooldowns:
            for item in cooldowns:
                aliases = " / ".join(item.get("aliases", [])) or item["label"]
                lines.append(
                    f"- `{item['topic']}` · {aliases} · since {item['since']} · {item['reason']} "
                    "· Reactivate only with explicit new future intent"
                )
        else:
            lines.append("- None")
        return "\n".join(lines) + "\n"

    def check_interests_pair(self) -> None:
        value = self.json_file("state/current_interests.json", validator=self.validate_interests)
        markdown = self.text("state/current_interests.md")
        if not isinstance(value, dict) or markdown is None:
            return
        try:
            rendered = self.render_interests(value)
        except (KeyError, TypeError) as exc:
            self.finding("interests_item_schema", self.root / "state/current_interests.json", str(exc))
            return
        if markdown != rendered:
            path = self.root / "state/current_interests.md"
            if self.repair_enabled:
                atomic_write(path, rendered)
                self.repaired("interests_markdown_rebuilt", path, "rebuilt Markdown deterministically from JSON")
            else:
                self.finding("interests_pair_mismatch", path, "Markdown does not match current_interests.json")

    def slot_path(self, kind: str, day: date, slot: int) -> Path:
        return self.root / "state/slots" / day.isoformat() / f"{REFLECTION_SPECS[kind]['prefix']}{slot}.md"

    def check_reflection_slots(self, kind: str, day: date) -> list[str] | None:
        spec = REFLECTION_SPECS[kind]
        contents: list[str] = []
        valid = True
        for slot in range(1, 6):
            path = self.slot_path(kind, day, slot)
            relative = self.relative(path)
            content = self.text(relative)
            if content is None:
                valid = False
                continue
            contents.append(content.rstrip("\n"))
            first = content.splitlines()[0] if content.splitlines() else ""
            expected_title = spec["titles"][slot]
            if expected_title is None:
                if first.startswith("## "):
                    self.finding("reflection_slot_title", path, "opening Self slot must not start with a section title")
                    valid = False
            elif first != expected_title:
                self.finding("reflection_slot_title", path, f"first line must be {expected_title!r}")
                valid = False
            lower, upper = spec["budgets"][slot]
            count = len(content.split())
            if not lower <= count <= upper:
                self.finding("reflection_slot_budget", path, f"{count} words; expected {lower}-{upper}")
                valid = False
        return contents if valid and len(contents) == 5 else None

    @staticmethod
    def assemble_reflection(kind: str, parts: list[str]) -> str:
        spec = REFLECTION_SPECS[kind]
        if kind == "self":
            return spec["document_header"] + parts[0] + "\n---\n\n" + "\n\n---\n\n".join(parts[1:]) + "\n"
        return spec["document_header"] + "\n\n---\n\n".join(parts) + "\n"

    def check_reflection_final(self, kind: str, day: date) -> None:
        parts = self.check_reflection_slots(kind, day)
        final_relative = REFLECTION_SPECS[kind]["final"]
        final = self.text(final_relative)
        if parts is None or final is None:
            return
        expected = self.assemble_reflection(kind, parts)
        if final != expected:
            path = self.root / final_relative
            if self.repair_enabled:
                atomic_write(path, expected)
                self.repaired("reflection_final_reassembled", path, f"rebuilt {kind} final from validated slots")
            else:
                self.finding("reflection_final_mismatch", path, f"{kind} final does not match validated slots")

    def check_reflection_trace(self, closed_day: date) -> None:
        content = self.text("reflection_trace.md")
        if content is None:
            return
        path = self.root / "reflection_trace.md"

        canonical_tension = re.compile(r"(?m)^## Tension Routing[ \t]*$")
        legacy_tension = re.compile(r"(?m)^### 4d\. Tension Routing[ \t]*$")
        legacy_matches = list(legacy_tension.finditer(content))
        if not canonical_tension.search(content) and len(legacy_matches) == 1 and self.repair_enabled:
            content = legacy_tension.sub("## Tension Routing", content, count=1)
            atomic_write(path, content)
            self.repaired(
                "reflection_trace_heading_normalized",
                path,
                "normalized exact legacy '### 4d. Tension Routing' heading to canonical '## Tension Routing'",
            )

        generated = re.findall(r"(?m)^generated_at:\s*(\d{4}-\d{2}-\d{2})(?:T[^\s]+)?\s*$", content)
        if not generated or generated[-1] != closed_day.isoformat():
            self.finding(
                "reflection_trace_date",
                path,
                f"latest generated_at is {generated[-1] if generated else 'missing'}, expected {closed_day}",
            )
        for heading in ("RAG Phase", "Analysis and Decision", "Tension Routing"):
            if not re.search(rf"(?m)^## {re.escape(heading)}\s*$", content):
                self.finding("reflection_trace_section", path, f"missing ## {heading}")

    def check_close_json(self, closed_day: date, plan_day: date) -> None:
        user_context = self.json_file("state/plan_user_context.json")
        if isinstance(user_context, dict):
            if user_context.get("version") != 1 or not isinstance(user_context.get("items"), list):
                self.finding("plan_user_context_schema", self.root / "state/plan_user_context.json", "invalid schema")
            if user_context.get("generated_on") != closed_day.isoformat():
                self.finding("plan_user_context_date", self.root / "state/plan_user_context.json", "generated_on mismatch")
            if user_context.get("plan_date") != plan_day.isoformat():
                self.finding("plan_user_context_date", self.root / "state/plan_user_context.json", "plan_date mismatch")

        plan_gate = self.json_file("state/plan_gate.json")
        if isinstance(plan_gate, dict):
            expected = {
                "version": 3,
                "run_date": closed_day.isoformat(),
                "plan_date": plan_day.isoformat(),
                "stage": "finalized",
            }
            for key, value in expected.items():
                if plan_gate.get(key) != value:
                    self.finding("plan_gate_state", self.root / "state/plan_gate.json", f"{key}={plan_gate.get(key)!r}, expected {value!r}")
            if not isinstance(plan_gate.get("eligible_interest_ids"), list) or not isinstance(
                plan_gate.get("used_interest_ids"), list
            ):
                self.finding("plan_gate_schema", self.root / "state/plan_gate.json", "interest id fields must be lists")

        plan_snapshot = self.json_file("state/plan_context_snapshot.json")
        if isinstance(plan_snapshot, dict):
            expected_keys = {
                "version",
                "run_date",
                "plan_date",
                "created_at",
                "context_sha256",
                "eligible_interest_ids",
                "context_bundle",
            }
            if set(plan_snapshot) != expected_keys or plan_snapshot.get("version") != 1:
                self.finding(
                    "plan_context_snapshot_schema",
                    self.root / "state/plan_context_snapshot.json",
                    "invalid frozen Plan context snapshot schema",
                )
            else:
                if plan_snapshot.get("run_date") != closed_day.isoformat():
                    self.finding(
                        "plan_context_snapshot_date",
                        self.root / "state/plan_context_snapshot.json",
                        "run_date mismatch",
                    )
                if plan_snapshot.get("plan_date") != plan_day.isoformat():
                    self.finding(
                        "plan_context_snapshot_date",
                        self.root / "state/plan_context_snapshot.json",
                        "plan_date mismatch",
                    )
                try:
                    parse_datetime(plan_snapshot.get("created_at", ""))
                except (TypeError, ValueError):
                    self.finding(
                        "plan_context_snapshot_time",
                        self.root / "state/plan_context_snapshot.json",
                        "created_at must be an ISO timestamp",
                    )
                eligible = plan_snapshot.get("eligible_interest_ids")
                bundle = plan_snapshot.get("context_bundle")
                digest = plan_snapshot.get("context_sha256")
                if not isinstance(eligible, list) or not all(
                    isinstance(item, str) for item in eligible
                ) or len(eligible) != len(set(eligible)):
                    self.finding(
                        "plan_context_snapshot_schema",
                        self.root / "state/plan_context_snapshot.json",
                        "eligible_interest_ids must be a unique string list",
                    )
                if not isinstance(bundle, dict):
                    self.finding(
                        "plan_context_snapshot_schema",
                        self.root / "state/plan_context_snapshot.json",
                        "context_bundle must be an object",
                    )
                else:
                    current = bundle.get("current_context")
                    interests = current.get("interests") if isinstance(current, dict) else None
                    bundle_ids: list[str] | None = None
                    if isinstance(interests, list):
                        candidate_ids = [
                            item.get("id") if isinstance(item, dict) else None for item in interests
                        ]
                        if all(isinstance(item, str) for item in candidate_ids) and len(
                            candidate_ids
                        ) == len(set(candidate_ids)):
                            bundle_ids = candidate_ids
                    if bundle_ids is None:
                        self.finding(
                            "plan_context_snapshot_schema",
                            self.root / "state/plan_context_snapshot.json",
                            "context_bundle interests must have unique string ids",
                        )
                    elif eligible != bundle_ids:
                        self.finding(
                            "plan_context_snapshot_interest_mismatch",
                            self.root / "state/plan_context_snapshot.json",
                            "eligible_interest_ids differ from context_bundle interests",
                        )
                    encoded = json.dumps(
                        bundle,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    expected_digest = hashlib.sha256(encoded).hexdigest()
                    if digest != expected_digest:
                        self.finding(
                            "plan_context_snapshot_digest",
                            self.root / "state/plan_context_snapshot.json",
                            "context_sha256 does not match context_bundle",
                        )
                if isinstance(plan_gate, dict) and eligible != plan_gate.get(
                    "eligible_interest_ids"
                ):
                    self.finding(
                        "plan_context_snapshot_gate_mismatch",
                        self.root / "state/plan_context_snapshot.json",
                        "eligible_interest_ids differ from plan_gate.json",
                    )

        consumption = self.json_file("state/plan_consumption.json")
        if not isinstance(consumption, dict) or consumption.get("version") != 1 or not isinstance(
            consumption.get("receipts"), list
        ):
            self.finding("plan_consumption_schema", self.root / "state/plan_consumption.json", "invalid schema")

        for kind in ("self", "rel"):
            relative = f"state/reflection_{kind}_gate.json"
            reflection_gate = self.json_file(relative)
            if isinstance(reflection_gate, dict):
                path = self.root / relative
                if reflection_gate.get("kind") != kind or reflection_gate.get("stage") != "finalized":
                    self.finding("reflection_gate_state", path, f"{kind} gate must be finalized")
                if reflection_gate.get("run_date") != closed_day.isoformat():
                    self.finding("reflection_gate_date", path, "run_date mismatch")

    def check_checkpoint(self, workflow: str, start: datetime, end: datetime) -> None:
        if not self.verify_checkpoints:
            return
        repo = Path(os.environ.get("DOLORES_BACKUP_REPO", self.root))
        if not (repo / ".git").exists():
            self.finding("checkpoint_unavailable", str(repo), "repository not found; checkpoint verification skipped", severity="warning")
            return
        result = subprocess.run(
            ["git", "-C", str(repo), "log", "-80", "--format=%cI%x09%s"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.finding("checkpoint_unavailable", str(repo), result.stderr.strip(), severity="warning")
            return
        prefix = f"dolores: {workflow} checkpoint"
        for line in result.stdout.splitlines():
            try:
                raw_time, subject = line.split("\t", 1)
                committed_at = parse_datetime(raw_time)
            except (ValueError, TypeError):
                continue
            if subject.startswith(prefix) and start <= committed_at <= end:
                return
        self.finding(
            "checkpoint_missing",
            str(repo),
            f"no {workflow} checkpoint between {start.isoformat()} and {end.isoformat()}",
        )

    def common_state(self, *, require_weather: bool = False, expected_sync_date: date | None = None) -> dict[str, Any] | None:
        world = self.json_file("state/world_context.json")
        if world is not None:
            self.validate_world(world, self.root / "state/world_context.json", require_weather=require_weather)
        affect = self.json_file("state/affect.json")
        if affect is not None:
            self.validate_affect(affect, self.root / "state/affect.json")
        thought_trace = self.json_file(
            "state/thought_trace.json",
            required=False,
            validator=self.validate_thought_trace,
        )
        if expected_sync_date and isinstance(thought_trace, dict):
            try:
                created_at = parse_datetime(thought_trace.get("created_at", ""))
                if created_at.date() != expected_sync_date:
                    self.finding(
                        "thought_trace_date_mismatch",
                        self.root / "state/thought_trace.json",
                        f"created_at date is {created_at.date()}, expected {expected_sync_date}",
                    )
            except (TypeError, ValueError):
                pass
        self.text("state/active_loops.md")
        pending = self.text("state/pending_message.md", terminal_newline=False)
        if pending is not None and not pending.strip():
            self.finding(
                "pending_empty",
                self.root / "state/pending_message.md",
                "pending_message must contain either EMPTY or a message",
            )
        self.check_timestamp("state/last_sync_at", expected_date=expected_sync_date)
        return world if isinstance(world, dict) else None

    def run_incremental(self) -> None:
        day = self.now.date()
        self.common_state()
        self.check_diary(day, required=False)
        self.check_thought_log(day, required=False)
        self.check_plan(day, require_all_periods=False)
        if self.health_enabled and self.now.timetz().replace(tzinfo=None) >= time(20, 10):
            self.check_health(day, required=True)
            self.check_exercise(day)

    def run_close(self) -> None:
        closed_day = self.now.date() - timedelta(days=1)
        plan_day = self.now.date()
        world = self.common_state(require_weather=True, expected_sync_date=plan_day)
        if isinstance(world, dict):
            try:
                current_time = parse_datetime(world.get("current_time", ""))
                if current_time.date() != plan_day:
                    self.finding("world_date_mismatch", self.root / "state/world_context.json", f"current_time date is {current_time.date()}, expected {plan_day}")
            except (TypeError, ValueError):
                pass
        self.check_diary(closed_day, required=True)
        self.check_thought_log(closed_day, required=False)
        self.check_thought_log(plan_day, required=False)
        if self.health_enabled:
            self.check_health(closed_day, required=True)
            self.check_exercise(closed_day)
        self.check_reflection_trace(closed_day)
        self.check_interests_pair()
        self.check_close_json(closed_day, plan_day)

        daily_plan = self.check_plan(plan_day, require_all_periods=True)
        draft = self.text("state/plan_draft.md")
        if daily_plan is not None and draft is not None and daily_plan != draft:
            self.finding("plan_draft_final_mismatch", self.root / "state/plan_draft.md", "draft and finalized plan differ")

        self.check_reflection_final("self", closed_day)
        self.check_reflection_final("rel", closed_day)
        self.text("memory/profile-user.md")
        for card in CARD_FILES:
            self.text(f"memory/cards/{card}")

        start_reflection = datetime.combine(closed_day, time(23, 0), TZ)
        midnight = datetime.combine(plan_day, time(0, 0), TZ)
        self.check_checkpoint("reflection", start_reflection, self.now + timedelta(minutes=2))
        self.check_checkpoint("heartbeat", midnight, self.now + timedelta(minutes=2))

    def run(self) -> dict[str, Any]:
        lifecycle = self.json_file("state/lifecycle.json", validator=self.validate_lifecycle)
        if isinstance(lifecycle, dict) and lifecycle.get("mode") != "active":
            self.skipped_reason = f"lifecycle mode is {lifecycle.get('mode')}"
        elif self.mode == "incremental":
            self.run_incremental()
        else:
            self.run_close()

        errors = [finding for finding in self.findings if finding.severity == "error"]
        return {
            "ok": not errors,
            "mode": self.mode,
            "run_at": self.now.isoformat(timespec="seconds"),
            "closed_day": (self.now.date() - timedelta(days=1)).isoformat() if self.mode == "close" else None,
            "plan_day": self.now.date().isoformat(),
            "skipped": self.skipped_reason,
            "checked": sorted(set(self.checked)),
            "repairs": [asdict(item) for item in self.repairs],
            "findings": [asdict(item) for item in self.findings],
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("incremental", "close"))
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--timezone", default=os.environ.get("DOLORES_TIMEZONE"), help="IANA timezone; defaults to the local system clock")
    parser.add_argument("--health-enabled", action="store_true")
    parser.add_argument("--now", help="ISO timestamp override for deterministic tests")
    parser.add_argument("--repair", action="store_true", help="apply only deterministic, lossless repairs")
    parser.add_argument(
        "--findings-exit-zero",
        action="store_true",
        help="return exit 0 after emitting a valid findings report; lock/runtime failures still fail",
    )
    parser.add_argument(
        "--verify-checkpoints",
        action="store_true",
        help="verify opt-in private Git checkpoints; never enabled by default",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    global TZ
    if args.timezone:
        TZ = ZoneInfo(args.timezone)
    now = parse_datetime(args.now) if args.now else datetime.now(TZ)
    root = args.root.resolve()
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]
    lock_path = Path(tempfile.gettempdir()) / f"dolores-daily-integrity-{digest}.lock"
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "mode": args.mode,
                        "run_at": now.isoformat(timespec="seconds"),
                        "findings": [
                            {
                                "code": "integrity_lock_busy",
                                "path": str(root),
                                "detail": "another integrity check is already running",
                                "severity": "error",
                                "model_repairable": False,
                            }
                        ],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 3
        auditor = Auditor(root, args.mode, now, args.repair, args.verify_checkpoints)
        auditor.health_enabled = args.health_enabled
        report = auditor.run()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["ok"] or args.findings_exit_zero else 2


if __name__ == "__main__":
    sys.exit(main())
