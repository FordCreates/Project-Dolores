#!/usr/bin/env python3
"""Deterministic pending-message delivery transaction.

Heartbeat Send and check-in Send invoke this file directly as command jobs. No
model participates in delivery. State is committed only after Telegram returns
a success acknowledgement.
"""

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.session_append import (
    SESSION_DIR,
    SESSION_KEY,
    SESSIONS_JSON,
    append_to_session,
)

WORKSPACE = Path("[WORKSPACE_PATH — USER CONFIG]")
PENDING = WORKSPACE / "state" / "pending_message.md"
RECEIPT = WORKSPACE / "state" / "send_delivery.json"
LOCK = WORKSPACE / "state" / ".send_delivery.lock"
EMPTY_MARKER = "EMPTY"
GATE_MINUTES = 20
TELEGRAM_ACCOUNT = "dolores"
TELEGRAM_TARGET = "[TELEGRAM_CHAT_ID — USER CONFIG]"
OPENCLAW_BIN = shutil.which("openclaw") or "openclaw"


class SendError(RuntimeError):
    """A delivery transaction could not be completed safely."""


@dataclass(frozen=True)
class SendConfig:
    pending: Path = PENDING
    receipt: Path = RECEIPT
    lock: Path = LOCK
    sessions_json: Path = SESSIONS_JSON
    session_dir: Path = SESSION_DIR
    session_key: str = SESSION_KEY
    empty_marker: str = EMPTY_MARKER
    gate_minutes: int = GATE_MINUTES
    telegram_account: str = TELEGRAM_ACCOUNT
    telegram_target: str = TELEGRAM_TARGET
    openclaw_bin: str = OPENCLAW_BIN


DEFAULT_CONFIG = SendConfig()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def read_pending(config: SendConfig) -> str:
    return config.pending.read_text(encoding="utf-8") if config.pending.exists() else ""


def is_empty(content: str, config: SendConfig) -> bool:
    return not content or content.strip() == config.empty_marker


def compare_and_clear(expected: str, config: SendConfig) -> bool:
    if read_pending(config) != expected:
        return False
    atomic_write_text(config.pending, config.empty_marker)
    return True


