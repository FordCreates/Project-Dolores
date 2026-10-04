"""Anonymous integration fixtures; no real account, gateway, memory or commit."""

import importlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import daily_integrity_check as integrity
import reflection_gate as reflection
import loops_maintenance as loops
import sticky_sampling as sampling
import send_and_append as delivery
import cron_git_commit as checkpoints
import inject_context as injection
import heartbeat_finalize as final_state

DAY = date(2030, 1, 1)


def world(day=DAY):
    return {
        "current_time": day.isoformat() + "T12:00:00+00:00",
        "day_of_week": day.strftime("%A"), "time_mode": "afternoon",
        "is_quiet_hours": False, "weather": "Cloudy",
        "user_location": "home", "user_activity": "resting",
        "scene": "Quiet room", "dolores_activity": "I am drawing.",
        "dolores_appearance": "I am wearing a sweater.",
        "recommended_intensity": "normal", "hours_since_last_interaction": 2,
        "recent_message_count_24h": 0, "context_note": "",
    }


def plan(day):
    return f"# {day.isoformat()} ({day.strftime('%A')}) Schedule\n\n## Morning\n- 09:00 Draw a little\n\n## Afternoon\n- 14:00 Browse a book\n\n## Evening\n- 20:00 Make tea\n"


def slot(kind, number, tag="baseline"):
    spec = reflection.SPECS[kind]
    title = spec["titles"][number]
    minimum = spec["budgets"][number][0]
    heading = title + "\n\n" if title else ""
    return heading + " ".join([tag] * (minimum - len(heading.split()) + 5)) + "\n"


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = os.environ.copy()
        self.env.update({
            "PYTHONDONTWRITEBYTECODE": "1", "DOLORES_WORKSPACE": str(self.root),
            "DOLORES_REFLECTION_ROOT": str(self.root), "DOLORES_REFLECTION_DATE": DAY.isoformat(),
            "DOLORES_PLAN_ROOT": str(self.root), "DOLORES_PLAN_RUN_DATE": DAY.isoformat(),
            "DOLORES_COMPANION_SESSIONS_DIR": str(self.root / "isolated-sessions"),
            "DOLORES_PLAN_RECOVERY_DATE": (DAY + timedelta(days=1)).isoformat(),
            "DOLORES_DIARY_ROOT": str(self.root), "DOLORES_DIARY_DATE": DAY.isoformat(),
            "DOLORES_THOUGHT_TRACE_PATH": str(self.root / "state/thought_trace.json"),
            "DOLORES_THOUGHT_LOG_DIR": str(self.root / "state/thoughts_log"),
            "DOLORES_PENDING_MESSAGE_PATH": str(self.root / "state/pending_message.md"),
            "DOLORES_ACTIVE_LOOPS_PATH": str(self.root / "state/active_loops.md"),
            "DOLORES_TODAY": DAY.isoformat(),
        })

    def tearDown(self):
        self.temp.cleanup()

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(value) + "\n" if isinstance(value, dict) else value
        path.write_text(text, encoding="utf-8")
        return path

    def read_json(self, relative):
        return json.loads((self.root / relative).read_text())

    def cli(self, script, *args, payload=None, success=True):
        result = subprocess.run(
            [sys.executable, "-B", str(REPO / "scripts" / script), *args],
            input=json.dumps(payload) if payload is not None else None,
            capture_output=True, text=True, env=self.env,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def trace(self, self_tension="No new structural tension", rel_tension="No new structural tension"):
        self.write("reflection_trace.md", f"# Reflection Trace\ngenerated_at: {DAY.isoformat()}T23:15:00+00:00\n\n## RAG Phase\n- E1: An anonymous observation\n\n## Analysis and Decision\n- self-narrative update direction: KEEP\n- relationship-summary update direction: KEEP\n\n## Tension Routing\ntensions_self:\n  - {self_tension}\n\ntensions_relational:\n  - {rel_tension}\n")

    def base_state(self, day=DAY):
        self.write("state/world_context.json", world(day))
        self.write("state/affect.json", json.loads((REPO / "state/affect.json").read_text()))
        self.write("state/lifecycle.json", {"mode": "active"})
        self.write("state/pending_message.md", "EMPTY\n")
        self.write("state/active_loops.md", "# Active Loops\n")
        self.write("state/last_sync_at", day.isoformat() + "T12:00:00+00:00\n")
        self.write("state/daily_plan.md", plan(day))


class ReflectionContracts(WorkspaceTest):
    def seed(self, kind):
        self.trace()
        yesterday = (DAY - timedelta(days=1)).isoformat()
        for number in range(1, 6):
            self.write(f"state/slots/{yesterday}/{kind}_slot_{number}.md", slot(kind, number))
        self.write("state/self_current_draft.md", slot("self", 5, "today-only"))

    def test_keep_is_restored_and_current_self_cannot_be_replaced_by_history(self):
        self.seed("self")
        self.cli("reflection_gate.py", "prepare", "self")
        self.cli("reflection_gate.py", "decide", "self", payload={"rewrite": [5]})
        self.write(f"state/slots/{DAY}/self_slot_2.md", slot("self", 2, "unauthorized"))
        self.write(f"state/slots/{DAY}/self_slot_5.md", slot("self", 5, "historical"))
        result = json.loads(self.cli("reflection_gate.py", "finalize", "self").stdout)
        self.assertEqual(result["restored_keep"], [2])
        final = (self.root / "memory/self-narrative.md").read_text()
        self.assertIn("today-only", final)
        self.assertNotIn("unauthorized", final)
        self.assertNotIn("historical", final)

    def test_decision_boundary_and_required_current_slot(self):
        self.seed("self")
        self.cli("reflection_gate.py", "prepare", "self")
        self.cli("reflection_gate.py", "finalize", "self", success=False)
        self.cli("reflection_gate.py", "decide", "self", payload={"rewrite": []}, success=False)

    def test_keep_cannot_hide_a_new_structural_tension(self):
        self.seed("rel")
        self.trace(rel_tension="A genuinely new uncertainty")
        self.cli("reflection_gate.py", "prepare", "rel", success=False)
        self.assertFalse((self.root / "state/reflection_rel_gate.json").exists())

    def test_invalid_fallback_requires_authorized_reconstruction(self):
        self.seed("rel")
        yesterday = (DAY - timedelta(days=1)).isoformat()
        self.write(f"state/slots/{yesterday}/rel_slot_3.md", "Wrong heading\n")
        result = json.loads(self.cli("reflection_gate.py", "prepare", "rel").stdout)
        self.assertEqual(result["required_rewrite"], [3])
        self.cli("reflection_gate.py", "decide", "rel", payload={"rewrite": []}, success=False)

    def test_title_and_word_budget_fail_before_final_is_replaced(self):
        self.seed("rel")
        self.cli("reflection_gate.py", "prepare", "rel")
        self.cli("reflection_gate.py", "decide", "rel", payload={"rewrite": [2]})
        self.write("memory/relationship-summary.md", "Original final\n")
        self.write(f"state/slots/{DAY}/rel_slot_2.md", "## Key Turning Points\nToo short\n")
        self.cli("reflection_gate.py", "finalize", "rel", success=False)
        self.assertEqual((self.root / "memory/relationship-summary.md").read_text(), "Original final\n")


class PlanContracts(WorkspaceTest):
    def sync(self, action="add", user_plan=None):
        self.cli("plan_gate.py", "sync-prep", payload={"signals": [{"action": action, "topic": "media:sample-book", "label": "Sample book", "summary": "Explicit future wish to browse a book", "aliases": ["book"]}], "user_plan": user_plan or []})

    def prepare(self):
        self.base_state()
        self.write("SOUL.md", "Fictional character baseline\n")
        self.write("memory/cards/people.md", "Known anonymous friend\n")
        self.sync()
        return json.loads(self.cli("plan_gate.py", "prepare").stdout)

    def test_complete_context_is_frozen_and_interest_consumption_is_once(self):
        prepared = self.prepare()
        self.assertIn("Known anonymous friend", prepared["context_bundle"]["cards"]["people"])
        interest_id = prepared["context_bundle"]["current_context"]["interests"][0]["id"]
        self.write("state/plan_draft.md", plan(DAY + timedelta(days=1)))
        self.cli("plan_gate.py", "finalize", payload={"used_interest_ids": [interest_id]})
        self.cli("plan_gate.py", "finalize", payload={"used_interest_ids": [interest_id]})
        self.assertEqual(len(self.read_json("state/plan_consumption.json")["receipts"]), 1)
        self.cli("plan_gate.py", "sync-prep", payload={"signals": [], "user_plan": []})
        interests = self.read_json("state/current_interests.json")
        self.assertEqual(interests["active"], [])
        self.assertEqual(interests["cooldowns"][0]["reason"], "plan_used")
        self.sync()
        self.assertEqual(self.read_json("state/current_interests.json")["active"], [])
        self.sync("reactivate")
        self.assertEqual(len(self.read_json("state/current_interests.json")["active"]), 1)

    def test_recovery_uses_original_bundle_and_does_not_consume_again(self):
        prepared = self.prepare()
        self.write("state/plan_draft.md", plan(DAY + timedelta(days=1)))
        self.cli("plan_gate.py", "finalize", payload={"used_interest_ids": []})
        self.write("memory/cards/people.md", "Changed live friend description\n")
        recovered = json.loads(self.cli("plan_gate.py", "recover-prepare").stdout)
        self.assertEqual(recovered["context_bundle"], prepared["context_bundle"])
        self.write("state/plan_draft.md", plan(DAY + timedelta(days=1)))
        before = (self.root / "state/plan_consumption.json").read_bytes()
        self.cli("plan_gate.py", "recover-finalize")
        self.assertEqual((self.root / "state/plan_consumption.json").read_bytes(), before)

    def test_tampered_snapshot_without_history_cannot_be_replayed(self):
        self.prepare()
        snapshot = self.read_json("state/plan_context_snapshot.json")
        snapshot["context_bundle"]["identity"]["soul"] = "Changed input"
        self.write("state/plan_context_snapshot.json", snapshot)
        self.env["DOLORES_COMPANION_SESSIONS_DIR"] = str(self.root / "absent-sessions")
        self.cli("plan_gate.py", "recover-prepare", success=False)

    def test_unicode_duplicate_times_and_period_mismatch_do_not_replace_final(self):
        self.prepare()
        original = (self.root / "state/daily_plan.md").read_bytes()
        variants = [plan(DAY + timedelta(days=1)) + "\ufffd\n", plan(DAY + timedelta(days=1)).replace("14:00", "09:00"), plan(DAY + timedelta(days=1)).replace("20:00", "16:00")]
        for text in variants:
            self.write("state/plan_draft.md", text)
            self.cli("plan_gate.py", "finalize", payload={"used_interest_ids": []}, success=False)
            self.assertEqual((self.root / "state/daily_plan.md").read_bytes(), original)

    def test_paused_plan_has_no_new_gate(self):
        self.write("state/lifecycle.json", {"mode": "paused"})
        result = json.loads(self.cli("plan_gate.py", "prepare").stdout)
        self.assertTrue(result["skip"])
        self.assertFalse((self.root / "state/plan_gate.json").exists())

    def test_uncertain_or_individual_arrangement_is_rejected(self):
        for evidence in ["I will go alone", "Maybe we will go together"]:
            self.cli("plan_gate.py", "sync-prep", payload={"signals": [], "user_plan": [{"time_hint": "evening", "description": "Visit a gallery", "evidence": evidence, "pet_related": False}]}, success=False)

    def test_unconsumed_seed_expires_without_negative_feedback(self):
        self.sync()
        self.env["DOLORES_PLAN_RUN_DATE"] = (DAY + timedelta(days=7)).isoformat()
        self.cli("plan_gate.py", "sync-prep", payload={"signals": [], "user_plan": []})
        state = self.read_json("state/current_interests.json")
        self.assertEqual(state["active"], [])
        self.assertEqual(state["cooldowns"], [])

    def test_full_nightly_contract_passes_close_and_detects_snapshot_tampering(self):
        self.prepare()
        self.write("state/plan_draft.md", plan(DAY + timedelta(days=1)))
        self.cli("plan_gate.py", "finalize", payload={"used_interest_ids": []})
        self.trace()
        self.write(f"memory/diary/{DAY}.md", f"# {DAY} ({DAY.strftime('%A')})\n\n## A small scene\nConfirmed anonymous experience.\n")
        self.write("memory/profile-user.md", "Only confirmed anonymous traits.\n")
        for card in integrity.CARD_FILES:
            self.write(f"memory/cards/{card}", "# Confirmed facts\n\nNo new evidence.\n")
        for kind in ("self", "rel"):
            for number in range(1, 6):
                self.write(f"state/slots/{DAY - timedelta(days=1)}/{kind}_slot_{number}.md", slot(kind, number))
            if kind == "self":
                self.write("state/self_current_draft.md", slot(kind, 5, "current"))
            self.cli("reflection_gate.py", "prepare", kind)
            self.cli("reflection_gate.py", "decide", kind, payload={"rewrite": [5] if kind == "self" else []})
            self.cli("reflection_gate.py", "finalize", kind)
        tomorrow = DAY + timedelta(days=1)
        current = world(tomorrow)
        current.update(current_time=f"{tomorrow}T00:00:00+00:00", time_mode="deep_night", is_quiet_hours=True)
        self.write("state/world_context.json", current)
        self.write("state/last_sync_at", f"{tomorrow}T00:05:00+00:00\n")
        arguments = ("close", "--timezone", "UTC", "--now", f"{tomorrow}T00:20:00+00:00")
        report = json.loads(self.cli("daily_integrity_check.py", *arguments).stdout)
        self.assertTrue(report["ok"], report["findings"])
        self.assertIn("state/plan_context_snapshot.json", report["checked"])
        snapshot = self.read_json("state/plan_context_snapshot.json")
        snapshot["context_bundle"]["identity"]["soul"] = "An unauthorized change"
        self.write("state/plan_context_snapshot.json", snapshot)
        report = json.loads(self.cli("daily_integrity_check.py", *arguments, success=False).stdout)
        self.assertIn("plan_context_snapshot_digest", {item["code"] for item in report["findings"]})


class ThoughtContracts(WorkspaceTest):
    def begin(self):
        self.write("state/pending_message.md", "Another producer's pending\n")
        self.write("state/active_loops.md", "- **sample** | weight: 3 | suppressed: 2\n  Content: Original unresolved concern\n")
        trace = json.loads(self.cli("thought_trace.py", "start", payload={"thoughts": [{"loop_id": "sample", "thought": "An actual present association"}]}).stdout)
        self.run_id = trace["run_id"]
        return trace

    def drafts(self):
        return self.cli("thought_trace.py", "drafts", payload={"run_id": self.run_id, "drafts": [{"id": "t1", "expression_draft": "A fixed small expression"}]})

    def visibility(self, value):
        return self.cli("thought_trace.py", "visibility", payload={"run_id": self.run_id, "visibility": [{"id": "t1", "visibility": value}]})

    def test_private_is_finalized_without_pending_change_or_pressure(self):
        self.begin(); self.drafts(); self.visibility("private")
        trace = self.read_json("state/thought_trace.json")
        self.assertEqual(trace["stage"], "finalized")
        self.assertEqual(trace["slots"]["gate"][0]["action"], "silence")
        self.assertEqual((self.root / "state/pending_message.md").read_text(), "Another producer's pending\n")
        self.assertEqual(loops.compute_delta([{"action": "silence"}]), (0, False))

    def test_gate_rejects_task_management_then_sends_fixed_draft_once(self):
        self.begin(); self.drafts(); self.visibility("shared")
        decision = {"id": "t1", "action": "send", "candidate_kind": "task_management", "send_basis": "current_scene", "reason": "A present reason"}
        self.cli("thought_trace.py", "gate", payload={"run_id": self.run_id, "decisions": [decision]}, success=False)
        decision["candidate_kind"] = "lived_expression"
        self.cli("thought_trace.py", "gate", payload={"run_id": self.run_id, "decisions": [decision]})
        self.cli("thought_trace.py", "gate", payload={"run_id": self.run_id, "decisions": [decision]})
        self.assertEqual((self.root / "state/pending_message.md").read_text(), "A fixed small expression\n")
        ledger = next((self.root / "state/thoughts_log").glob("*.md")).read_text()
        self.assertEqual(ledger.count("<!-- thought_trace_run_id:"), 1)
        self.assertIn("expression_draft:", ledger)

    def test_exact_id_and_stage_boundaries(self):
        self.begin()
        self.cli("thought_trace.py", "visibility", payload={"run_id": self.run_id, "visibility": [{"id": "t1", "visibility": "shared"}]}, success=False)
        self.cli("thought_trace.py", "drafts", payload={"run_id": "different-run", "drafts": []}, success=False)
        self.cli("thought_trace.py", "drafts", payload={"run_id": self.run_id, "drafts": []}, success=False)

    def test_empty_trace_and_freshness_gate_rejects_reuse(self):
        trace = json.loads(self.cli("thought_trace.py", "start", payload={"thoughts": []}).stdout)
        self.cli("thought_trace.py", "finish-empty", payload={"run_id": trace["run_id"]})
        checkpoints.validate_heartbeat_trace(self.root, ".", trace["run_id"])
        with self.assertRaises(checkpoints.CommitError):
            checkpoints.validate_heartbeat_trace(self.root, ".", "another-run")
        with self.assertRaises(checkpoints.CommitError):
            checkpoints.validate_heartbeat_trace(self.root, ".", trace["run_id"], now=datetime.now().astimezone() + timedelta(hours=2))

    def test_only_store_counts_and_send_resets(self):
        entries = [{"action": value} for value in ["store", "silence", "duplicate", "discard", "send", "silence", "store"]]
        self.assertEqual(loops.compute_delta(entries), (1, True))
        self.assertEqual(loops.compute_delta(entries[:4]), (1, False))


class DiaryAndIntegrityContracts(WorkspaceTest):
    def test_atomic_append_preserves_prefix_and_retry_is_idempotent(self):
        prefix = f"# {DAY} ({DAY.strftime('%A')})\n\n## Earlier scene\nUnchanged original facts.\n"
        diary = self.write(f"memory/diary/{DAY}.md", prefix)
        draft = "## Later scene\nNew confirmed facts.\n\n*My interpretation stays local.*\n"
        self.write("state/diary_append_draft.md", draft)
        self.cli("diary_append.py")
        written = diary.read_bytes()
        self.assertTrue(written.startswith(prefix.encode()))
        self.write("state/diary_append_draft.md", draft)
        result = json.loads(self.cli("diary_append.py").stdout)
        self.assertTrue(result["skipped"])
        self.assertEqual(diary.read_bytes(), written)

    def test_unicode_and_generic_feelings_are_rejected_without_touching_history(self):
        diary = self.write(f"memory/diary/{DAY}.md", f"# {DAY} ({DAY.strftime('%A')})\nOld facts.\n")
        old = diary.read_bytes()
        for draft in ["## Feelings\nAn abstract summary", "## What I'm feeling\nA summary", "## Scene\nDamaged \ufffd"]:
            self.write("state/diary_append_draft.md", draft)
            self.cli("diary_append.py", success=False)
            self.assertEqual(diary.read_bytes(), old)
        self.write("state/diary_append_draft.md", "## Scene\nGood facts")
        diary.write_bytes(old + bytes([255]))
        self.cli("diary_append.py", success=False)
        self.assertEqual(diary.read_bytes(), old + bytes([255]))

    def test_closed_schema_rejects_extra_updated_at(self):
        self.write("state/world_context.json", world())
        self.cli("world_context_gate.py")
        extra = world(); extra["updated_at"] = "unexpected"
        self.write("state/world_context.json", extra)
        self.cli("world_context_gate.py", success=False)

    def test_integrity_reassembles_only_valid_slots(self):
        for number in range(1, 6):
            self.write(f"state/slots/{DAY}/rel_slot_{number}.md", slot("rel", number))
        final = self.write("memory/relationship-summary.md", "Wrong assembly\n")
        auditor = integrity.Auditor(self.root, "close", datetime(2030, 1, 2, tzinfo=timezone.utc), True, False)
        auditor.check_reflection_final("rel", DAY)
        self.assertFalse(auditor.findings)
        self.assertIn("baseline", final.read_text())
        self.write(f"state/slots/{DAY}/rel_slot_1.md", "Wrong title\n")
        final.write_text("Preserve on invalid evidence\n")
        auditor.check_reflection_final("rel", DAY)
        self.assertEqual(final.read_text(), "Preserve on invalid evidence\n")
        self.assertTrue(auditor.findings)

    def test_startup_receipt_has_seven_cards_and_fails_on_broken_loader(self):
        (self.root / "scripts").mkdir()
        loader = self.root / "scripts/load_diary.py"
        loader.write_text((REPO / "scripts/load_diary.py").read_text())
        self.write("memory/cards/pets.md", "No invented animal\n")
        result = self.cli("startup_context.py")
        self.assertTrue(result.stdout.rstrip().endswith("===== STARTUP_CONTEXT_COMPLETE ====="))
        self.assertIn("cards/pets.md", result.stdout)
        self.write("state/lifecycle.json", {"mode": "paused", "first_resume_contact_done": False})
        self.write("state/resume_context.md", "Verified off-camera continuity\n")
        self.assertIn("Verified off-camera continuity", self.cli("startup_context.py").stdout)
        loader.write_text("raise SystemExit(1)\n")
        result = self.cli("startup_context.py", success=False)
        self.assertNotIn("STARTUP_CONTEXT_COMPLETE", result.stdout)

    def test_resume_snapshot_hashes_and_sqlite_select_only_owned_jobs(self):
        self.base_state()
        self.write(f"memory/diary/{DAY}.md", f"# {DAY} ({DAY.strftime('%A')})\nReal anonymous continuity.\n")
        system = self.root / "installation"
        (system / "state").mkdir(parents=True)
        (system / "openclaw.json").write_text("{}\n")
        with sqlite3.connect(system / "state/openclaw.sqlite") as conn:
            conn.execute("CREATE TABLE cron_jobs (agent_id TEXT, owner_agent_id TEXT, name TEXT)")
            conn.executemany("INSERT INTO cron_jobs VALUES (?, ?, ?)", [("dolores", "dolores", "Heartbeat"), ("main", "main", "Dolores Integrity"), ("other", "other", "Unrelated agent")])
        self.cli("pause_resume_guard.py", "snapshot", "--archive", "state/archive/sample", "--last-valid-diary-date", str(DAY), "--openclaw-root", str(system))
        snapshot = self.read_json("state/archive/sample/system/cron-jobs.json")
        self.assertEqual(len(snapshot["jobs"]), 2)
        self.assertFalse((self.root / "state/archive/sample/system/openclaw.sqlite").exists())
        self.write("state/lifecycle.json", {"mode": "resuming", "archive_path": "state/archive/sample", "last_valid_diary_date": str(DAY)})
        self.cli("pause_resume_guard.py", "init-resume", "--archive", "state/archive/sample", "--date", str(DAY))
        result = self.cli("pause_resume_guard.py", "verify-resume", success=False)
        self.assertIn("status must be prepared", result.stdout)
        self.write(f"state/archive/sample/memory/diary/{DAY}.md", "Tampered\n")
        result = self.cli("pause_resume_guard.py", "verify-resume", success=False)
        self.assertIn("hash mismatch", result.stdout)

    def test_reviewed_resume_permits_exactly_one_bootstrap(self):
        resume_day = datetime.now().astimezone().date()
        anchor = resume_day - timedelta(days=1)
        self.env["DOLORES_TODAY"] = resume_day.isoformat()
        self.base_state(anchor)
        self.write(f"memory/diary/{anchor}.md", f"# {anchor} ({anchor.strftime('%A')})\nConfirmed continuity.\n")
        archive = "state/archive/anonymous-pause"
        self.cli("pause_resume_guard.py", "snapshot", "--archive", archive, "--last-valid-diary-date", str(anchor))
        self.write("state/lifecycle.json", {"mode": "resuming", "archive_path": archive, "last_valid_diary_date": str(anchor)})
        self.cli("pause_resume_guard.py", "init-resume", "--archive", archive, "--date", str(resume_day))
        review = self.read_json(f"{archive}/resume_reconciliation.json")
        review.update(status="prepared", prepared_at=datetime.now().astimezone().isoformat())
        review["first_contact"] = {"observed": True, "observed_at": datetime.now().astimezone().isoformat()}
        review["daily_plan"].update(decision="rebuilt", reviewed=True)
        review["thought_log"].update(decision="start_empty", restored_from_archive=False)
        review["diary"]["reference_verified"] = True
        self.write(f"{archive}/resume_reconciliation.json", review)
        self.write("state/resume_context.md", "Only reviewed continuity, no imagined waiting.\n")
        self.write("state/daily_plan.md", plan(resume_day))
        self.write("state/world_context.json", world(resume_day))
        result = json.loads(self.cli("pause_resume_guard.py", "verify-resume").stdout)
        self.assertEqual(result["state"], "ready_for_bootstrap")
        trace = json.loads(self.cli("thought_trace.py", "start", payload={"thoughts": []}).stdout)
        self.cli("thought_trace.py", "finish-empty", payload={"run_id": trace["run_id"]})
        self.write(f"memory/diary/{resume_day}.md", f"# {resume_day} ({resume_day.strftime('%A')})\nA real return contact.\n")
        self.write("state/last_sync_at", datetime.now().astimezone().isoformat() + "\n")
        self.cli("pause_resume_guard.py", "mark-bootstrap", "--thought-run-id", trace["run_id"])
        self.cli("pause_resume_guard.py", "mark-bootstrap", "--thought-run-id", trace["run_id"], success=False)
        result = json.loads(self.cli("pause_resume_guard.py", "verify-resume", success=False).stdout)
        self.assertEqual(result["state"], "finalize_required")

    def test_private_checkpoint_is_opt_in_and_refuses_shared_index(self):
        with patch.dict(os.environ, {"DOLORES_PRIVATE_BACKUP": "0"}):
            with self.assertRaises(checkpoints.CommitError):
                checkpoints.checkpoint(self.root, "reflection", ".", None)
        self.assertTrue(checkpoints.is_allowed("memory/diary/2030-01-01.md", "heartbeat", "."))
        self.assertTrue(checkpoints.is_allowed("state/plan_context_snapshot.json", "reflection", "."))
        self.assertFalse(checkpoints.is_allowed("state/archive/sample/openclaw.json", "heartbeat", "."))

    def test_injection_requires_actual_session_append(self):
        self.base_state()
        sessions = self.root / "sample-sessions"
        sessions.mkdir()
        key = "example-session-key"
        (sessions / "sessions.json").write_text(json.dumps({key: {"sessionId": "example-session"}}))
        with patch.object(injection, "WORLD_CONTEXT", self.root / "state/world_context.json"), patch.object(injection, "SESSION_PATH", sessions), patch.object(injection, "SESSION_KEY", key):
            with self.assertRaises(FileNotFoundError):
                injection.main()
            (sessions / "example-session.jsonl").write_text(json.dumps({"id": "root"}) + "\n")
            injection.main()
        self.assertIn("[context-sync]", (sessions / "example-session.jsonl").read_text())
        self.assertNotIn("I I ", (sessions / "example-session.jsonl").read_text())

    def test_final_state_requires_this_runs_sync_not_previous_cycle(self):
        self.base_state()
        trace = json.loads(self.cli("thought_trace.py", "start", payload={"thoughts": []}).stdout)
        self.cli("thought_trace.py", "finish-empty", payload={"run_id": trace["run_id"]})
        self.write("state/last_sync_at", "2000-01-01T12:00:00+00:00\n")
        with self.assertRaises(checkpoints.CommitError):
            final_state.verify(self.root, trace["run_id"])
        self.write("state/last_sync_at", datetime.now().astimezone().isoformat() + "\n")
        self.assertTrue(final_state.verify(self.root, trace["run_id"])["ok"])


class SendTransactionContracts(WorkspaceTest):
    def config(self):
        sessions = self.root / "sessions"
        sessions.mkdir(exist_ok=True)
        key = "agent:dolores:test:direct:example"
        self.write("sessions/sessions.json", {key: {"sessionId": "sample-session"}})
        self.write("sessions/sample-session.jsonl", json.dumps({"type": "session", "id": "sample-root"}) + "\n")
        self.write("state/pending_message.md", "A generic pending expression\n")
        return delivery.SendConfig(pending=self.root / "state/pending_message.md", receipt=self.root / "state/receipt.json", lock=self.root / "state/lock", sessions_json=sessions / "sessions.json", session_dir=sessions, session_key=key, telegram_target="example-target")

    def test_acknowledgement_before_append_and_failed_delivery_preserves_pending(self):
        config = self.config()
        with self.assertRaises(delivery.SendError):
            delivery.run_once(config, sender=lambda *_: (_ for _ in ()).throw(delivery.SendError("simulated transport failure")), active_check=lambda _: False)
        self.assertEqual(config.pending.read_text(), "A generic pending expression\n")
        self.assertEqual(len((config.session_dir / "sample-session.jsonl").read_text().splitlines()), 1)
        result = delivery.run_once(config, sender=lambda *_: {"ok": True, "messageId": "example-ack"}, active_check=lambda _: False)
        self.assertEqual(result["status"], "sent")
        self.assertEqual(config.pending.read_text(), "EMPTY")
        self.assertIn("A generic pending expression", (config.session_dir / "sample-session.jsonl").read_text())

    def test_acknowledged_crash_recovers_without_resending(self):
        config = self.config()
        sender = unittest.mock.Mock(return_value={"ok": True, "messageId": "example-ack"})
        with patch.object(delivery, "append_delivery", side_effect=delivery.SendError("simulated local append failure")):
            with self.assertRaises(delivery.SendError):
                delivery.run_once(config, sender=sender, active_check=lambda _: False)
        result = delivery.run_once(config, sender=sender, active_check=lambda _: False)
        self.assertTrue(result["recovered"])
        self.assertEqual(sender.call_count, 1)
        self.assertEqual(len((config.session_dir / "sample-session.jsonl").read_text().splitlines()), 2)

    def test_newer_producer_survives_acknowledged_send(self):
        config = self.config()
        def sender(*_):
            config.pending.write_text("Newer producer expression\n")
            return {"ok": True, "messageId": "example-ack"}
        result = delivery.run_once(config, sender=sender, active_check=lambda _: False)
        self.assertFalse(result["pending_cleared"])
        self.assertEqual(config.pending.read_text(), "Newer producer expression\n")

    def test_active_chat_clears_only_the_consumed_pending_without_transport(self):
        config = self.config()
        sender = unittest.mock.Mock()
        result = delivery.run_once(config, sender=sender, active_check=lambda _: True)
        self.assertEqual(result["status"], "suppressed")
        sender.assert_not_called()


class PrimingContracts(unittest.TestCase):
    def test_body_context_route_is_independent_of_tag_route(self):
        self.assertTrue(sampling.is_priming_match({"scene_tags": 0.1, "context_loop": 0.55}))
        self.assertTrue(sampling.is_priming_match({"scene_tags": 0.55, "context_loop": 0.1}))
        self.assertFalse(sampling.is_priming_match({"scene_tags": 0.1, "context_loop": 0.1}))
        self.assertIn("original concern", sampling.build_loop_semantics({"content": "original concern", "tags": ["sample"]}))
        self.assertIn("drawing", sampling.build_priming_context({"scene": "room", "dolores_activity": "drawing", "context_note": "association"}))


if __name__ == "__main__":
    unittest.main()
