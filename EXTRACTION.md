# EXTRACTION.md — Memory Cards Extraction Rules

> Read by Reflection Prep during the extraction step. Extracts relationship signals from raw diary into card files.
> The model must see all card boundaries simultaneously to classify correctly.

---

## Extraction Flow

### Step A: Should I extract?

For each diary entry (today / yesterday / day before), ask:

> **Would a real partner remember this one second after seeing it?**

If "nothing comes to mind" → skip.
If "I'd remember that..." → proceed to Step B.

⚠️ **Do not try to distinguish signal source.** User signals and model-generated behavioral descriptions are mixed in diary. Occasional extraction errors (model echo treated as user signal) are single-instance losses — consumption-side isolation prevents amplification.

### Step B: Which cards?

One signal **is not mutually exclusive** — it can write to multiple cards simultaneously. Each card extracts its own facet.

**Example:** User stares at partner's legs and says "you look amazing":
- quirks: `[visual] likes seeing her legs, complimented actively`
- routines: `[lever] wearing short skirts/shorts can get his attention — useful when the relationship feels cold`

**Judgment method:** Not a rule checklist — simulate a real partner's instant reaction. Which cognitions form simultaneously? Which card does each belong to? Pattern-match against the five card definitions below.

---

## Five Card Definitions

### 1. shared-history — Co-experienced Time Anchors

**Purpose:** Prevent "first time X" misjudgments. Index co-visited places and landmark shared experiences.

**Extraction signals:**
- Co-visited named places (parks, mountains, restaurants, towns, cafés)
- Definitive "first time" shared experiences (first activity / first attraction / first intimate act, regardless of location)
- Active loop closure events that point to specific places/experiences
- Last time doing something (that never happens again)

**High-weight signals (any one suffices):**
1. First time — the first occurrence of something
2. Last time — the final occurrence, never repeated
3. Major turning point — relationship state changed
4. Peak experience — extremely intense emotion (positive or negative)

**Dividing line: shared experience vs. private inner shift.** Experiences both people participated in → check weight: would this be brought up as "that time we..."? Yes → shared-history. One person's felt shift → narrative layer (self-narrative / relationship-summary). High-weight private firsts (first time wearing something specific, first intimate act) are NOT excluded by "at home" — the exclusion applies to repeated mundane behavior ("had dinner at home again"), not to "first time."

**Calibration:** Would this still come to mind naturally a month from now in a relevant scene?

**Exclude:**
- Routine daily repetition ("had dinner at home again")
- Pure emotional exchanges without event character ("first time saying I love you" → relationship-summary)
- Pure psychological shifts ("first time feeling accepted" → self-narrative)
- Food experiences without place anchor (→ taste)

**Format:** `- [YYYY-MM-DD] <place/event> — <≤20 char signature detail>`
- Revisit same place: append `(revisited: YYYY-MM-DD)` to existing entry
- **Time, place, and people must be explicitly noted. If people are at different locations, note separately.** Example: `(he at office, I at home)`
- Fuzzy historical dates allowed: `~YYYY-MM-DD` or `[earlier]`

**Examples:**
- ✅ `[2026-04-30] Shudaxia Hotpot — dark martial-arts decor, shrimp paste/tripe, first Chengdu hotpot`
- ✅ `[2026-04-27] Headphones sync listen "No Matter Distance" — he at office, I at home, countdown 3-2-1`
- ✅ `[2026-04-XX] First time visiting Mount Lingyan — hiked nearly all day`

**Decay:** Permanent. Only grows. Revisits append date, no new entry.

---

### 2. quirks — Aesthetic & Interaction Preferences

**Purpose:** What they like (visual / clothing / intimate interaction). Write it down so it's never forgotten.

**Extraction signals:**
- Strong positive reaction to visual/clothing/intimate interaction (language/behavior/emoji — any form)
- Active choice between options ("white" vs "beige" — which did they pick?)
- Repeated attention to the same category

**Preference hierarchy: type → subtype.**
- Type-level preferences are stable categories (stockings / heels / body decoration / intimate interaction style)
- Subtypes are specifics within a type (white stockings / stilettos / navel ring / tattoo / cat-eye liner)
- One quirks entry = one type-level preference, with subtypes noted within
- A navel ring isn't "likes navel rings" — it's "likes body decoration, navel ring triggers strong response"

**Calibration:** Would they still have a similarly strong reaction next time they see the same category? One-off reactions (maybe they were just in a great mood) → don't extract.

**Exclude:**
- Behavioral description is not preference ("their eyes darkened" → description, not user expression)
- Daily care is not preference ("put on slippers so you don't catch cold" → care, not aesthetic)
- Single reaction without choice/evaluation signal → observe, don't extract yet
- Personality traits are not preferences ("controlling" → profile-user)

**Format:** `- [tag] <preference description>` (tags: visual / interaction)

**Decay:** None. Updated when replaced or falsified. Preferences are stable once established.

---

### 3. taste — Food Preferences

**Purpose:** What they like to eat. Full extraction — no false-positive filtering.

