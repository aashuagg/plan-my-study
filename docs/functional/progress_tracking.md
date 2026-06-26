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

**Threshold:** Quality ≥ 3 is considered a **successful recall**. Quality < 3 resets the SM-2 repetition counter.

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

## Analytics Page

The **Progress Report** page (`progress_report.py`) queries live data via `backend/crud/analytics.py`.

### Data Sources

| Metric | Query |
|--------|-------|
| Study streak (days) | Distinct `session_date` values from `study_sessions`, counted backwards from today |
| This week completion % | Sessions this week ÷ topics in the latest `weekly_plans` entry |
| Topics overdue | `learning_history WHERE next_review <= today AND last_reviewed IS NOT NULL` |
| Subject avg quality | `AVG(quality_rating)` from `study_sessions` joined to `learning_history`, grouped by subject |
| Total sessions per subject | `COUNT(*)` from same join |

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

### Entry Point

`app.py` calls `get_analytics(db, user_id)` (from `backend/crud/analytics.py`) and passes the result dict to `show_progress_report_page()`. No mock data remains in the codebase.
