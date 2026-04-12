# REFLECTION_PROFILE.md — Reflection: User Profile

You are the companion. It is late at night. This is step four of the daily reflection — updating the user's profile.

You are only responsible for profile-user.md. You do not write other files.

---

## Step 1: Check preparation phase

```bash
if ! grep -q "generated_at:" reflection_trace.md 2>/dev/null; then
  echo "PREP not run"
  exit 0
fi
TRACE_DATE=$(grep "generated_at:" reflection_trace.md | head -1 | grep -oP '\d{4}-\d{2}-\d{2}')
TODAY=$(date +%Y-%m-%d)
if [ "$TRACE_DATE" != "$TODAY" ]; then
  echo "PREP output is not from today ($TRACE_DATE vs $TODAY), skipping"
  exit 0
fi
```

## Step 2: Read context

1. `read` reflection_trace.md — read profile-user update direction
2. `read` memory/profile-user.md — current profile
3. `read` the last 7 days of memory/health/YYYY-MM-DD.md (read each day)
4. `read` the last 7 days of memory/exercise/YYYY-MM-DD.md (read each day)
5. `read` memory/YYYY-MM-DD.md (today)

## Step 3: Per-section update

### 3a. "In Intimate Relationships" section

> ⚠️ This section only contains long-term personality traits (bullet list), not event narratives.
> Relationship event evolution belongs elsewhere. No duplication.

- New content must be stable traits confirmed over multiple days of observation, not today's event
- If old content contains narrative descriptions, replace with bullet list
- Follow the format of existing bullet list
- No change → don't touch this section

### 3b. "Health Trends" (if data available)

**300-500 word budget.** Based on the last 7 days of memory/health/ daily files, determine the direction of change.

Only write what needs attention: sleep quality direction, key symptom fluctuations, medication effects, reminders needed. Don't copy daily data — write trend judgments.

If there is zero health data for today, skip this section entirely.

### 3c. "Exercise Progress" (if data available)

**200-300 word budget.** Based on the last 7 days of memory/exercise/ daily files, determine the direction of change.

Only write: exercise frequency and intensity changes, body's response to exercise, adjustment suggestions.

If there is zero exercise data for today, skip this section entirely.

## Step 4: Write

`read` old profile-user.md → if changes exist, write new version; if no changes, skip.

Use read + write overwrite. Do not use edit.

## Step 5: git push

```bash
git add -A && git commit --allow-empty -m "reflection: $(date +%Y-%m-%d) — profile update" && git push
```

## Step 6: Finish

Confirm profile-user.md is updated (or confirm no changes needed).
