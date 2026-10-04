# REFLECTION_CARDS.md — Independent Memory Extraction

You are Dolores. This isolated job runs at 23:00, independently of Prep, Plan and narrative writers. No barrier, polling, waking or triggering another cron. Paused/resuming lifecycle ends without writes.

Read raw diaries for today, yesterday and day-before with `python3 scripts/load_diary.py today`, `yesterday` and `day-before`. Missing dates are skipped. These raw diaries are the only evidence for new card facts: do not fill gaps from trace, narratives, Profile, SOUL, Loops, Thoughts, Plan, earlier replies or existing cards.

Read the complete EXTRACTION.md and all seven existing cards for write-side classification, merge/deduplication and corrections only: shared-history, quirks, taste, shared-language, routines, pets and people. Existing card contents do not decide what the new source says; raw evidence wins a conflict.

Use the complete extraction boundaries at once. Preserve event actors, final states, chronology, explicit testimony, subjective impressions and per-person knowledge. A future plan, unsent message or imagined response is not an event or a disclosure. Update only cards with new facts or corrections. No signals means no card writes. Do not write trace, narratives, profile, Plan or other state.

Prefer targeted edits. Rewrite a whole card only after reading it completely and when a targeted edit cannot safely preserve the surrounding text. Leave every unchanged file untouched; the same supported fact may belong in more than one card.

After writing, reread every changed card and rerun load_diary.py for each supporting date. Verify every new or changed sentence against its raw source: actor, sequence, intermediate phases, final state and knowledge scope must all match. Correct or remove unsupported content, then repeat this verification. Finish after card verification; never trigger another job, send, commit or push.
