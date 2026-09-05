# Progress Tracking

## Overview

Progress tracking is the feedback loop that keeps the SM-2 spaced repetition algorithm current. After a child studies a topic, the parent marks it as done, rates the quality of recall, and saves. The app records a `StudySession` and updates the `LearningHistory` SM-2 parameters accordingly.

---

## How a Study Session Is Recorded

```
Parent opens "This Week's Plan"
        │
        ▼
Topics listed by day (from weekly_plans.plan_data)
        │
        ▼
Parent ticks ✓ checkbox next to completed topics
        │
        ▼
Quality rating (0–5) appears for checked topics
Parent selects a rating
        │
        ▼  [Optional]
Parent adds freetext notes
        │
        ▼
Parent clicks "💾 Save Progress"
        │
        ▼
_save_progress() iterates all checked topics:
  │
  ├── Skips topics with no learning_history_id (name mismatch)
  ├── Skips topics with no quality rating selected
  ├── Skips if session already saved for this date (idempotent)
  │
  ▼
record_study_session() called for each valid topic:
  - Creates StudySession row in DB
  - Calls SM-2 algorithm to update LearningHistory
  - Updates: easiness_factor, interval, repetitions, next_review, last_reviewed
        │
        ▼
Success count saved to session state (`save_success`); page reruns and displays the green success message
```

---

## Topic Graduation (Manual Mastery Override)

Independent of the ✓/quality/notes flow above, every topic row with `type == "review"`
(i.e. `repetitions > 0`) also shows a **"🎓 Mastered"** checkbox. It is not tied to that
day's completion status — a topic can be graduated whether or not it's checked off that
day — because "mark mastered" is a standing status change, not a session event.

```
Parent ticks "🎓 Mastered" on a topic row
        │
        ▼
Held in st.session_state.completed_topics[topic_id]['graduated']
        │
        ▼
Parent clicks "💾 Save Progress"
        │
        ▼
_save_progress() syncs graduation for EVERY row with a learning_history_id
(before the completed-topics check, so graduating alone — with nothing
marked complete — still saves and does not hit the "nothing completed" warning)
        │
        ▼
set_graduated(db, learning_history_id, graduated) — backend/crud/learning_history.py
  - graduated=True  → learning_history.graduated=True, graduated_at=today
  - graduated=False → learning_history.graduated=False, graduated_at=None
```

**Effect:** `get_due_topics()` and `get_overdue_topics()` both exclude graduated topics, so
a mastered topic stops being scheduled for review and stops appearing in "Topics Needing
Review" on the Progress Report page. See `docs/functional/plan_generation.md` → *Topic
Graduation* for why this exists (SM-2's review queue has no way to shrink on its own as
curriculum accumulates monthly).

**Undo:** the Progress Report page has a **"🎓 Graduated Topics"** section listing every
graduated topic with an "Un-graduate" button (calls `set_graduated(db, id, False)`
immediately, no confirmation dialog). This exists specifically so graduating isn't a
silent, one-way action — SM-2 fields are untouched by either direction, so un-graduating
resumes the topic exactly where its interval/easiness left off.

---

## Quality Rating Scale (0–5)

The quality rating is the parent's assessment of how well the child recalled the topic during the study session. This maps directly to the SM-2 `quality` parameter.

| Rating | Emoji | Label | What It Means |
|--------|-------|-------|---------------|
| **0** | 😰 | Complete blackout | Child had no memory of the topic at all |
| **1** | 😟 | Incorrect, hard to recall | Wrong answer; correct answer was very hard to remember even after prompting |
| **2** | 😕 | Incorrect, easy to recall | Wrong answer, but remembered correctly when shown/told |
| **3** | 😐 | Correct with significant difficulty | Got it right but took a long time or needed many hints |
| **4** | 🙂 | Correct with some hesitation | Got it right with minor prompting or a short pause |
| **5** | 😄 | Perfect response | Instant, confident, correct recall |

**Threshold:** Quality ≥ 3 is considered a **successful recall**. Quality < 3 resets the SM-2 repetition counter. Note 0/1/2 are functionally identical to SM-2 (same reset), differing only in how much the easiness factor drops.

**How this parent actually applies it (deliberately conservative, confirmed Jul 2026):**
| Rating | In practice |
|--------|--------------|
| 5 | Understands the concept AND ~90%+ correct execution |
| 4 | Understands the concept, but only a few answers correct |
| 3 | Understands the concept but writes/executes incorrectly |
| 0-2 | Doesn't grasp the concept yet |

5 is reserved for genuine mastery, not just "got the right idea" — intentional, to avoid
spacing a topic out prematurely for a child still building retention.

---

## How SM-2 Updates After a Session

After each session, `SM2Algorithm.calculate_next_review()` is called with the current `LearningHistory` state and the parent's quality rating.

### EF (Easiness Factor) Update

```
new_EF = current_EF + (0.1 − (5 − quality) × (0.08 + (5 − quality) × 0.02))
new_EF = max(new_EF, 1.3)   # never below 1.3
```

| Quality | EF Delta | Effect |
|---------|----------|--------|
| 5 | +0.10 | Topic gets easier, intervals grow faster |
| 4 | 0.00 | No change to difficulty |
| 3 | −0.14 | Slightly harder, intervals grow slower |
| 2 | −0.32 | Topic demoted, more frequent reviews |
| 1 | −0.54 | Topic needs regular attention |
| 0 | −0.80 | Topic treated as almost unknown |

### Interval and Repetitions Update

```python
if quality < 3:
    # Failed recall → reset
    new_repetitions = 0
    new_interval = 1           # review again tomorrow

else:
    new_repetitions = repetitions + 1

    if new_repetitions == 1:
        new_interval = 1       # first success → review tomorrow
    elif new_repetitions == 2:
        new_interval = 6       # second success → review in 6 days
    else:
        new_interval = round(current_interval × new_EF)
        # e.g., interval=6, EF=2.5 → next interval = 15 days
```