def read_receipt(config: SendConfig) -> dict[str, Any] | None:
    if not config.receipt.exists():
        return None
    try:
        payload = json.loads(config.receipt.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SendError(f"delivery receipt is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise SendError("delivery receipt must be a JSON object")
    return payload


def write_receipt(payload: dict[str, Any], config: SendConfig) -> None:
    payload["updated_at"] = utc_now()
    atomic_write_json(config.receipt, payload)


def is_user_active(config: SendConfig = DEFAULT_CONFIG) -> bool:
    """Check if user has interacted within the gate window. True = suppress send."""
    try:
        sessions = json.loads(config.sessions_json.read_text(encoding="utf-8"))
        session_id = sessions[config.session_key]["sessionId"]
        jsonl_path = config.session_dir / f"{session_id}.jsonl"
        if not jsonl_path.exists():
            return False
        lines = jsonl_path.read_text(encoding="utf-8").strip().split("\n")
        for line in reversed(lines):
            entry = json.loads(line)
            msg = entry.get("message", {})
            if msg.get("role") == "user":
                ts = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - ts).total_seconds() / 60
                return age < config.gate_minutes
        return False
    except Exception:
        return False  # fail-open: on any error, allow send


def extract_json_object(stdout: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(stdout):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(stdout[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise SendError("message CLI returned no JSON acknowledgement")


def find_message_id(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("messageId", "message_id"):
            if value.get(key) is not None:
                return str(value[key])
        for child in value.values():
            found = find_message_id(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_message_id(child)
            if found:
                return found
    return None


def send_telegram(content: str, config: SendConfig) -> dict[str, Any]:
    command = [
        config.openclaw_bin,
        "message",
        "send",
        "--account",
        config.telegram_account,
        "--channel",
        "telegram",
        "--target",
        config.telegram_target,
        "--message",
        content,
        "--json",
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=45, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise SendError("Telegram send timed out; pending was preserved") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SendError(
            f"Telegram send failed with exit {result.returncode}: {detail[-1000:]}"
        )
    acknowledgement = extract_json_object(result.stdout)
    if acknowledgement.get("error") or acknowledgement.get("ok") is False:
        raise SendError(f"Telegram rejected delivery: {acknowledgement}")
    return acknowledgement


def append_delivery(receipt: dict[str, Any], config: SendConfig) -> None:
    append_to_session(
        receipt["content"],
        entry_id=receipt["session_entry_id"],
        timestamp=receipt["sent_at"],
        sessions_json=config.sessions_json,
        session_dir=config.session_dir,
        session_key=config.session_key,
        raise_on_error=True,
    )


def finish_acknowledged_delivery(
    receipt: dict[str, Any], config: SendConfig
) -> dict[str, Any]:
    append_delivery(receipt, config)
    receipt["session_appended"] = True
    receipt["pending_cleared"] = compare_and_clear(receipt["content"], config)
    receipt["status"] = "committed"
    receipt["committed_at"] = utc_now()
    receipt.pop("error", None)
    write_receipt(receipt, config)
    return {
        "status": "sent",
        "delivery_id": receipt["delivery_id"],
        "message_id": receipt.get("message_id"),
        "pending_cleared": receipt["pending_cleared"],
        "recovered": bool(receipt.get("recovered")),
    }


def recover_if_needed(config: SendConfig) -> dict[str, Any] | None:
    receipt = read_receipt(config)
    if not receipt:
        return None
    if receipt.get("status") == "delivered":
        receipt["recovered"] = True
        return finish_acknowledged_delivery(receipt, config)
    if receipt.get("status") == "sending":
        raise SendError(
            "previous send stopped after transport began; outcome is uncertain and "
            "pending was preserved for manual reconciliation"
        )
    return None


SendCallable = Callable[[str, SendConfig], dict[str, Any]]


def run_once(
    config: SendConfig = DEFAULT_CONFIG,
    *,
    sender: SendCallable = send_telegram,
    active_check: Callable[[SendConfig], bool] = is_user_active,
) -> dict[str, Any]:
    config.lock.parent.mkdir(parents=True, exist_ok=True)
    with config.lock.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)

        recovered = recover_if_needed(config)
        if recovered:
            return recovered

        content = read_pending(config)
        if is_empty(content, config):
            if not config.pending.exists():
                atomic_write_text(config.pending, config.empty_marker)
            return {"status": "empty"}

        if active_check(config):
            receipt = {
                "schema_version": 1,
                "delivery_id": uuid.uuid4().hex,
                "content_sha256": content_hash(content),
                "status": "suppressed",
                "created_at": utc_now(),
                "pending_cleared": compare_and_clear(content, config),
                "reason": f"user active within {config.gate_minutes} minutes",
            }
            write_receipt(receipt, config)
            return {
                "status": "suppressed",
                "delivery_id": receipt["delivery_id"],
                "pending_cleared": receipt["pending_cleared"],
            }

        delivery_id = uuid.uuid4().hex
        receipt = {
            "schema_version": 1,
            "delivery_id": delivery_id,
            "session_entry_id": delivery_id[:8],
            "content_sha256": content_hash(content),
            "content": content,
            "status": "sending",
            "created_at": utc_now(),
        }
        write_receipt(receipt, config)

        try:
            acknowledgement = sender(content, config)
        except Exception as exc:
            receipt["status"] = "failed"
            receipt["error"] = str(exc)
            write_receipt(receipt, config)
            if isinstance(exc, SendError):
                raise
            raise SendError(str(exc)) from exc

        receipt["status"] = "delivered"
        receipt["sent_at"] = utc_now()
        receipt["message_id"] = find_message_id(acknowledgement)
        receipt["acknowledgement"] = acknowledgement
        write_receipt(receipt, config)
        return finish_acknowledged_delivery(receipt, config)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="validate configuration without sending"
    )
    return parser.parse_args()


def check_state(config: SendConfig) -> dict[str, Any]:
    executable = config.openclaw_bin
    available = Path(executable).exists() if "/" in executable else bool(shutil.which(executable))
    if not available:
        raise SendError(f"openclaw executable not found: {executable}")
    receipt = read_receipt(config)
    return {
        "status": "ok",
        "pending_exists": config.pending.exists(),
        "pending_empty": is_empty(read_pending(config), config),
        "receipt_status": receipt.get("status") if receipt else None,
        "openclaw_bin": executable,
    }


def main() -> int:
    args = parse_args()
    try:
        result = check_state(DEFAULT_CONFIG) if args.check else run_once(DEFAULT_CONFIG)
    except Exception as exc:
        print(
            json.dumps({"status": "error", "error": str(exc), "at": utc_now()}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
