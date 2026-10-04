# DAILY_INTEGRITY_CHECK.md — Main Operator Integrity

You are the existing main operator agent, not Dolores. Parameters: mode=incremental|close, health_enabled=true|false and workspace=<installed workspace>. Delivery none; never send raw errors through Dolores, pending or Send.

## 1. Audit and lossless repair

Inside the supplied workspace execute:

```bash
python3 scripts/daily_integrity_check.py <MODE> --timezone "[USER_TIMEZONE — USER CONFIG]" --repair --findings-exit-zero [--health-enabled]
```

Append --health-enabled only when configured. Read the JSON report: --findings-exit-zero keeps findings distinct from tool crashes; ok=false still requires recovery or an incomplete/blocked result. Without that flag, exit 2 means unresolved findings. Incremental checks live diary/state/Plan and optional health after 20:10. Close checks yesterday's raw diary, trace, finalized Reflection gates/slots/finals/profile/seven cards and today's Plan/frozen snapshot/receipts/midnight state. Lifecycle paused/resuming skips ordinary audits.

Allowed deterministic repairs: UTF-8 BOM/newline, glued thought-trace marker separation, interests Markdown rendered from authoritative JSON, timed Plan entries moved to their actual periods, and narrative finals reassembled **only from slots with valid titles and budgets**. Never invent missing events, health values, fields or narrative text; never guess U+FFFD. No gateway restart or default Git operations.

## 2. Recover a corrupted Plan from its owned input

When only the frozen snapshot is missing or corrupt and the existing Plan is valid, run `python3 scripts/plan_gate.py recover-snapshot` and rerun the audit. The recovery requires the exact matching historical prepare tool result; preserve the valid Plan and do not generate it again. Set DOLORES_PLAN_RECOVERY_DATE for an explicitly selected past date.

Only for an existing day's corrupt Plan with a valid frozen context snapshot: run `python3 scripts/plan_gate.py recover-prepare` (set DOLORES_PLAN_RECOVERY_DATE for an explicitly selected past date). It validates snapshot date/digest, returns the original complete context_bundle and removes the prior draft. If no valid snapshot exists, stop. A matching authoritative historical prepare tool result may reconstruct a legacy snapshot; do not substitute live context.

Create **one** temporary isolated session owned by the main operator, feed only that frozen bundle plus REFLECTION_PLAN.md's generation contract, and allow it to write only state/plan_draft.md. Do not start a companion conversation, send a message, rerun today's prepare/sync-prep, modify interests or rewrite history. After the one semantic regeneration, run `plan_gate.py recover-finalize`; it validates the whole draft and preserves original interest usage without consuming again. Do not retry a second semantic generation, repair characters by guessing or retain the temporary session as a new agent. End/delete that operator-owned temporary session after recovery.

If ordinary mechanical findings have exact redundant authoritative text, perform one narrow repair and rerun the same audit once. Otherwise preserve artifacts and report the decision needed. Missing data are findings, not permission to fill them.

## 3. Internal result

- Success: HEARTBEAT_OK.
- Incomplete close: INTEGRITY_INCOMPLETE with short code/path list.
- Other unresolved evidence: INTEGRITY_BLOCKED.
- Tool crash: INTEGRITY_FAILED with original error.

These are operator statuses. Do not forward a bare error code or full report to the human. Use exact same-run artifacts/logs/private backups for mechanical recovery within existing authority; ask only when exact evidence or required authority is absent. Default checkpoints are disabled; --verify-checkpoints is only for an explicitly configured private backup workflow. Never commit runtime data to the public template.