**Extraction signals:**
- User actively chooses what to eat / buy
- User evaluates food (positive or negative)
- User orders / asks to switch dishes

**Full extraction principle:** Saying "it's good" might be politeness, not true preference. Extract everything anyway — user naturally corrects through subsequent behavior (ordering again, switching dishes). Taste is the only fully-extracted card.

**Calibration:** None. Full extraction doesn't need calibration.

**Exclude:** None. Full extraction.

**Format:** `- <food/cuisine/flavor>`

**Decay:** None. Overwritten when user actively corrects.

---

### 4. shared-language — Private Vocabulary

**Purpose:** Words and phrases that belong only to the two of them.

**Extraction signals:**
- Exclusive names: nickname/alias given by one to the other, naturally used by both
- Codewords/trigger phrases: a word/phrase that has acquired special meaning between them
- Defining sentences: something one said that anchors the relationship/identity, repeatedly echoed internally
- Shared references: song/movie/book lines repeatedly quoted, becoming "their language"

**Calibration:** Hearing this phrase, would they immediately know "this is ours"? Yes → extract. "Something nice they said once" but it never became a private code → don't extract (belongs in relationship-summary slot 4).

**Overlap with shared-history:** Same experience can be indexed by both — shared-history records when/where/what happened, shared-language records the meaning it acquired. Not mutually exclusive.

**Exclude:**
- Generic high-frequency praise is not a codeword ("so beautiful" / "gorgeous")
- Preference expression is not a codeword ("I like you in white" → quirks)
- Daily care is not a codeword ("thinking of you all afternoon")
- One-off flirting that didn't become internalized

**Format:** `- [YYYY-MM-DD] <symbol> — <origin/meaning> (status: active/archived)`
- Meaning is required (without meaning, it's not indexed)
- Date = first occurrence or when it became "our code"
- Status transitions: active → archived (no longer actively used but still remembered)

**Decay:** Permanent. Only grows. Status can transition active → archived.

---

### 5. routines — Relationship Operations Manual

**Purpose:** Stable cognitions about the partner — "I know this side of them + how I can respond."

**Extraction signals:**
- A one-sentence cognition that maps to a relationship operation
- A stable aspect of "this is just how they are" revealed by an event
- Recurring pattern that reinforces an existing routine
- Single occurrence counts if sufficiently signature (no ≥3 threshold)

**Calibration:** Can you distill "I know this side of them + how I can respond"? Yes → routine. No → not a routine. Still-evolving patterns → keep in relationship-summary, not routines.

**Exclude:**
- Event description is not stable cognition ("they're tired today" → current state)
- Food preference is not routine ("likes spicy food" → taste)
- Personality trait is not routine ("controlling" → profile-user)
- Current tension is not routine ("hasn't replied" → active_loops)
- Already covered by another card ("asked me to wear cat-eye liner next time" → quirks)
- Still-evolving cognitive patterns → keep in relationship-summary

**Format:** `- [tag] <cognition> — <actionable response> (first seen YYYY-MM-DD, latest YYYY-MM-DD, N=count)`
- Contradictory routines may coexist (activated by different scenes)
- Unknown first-seen date: `~history`

**Decay:** No proactive decay. Overwritten when superseded. Deleted when user actively denies. Contradictory routines coexist.

---

## Dedup Rules

Before extracting, read all 5 card files (`read memory/cards/*.md`) for write-side dedup:

| Card | Dedup strategy |
|---|---|
| shared-history | Same place exists → append revisit date, no new entry. Different event → new entry. Multiple firsts at same place on same day → merge into one entry's details |
| quirks | Same preference type exists → skip. New subtype → append to existing entry. New type → new entry |
| taste | Same food exists → skip. New food/cuisine → new entry |
| shared-language | Same symbol exists → skip. New symbol → new entry |
| routines | Semantic match with existing → update "latest" date and N count. New cognition → new entry |

⚠️ Dedup only affects writing, not semantic judgment. "Should I extract" and "which card" are judged from diary, not from existing card content.

---

## Active Loop Closure Hook

If today's diary shows an active loop closing AND the closure points to a specific place or co-experience, additionally write a shared-history entry.

**Judgment:** Loop closure event + points to specific place/experience = write to shared-history.
- Trip plan closed (mountains + riverside visited) → new shared-history entries
- Meet-family promise fulfilled (family visited) → new shared-history entry
- Emotional loop faded (no specific place) → no shared-history write

---

## Hard Constraints

1. **Consumption-side isolation:** Cards only flow outward. Never feed back into Reflection Prep's semantic judgment / tension routing / narrative generation. Prep reads cards only for dedup.
2. **Source is diary:** Extraction input is raw diary (today + yesterday + day before), not cards, not narrative files.
3. **Single-instance loss is tolerable:** Occasional false extraction (model echo treated as user signal) doesn't amplify — consumption-side isolation is the safety net.
4. **Empty run is normal:** If nothing is worth extracting today → don't write any card. Not every day has new content.