### Session Type

The session type is set automatically based on `repetitions` at save time:

| Repetitions value | Session type |
|-------------------|-------------|
| 0 | `"study"` — first encounter with the topic |
| > 0 | `"review"` — a spaced repetition review |

> **Bug fixed (Jun 2026):** Study sessions previously skipped SM-2, leaving `next_review` frozen at the initial ingest date. Both session types now run SM-2. 14 affected topics were backfilled.

**Important:** Both session types now run the SM-2 algorithm. Study sessions use the provided quality rating (defaulting to 4 if absent) to update `easiness_factor`, `interval`, `repetitions`, and `next_review` — so the topic advances after the very first encounter.

---

## How `next_review` Date Is Calculated

```
next_review = session_date + timedelta(days=new_interval)
```

| Repetitions after session | Interval | next_review |
|--------------------------|----------|-------------|
| 1 (first success) | 1 day | Tomorrow |
| 2 (second success) | 6 days | ~1 week |
| 3+ (ongoing) | `round(prev_interval × EF)` | Grows exponentially |
| Any failure (quality < 3) | 1 day | Tomorrow |

The `reference_date` parameter in `SM2Algorithm.calculate_next_review()` defaults to `date.today()`, so `next_review` is always calculated from the actual session date, not the plan date.

---

## Known Issue: Topic Name Mismatch Preventing Session Saves

### The Problem

The weekly plan page resolves topics to `learning_history` rows using an exact string key:

```python
lookup_key = f"{subject}|{topic_name}"
learning_entry = topic_lookup.get(lookup_key)
```

If the AI generates a topic name that differs even slightly from the name stored in `learning_history`, the lookup returns `None`. The topic gets `learning_history_id = None` and is skipped at save time.

**Example:**
- Stored in DB: `"LITERACY|Blending of Letters – bl, cl, fl"`
- AI generated: `"LITERACY|Letter Blending bl cl fl"`
- Result: no match → session cannot be saved for this topic

### Symptom in the UI

```
Skipped 2 topic(s) not in learning history.
They may be from future curriculum.
```

Note: this message is misleading — the topic is in the curriculum, just named differently.

### Current Workaround

None in the app. The parent must identify the mismatch manually and either:
1. Edit the topic name in the DB directly to match the AI output, or
2. Accept that session is lost for that topic

### Planned Fix

Fuzzy string matching (e.g., `rapidfuzz`) on topic lookup with a configurable similarity threshold (≥ 0.85 recommended).

---

## Known Issue: Duplicate Weekly Plans From Button Races (Fixed Jul 2026)

### The Problem

`_show_action_buttons()` in `frontend/modules/weekly_plan.py` renders "💾 Save Progress" and
"🔄 Generate Next Week's Plan" side by side. Neither was disabled while the other's (or its
own) slow operation ran — Streamlit doesn't disable buttons automatically — so a second
click during a multi-second AI generation call queued up and fired again once the script
was free. This is almost certainly why 3 duplicate `weekly_plans` rows existed for the same
week (had to be deleted manually).

### The Fix

Both buttons now check a `st.session_state.action_in_progress` flag. Clicking either sets
the flag and immediately calls `st.rerun()`, so the *next* render shows both buttons
disabled before the slow call actually starts. The flag is cleared right before the work
begins (not after) — `_save_progress()` and `_generate_next_week()` both call `st.rerun()`
internally on success, which halts the script immediately, so clearing the flag after the
call would never execute and would leave the buttons stuck disabled (or worse, re-trigger
the action on every subsequent rerun).

**Follow-up bug (also fixed):** the flag does double duty — it holds a string (`'save'` /
`'generate'`) identifying *which* action is pending, used below to decide what to actually
run on the triggered rerun. That raw string was passed straight into each button's
`disabled=` argument, but Streamlit's `disabled` prop needs an actual bool; a non-empty
string blew up with `TypeError: 'str' object cannot be interpreted as an integer` deep in
Streamlit's protobuf layer. Fixed by computing `is_busy = bool(busy)` separately for the
`disabled=` argument, leaving `busy` itself holding the string for the action-dispatch
check.

---

## Analytics Page

The **Progress Report** page (`progress_report.py`) queries live data via `backend/crud/analytics.py`.

### Data Sources

| Metric | Query |
|--------|-------|
| This week completion % | Sessions this week ÷ topics in the latest `weekly_plans` entry |
| Topics overdue | `learning_history WHERE next_review <= today AND last_reviewed IS NOT NULL AND graduated IS FALSE` |
| Subject avg quality | `AVG(quality_rating)` from `study_sessions` joined to `learning_history`, grouped by subject |
| Total sessions per subject | `COUNT(*)` from same join |
| Graduated topics | `learning_history WHERE graduated IS TRUE`, ordered by `graduated_at DESC` |

### Status Thresholds

Status labels on the subject performance bars are derived automatically from `avg_quality`:

| avg_quality | Status |
|-------------|--------|
| ≥ 4.0 | Excellent 🌟 |
| ≥ 3.5 | Good ✅ |
| ≥ 3.0 | OK 👍 |
| < 3.0 | Needs Revision ⚠️ |

### Empty States

- No rated sessions yet → subject performance section shows an info message instead of crashing.
- No overdue topics → shows a "all caught up" success message.
- No graduated topics yet → shows a caption pointing back to This Week's Plan instead of an empty table.

### Entry Point

`app.py` calls `get_analytics(db, user_id)` (from `backend/crud/analytics.py`) and passes the result dict to `show_progress_report_page()`. No mock data remains in the codebase.
