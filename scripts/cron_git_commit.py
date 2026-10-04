#!/usr/bin/env python3
"""Create a local, path-scoped Git checkpoint for a Dolores cron workflow.

The OpenClaw repository is shared with unrelated agents and runtime data, so a
cron must never use ``git add -A`` at repository scope.  This helper stages only
the files that the selected Dolores workflow is allowed to write, verifies the
index again before committing, and deliberately never pushes.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import NoReturn


DEFAULT_WORKSPACE_PREFIX = "."
HEARTBEAT_TRACE_MAX_AGE = timedelta(minutes=30)
HEARTBEAT_TRACE_FUTURE_TOLERANCE = timedelta(minutes=5)

HEARTBEAT_FILES = {
    "state/active_loops.md",
    "state/affect.json",
    "state/last_sync_at",
    "state/pending_message.md",
    "state/primed_sticky.md",
    "state/thought_trace.json",
    "state/world_context.json",
}
HEARTBEAT_DIRS = {
    "memory/diary",
    "state/thoughts_log",
}

REFLECTION_FILES = {
    "reflection_trace.md",
    "state/current_interests.json",
    "state/current_interests.md",
    "state/daily_plan.md",
    "state/plan_consumption.json",
    "state/plan_draft.md",
    "state/plan_gate.json",
    "state/plan_context_snapshot.json",
    "state/plan_user_context.json",
    "state/world_context.json",
    "state/self_current_draft.md",
    "state/reflection_self_gate.json",
    "state/reflection_rel_gate.json",
    "memory/profile-user.md",
    "memory/relationship-summary.md",
    "memory/self-narrative.md",
}
REFLECTION_DIRS = {
    "memory/cards",
    "state/slots",
}

INTEGRITY_FILES = HEARTBEAT_FILES | REFLECTION_FILES
INTEGRITY_DIRS = HEARTBEAT_DIRS | REFLECTION_DIRS | {
    "memory/health",
    "memory/exercise",
}


class CommitError(RuntimeError):
    """A guard or Git operation prevented a safe checkpoint."""


def run_git(
    repo: Path,
    *args: str,
    check: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=text,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.strip() if text else result.stderr.decode(errors="replace").strip()
        raise CommitError(f"git {' '.join(args)} failed: {stderr or f'exit {result.returncode}'}")
    return result


def fail(message: str, workflow: str | None = None) -> NoReturn:
    payload = {
        "ok": False,
        "workflow": workflow,
        "error": message,
        "pushed": False,
    }
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    raise SystemExit(1)


def parse_nul(raw: bytes) -> list[str]:
    return [item.decode("utf-8", errors="surrogateescape") for item in raw.split(b"\0") if item]


def relative_to_workspace(path: str, workspace_prefix: str) -> str | None:
    prefix = workspace_prefix.strip("/") + "/"
    if workspace_prefix in {"", "."}:
        return path
    if not path.startswith(prefix):
        return None
    return path[len(prefix) :]


def inside_markdown_dir(relative: str, directory: str) -> bool:
    path = PurePosixPath(relative)
    root = PurePosixPath(directory)
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return path.suffix == ".md" and path != root


def is_allowed(path: str, workflow: str, workspace_prefix: str) -> bool:
    relative = relative_to_workspace(path, workspace_prefix)
    if relative is None:
        return False

    files, directories = {
        "heartbeat": (HEARTBEAT_FILES, HEARTBEAT_DIRS),
        "reflection": (REFLECTION_FILES, REFLECTION_DIRS),
        "integrity": (INTEGRITY_FILES, INTEGRITY_DIRS),
    }[workflow]
    return relative in files or any(
        inside_markdown_dir(relative, directory) for directory in directories
    )


def dirty_paths(repo: Path) -> list[str]:
    tracked = parse_nul(run_git(repo, "diff", "--name-only", "-z", text=False).stdout)
    untracked = parse_nul(
        run_git(repo, "ls-files", "--others", "--exclude-standard", "-z", text=False).stdout
    )
    return sorted(set(tracked + untracked))


def staged_paths(repo: Path) -> list[str]:
    return parse_nul(run_git(repo, "diff", "--cached", "--name-only", "-z", text=False).stdout)


def default_message(workflow: str) -> str:
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    return f"dolores: {workflow} checkpoint {timestamp}"


def validate_changed_text(repo: Path, paths: list[str]) -> None:
    """Fail closed before staging any damaged text artifact."""
    for relative in paths:
        path = repo / relative
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_file():
            raise CommitError(f"checkpoint path must be a regular file: {relative}")
        try:
            content = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CommitError(f"checkpoint path is not valid UTF-8: {relative}: {exc}") from exc
        if "\ufffd" in content:
            count = content.count("\ufffd")
            raise CommitError(
                f"checkpoint path contains {count} Unicode replacement character(s): {relative}"
            )


def validate_world_context(repo: Path, workspace_prefix: str) -> None:
    gate = Path(__file__).with_name("world_context_gate.py")
    workspace = repo / workspace_prefix.strip("/")
    env = os.environ.copy()
    env["DOLORES_WORKSPACE"] = str(workspace)
    result = subprocess.run(
        [sys.executable, str(gate)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        detail = (result.stdout or result.stderr).strip() or f"exit {result.returncode}"
        raise CommitError(f"world_context schema validation failed: {detail}")


def parse_aware_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise CommitError(f"thought trace {field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CommitError(f"thought trace {field} is not a valid ISO timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CommitError(f"thought trace {field} must include a timezone: {value!r}")
    return parsed


def validate_heartbeat_trace(
    repo: Path,
    workspace_prefix: str,
    thought_run_id: str | None,
    *,
    now: datetime | None = None,
) -> None:
    if not thought_run_id:
        raise CommitError(
            "heartbeat checkpoint requires --thought-run-id from this run's finalized Step 5"
        )

    trace_path = repo / workspace_prefix.strip("/") / "state/thought_trace.json"
    try:
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CommitError(f"heartbeat thought trace is missing: {trace_path}") from exc
    except json.JSONDecodeError as exc:
        raise CommitError(f"heartbeat thought trace is invalid JSON: {exc}") from exc
    if not isinstance(trace, dict):
        raise CommitError("heartbeat thought trace must be a JSON object")

    actual_run_id = trace.get("run_id")
    if actual_run_id != thought_run_id:
        raise CommitError(
            "heartbeat thought run_id mismatch: "
            f"expected={thought_run_id!r}, trace={actual_run_id!r}"
        )
    if trace.get("stage") != "finalized":
        raise CommitError(
            f"heartbeat thought trace is not finalized: stage={trace.get('stage')!r}"
        )

    created_at_raw = trace.get("created_at")
    finalized_at_raw = trace.get("finalized_at")
    created_at = parse_aware_timestamp(created_at_raw, "created_at")
    finalized_at = parse_aware_timestamp(finalized_at_raw, "finalized_at")
    if not thought_run_id.startswith(f"{created_at_raw}-"):
        raise CommitError("heartbeat thought run_id does not encode trace created_at")
    if finalized_at < created_at:
        raise CommitError("heartbeat thought trace finalized_at precedes created_at")

    current = now or datetime.now().astimezone()
    if current.tzinfo is None or current.utcoffset() is None:
        raise CommitError("heartbeat checkpoint clock must include a timezone")
    age = current - finalized_at
    if age > HEARTBEAT_TRACE_MAX_AGE:
        raise CommitError(
            "heartbeat thought trace is stale: "
            f"finalized_at={finalized_at_raw}, max_age={int(HEARTBEAT_TRACE_MAX_AGE.total_seconds() // 60)}m"
        )
    if age < -HEARTBEAT_TRACE_FUTURE_TOLERANCE:
        raise CommitError(
            f"heartbeat thought trace is from the future: finalized_at={finalized_at_raw}"
        )


def unstage(repo: Path, paths: list[str]) -> None:
    if not paths:
        return
    subprocess.run(
        ["git", "-C", str(repo), "restore", "--staged", "--", *paths],
        check=False,
        capture_output=True,
        text=True,
    )


def checkpoint(
    repo: Path,
    workflow: str,
    workspace_prefix: str,
    message: str | None,
    thought_run_id: str | None = None,
) -> dict[str, object]:
    if os.environ.get("DOLORES_PRIVATE_BACKUP") != "1":
        raise CommitError("set DOLORES_PRIVATE_BACKUP=1 only for an explicitly configured private backup repository")
    if not repo.is_dir():
        raise CommitError(f"repository does not exist: {repo}")
    run_git(repo, "rev-parse", "--is-inside-work-tree")
    if workflow == "heartbeat":
        validate_heartbeat_trace(repo, workspace_prefix, thought_run_id)
    elif thought_run_id is not None:
        raise CommitError("--thought-run-id is only valid for heartbeat checkpoints")
    validate_world_context(repo, workspace_prefix)

    git_dir_raw = run_git(repo, "rev-parse", "--absolute-git-dir").stdout.strip()
    lock_path = Path(git_dir_raw) / "dolores-cron-commit.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CommitError("another Dolores cron commit is already running") from exc

        existing_staged = staged_paths(repo)
        if existing_staged:
            preview = ", ".join(existing_staged[:8])
            if len(existing_staged) > 8:
                preview += f", ... (+{len(existing_staged) - 8})"
            raise CommitError(f"refusing to mix with pre-existing staged changes: {preview}")

        changed = dirty_paths(repo)
        allowed = [path for path in changed if is_allowed(path, workflow, workspace_prefix)]

        validate_changed_text(repo, allowed)

        if workflow == "integrity" and not allowed:
            return {
                "ok": True,
                "workflow": workflow,
                "commit": run_git(repo, "rev-parse", "HEAD").stdout.strip(),
                "paths": [],
                "ignoredDirtyPaths": len(changed),
                "skipped": True,
                "pushed": False,
            }

        try:
            if allowed:
                run_git(repo, "add", "-A", "--", *allowed)

            staged = staged_paths(repo)
            unexpected = [path for path in staged if not is_allowed(path, workflow, workspace_prefix)]
            if unexpected:
                raise CommitError(f"staged path escaped {workflow} allowlist: {', '.join(unexpected)}")

            if set(staged) != set(allowed):
                raise CommitError(
                    "staged paths differ from the approved change set: "
                    f"approved={allowed!r}, staged={staged!r}"
                )

            run_git(repo, "diff", "--cached", "--check")
            run_git(
                repo,
                "-c",
                "core.hooksPath=/dev/null",
                "commit",
                "--allow-empty",
                "-m",
                message or default_message(workflow),
            )
            commit = run_git(repo, "rev-parse", "HEAD").stdout.strip()
        except Exception:
            unstage(repo, allowed)
            raise

        result: dict[str, object] = {
            "ok": True,
            "workflow": workflow,
            "commit": commit,
            "paths": staged,
            "ignoredDirtyPaths": len(changed) - len(allowed),
            "skipped": False,
            "pushed": False,
        }
        if workflow == "heartbeat":
            result["thoughtRunId"] = thought_run_id
        return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow", choices=("heartbeat", "reflection", "integrity"))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--workspace-prefix", default=DEFAULT_WORKSPACE_PREFIX)
    parser.add_argument("--message")
    parser.add_argument("--thought-run-id")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        result = checkpoint(
            repo=args.repo.resolve(),
            workflow=args.workflow,
            workspace_prefix=args.workspace_prefix,
            message=args.message,
            thought_run_id=args.thought_run_id,
        )
    except CommitError as exc:
        fail(str(exc), args.workflow)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
