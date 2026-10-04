#!/usr/bin/env python3
"""Deterministic pause/resume snapshot and recovery gate for Dolores.

The script deliberately does not enable accounts, bindings, or cron jobs.  It
only preserves the cognitive continuity inputs and verifies that an operator
has reconciled them before the one allowed bootstrap Heartbeat.

Commands:
  snapshot --archive state/archive/pre-pause-... --last-valid-diary-date DATE
  init-resume --archive state/archive/pre-pause-... --date DATE
  verify-resume
  mark-bootstrap --thought-run-id RUN_ID
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(
    os.environ.get(
        "DOLORES_WORKSPACE",
        Path(__file__).resolve().parents[1],
    )
).resolve()
STATE = ROOT / "state"
ARCHIVE_ROOT = (STATE / "archive").resolve()

LOOP_RE = re.compile(r"^- \*\*([^*]+)\*\*", re.MULTILINE)
TIME_ENTRY_RE = re.compile(r"^- \d{2}:\d{2}\s+\S", re.MULTILINE)
DATE_TITLE_RE = re.compile(r"^#\s+(\d{4}-\d{2}-\d{2})(?:\b|（)")

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

WORLD_CONTEXT_FIELDS = {
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

REQUIRED_STATE_SNAPSHOT_PATHS = (
    "state/world_context.json",
    "state/active_loops.md",
    "state/affect.json",
    "state/daily_plan.md",
    "state/pending_message.md",
    "state/lifecycle.json",
    "state/last_sync_at",
)

OPTIONAL_STATE_SNAPSHOT_PATHS = (
    "state/current_interests.json",
    "state/current_interests.md",
)

STABLE_CONTEXT_PATHS = (
    "memory/self-narrative.md",
    "memory/relationship-summary.md",
    "memory/profile-user.md",
    "memory/cards/shared-history.md",
    "memory/cards/quirks.md",
    "memory/cards/taste.md",
    "memory/cards/shared-language.md",
    "memory/cards/routines.md",
    "memory/cards/pets.md",
    "memory/cards/people.md",
)


class GuardError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def current_date() -> date:
    override = os.environ.get("DOLORES_TODAY")
    return date.fromisoformat(override) if override else date.today()


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GuardError(f"missing {label}: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardError(f"invalid {label}: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise GuardError(f"{label} must be a JSON object: {path}")
    return payload


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_loop_ids(text: str) -> list[str]:
    return LOOP_RE.findall(text)


def safe_archive_path(raw: str) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(ARCHIVE_ROOT)
    except ValueError as exc:
        raise GuardError(f"archive must stay under {ARCHIVE_ROOT}: {candidate}") from exc
    return candidate


def archive_from_lifecycle(lifecycle: dict[str, Any]) -> Path:
    raw = lifecycle.get("archive_path")
    if not isinstance(raw, str) or not raw.strip():
        raise GuardError("lifecycle.archive_path is required while resuming")
    return safe_archive_path(raw)


def history_files(anchor: date, limit: int = 7) -> list[Path]:
    found: list[Path] = []
    for offset in range(90):
        target = anchor - timedelta(days=offset)
        path = ROOT / "memory" / "diary" / f"{target.isoformat()}.md"
        if path.exists() and path.read_text(encoding="utf-8").strip():
            found.append(path)
            if len(found) >= limit:
                break
    return found


def validate_manifest_integrity(archive: Path, manifest: dict[str, Any]) -> None:
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise GuardError("pause manifest must contain hashed files")
    for item in files:
        if not isinstance(item, dict):
            raise GuardError("pause manifest file entries must be objects")
        relative = item.get("archive_path")
        expected_hash = item.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            raise GuardError("pause manifest file entry needs archive_path and sha256")
        path = (archive / relative).resolve()
        try:
            path.relative_to(archive.resolve())
        except ValueError as exc:
            raise GuardError(f"manifest path escapes archive: {relative}") from exc
        if not path.is_file():
            raise GuardError(f"archived snapshot file is missing: {relative}")
        actual_hash = sha256(path)
        if actual_hash != expected_hash:
            raise GuardError(
                f"archived snapshot hash mismatch: {relative}: "
                f"expected={expected_hash} actual={actual_hash}"
            )

    loops_path = archive / "state" / "active_loops.md"
    if not loops_path.exists():
        loops_path = archive / "active_loops.md"
    actual_loop_ids = (
        parse_loop_ids(loops_path.read_text(encoding="utf-8"))
        if loops_path.exists()
        else []
    )
    if actual_loop_ids != manifest.get("loop_ids"):
        raise GuardError(
            "pause manifest loop_ids do not match archived active_loops.md: "
            f"manifest={manifest.get('loop_ids')} archive={actual_loop_ids}"
        )


def copy_into_archive(source: Path, archive: Path, destination: str) -> dict[str, str]:
    target = archive / destination
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return {
        "source": str(source),
        "archive_path": destination,
        "sha256": sha256(target),
    }


def snapshot(args: argparse.Namespace) -> dict[str, Any]:
    archive = safe_archive_path(args.archive)
    if archive.exists() and any(archive.iterdir()):
        raise GuardError(f"archive already exists and is not empty: {archive}")
    archive.mkdir(parents=True, exist_ok=True)

    anchor = date.fromisoformat(args.last_valid_diary_date)
    pause_date = date.fromisoformat(args.pause_date) if args.pause_date else current_date()
    copied: list[dict[str, str]] = []
    missing_optional: list[str] = []

    for relative in REQUIRED_STATE_SNAPSHOT_PATHS:
        source = ROOT / relative
        if not source.is_file():
            raise GuardError(f"required pause snapshot source is missing: {source}")
        copied.append(copy_into_archive(source, archive, relative))

    for relative in OPTIONAL_STATE_SNAPSHOT_PATHS + STABLE_CONTEXT_PATHS:
        source = ROOT / relative
        if not source.is_file():
            missing_optional.append(relative)
            continue
        copied.append(copy_into_archive(source, archive, relative))

    thought_relative = f"state/thoughts_log/{pause_date.isoformat()}.md"
    thought_source = ROOT / thought_relative
    if thought_source.exists():
        copied.append(copy_into_archive(thought_source, archive, thought_relative))
    else:
        missing_optional.append(thought_relative)

    diaries = history_files(anchor)
    if not diaries or diaries[0].stem != anchor.isoformat():
        raise GuardError(
            f"last valid raw diary is missing or empty: memory/diary/{anchor.isoformat()}.md"
        )
    history_sha256: dict[str, str] = {}
    for source in diaries:
        copied_item = copy_into_archive(
            source,
            archive,
            f"memory/diary/{source.name}",
        )
        copied.append(copied_item)
        history_sha256[source.stem] = copied_item["sha256"]

    # System snapshots are explicit private backups. Never copy the whole
    # shared SQLite database, which contains other agents' records.
    if args.openclaw_root:
        system_root = args.openclaw_root.resolve()
        config = system_root / "openclaw.json"
        if not config.is_file():
            raise GuardError("configured OpenClaw root has no openclaw.json")
        copied.append(copy_into_archive(config, archive, "system/openclaw.json"))
        database = system_root / "state/openclaw.sqlite"
        if database.exists():
            with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(
                    "SELECT * FROM cron_jobs WHERE agent_id = ? OR owner_agent_id = ? OR name LIKE ?",
                    (args.agent_id, args.agent_id, f"{args.agent_id.capitalize()} %"),
                )
                jobs = [dict(row) for row in rows]
            cron_snapshot = {"storage": "sqlite", "jobs": jobs}
        else:
            legacy = load_json(system_root / "cron/jobs.json", "legacy cron store")
            jobs = [job for job in legacy.get("jobs", []) if job.get("agentId") == args.agent_id or str(job.get("name", "")).startswith(args.agent_id.capitalize() + " ")]
            cron_snapshot = {"storage": "json", "jobs": jobs}
        cron_path = archive / "system/cron-jobs.json"
        write_json_atomic(cron_path, cron_snapshot)
        copied.append({"source": "selected cron configuration", "archive_path": "system/cron-jobs.json", "sha256": sha256(cron_path)})

    loops_path = archive / "state" / "active_loops.md"
    loop_ids = parse_loop_ids(loops_path.read_text(encoding="utf-8")) if loops_path.exists() else []
    manifest = {
        "schema_version": 1,
        "snapshot_mode": "deterministic",
        "created_at": now_iso(),
        "pause_date": pause_date.isoformat(),
        "last_valid_diary_date": anchor.isoformat(),
        "history_dates": [path.stem for path in diaries],
        "history_sha256": history_sha256,
        "loop_ids": loop_ids,
        "continuity_policy": {
            "review_on_resume": ["state/active_loops.md"],
            "rebuild_for_resume_day": [
                "state/world_context.json",
                "state/daily_plan.md",
            ],
            "clear_before_resume": ["state/pending_message.md"],
            "quarantine_not_restore": [thought_relative],
            "preserve_as_reference": [
                "state/affect.json",
                *STABLE_CONTEXT_PATHS,
                *[f"memory/diary/{path.name}" for path in diaries],
            ],
        },
        "files": copied,
        "missing_optional": missing_optional,
    }
    write_json_atomic(archive / "pause_manifest.json", manifest)
    return {
        "ok": True,
        "state": "snapshot_created",
        "archive": str(archive),
        "file_count": len(copied),
        "loop_count": len(loop_ids),
        "history_count": len(diaries),
    }


def init_resume(args: argparse.Namespace) -> dict[str, Any]:
    archive = safe_archive_path(args.archive)
    manifest = load_json(archive / "pause_manifest.json", "pause manifest")
    target = archive / "resume_reconciliation.json"
    if target.exists() and not args.force:
        raise GuardError(f"resume reconciliation already exists: {target}")

    prepared_for = date.fromisoformat(args.date)
    payload = {
        "schema_version": 1,
        "archive_path": str(archive.relative_to(ROOT)),
        "prepared_for_date": prepared_for.isoformat(),
        "prepared_at": None,
        "status": "review",
        "first_contact": {"observed": False, "observed_at": None},
        "loops": [
            {"loop_id": loop_id, "decision": "review", "reason": ""}
            for loop_id in manifest.get("loop_ids", [])
        ],
        "additional_loops": [],
        "daily_plan": {
            "decision": "review",
            "date": prepared_for.isoformat(),
            "reviewed": False,
            "reviewed_against": manifest.get("pause_date"),
        },
        "thought_log": {
            "decision": "review",
            "restored_from_archive": None,
        },
        "diary": {
            "last_valid_diary_date": manifest.get("last_valid_diary_date"),
            "history_policy": "last_7_raw",
            "reference_verified": False,
        },
        "bootstrap": None,
    }
    write_json_atomic(target, payload)
    return {
        "ok": True,
        "state": "review_template_created",
        "path": str(target),
        "loop_count": len(payload["loops"]),
    }


def validate_exact_numeric_fields(path: Path, expected: set[str], label: str) -> None:
    payload = load_json(path, label)
    actual = set(payload)
    if actual != expected:
        raise GuardError(
            f"{label} field mismatch: missing={sorted(expected - actual)} "
            f"extra={sorted(actual - expected)}"
        )
    for key, value in payload.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise GuardError(f"{label}.{key} must be numeric")
        if not 0.0 <= float(value) <= 1.0:
            raise GuardError(f"{label}.{key} must be between 0 and 1")


def validate_world_context(path: Path, prepared_for: str) -> None:
    payload = load_json(path, "world context")
    actual = set(payload)
    if actual != WORLD_CONTEXT_FIELDS:
        raise GuardError(
            "world context field mismatch: "
            f"missing={sorted(WORLD_CONTEXT_FIELDS - actual)} "
            f"extra={sorted(actual - WORLD_CONTEXT_FIELDS)}"
        )
    current_time = payload.get("current_time")
    if not isinstance(current_time, str) or not current_time.startswith(prepared_for):
        raise GuardError(
            f"world_context.current_time must be rebuilt for {prepared_for}: {current_time!r}"
        )


def validate_plan(path: Path, plan_meta: dict[str, Any], prepared_for: str) -> None:
    if plan_meta.get("decision") != "rebuilt":
        raise GuardError("daily_plan.decision must be rebuilt")
    if plan_meta.get("date") != prepared_for:
        raise GuardError("daily_plan.date must equal prepared_for_date")
    if plan_meta.get("reviewed") is not True:
        raise GuardError("daily_plan must be explicitly reviewed against a prior full plan")
    if not str(plan_meta.get("reviewed_against", "")).strip():
        raise GuardError("daily_plan.reviewed_against is required")

    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise GuardError(f"missing rebuilt daily plan: {path}") from exc
    title = DATE_TITLE_RE.search(text)
    if not title or title.group(1) != prepared_for:
        raise GuardError(f"daily plan title must start with {prepared_for}")
    if not TIME_ENTRY_RE.search(text):
        raise GuardError("daily plan needs at least one concrete timed life segment")
    if text in {"EMPTY", "# Daily Plan\n\nEMPTY"}:
        raise GuardError("daily plan is still a placeholder")


def verify_prepared(
    lifecycle: dict[str, Any],
    manifest: dict[str, Any],
    reconciliation: dict[str, Any],
    archive: Path,
) -> dict[str, Any]:
    if reconciliation.get("status") != "prepared":
        raise GuardError("resume reconciliation status must be prepared")
    prepared_for = reconciliation.get("prepared_for_date")
    if prepared_for != current_date().isoformat():
        raise GuardError(
            f"prepared_for_date must be today ({current_date().isoformat()}), got {prepared_for!r}"
        )
    if not str(reconciliation.get("prepared_at", "")).strip():
        raise GuardError("resume reconciliation prepared_at is required")
    if reconciliation.get("archive_path") != str(archive.relative_to(ROOT)):
        raise GuardError("resume reconciliation archive_path does not match lifecycle.archive_path")

    first_contact = reconciliation.get("first_contact")
    if not isinstance(first_contact, dict) or first_contact.get("observed") is not True:
        raise GuardError("first real resume contact must be observed before bootstrap Heartbeat")
    if not str(first_contact.get("observed_at", "")).strip():
        raise GuardError("first_contact.observed_at is required")

    archived_ids = manifest.get("loop_ids")
    if not isinstance(archived_ids, list) or not all(isinstance(item, str) for item in archived_ids):
        raise GuardError("pause manifest loop_ids must be a string list")
    if len(archived_ids) != len(set(archived_ids)):
        raise GuardError("pause manifest has duplicate loop_ids")

    decisions = reconciliation.get("loops")
    if not isinstance(decisions, list):
        raise GuardError("resume reconciliation loops must be a list")
    decision_by_id: dict[str, dict[str, Any]] = {}
    for item in decisions:
        if not isinstance(item, dict) or not isinstance(item.get("loop_id"), str):
            raise GuardError("every loop decision needs a loop_id")
        loop_id = item["loop_id"]
        if loop_id in decision_by_id:
            raise GuardError(f"duplicate loop decision: {loop_id}")
        if item.get("decision") not in {"restore", "close", "quarantine"}:
            raise GuardError(f"unresolved loop decision for {loop_id}")
        if len(str(item.get("reason", "")).strip()) < 8:
            raise GuardError(f"loop decision needs a concrete reason: {loop_id}")
        decision_by_id[loop_id] = item
    if set(decision_by_id) != set(archived_ids):
        raise GuardError(
            "every archived loop needs exactly one disposition: "
            f"missing={sorted(set(archived_ids) - set(decision_by_id))} "
            f"extra={sorted(set(decision_by_id) - set(archived_ids))}"
        )

    additional = reconciliation.get("additional_loops", [])
    if not isinstance(additional, list):
        raise GuardError("additional_loops must be a list")
    additional_ids: set[str] = set()
    for item in additional:
        if not isinstance(item, dict) or not isinstance(item.get("loop_id"), str):
            raise GuardError("every additional loop needs a loop_id")
        if len(str(item.get("source", "")).strip()) < 8:
            raise GuardError(f"additional loop needs current evidence: {item.get('loop_id')}")
        additional_ids.add(item["loop_id"])

    current_loops_path = STATE / "active_loops.md"
    current_ids = set(
        parse_loop_ids(current_loops_path.read_text(encoding="utf-8"))
        if current_loops_path.exists()
        else []
    )
    restored_ids = {
        loop_id
        for loop_id, item in decision_by_id.items()
        if item.get("decision") == "restore"
    }
    expected_current = restored_ids | additional_ids
    if current_ids != expected_current:
        raise GuardError(
            "active_loops does not match the reviewed recovery set: "
            f"missing={sorted(expected_current - current_ids)} "
            f"unexpected={sorted(current_ids - expected_current)}"
        )

    validate_plan(STATE / "daily_plan.md", reconciliation.get("daily_plan", {}), prepared_for)

    thought_meta = reconciliation.get("thought_log")
    if not isinstance(thought_meta, dict):
        raise GuardError("thought_log reconciliation is required")
    if thought_meta.get("decision") != "start_empty":
        raise GuardError("thought_log.decision must be start_empty")
    if thought_meta.get("restored_from_archive") is not False:
        raise GuardError("archived thought logs must not be restored into the resume day")
    thought_path = STATE / "thoughts_log" / f"{prepared_for}.md"
    if thought_path.exists():
        content = thought_path.read_text(encoding="utf-8").strip()
        if content not in {"", "EMPTY", f"# {prepared_for}\n\nEMPTY"}:
            raise GuardError("resume-day thought log must be empty before bootstrap Heartbeat")

    diary_meta = reconciliation.get("diary")
    if not isinstance(diary_meta, dict):
        raise GuardError("diary reconciliation is required")
    anchor_raw = lifecycle.get("last_valid_diary_date")
    if anchor_raw != manifest.get("last_valid_diary_date"):
        raise GuardError("lifecycle and pause manifest disagree on last_valid_diary_date")
    if diary_meta.get("last_valid_diary_date") != anchor_raw:
        raise GuardError("diary reconciliation anchor does not match lifecycle")
    if diary_meta.get("history_policy") != "last_7_raw":
        raise GuardError("diary history_policy must be last_7_raw")
    if diary_meta.get("reference_verified") is not True:
        raise GuardError("last valid raw diary reference must be explicitly verified")
    anchor = date.fromisoformat(str(anchor_raw))
    diaries = history_files(anchor)
    expected_history = manifest.get("history_dates", [])
    if not diaries or diaries[0].stem != anchor.isoformat():
        raise GuardError(f"missing last valid raw diary: {anchor.isoformat()}")
    if isinstance(expected_history, list) and expected_history:
        actual_dates = [path.stem for path in diaries]
        if actual_dates[: len(expected_history)] != expected_history:
            raise GuardError(
                f"raw diary history differs from pause manifest: {actual_dates}"
            )
        expected_hashes = manifest.get("history_sha256")
        if not isinstance(expected_hashes, dict):
            raise GuardError("pause manifest history_sha256 is required")
        if set(expected_hashes) != set(expected_history):
            raise GuardError("pause manifest history_sha256 dates do not match history_dates")
        for diary_path in diaries[: len(expected_history)]:
            expected_hash = expected_hashes.get(diary_path.stem)
            actual_hash = sha256(diary_path)
            if actual_hash != expected_hash:
                raise GuardError(
                    "raw diary content differs from pause snapshot: "
                    f"{diary_path.stem}: expected={expected_hash} actual={actual_hash}"
                )

    today_diary = ROOT / "memory" / "diary" / f"{prepared_for}.md"
    if today_diary.exists() and today_diary.read_text(encoding="utf-8").strip():
        raise GuardError("resume-day diary must be empty before bootstrap Heartbeat")

    pending = (STATE / "pending_message.md").read_text(encoding="utf-8").strip()
    if pending != "EMPTY":
        raise GuardError("pending_message must be EMPTY before bootstrap Heartbeat")
    if not (STATE / "resume_context.md").read_text(encoding="utf-8").strip():
        raise GuardError("resume_context.md is missing or empty")

    validate_exact_numeric_fields(STATE / "affect.json", AFFECT_FIELDS, "affect")
    validate_world_context(STATE / "world_context.json", prepared_for)

    return {
        "ok": True,
        "state": "ready_for_bootstrap",
        "archive": str(archive),
        "prepared_for_date": prepared_for,
        "restored_loops": sorted(restored_ids),
        "closed_or_quarantined_loops": sorted(set(archived_ids) - restored_ids),
        "history_count": len(diaries),
    }


def verify_resume() -> tuple[dict[str, Any], int]:
    lifecycle = load_json(STATE / "lifecycle.json", "lifecycle")
    mode = lifecycle.get("mode", "active")
    if mode == "active":
        return {"ok": True, "state": "not_resuming", "mode": mode}, 0
    if mode != "resuming":
        return {"ok": False, "state": "not_ready", "mode": mode}, 2

    archive = archive_from_lifecycle(lifecycle)
    manifest = load_json(archive / "pause_manifest.json", "pause manifest")
    validate_manifest_integrity(archive, manifest)
    reconciliation = load_json(
        archive / "resume_reconciliation.json",
        "resume reconciliation",
    )
    status = reconciliation.get("status")
    if status == "bootstrap_verified":
        return {
            "ok": False,
            "state": "finalize_required",
            "archive": str(archive),
            "bootstrap": reconciliation.get("bootstrap"),
        }, 3
    result = verify_prepared(lifecycle, manifest, reconciliation, archive)
    return result, 0


def mark_bootstrap(args: argparse.Namespace) -> dict[str, Any]:
    lifecycle = load_json(STATE / "lifecycle.json", "lifecycle")
    if lifecycle.get("mode") != "resuming":
        raise GuardError("lifecycle.mode must still be resuming")
    archive = archive_from_lifecycle(lifecycle)
    path = archive / "resume_reconciliation.json"
    reconciliation = load_json(path, "resume reconciliation")
    if reconciliation.get("status") != "prepared":
        raise GuardError("resume reconciliation status must still be prepared")

    prepared_for = reconciliation.get("prepared_for_date")
    if prepared_for != current_date().isoformat():
        raise GuardError("bootstrap checkpoint must belong to the prepared resume date")
    today_diary = ROOT / "memory" / "diary" / f"{prepared_for}.md"
    if not today_diary.exists() or not today_diary.read_text(encoding="utf-8").strip():
        raise GuardError("bootstrap Heartbeat did not produce a resume-day diary")
    last_sync = (STATE / "last_sync_at").read_text(encoding="utf-8").strip()
    if not last_sync.startswith(str(prepared_for)):
        raise GuardError("bootstrap Heartbeat did not update last_sync_at for resume day")
    validate_exact_numeric_fields(STATE / "affect.json", AFFECT_FIELDS, "affect")
    validate_world_context(STATE / "world_context.json", str(prepared_for))

    from heartbeat_finalize import verify
    from cron_git_commit import CommitError
    try:
        verify(ROOT, args.thought_run_id)
    except (CommitError, ValueError) as exc:
        raise GuardError(str(exc)) from exc

    reconciliation["status"] = "bootstrap_verified"
    reconciliation["bootstrap"] = {
        "verified_at": now_iso(),
        "thought_run_id": args.thought_run_id,
        "diary_sha256": sha256(today_diary),
        "last_sync_sha256": sha256(STATE / "last_sync_at"),
    }
    write_json_atomic(path, reconciliation)
    return {
        "ok": True,
        "state": "bootstrap_verified",
        "path": str(path),
        "thought_run_id": args.thought_run_id,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--archive", required=True)
    snapshot_parser.add_argument("--last-valid-diary-date", required=True)
    snapshot_parser.add_argument("--pause-date")
    snapshot_parser.add_argument("--openclaw-root", type=Path, help="explicit private config/cron snapshot; archives may contain secrets")
    snapshot_parser.add_argument("--agent-id", default="dolores")

    init_parser = subparsers.add_parser("init-resume")
    init_parser.add_argument("--archive", required=True)
    init_parser.add_argument("--date", required=True)
    init_parser.add_argument("--force", action="store_true")

    subparsers.add_parser("verify-resume")

    mark_parser = subparsers.add_parser("mark-bootstrap")
    mark_parser.add_argument("--thought-run-id", required=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "snapshot":
            payload, code = snapshot(args), 0
        elif args.command == "init-resume":
            payload, code = init_resume(args), 0
        elif args.command == "verify-resume":
            payload, code = verify_resume()
        elif args.command == "mark-bootstrap":
            payload, code = mark_bootstrap(args), 0
        else:  # pragma: no cover
            raise GuardError(f"unknown command: {args.command}")
    except (GuardError, ValueError, OSError) as exc:
        payload, code = {"ok": False, "state": "blocked", "errors": [str(exc)]}, 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
