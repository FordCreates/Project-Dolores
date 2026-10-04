# Pause and Resume

This is operator work. The guard never changes accounts, bindings, cron enablement or gateway processes. Pause is off-camera time; no character should experience the wall-clock gap as abandonment or lost memory.

## Pause

After a real diary/Heartbeat boundary, create a local continuity snapshot:

```bash
python3 scripts/pause_resume_guard.py snapshot --archive state/archive/pre-pause-YYYY-MM-DD --last-valid-diary-date YYYY-MM-DD
```

It hashes live state, stable context and the last seven valid active-period raw diaries, with loop ids and explicit restore/rebuild/quarantine policy. For a private system snapshot add --openclaw-root <your-openclaw-root> and --agent-id dolores. This copies local configuration (which may contain secrets) and exports only matching companion/operator cron rows from state/openclaw.sqlite, with a legacy jobs.json fallback. It never copies the shared database or archived other-agent run logs. An archive must remain under state/archive and must not already contain files. Archive paths/hashes are validated before recovery.

Set lifecycle.mode=paused only under operator authority, then disable the owned jobs/binding as requested. Do not write pause-gap narratives or alter stable memories merely because time passed. Archives are private and ignored; never publish them.

## Resume

After first real contact, set lifecycle.mode=resuming, last_valid_diary_date and archive_path. Initialize the review file:

```bash
python3 scripts/pause_resume_guard.py init-resume --archive state/archive/pre-pause-YYYY-MM-DD --date YYYY-MM-DD
```

Review every archived loop exactly once (restore/close/quarantine with a concrete reason); separately justify any new loop. Rebuild today's world and full life Plan, preserve affect as evidence, clear pending to EMPTY, start today's thought log and diary empty, and write resume_context.md. Verify the archived raw-history dates and hashes. Record real first-contact evidence and the completed review in resume_reconciliation.json, status prepared. Never restore an old thought/pending queue or age-expire sticky concerns.

```bash
python3 scripts/pause_resume_guard.py verify-resume
```

Only ready_for_bootstrap permits one complete Heartbeat. The loader uses the last valid active history while resuming. Bootstrap ends with:

```bash
python3 scripts/pause_resume_guard.py mark-bootstrap --thought-run-id '<this-run-id>'
```

It requires a real resume-day diary, current last_sync/world/affect and the fresh finalized thought trace, then seals hashes in reconciliation. A second bootstrap is rejected. The operator then switches lifecycle to active and restores the deliberately selected schedules/binding. Do not restart the gateway from this workflow; the human owns any needed restart.

## Optional private Git checkpoints

Public runtime flows do not commit. If a private backup repository is explicitly configured, deliberately configure that repository to track the owned runtime paths (the default installed ignores exclude life data), set DOLORES_PRIVATE_BACKUP=1 and invoke scripts/cron_git_commit.py with --repo and --workspace-prefix. The helper scopes paths by workflow, refuses existing staged content and damaged text, and never pushes. Heartbeat checkpoints also require the current --thought-run-id. Never enable this against a public template repository; archive/config/session files are outside its allowlist.
