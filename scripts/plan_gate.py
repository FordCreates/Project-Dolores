#!/usr/bin/env python3
"""Deterministic context, interest lifecycle, and write gate for Reflection Plan.

The model receives one complete current-life context bundle and makes one
intuitive planning decision. This script owns only mechanical work: persistent
interest lifecycle, context assembly, Markdown validation, final write, and
interest consumption receipts. It does not classify self/relationship entries
or censor semantic content.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("DOLORES_PLAN_ROOT", Path(__file__).resolve().parents[1]))
STATE = ROOT / "state"
INTERESTS_JSON = STATE / "current_interests.json"
INTERESTS_MD = STATE / "current_interests.md"
USER_CONTEXT = STATE / "plan_user_context.json"
CONSUMPTION = STATE / "plan_consumption.json"
GATE = STATE / "plan_gate.json"
PLAN_DRAFT = STATE / "plan_draft.md"
DAILY_PLAN = STATE / "daily_plan.md"
PLAN_CONTEXT_SNAPSHOT = STATE / "plan_context_snapshot.json"
SOUL = ROOT / "SOUL.md"
WORLD_CONTEXT = STATE / "world_context.json"
LIFECYCLE = STATE / "lifecycle.json"
SELF_NARRATIVE = ROOT / "memory/self-narrative.md"
RELATIONSHIP_SUMMARY = ROOT / "memory/relationship-summary.md"
PROFILE = ROOT / "memory/profile-user.md"
SHARED_HISTORY = ROOT / "memory/cards/shared-history.md"
QUIRKS = ROOT / "memory/cards/quirks.md"
TASTE = ROOT / "memory/cards/taste.md"
SHARED_LANGUAGE = ROOT / "memory/cards/shared-language.md"
ROUTINES = ROOT / "memory/cards/routines.md"
PETS = ROOT / "memory/cards/pets.md"
PEOPLE = ROOT / "memory/cards/people.md"
ACTIVE_LOOPS = STATE / "active_loops.md"
DIARY_DIR = ROOT / "memory" / "diary"
THOUGHTS_LOG_DIR = STATE / "thoughts_log"
SESSIONS_DIR = Path(
    os.environ.get(
        "DOLORES_COMPANION_SESSIONS_DIR",
        Path.home() / ".openclaw" / "agents" / "companion" / "sessions",
    )
)

PERIODS = ("Morning", "Afternoon", "Evening")
PERIOD_RANGES = {
    "Morning": (5 * 60, 12 * 60),
    "Afternoon": (12 * 60, 18 * 60),
    "Evening": (18 * 60, 24 * 60),
}
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

SHARED_EVIDENCE_MARKERS = ("together", "we will", "we are", "we're", "come with me", "come with you", "join me", "join you")
UNCERTAIN_PLAN_MARKERS = ("maybe", "probably", "possibly", "if ", "depending on", "unconfirmed")


def die(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def run_date() -> date:
    raw = os.environ.get("DOLORES_PLAN_RUN_DATE")
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        die("DOLORES_PLAN_RUN_DATE must be YYYY-MM-DD")


def plan_date() -> date:
    return run_date() + timedelta(days=1)


def now_iso() -> str:
    return os.environ.get("DOLORES_PLAN_NOW") or datetime.now().astimezone().isoformat(timespec="seconds")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"invalid JSON in {path}: {exc}")


def stdin_json() -> dict[str, Any]:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        die(f"invalid stdin JSON: {exc}")
    if not isinstance(payload, dict):
        die("payload must be an object")
    return payload


def exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        die(f"{label} must contain exactly: {', '.join(sorted(expected))}")


def contains_replacement_character(value: Any) -> bool:
    if isinstance(value, str):
        return "\ufffd" in value
    if isinstance(value, dict):
        return any(contains_replacement_character(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_replacement_character(item) for item in value)
    return False


def ensure_no_replacement_character(value: Any, label: str) -> None:
    """Reject corrupted Unicode before it can cross an ownership boundary."""
    if contains_replacement_character(value):
        die(f"{label} contains Unicode replacement character U+FFFD")


def context_digest(bundle: dict[str, Any]) -> str:
    encoded = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def bundle_interest_ids(bundle: dict[str, Any]) -> list[str]:
    current = bundle.get("current_context")
    if not isinstance(current, dict) or not isinstance(current.get("interests"), list):
        raise ValueError("context_bundle.current_context.interests must be a list")
    ids: list[str] = []
    for index, item in enumerate(current["interests"]):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError(f"context_bundle.current_context.interests[{index}] has no string id")
        ids.append(item["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("context_bundle contains duplicate interest ids")
    return ids


def make_context_snapshot(
    *,
    source_run_date: str,
    target_plan_date: str,
    bundle: dict[str, Any],
    eligible_interest_ids: list[str],
    created_at: str | None = None,
) -> dict[str, Any]:
    ensure_no_replacement_character(bundle, "context_bundle")
    try:
        bundle_ids = bundle_interest_ids(bundle)
    except ValueError as exc:
        die(str(exc))
    if eligible_interest_ids != bundle_ids:
        die("eligible_interest_ids do not match context_bundle interests")
    return {
        "version": 1,
        "run_date": source_run_date,
        "plan_date": target_plan_date,
        "created_at": created_at or now_iso(),
        "context_sha256": context_digest(bundle),
        "eligible_interest_ids": eligible_interest_ids,
        "context_bundle": bundle,
    }


def validate_context_snapshot(value: Any, expected_plan_date: date) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("plan context snapshot must be an object")
    expected_keys = {
        "version",
        "run_date",
        "plan_date",
        "created_at",
        "context_sha256",
        "eligible_interest_ids",
        "context_bundle",
    }
    if set(value) != expected_keys:
        raise ValueError("plan context snapshot has an unexpected schema")
    if value.get("version") != 1:
        raise ValueError("plan context snapshot has unsupported version")
    if value.get("plan_date") != expected_plan_date.isoformat():
        raise ValueError(
            "plan context snapshot belongs to another plan date: "
            f"{value.get('plan_date')!r}"
        )
    try:
        source_day = date.fromisoformat(value.get("run_date", ""))
    except (TypeError, ValueError):
        raise ValueError("plan context snapshot has invalid run_date") from None
    if source_day + timedelta(days=1) != expected_plan_date:
        raise ValueError("plan context snapshot run_date/plan_date relationship is invalid")
    try:
        datetime.fromisoformat(str(value.get("created_at", "")).replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("plan context snapshot has invalid created_at") from None
    if not isinstance(value.get("eligible_interest_ids"), list) or not all(
        isinstance(item, str) for item in value["eligible_interest_ids"]
    ):
        raise ValueError("plan context snapshot eligible_interest_ids must be a string list")
    if len(value["eligible_interest_ids"]) != len(set(value["eligible_interest_ids"])):
        raise ValueError("plan context snapshot eligible_interest_ids must be unique")
    bundle = value.get("context_bundle")
    if not isinstance(bundle, dict):
        raise ValueError("plan context snapshot context_bundle must be an object")
    if contains_replacement_character(bundle):
        raise ValueError("plan context snapshot context_bundle contains U+FFFD")
    try:
        bundle_ids = bundle_interest_ids(bundle)
    except ValueError as exc:
        raise ValueError(str(exc)) from None
    if value["eligible_interest_ids"] != bundle_ids:
        raise ValueError("plan context snapshot interest ids do not match context_bundle")
    if value.get("context_sha256") != context_digest(bundle):
        raise ValueError("plan context snapshot digest mismatch")
    return value


def tool_result_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "\n".join(parts)


def legacy_snapshot_from_sessions(expected_plan_date: date) -> dict[str, Any] | None:
    """Backfill one pre-snapshot Plan from its authoritative prepare tool result."""
    if not SESSIONS_DIR.is_dir():
        return None
    candidates = sorted(
        (
            path
            for path in SESSIONS_DIR.glob("*.jsonl")
            if ".trajectory" not in path.name
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        except (OSError, UnicodeDecodeError):
            continue
        except json.JSONDecodeError:
            continue
        prepare_call_ids: set[str] = set()
        for record in records:
            message = record.get("message")
            if not isinstance(message, dict) or message.get("role") != "assistant":
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if not isinstance(item, dict) or item.get("name") != "exec":
                    continue
                arguments = item.get("arguments")
                command = arguments.get("command") if isinstance(arguments, dict) else None
                if isinstance(command, str) and "plan_gate.py prepare" in command:
                    call_id = item.get("id")
                    if isinstance(call_id, str):
                        prepare_call_ids.add(call_id)
        for record in reversed(records):
            message = record.get("message")
            if not isinstance(message, dict) or message.get("role") != "toolResult":
                continue
            if message.get("toolName") != "exec":
                continue
            if message.get("toolCallId") not in prepare_call_ids:
                continue
            text = tool_result_text(message).strip()
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if (
                not isinstance(payload, dict)
                or payload.get("ok") is not True
                or payload.get("skip") is not False
                or payload.get("plan_date") != expected_plan_date.isoformat()
                or not isinstance(payload.get("context_bundle"), dict)
            ):
                continue
            try:
                source_day = date.fromisoformat(payload.get("run_date", ""))
                eligible_ids = bundle_interest_ids(payload["context_bundle"])
            except (TypeError, ValueError):
                continue
            if source_day + timedelta(days=1) != expected_plan_date:
                continue
            if contains_replacement_character(payload["context_bundle"]):
                continue
            return make_context_snapshot(
                source_run_date=payload.get("run_date", ""),
                target_plan_date=payload["plan_date"],
                bundle=payload["context_bundle"],
                eligible_interest_ids=eligible_ids,
                created_at=record.get("timestamp") if isinstance(record.get("timestamp"), str) else None,
            )
    return None


def load_context_snapshot(expected_plan_date: date) -> dict[str, Any]:
    invalid_detail: str | None = None
    snapshot: Any = None
    if PLAN_CONTEXT_SNAPSHOT.exists():
        try:
            snapshot = json.loads(PLAN_CONTEXT_SNAPSHOT.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            invalid_detail = str(exc)
        else:
            try:
                return validate_context_snapshot(snapshot, expected_plan_date)
            except ValueError as exc:
                invalid_detail = str(exc)
    snapshot = legacy_snapshot_from_sessions(expected_plan_date)
    if snapshot is None:
        detail = f"; existing snapshot invalid: {invalid_detail}" if invalid_detail else ""
        die(
            "no valid frozen Plan context exists for "
            f"{expected_plan_date.isoformat()}; automatic semantic recovery is unavailable{detail}"
        )
    try:
        snapshot = validate_context_snapshot(snapshot, expected_plan_date)
    except ValueError as exc:
        die(f"recovered Plan context snapshot is invalid: {exc}")
    atomic_json(PLAN_CONTEXT_SNAPSHOT, snapshot)
    return snapshot


def one_line(value: Any, label: str, minimum: int = 1, maximum: int = 200) -> str:
    if not isinstance(value, str):
        die(f"{label} must be a string")
    clean = value.strip()
    if "\n" in clean or "\r" in clean or not minimum <= len(clean) <= maximum:
        die(f"{label} must be one line with {minimum}-{maximum} characters")
    return clean


def default_interests() -> dict[str, Any]:
    return {"version": 1, "updated_at": None, "active": [], "cooldowns": []}


def load_interests() -> dict[str, Any]:
    state = read_json(INTERESTS_JSON, default_interests())
    if not isinstance(state, dict):
        die("current_interests.json must be an object")
    exact_keys(state, {"version", "updated_at", "active", "cooldowns"}, "current_interests.json")
    if state["version"] != 1 or not isinstance(state["active"], list) or not isinstance(state["cooldowns"], list):
        die("current_interests.json has unsupported schema")
    return state


def normalize_aliases(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or len(value) > 8:
        die(f"{label} must be a list with at most 8 aliases")
    aliases: list[str] = []
    for index, item in enumerate(value):
        alias = one_line(item, f"{label}[{index}]", 1, 40)
        if alias not in aliases:
            aliases.append(alias)
    return aliases


def validate_topic(value: Any) -> str:
    topic = one_line(value, "signal.topic", 3, 100)
    if ":" not in topic or topic.startswith(":") or topic.endswith(":"):
        die("signal.topic must be a canonical category:name key, for example food:pasta")
    return topic


def merge_aliases(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for alias in group:
            if alias and alias not in merged:
                merged.append(alias)
    return merged[:8]


def alias_key(value: str) -> str:
    return re.sub(r"[\s\"'·_\-—]+", "", value).lower()


def resolve_topic(
    state: dict[str, Any], topic: str, label: str, aliases: list[str]
) -> tuple[str, list[str]]:
    """Reuse an existing canonical topic when same-category aliases overlap."""
    category = topic.split(":", 1)[0]
    candidate_keys = {alias_key(value) for value in [label, *aliases] if value}
    for item in [*state["active"], *state["cooldowns"]]:
        existing_topic = item.get("topic")
        if not isinstance(existing_topic, str) or existing_topic.split(":", 1)[0] != category:
            continue
        existing_values = [item.get("label", ""), *item.get("aliases", [])]
        existing_keys = {alias_key(value) for value in existing_values if isinstance(value, str) and value}
        if candidate_keys & existing_keys:
            return existing_topic, merge_aliases(item.get("aliases", []), aliases, [label])
    return topic, aliases


def make_interest_id(topic: str, existing_ids: set[str]) -> str:
    prefix = f"i-{run_date().strftime('%Y%m%d')}-{hashlib.sha256(topic.encode()).hexdigest()[:10]}"
    candidate = prefix
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{prefix}-{suffix}"
        suffix += 1
    return candidate


def put_cooldown(
    state: dict[str, Any], topic: str, label: str, aliases: list[str], reason: str
) -> None:
    previous = next((item for item in state["cooldowns"] if item.get("topic") == topic), None)
    old_aliases = previous.get("aliases", []) if isinstance(previous, dict) else []
    state["cooldowns"] = [item for item in state["cooldowns"] if item.get("topic") != topic]
    state["cooldowns"].append(
        {
            "topic": topic,
            "label": label,
            "aliases": merge_aliases(old_aliases, aliases, [label]),
            "since": run_date().isoformat(),
            "reason": reason,
            "reactivation": "explicit_future_intent_only",
        }
    )


def load_receipts() -> dict[str, Any]:
    receipts = read_json(CONSUMPTION, {"version": 1, "receipts": []})
    if not isinstance(receipts, dict):
        die("plan_consumption.json must be an object")
    exact_keys(receipts, {"version", "receipts"}, "plan_consumption.json")
    if receipts["version"] != 1 or not isinstance(receipts["receipts"], list):
        die("plan_consumption.json has unsupported schema")
    return receipts


def expire_stale_interests(state: dict[str, Any]) -> list[str]:
    expired: list[str] = []
    kept: list[dict[str, Any]] = []
    for item in state["active"]:
        raw_source_date = item.get("source_date")
        try:
            source_date = date.fromisoformat(raw_source_date)
        except (TypeError, ValueError):
            die("active interest has invalid source_date")
        if (run_date() - source_date).days >= 7:
            expired.append(item.get("topic", item.get("id", "unknown")))
        else:
            kept.append(item)
    state["active"] = kept
    return expired


def apply_pending_receipts(state: dict[str, Any], receipts: dict[str, Any]) -> list[str]:
    applied: list[str] = []
    for receipt in receipts["receipts"]:
        if not isinstance(receipt, dict) or receipt.get("status") != "pending":
            continue
        interest_id = receipt.get("interest_id")
        topic = receipt.get("topic")
        if not isinstance(interest_id, str) or not isinstance(topic, str):
            die("pending consumption receipt is malformed")
        active = next(
            (item for item in state["active"] if item.get("id") == interest_id or item.get("topic") == topic),
            None,
        )
        label = receipt.get("label") if isinstance(receipt.get("label"), str) else topic
        aliases = active.get("aliases", []) if isinstance(active, dict) else []
        if isinstance(active, dict):
            label = active.get("label", label)
        state["active"] = [
            item for item in state["active"] if item.get("id") != interest_id and item.get("topic") != topic
        ]
        put_cooldown(state, topic, label, aliases, "plan_used")
        receipt["status"] = "applied"
        receipt["applied_at"] = now_iso()
        applied.append(topic)
    return applied


def render_interests(state: dict[str, Any]) -> str:
    lines = [
        "# Current Interests — Recent Sparks",
        "",
        "> `scripts/plan_gate.py` is the sole writer. Plan receives seeds in its frozen context bundle.",
        "> Seeds are consumed once. Completed or scheduled topics cool down until explicit new future intent.",
        "",
        "## Available Seeds",
        "",
    ]
    if state["active"]:
        for item in state["active"]:
            lines.append(
                f"- `{item['id']}` · `{item['topic']}` · [{item['source_date']}] "
                f"{item['label']} — {item['summary']}"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Cooldown Topics (Prep deduplication only)", ""])
    if state["cooldowns"]:
        for item in state["cooldowns"]:
            aliases = " / ".join(item.get("aliases", [])) or item["label"]
            lines.append(
                f"- `{item['topic']}` · {aliases} · since {item['since']} · {item['reason']} "
                "· Reactivate only with explicit new future intent"
            )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def validate_user_plan(raw_items: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_items, list) or len(raw_items) > 3:
        die("user_plan must be a list with at most 3 explicit shared events")
    items: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict):
            die(f"user_plan[{index}] must be an object")
        exact_keys(raw, {"time_hint", "description", "evidence", "pet_related"}, f"user_plan[{index}]")
        if not isinstance(raw["pet_related"], bool):
            die(f"user_plan[{index}].pet_related must be boolean")
        description = one_line(raw["description"], f"user_plan[{index}].description", 4, 180)
        evidence = one_line(raw["evidence"], f"user_plan[{index}].evidence", 2, 240)
        if not any(marker in evidence.lower() for marker in SHARED_EVIDENCE_MARKERS):
            die(
                f"user_plan[{index}].evidence lacks an explicit shared-participation marker "
                f"such as together / we will / come with me"
            )
        uncertain = next(
            (marker for marker in UNCERTAIN_PLAN_MARKERS if marker in description.lower() or marker in evidence.lower()), None
        )
        if uncertain:
            die(f"user_plan[{index}] is conditional or unconfirmed ({uncertain})")
        items.append(
            {
                "id": f"u{index}",
                "time_hint": one_line(raw["time_hint"], f"user_plan[{index}].time_hint", 0, 40),
                "description": description,
                "evidence": evidence,
                "pet_related": raw["pet_related"],
            }
        )
    return items


def sync_prep() -> None:
    payload = stdin_json()
    exact_keys(payload, {"signals", "user_plan"}, "sync-prep payload")
    signals = payload["signals"]
    if not isinstance(signals, list) or len(signals) > 5:
        die("signals must be a list with at most 5 items")

    state = load_interests()
    receipts = load_receipts()
    expired = expire_stale_interests(state)
    applied = apply_pending_receipts(state, receipts)
    ignored: list[str] = []
    changed: list[str] = []

    for index, raw in enumerate(signals):
        if not isinstance(raw, dict):
            die(f"signals[{index}] must be an object")
        exact_keys(raw, {"action", "topic", "label", "summary", "aliases"}, f"signals[{index}]")
        action = raw["action"]
        if action not in {"add", "reactivate", "cooldown"}:
            die(f"signals[{index}].action must be add, reactivate, or cooldown")
        topic = validate_topic(raw["topic"])
        label = one_line(raw["label"], f"signals[{index}].label", 1, 80)
        summary = one_line(raw["summary"], f"signals[{index}].summary", 2, 240)
        aliases = merge_aliases(normalize_aliases(raw["aliases"], f"signals[{index}].aliases"), [label])
        topic, aliases = resolve_topic(state, topic, label, aliases)

        active = next((item for item in state["active"] if item.get("topic") == topic), None)
        cooldown = next((item for item in state["cooldowns"] if item.get("topic") == topic), None)

        if action == "cooldown":
            if isinstance(active, dict):
                aliases = merge_aliases(active.get("aliases", []), aliases)
                label = active.get("label", label)
            state["active"] = [item for item in state["active"] if item.get("topic") != topic]
            put_cooldown(state, topic, label, aliases, "completed_or_explicit_negative")
            changed.append(f"cooldown:{topic}")
            continue

        if action == "add" and isinstance(cooldown, dict):
            ignored.append(f"blocked_by_cooldown:{topic}")
            continue

        if action == "reactivate":
            state["cooldowns"] = [item for item in state["cooldowns"] if item.get("topic") != topic]

        if isinstance(active, dict):
            active["label"] = label
            active["summary"] = summary
            active["aliases"] = merge_aliases(active.get("aliases", []), aliases)
            active["source_date"] = run_date().isoformat()
            changed.append(f"refresh:{topic}")
        else:
            existing_ids = {item.get("id") for item in state["active"] if isinstance(item.get("id"), str)}
            state["active"].append(
                {
                    "id": make_interest_id(topic, existing_ids),
                    "topic": topic,
                    "label": label,
                    "summary": summary,
                    "aliases": aliases,
                    "created_at": now_iso(),
                    "source_date": run_date().isoformat(),
                }
            )
            changed.append(f"add:{topic}")

    state["active"] = state["active"][-5:]
    state["cooldowns"] = state["cooldowns"][-50:]
    state["updated_at"] = now_iso()
    user_plan = validate_user_plan(payload["user_plan"])
    user_context = {
        "version": 1,
        "generated_on": run_date().isoformat(),
        "plan_date": plan_date().isoformat(),
        "items": user_plan,
    }

    atomic_json(INTERESTS_JSON, state)
    atomic_write(INTERESTS_MD, render_interests(state))
    atomic_json(USER_CONTEXT, user_context)
    atomic_json(CONSUMPTION, receipts)
    print(
        json.dumps(
            {
                "ok": True,
                "run_date": run_date().isoformat(),
                "plan_date": plan_date().isoformat(),
                "receipt_topics_applied": applied,
                "expired_topics": expired,
                "changes": changed,
                "ignored": ignored,
                "active_count": len(state["active"]),
                "cooldown_count": len(state["cooldowns"]),
                "user_plan_count": len(user_plan),
            },
            ensure_ascii=False,
        )
    )


def lifecycle_mode() -> str:
    lifecycle = read_json(LIFECYCLE, {})
    if not isinstance(lifecycle, dict):
        return "active"
    mode = lifecycle.get("mode", "active")
    return mode if isinstance(mode, str) else "active"


def context_text(path: Path) -> str | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None


def load_user_context() -> list[dict[str, Any]]:
    context = read_json(USER_CONTEXT, {})
    if not isinstance(context, dict) or context.get("plan_date") != plan_date().isoformat():
        return []
    items = context.get("items")
    if not isinstance(items, list):
        return []
    return [
        {
            "id": item.get("id"),
            "time_hint": item.get("time_hint"),
            "description": item.get("description"),
            "pet_related": item.get("pet_related", False),
        }
        for item in items
        if isinstance(item, dict)
    ]


def eligible_interests() -> list[dict[str, str]]:
    state = load_interests()
    receipts = load_receipts()
    pending_ids = {
        item.get("interest_id")
        for item in receipts["receipts"]
        if isinstance(item, dict) and item.get("status") == "pending"
    }
    result: list[dict[str, str]] = []
    for item in state["active"]:
        if item.get("id") in pending_ids:
            continue
        result.append(
            {
                "id": item["id"],
                "topic": item["topic"],
                "label": item["label"],
                "summary": item["summary"],
            }
        )
    return result


def context_bundle() -> dict[str, Any]:
    return {
        "identity": {
            "soul": context_text(SOUL),
            "self_narrative": context_text(SELF_NARRATIVE),
        },
        "relationship": {
            "relationship_summary": context_text(RELATIONSHIP_SUMMARY),
            "profile": context_text(PROFILE),
        },
        "cards": {
            "shared_history": context_text(SHARED_HISTORY),
            "quirks": context_text(QUIRKS),
            "taste": context_text(TASTE),
            "shared_language": context_text(SHARED_LANGUAGE),
            "routines": context_text(ROUTINES),
            "pets": context_text(PETS),
            "people": context_text(PEOPLE),
        },
        "current_context": {
            "today_diary": context_text(DIARY_DIR / f"{run_date().isoformat()}.md"),
            "today_thought_log": context_text(
                THOUGHTS_LOG_DIR / f"{run_date().isoformat()}.md"
            ),
            "active_loops": context_text(ACTIVE_LOOPS),
            "world_context": read_json(WORLD_CONTEXT, {}),
            "interests": eligible_interests(),
            "user_plan": load_user_context(),
        },
    }


def save_gate(gate: dict[str, Any]) -> None:
    atomic_json(GATE, gate)


def load_gate(stages: set[str]) -> dict[str, Any]:
    gate = read_json(GATE)
    if not isinstance(gate, dict):
        die("plan gate missing; run prepare first")
    if gate.get("run_date") != run_date().isoformat() or gate.get("plan_date") != plan_date().isoformat():
        die("plan gate belongs to another run")
    if gate.get("stage") not in stages:
        die(f"plan gate stage must be one of {sorted(stages)}")
    return gate


def prepare() -> None:
    mode = lifecycle_mode()
    if mode != "active":
        print(json.dumps({"ok": True, "skip": True, "reason": f"lifecycle:{mode}"}, ensure_ascii=False))
        return

    if PLAN_DRAFT.exists():
        PLAN_DRAFT.unlink()

    bundle = context_bundle()
    ensure_no_replacement_character(bundle, "context_bundle")
    interests = bundle["current_context"]["interests"]
    snapshot = make_context_snapshot(
        source_run_date=run_date().isoformat(),
        target_plan_date=plan_date().isoformat(),
        bundle=bundle,
        eligible_interest_ids=[item["id"] for item in interests],
        created_at=now_iso(),
    )
    gate = {
        "version": 3,
        "run_date": snapshot["run_date"],
        "plan_date": snapshot["plan_date"],
        "stage": "prepared",
        "eligible_interest_ids": snapshot["eligible_interest_ids"],
        "used_interest_ids": [],
    }
    save_gate(gate)
    atomic_json(PLAN_CONTEXT_SNAPSHOT, snapshot)
    print(
        json.dumps(
            {
                "ok": True,
                "skip": False,
                "run_date": gate["run_date"],
                "plan_date": gate["plan_date"],
                "context_bundle": bundle,
                "output": {
                    "draft_path": str(PLAN_DRAFT.relative_to(ROOT)),
                    "final_path": str(DAILY_PLAN.relative_to(ROOT)),
                    "finalize_payload": {"used_interest_ids": []},
                },
            },
            ensure_ascii=False,
        )
    )


def minutes(value: str) -> int:
    match = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", value)
    if not match:
        die(f"invalid time {value!r}; expected HH:MM")
    return int(match.group(1)) * 60 + int(match.group(2))


def validate_period_time(period: str, raw_time: str, label: str) -> None:
    value = minutes(raw_time)
    lower, upper = PERIOD_RANGES[period]
    if not lower <= value < upper:
        die(f"{label} time {raw_time} does not belong to {period}")


def validate_plan_draft(target_day: date | None = None) -> tuple[str, int]:
    if not PLAN_DRAFT.exists():
        die("state/plan_draft.md missing")
    try:
        raw = PLAN_DRAFT.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    except UnicodeDecodeError as exc:
        die(f"state/plan_draft.md is not valid UTF-8: {exc}")
    if not raw:
        die("state/plan_draft.md is empty")
    if "\ufffd" in raw:
        die("state/plan_draft.md contains Unicode replacement character U+FFFD")

    target_day = target_day or plan_date()
    expected_title = f"# {target_day.isoformat()} ({WEEKDAYS[target_day.weekday()]}) Schedule"
    lines = raw.split("\n")
    if lines[0].strip() != expected_title:
        die(f"plan title must be exactly: {expected_title}")

    seen_periods: list[str] = []
    current_period: str | None = None
    seen_times: set[str] = set()
    period_times: dict[str, list[int]] = {period: [] for period in PERIODS}
    entry_count = 0

    for line_number, raw_line in enumerate(lines[1:], start=2):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("## "):
            period = line[3:].strip()
            if period not in PERIODS:
                die(f"unknown period heading on line {line_number}: {period}")
            expected = PERIODS[len(seen_periods)] if len(seen_periods) < len(PERIODS) else None
            if period != expected:
                die("period headings must appear once in order: Morning, Afternoon, Evening")
            seen_periods.append(period)
            current_period = period
            continue
        if current_period is None:
            die(f"content appears before the first period heading on line {line_number}")
        match = re.fullmatch(r"-\s+([0-2]\d:[0-5]\d)\s+(.+)", line)
        if not match:
            die(f"line {line_number} must be '- HH:MM activity description'")
        time_value, text = match.groups()
        if not text.strip():
            die(f"line {line_number} has an empty activity description")
        validate_period_time(current_period, time_value, f"line {line_number}")
        if time_value in seen_times:
            die(f"duplicate plan time: {time_value}")
        seen_times.add(time_value)
        period_times[current_period].append(minutes(time_value))
        entry_count += 1

    if tuple(seen_periods) != PERIODS:
        die("plan must contain Morning, Afternoon, Evening headings")
    for period in PERIODS:
        if not period_times[period]:
            die(f"plan must contain at least one {period} entry")
        if period_times[period] != sorted(period_times[period]):
            die(f"{period} entries must be in chronological order")

    return raw + "\n", entry_count


def validate_used_interest_ids(gate: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    exact_keys(payload, {"used_interest_ids"}, "finalize payload")
    raw_ids = payload["used_interest_ids"]
    if not isinstance(raw_ids, list):
        die("used_interest_ids must be a list")
    used: list[str] = []
    for index, value in enumerate(raw_ids):
        interest_id = one_line(value, f"used_interest_ids[{index}]", 2, 100)
        if interest_id in used:
            die(f"duplicate used interest id: {interest_id}")
        used.append(interest_id)

    eligible = set(gate.get("eligible_interest_ids", []))
    unknown = [interest_id for interest_id in used if interest_id not in eligible]
    if unknown:
        die(f"used_interest_ids contains unavailable ids: {unknown}")

    active_ids = {item["id"] for item in load_interests()["active"]}
    disappeared = [interest_id for interest_id in used if interest_id not in active_ids]
    if disappeared:
        die(f"used interests disappeared before finalize: {disappeared}")
    return used


def append_receipts(used_interest_ids: list[str]) -> None:
    if not used_interest_ids:
        return
    interests = {item["id"]: item for item in load_interests()["active"]}
    receipts = load_receipts()
    for interest_id in used_interest_ids:
        item = interests[interest_id]
        duplicate = any(
            receipt.get("plan_date") == plan_date().isoformat()
            and receipt.get("interest_id") == interest_id
            and receipt.get("status") in {"pending", "applied"}
            for receipt in receipts["receipts"]
            if isinstance(receipt, dict)
        )
        if duplicate:
            continue
        receipts["receipts"].append(
            {
                "status": "pending",
                "plan_date": plan_date().isoformat(),
                "interest_id": interest_id,
                "topic": item["topic"],
                "label": item["label"],
                "created_at": now_iso(),
            }
        )
    receipts["receipts"] = receipts["receipts"][-30:]
    atomic_json(CONSUMPTION, receipts)


def finalize() -> None:
    gate = load_gate({"prepared", "finalized"})
    payload = stdin_json()
    used_interest_ids = validate_used_interest_ids(gate, payload)
    rendered, entry_count = validate_plan_draft()

    atomic_write(DAILY_PLAN, rendered)
    append_receipts(used_interest_ids)
    gate["stage"] = "finalized"
    gate["used_interest_ids"] = used_interest_ids
    save_gate(gate)
    print(
        json.dumps(
            {
                "ok": True,
                "stage": gate["stage"],
                "plan_date": gate["plan_date"],
                "entry_count": entry_count,
                "used_interest_ids": used_interest_ids,
                "final_path": str(DAILY_PLAN),
            },
            ensure_ascii=False,
        )
    )


def recovery_plan_date() -> date:
    raw = os.environ.get("DOLORES_PLAN_RECOVERY_DATE")
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        die("DOLORES_PLAN_RECOVERY_DATE must be YYYY-MM-DD")


def validate_recovery_used_interest_ids(
    raw_ids: Any, snapshot: dict[str, Any]
) -> list[str]:
    if not isinstance(raw_ids, list) or not all(isinstance(item, str) for item in raw_ids):
        raise ValueError("used_interest_ids must be a string list")
    if len(raw_ids) != len(set(raw_ids)):
        raise ValueError("used_interest_ids must be unique")
    eligible = set(snapshot["eligible_interest_ids"])
    unknown = [interest_id for interest_id in raw_ids if interest_id not in eligible]
    if unknown:
        raise ValueError(f"used_interest_ids contains unavailable ids: {unknown}")
    return raw_ids


def optional_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def recover_used_interest_ids(target_day: date, snapshot: dict[str, Any]) -> list[str]:
    existing = optional_json(GATE)
    if isinstance(existing, dict) and existing.get("plan_date") == target_day.isoformat():
        try:
            return validate_recovery_used_interest_ids(
                existing.get("used_interest_ids"), snapshot
            )
        except ValueError:
            pass

    consumption = optional_json(CONSUMPTION)
    candidates: list[str] = []
    if isinstance(consumption, dict) and isinstance(consumption.get("receipts"), list):
        for receipt in consumption["receipts"]:
            if (
                isinstance(receipt, dict)
                and receipt.get("plan_date") == target_day.isoformat()
                and receipt.get("status") in {"pending", "applied"}
                and isinstance(receipt.get("interest_id"), str)
                and receipt["interest_id"] not in candidates
            ):
                candidates.append(receipt["interest_id"])
    try:
        return validate_recovery_used_interest_ids(candidates, snapshot)
    except ValueError as exc:
        die(f"cannot reconstruct Plan interest usage from receipts: {exc}")


def recover_snapshot() -> None:
    target_day = recovery_plan_date()
    snapshot = load_context_snapshot(target_day)
    print(
        json.dumps(
            {
                "ok": True,
                "recovery": True,
                "run_date": snapshot["run_date"],
                "plan_date": snapshot["plan_date"],
                "context_sha256": snapshot["context_sha256"],
                "snapshot_path": str(PLAN_CONTEXT_SNAPSHOT.relative_to(ROOT)),
            },
            ensure_ascii=False,
        )
    )


def recover_prepare() -> None:
    mode = lifecycle_mode()
    if mode != "active":
        die(f"cannot recover Plan while lifecycle is {mode}")

    target_day = recovery_plan_date()
    snapshot = load_context_snapshot(target_day)
    used_interest_ids = recover_used_interest_ids(target_day, snapshot)

    if PLAN_DRAFT.exists():
        PLAN_DRAFT.unlink()
    gate = {
        "version": 3,
        "run_date": snapshot["run_date"],
        "plan_date": snapshot["plan_date"],
        "stage": "recovery_prepared",
        "eligible_interest_ids": snapshot["eligible_interest_ids"],
        "used_interest_ids": used_interest_ids,
    }
    save_gate(gate)
    print(
        json.dumps(
            {
                "ok": True,
                "recovery": True,
                "run_date": gate["run_date"],
                "plan_date": gate["plan_date"],
                "context_sha256": snapshot["context_sha256"],
                "context_bundle": snapshot["context_bundle"],
                "output": {
                    "draft_path": str(PLAN_DRAFT.relative_to(ROOT)),
                    "final_path": str(DAILY_PLAN.relative_to(ROOT)),
                    "finalize_command": "python3 scripts/plan_gate.py recover-finalize",
                },
            },
            ensure_ascii=False,
        )
    )


def recover_finalize() -> None:
    gate = read_json(GATE)
    if not isinstance(gate, dict):
        die("plan gate missing; run recover-prepare first")
    if gate.get("stage") != "recovery_prepared":
        die("plan gate stage must be recovery_prepared")
    try:
        target_day = date.fromisoformat(gate.get("plan_date", ""))
        source_day = date.fromisoformat(gate.get("run_date", ""))
    except (TypeError, ValueError):
        die("recovery plan gate has invalid dates")
    if source_day + timedelta(days=1) != target_day:
        die("recovery plan gate run_date/plan_date relationship is invalid")
    if target_day != recovery_plan_date():
        die("recovery plan gate belongs to another target day")

    snapshot = load_context_snapshot(target_day)
    if gate.get("eligible_interest_ids") != snapshot["eligible_interest_ids"]:
        die("recovery plan gate no longer matches the frozen context snapshot")
    try:
        used_interest_ids = validate_recovery_used_interest_ids(
            gate.get("used_interest_ids"), snapshot
        )
    except ValueError as exc:
        die(f"recovery plan gate has invalid interest usage: {exc}")
    rendered, entry_count = validate_plan_draft(target_day)
    atomic_write(DAILY_PLAN, rendered)
    gate["stage"] = "finalized"
    save_gate(gate)
    print(
        json.dumps(
            {
                "ok": True,
                "recovery": True,
                "stage": gate["stage"],
                "plan_date": gate["plan_date"],
                "entry_count": entry_count,
                "used_interest_ids": used_interest_ids,
                "final_path": str(DAILY_PLAN),
            },
            ensure_ascii=False,
        )
    )


COMMANDS = {
    "sync-prep": sync_prep,
    "prepare": prepare,
    "finalize": finalize,
    "recover-snapshot": recover_snapshot,
    "recover-prepare": recover_prepare,
    "recover-finalize": recover_finalize,
}


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        die(
            "usage: plan_gate.py "
            "sync-prep|prepare|finalize|recover-snapshot|recover-prepare|recover-finalize"
        )
    COMMANDS[sys.argv[1]]()
