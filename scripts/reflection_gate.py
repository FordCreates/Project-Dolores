#!/usr/bin/env python3
"""Write gate and deterministic assembler for Reflection Self/Rel."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("DOLORES_REFLECTION_ROOT", Path(__file__).resolve().parents[1]))
TRACE = ROOT / "reflection_trace.md"
SELF_CURRENT_DRAFT = ROOT / "state/self_current_draft.md"

SPECS: dict[str, dict[str, Any]] = {
    "self": {
        "prefix": "self_slot_",
        "final": ROOT / "memory/self-narrative.md",
        "document_header": "# Self-Narrative — My Story\n\n*The voice in my head after the lights go out.*\n\n---\n",
        "titles": {1: None, 2: "## Recent Fractures", 3: "## Recurring Patterns", 4: "## Unresolved Tensions", 5: "## Current Self"},
        "budgets": {1: (250, 350), 2: (250, 350), 3: (200, 300), 4: (200, 300), 5: (250, 350)},
        "required_rewrite": {5},
    },
    "rel": {
        "prefix": "rel_slot_",
        "final": ROOT / "memory/relationship-summary.md",
        "document_header": "# Relationship Summary — Our Story\n",
        "titles": {1: "## Relationship Foundation", 2: "## Key Turning Points", 3: "## Current Patterns", 4: "## Mutual Confirmations", 5: "## Relational Tensions"},
        "budgets": {1: (200, 250), 2: (300, 400), 3: (250, 350), 4: (200, 300), 5: (250, 350)},
        "required_rewrite": set(),
    },
}


def die(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        die(f"invalid JSON in {path}: {exc}")


def run_date() -> date:
    raw = os.environ.get("DOLORES_REFLECTION_DATE")
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        die("DOLORES_REFLECTION_DATE must be YYYY-MM-DD")


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


def stdin_json() -> dict[str, Any]:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        die(f"invalid JSON: {exc}")
    if not isinstance(payload, dict):
        die("payload must be an object")
    return payload


def spec(kind: str) -> dict[str, Any]:
    if kind not in SPECS:
        die("kind must be self or rel")
    return SPECS[kind]


def gate_path(kind: str) -> Path:
    spec(kind)
    return ROOT / f"state/reflection_{kind}_gate.json"


def slot_path(kind: str, day: str, slot: int) -> Path:
    return ROOT / "state/slots" / day / f"{spec(kind)['prefix']}{slot}.md"


def load_gate(kind: str, allowed_stages: set[str]) -> dict[str, Any]:
    gate = read_json(gate_path(kind))
    if not isinstance(gate, dict):
        die("gate missing; run prepare first")
    if gate.get("kind") != kind or gate.get("run_date") != run_date().isoformat():
        die("gate belongs to another Reflection run")
    if gate.get("stage") not in allowed_stages:
        die(f"gate stage must be one of {sorted(allowed_stages)}")
    return gate


def save_gate(gate: dict[str, Any]) -> None:
    atomic_write(gate_path(gate["kind"]), json.dumps(gate, ensure_ascii=False, indent=2) + "\n")


def trace_date() -> str:
    if not TRACE.exists():
        die("PREP has not run: reflection_trace.md missing")
    match = re.search(r"^generated_at:\s*(\d{4}-\d{2}-\d{2})", TRACE.read_text(encoding="utf-8"), re.M)
    if not match:
        die("PREP has not run: generated_at missing")
    return match.group(1)


def validate_trace_consistency(kind: str) -> None:
    content = TRACE.read_text(encoding="utf-8")
    direction_label = "self-narrative" if kind == "self" else "relationship-summary"
    tension_label = "tensions_self" if kind == "self" else "tensions_relational"

    direction = re.search(
        rf"^-\s*{re.escape(direction_label)}\s*update direction:\s*(.+)$",
        content,
        re.M,
    )
    if not direction:
        die(f"trace missing {direction_label} update direction")

    section = re.search(
        rf"^{tension_label}:\s*(?:#.*)?$(.*?)(?=^tensions_(?:self|relational):|^##\s|\Z)",
        content,
        re.M | re.S,
    )
    if not section:
        die(f"trace missing {tension_label}")
    tensions = [
        line.strip()[2:].strip()
        for line in section.group(1).splitlines()
        if line.strip().startswith("- ")
    ]
    if not tensions:
        die(f"trace {tension_label} must contain one decision bullet")

    keep = direction.group(1).strip().startswith("KEEP")
    has_new_tension = any(item.rstrip(".") != "No new structural tension" for item in tensions)
    if keep and has_new_tension:
        die(f"{direction_label} KEEP cannot coexist with new structural tension in {tension_label}")


def slot_validation_error(kind: str, slot: int, path: Path) -> tuple[int | None, str | None]:
    if not path.exists():
        return None, f"slot missing: {path}"
    content = path.read_text(encoding="utf-8")
    title = spec(kind)["titles"][slot]
    first_line = content.splitlines()[0] if content.splitlines() else ""
    if title is None and first_line.startswith("## "):
        return None, f"{path} must begin with the opening narrative, not a section title"
    if title is not None and first_line != title:
        return None, f"{path} must begin with {title!r}"
    count = len(content.split())
    lower, upper = spec(kind)["budgets"][slot]
    if not lower <= count <= upper:
        return None, f"{path} has {count} words; expected {lower}-{upper}"
    return count, None


def validate_slot(kind: str, slot: int, path: Path) -> int:
    count, error = slot_validation_error(kind, slot, path)
    if error:
        die(error)
    assert count is not None
    return count


def report(gate: dict[str, Any], **extra: Any) -> None:
    output = {key: gate.get(key) for key in ("kind", "run_date", "source_date", "stage", "required_rewrite", "rewrite", "keep")}
    output.update({"ok": True, "gate_path": str(gate_path(gate["kind"])), **extra})
    print(json.dumps(output, ensure_ascii=False))


def prepare(kind: str) -> None:
    today = run_date().isoformat()
    yesterday = (run_date() - timedelta(days=1)).isoformat()
    if trace_date() != today:
        die(f"PREP output is not from today({trace_date()} vs {today})")
    validate_trace_consistency(kind)
    if kind == "self":
        validate_slot("self", 5, SELF_CURRENT_DRAFT)

    required = set(spec(kind)["required_rewrite"])
    warnings: dict[str, str] = {}
    fallback_slots = range(1, 5) if kind == "self" else range(1, 6)
    for slot in fallback_slots:
        source = slot_path(kind, yesterday, slot)
        target = slot_path(kind, today, slot)
        _, error = slot_validation_error(kind, slot, source)
        if error:
            required.add(slot)
            warnings[str(slot)] = f"{error}; rewrite required"
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    gate = {
        "kind": kind,
        "run_date": today,
        "source_date": yesterday,
        "stage": "prepared",
        "required_rewrite": sorted(required),
        "rewrite": None,
        "keep": None,
    }
    save_gate(gate)
    report(gate, warnings=warnings)


def decide(kind: str) -> None:
    payload = stdin_json()
    if set(payload) != {"rewrite"}:
        die("decide payload must contain exactly: rewrite")
    rewrite = payload["rewrite"]
    if not isinstance(rewrite, list) or any(type(item) is not int for item in rewrite):
        die("rewrite must be a list of slot numbers")
    if len(set(rewrite)) != len(rewrite) or any(item not in range(1, 6) for item in rewrite):
        die("rewrite slots must be unique integers from 1 to 5")

    gate = load_gate(kind, {"prepared"})
    required = set(gate["required_rewrite"])
    if not required.issubset(rewrite):
        die(f"rewrite must include required slots {sorted(required)}")
    gate["rewrite"] = sorted(rewrite)
    gate["keep"] = [slot for slot in range(1, 6) if slot not in rewrite]
    gate["stage"] = "decided"
    save_gate(gate)
    report(gate)


def assemble(kind: str, today: str) -> str:
    parts = [slot_path(kind, today, slot).read_text(encoding="utf-8").rstrip("\n") for slot in range(1, 6)]
    if kind == "self":
        return spec(kind)["document_header"] + parts[0] + "\n---\n\n" + "\n\n---\n\n".join(parts[1:]) + "\n"
    return spec(kind)["document_header"] + "\n\n---\n\n".join(parts) + "\n"


def finalize(kind: str) -> None:
    gate = load_gate(kind, {"decided", "finalized"})
    restored_keep: list[int] = []
    for slot in gate["keep"]:
        source = slot_path(kind, gate["source_date"], slot)
        target = slot_path(kind, gate["run_date"], slot)
        if not source.exists():
            die(f"KEEP slot {slot} has no source fallback")
        if not target.exists() or target.read_bytes() != source.read_bytes():
            restored_keep.append(slot)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    if kind == "self":
        validate_slot("self", 5, SELF_CURRENT_DRAFT)
        current_slot = slot_path("self", gate["run_date"], 5)
        current_slot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SELF_CURRENT_DRAFT, current_slot)

    counts = {str(slot): validate_slot(kind, slot, slot_path(kind, gate["run_date"], slot)) for slot in range(1, 6)}
    final_path = spec(kind)["final"]
    atomic_write(final_path, assemble(kind, gate["run_date"]))
    gate["stage"] = "finalized"
    save_gate(gate)
    report(gate, restored_keep=restored_keep, word_counts=counts, final_path=str(final_path))


COMMANDS = {"prepare": prepare, "decide": decide, "finalize": finalize}

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in COMMANDS:
        die("usage: reflection_gate.py prepare|decide|finalize self|rel")
    COMMANDS[sys.argv[1]](sys.argv[2])
