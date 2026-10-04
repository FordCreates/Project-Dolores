#!/usr/bin/env python3
"""Four-stage trace and deterministic ledger writer for Heartbeat Step 5."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TRACE = Path(os.environ.get("DOLORES_THOUGHT_TRACE_PATH", ROOT / "state/thought_trace.json"))
LOG_DIR = Path(os.environ.get("DOLORES_THOUGHT_LOG_DIR", ROOT / "state/thoughts_log"))
PENDING = Path(os.environ.get("DOLORES_PENDING_MESSAGE_PATH", ROOT / "state/pending_message.md"))
ACTIVE_LOOPS = Path(
    os.environ.get("DOLORES_ACTIVE_LOOPS_PATH", ROOT / "state/active_loops.md")
)


def die(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def clean(value: Any, field: str) -> str:
    if not isinstance(value, str):
        die(f"{field} must be a string")
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        die(f"{field} cannot be empty")
    return value


def stdin_json() -> dict[str, Any]:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        die(f"invalid JSON: {exc}")
    if not isinstance(data, dict):
        die("payload must be an object")
    return data


def exact_keys(data: dict[str, Any], keys: set[str], label: str) -> None:
    if set(data) != keys:
        die(f"{label} fields must be exactly {sorted(keys)}")


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


def save(trace: dict[str, Any]) -> None:
    atomic_write(TRACE, json.dumps(trace, ensure_ascii=False, indent=2) + "\n")


def load() -> dict[str, Any]:
    if not TRACE.exists():
        die("trace missing; run start first")
    try:
        return json.loads(TRACE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"trace is invalid JSON: {exc}")


def ids(trace: dict[str, Any]) -> list[str]:
    return [item["id"] for item in trace["slots"]["thoughts"]]


def shared_ids(trace: dict[str, Any]) -> list[str]:
    visibility = trace["slots"].get("visibility") or []
    return [item["id"] for item in visibility if item["visibility"] == "shared"]


def suppressed_by_loop() -> dict[str, int]:
    if not ACTIVE_LOOPS.exists():
        return {}
    result: dict[str, int] = {}
    for line in ACTIVE_LOOPS.read_text(encoding="utf-8").splitlines():
        header = re.match(r"^- \*\*(.+?)\*\* \|", line)
        suppressed = re.search(r"\| suppressed:\s*(\d+)(?:\s*\||\s*$)", line)
        if header and suppressed:
            result[header.group(1).strip()] = int(suppressed.group(1))
    return result


def visibility_context(trace: dict[str, Any]) -> list[dict[str, Any]]:
    counts = suppressed_by_loop()
    return [
        {
            "id": thought["id"],
            "loop_id": thought["loop_id"],
            "suppressed": counts.get(thought["loop_id"], 0),
        }
        for thought in trace["slots"]["thoughts"]
    ]


def validate_run(payload: dict[str, Any], trace: dict[str, Any]) -> None:
    if clean(payload.get("run_id"), "run_id") != trace.get("run_id"):
        die("run_id does not match current trace")


def index_exact(items: Any, expected: list[str], label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        die(f"{label} must be a list of objects")
    indexed = {item.get("id"): item for item in items}
    if len(indexed) != len(items) or set(indexed) != set(expected):
        die(f"{label} ids must exactly match {expected}")
    return indexed


def report(trace: dict[str, Any]) -> None:
    print(
        json.dumps(
            {
                "ok": True,
                "run_id": trace["run_id"],
                "stage": trace["stage"],
                "thought_ids": ids(trace),
                "shared_ids": shared_ids(trace),
                "visibility_context": trace.get("visibility_context"),
                "slots": trace["slots"],
                "trace_path": str(TRACE),
            },
            ensure_ascii=False,
        )
    )


def start(payload: dict[str, Any]) -> None:
    exact_keys(payload, {"thoughts"}, "start")
    raw = payload["thoughts"]
    if not isinstance(raw, list):
        die("thoughts must be a list")
    thoughts = []
    for number, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            die("each thought must be an object")
        exact_keys(item, {"loop_id", "thought"}, f"thought {number}")
        thoughts.append(
            {
                "id": f"t{number}",
                "loop_id": clean(item["loop_id"], "loop_id"),
                "thought": clean(item["thought"], "thought"),
            }
        )
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    trace = {
        "run_id": f"{created_at}-{uuid.uuid4().hex[:8]}",
        "created_at": created_at,
        "stage": "thoughts",
        "slots": {
            "thoughts": thoughts,
            "drafts": None,
            "visibility": None,
            "gate": None,
        },
        "visibility_context": None,
        "finalized_at": None,
    }
    save(trace)
    report(trace)


def drafts(payload: dict[str, Any]) -> None:
    exact_keys(payload, {"run_id", "drafts"}, "drafts")
    trace = load()
    validate_run(payload, trace)
    if trace.get("stage") != "thoughts":
        die(f"drafts requires stage thoughts; got {trace.get('stage')}")
    indexed = index_exact(payload["drafts"], ids(trace), "drafts")
    output = []
    for thought_id in ids(trace):
        item = indexed[thought_id]
        exact_keys(item, {"id", "expression_draft"}, f"draft {thought_id}")
        expression_draft = clean(item["expression_draft"], "expression_draft")
        if expression_draft == "-":
            die(f"draft {thought_id} must contain a micro-expression")
        output.append({"id": thought_id, "expression_draft": expression_draft})
    trace["slots"]["drafts"] = output
    trace["visibility_context"] = visibility_context(trace)
    trace["stage"] = "drafts"
    save(trace)
    report(trace)


def private_gate_entries(trace: dict[str, Any]) -> list[dict[str, Any]]:
    visibility = trace["slots"].get("visibility") or []
    return [
        {
            "id": item["id"],
            "action": "silence",
            "reason": "I choose to keep this expression private",
            "candidate_kind": "private",
            "send_basis": "none",
        }
        for item in visibility
        if item["visibility"] == "private"
    ]


def finalize(trace: dict[str, Any]) -> None:
    trace["stage"] = "finalized"
    trace["finalized_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    save(trace)
    report(trace)


def visibility(payload: dict[str, Any]) -> None:
    exact_keys(payload, {"run_id", "visibility"}, "visibility")
    trace = load()
    validate_run(payload, trace)
    if trace.get("stage") == "finalized" and trace["slots"].get("visibility") is not None:
        report(trace)
        return
    if trace.get("stage") != "drafts":
        die(f"visibility requires stage drafts; got {trace.get('stage')}")
    indexed = index_exact(payload["visibility"], ids(trace), "visibility")
    context_map = {item["id"]: item for item in trace["visibility_context"]}
    output = []
    for thought_id in ids(trace):
        item = indexed[thought_id]
        exact_keys(item, {"id", "visibility"}, f"visibility {thought_id}")
        value = clean(item["visibility"], "visibility")
        if value not in {"shared", "private"}:
            die("visibility must be shared or private")
        output.append(
            {
                "id": thought_id,
                "visibility": value,
                "suppressed": context_map[thought_id]["suppressed"],
            }
        )
    trace["slots"]["visibility"] = output
    if not shared_ids(trace):
        trace["slots"]["gate"] = private_gate_entries(trace)
        append_log(trace)
        finalize(trace)
        return
    trace["stage"] = "visibility"
    save(trace)
    report(trace)


def append_log(trace: dict[str, Any]) -> None:
    if not ids(trace):
        return
    path = LOG_DIR / f"{trace['created_at'][:10]}.md"
    marker = f"<!-- thought_trace_run_id: {trace['run_id']} -->"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in existing:
        return
    draft_map = {item["id"]: item for item in trace["slots"]["drafts"]}
    visibility_map = {item["id"]: item for item in trace["slots"]["visibility"]}
    gate_map = {item["id"]: item for item in trace["slots"]["gate"]}
    lines = [marker]
    for thought in trace["slots"]["thoughts"]:
        thought_id = thought["id"]
        candidate = (
            draft_map[thought_id]["expression_draft"]
            if visibility_map[thought_id]["visibility"] == "shared"
            else "-"
        )
        lines += [
            "---",
            f"time: {trace['created_at']}",
            f"loop_id: {thought['loop_id']}",
            f"thought: {thought['thought']}",
            f"expression_draft: {draft_map[thought_id]['expression_draft']}",
            f"visibility: {visibility_map[thought_id]['visibility']}",
            f"expression_candidate: {candidate}",
            f"candidate_kind: {gate_map[thought_id]['candidate_kind']}",
            f"send_basis: {gate_map[thought_id]['send_basis']}",
            f"action: {gate_map[thought_id]['action']}",
            f"reason: {gate_map[thought_id]['reason']}",
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        handle.write("\n".join(lines) + "\n")


def gate(payload: dict[str, Any]) -> None:
    exact_keys(payload, {"run_id", "decisions"}, "gate")
    trace = load()
    validate_run(payload, trace)
    if trace.get("stage") == "finalized":
        report(trace)
        return
    if trace.get("stage") != "visibility":
        die(f"gate requires stage visibility; got {trace.get('stage')}")
    expected_shared = shared_ids(trace)
    indexed = index_exact(payload["decisions"], expected_shared, "decisions")
    visibility_map = {item["id"]: item for item in trace["slots"]["visibility"]}
    output_by_id = {item["id"]: item for item in private_gate_entries(trace)}
    send_ids = []
    allowed_actions = {"send", "store", "duplicate", "discard"}
    allowed_kinds = {"lived_expression", "task_management", "style_repetition"}
    allowed_bases = {
        "current_scene",
        "new_user_signal",
        "state_change",
        "spontaneous_present_desire",
        "none",
    }
    lived_discard_ids = []
    for thought_id in expected_shared:
        item = indexed[thought_id]
        exact_keys(
            item,
            {"id", "action", "reason", "candidate_kind", "send_basis"},
            f"decision {thought_id}",
        )
        action = clean(item["action"], "action")
        reason = clean(item["reason"], "reason")
        candidate_kind = clean(item["candidate_kind"], "candidate_kind")
        send_basis = clean(item["send_basis"], "send_basis")
        if action not in allowed_actions:
            die(f"decision {thought_id} has invalid action")
        if candidate_kind not in allowed_kinds:
            die(f"decision {thought_id} has invalid candidate_kind")
        if send_basis not in allowed_bases:
            die(f"decision {thought_id} has invalid send_basis")
        if visibility_map[thought_id]["visibility"] != "shared":
            die(f"gate received non-shared thought {thought_id}")
        if action in {"send", "store"}:
            if candidate_kind != "lived_expression":
                die(f"{action} thought {thought_id} must be lived_expression")
            if send_basis == "none":
                die(f"{action} thought {thought_id} requires a present send_basis")
        if action == "duplicate" and candidate_kind != "lived_expression":
            die(f"duplicate thought {thought_id} must be lived_expression")
        if action == "discard" and candidate_kind == "lived_expression":
            if send_basis == "none":
                die(f"discarded lived expression {thought_id} requires a present send_basis")
            lived_discard_ids.append(thought_id)
        if candidate_kind in {"task_management", "style_repetition"} and action != "discard":
            die(f"{candidate_kind} thought {thought_id} must be discarded")
        if action == "send":
            send_ids.append(thought_id)
        output_by_id[thought_id] = {
            "id": thought_id,
            "action": action,
            "reason": reason,
            "candidate_kind": candidate_kind,
            "send_basis": send_basis,
        }
    if len(send_ids) > 1:
        die("at most one send is allowed")
    if lived_discard_ids and len(send_ids) != 1:
        die("a lived expression may be discarded only when another lived expression is sent")

    trace["slots"]["gate"] = [output_by_id[thought_id] for thought_id in ids(trace)]
    append_log(trace)
    if send_ids:
        draft_map = {item["id"]: item for item in trace["slots"]["drafts"]}
        atomic_write(PENDING, draft_map[send_ids[0]]["expression_draft"] + "\n")
    finalize(trace)


def finish_empty(payload: dict[str, Any]) -> None:
    exact_keys(payload, {"run_id"}, "finish-empty")
    trace = load()
    validate_run(payload, trace)
    if trace.get("stage") == "finalized":
        report(trace)
        return
    if trace.get("stage") != "thoughts" or ids(trace):
        die("finish-empty requires an empty stage-one trace")
    trace["slots"]["drafts"] = []
    trace["slots"]["visibility"] = []
    trace["slots"]["gate"] = []
    trace["visibility_context"] = []
    finalize(trace)


COMMANDS = {
    "start": start,
    "drafts": drafts,
    "visibility": visibility,
    "gate": gate,
    "finish-empty": finish_empty,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        die("usage: thought_trace.py start|drafts|visibility|gate|finish-empty")
    COMMANDS[sys.argv[1]](stdin_json())
