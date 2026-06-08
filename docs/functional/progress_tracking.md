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
Success count shown; page reruns to reflect updated state
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

## Current State of the Analytics Page

The **Progress Report** page (`progress_report.py`) is scaffolded but does **not** query real data.

All metrics shown are hardcoded mock values defined in `app.py`:

```python
MOCK_ANALYTICS = {
    "subject_performance": [
        {"subject": "LITERACY", "avg_quality": 4.2, "total_sessions": 25, "status": "Good ✅"},
        {"subject": "NUMERACY", "avg_quality": 3.8, "total_sessions": 22, "status": "Good ✅"},
        {"subject": "HINDI",    "avg_quality": 2.9, "total_sessions": 18, "status": "Needs Revision ⚠️"},
        {"subject": "KANNADA",  "avg_quality": 3.5, "total_sessions": 15, "status": "OK 👍"},
        {"subject": "GENERAL AWARENESS", "avg_quality": 4.5, "total_sessions": 20, "status": "Excellent 🌟"},
    ],
    "overdue_count": 428,       # ← hardcoded; real value would come from learning_history
    "study_streak": 5,          # ← hardcoded
    "this_week_completion": 40  # ← hardcoded percentage
}
```

### What the Analytics Page Shows (all mock)

| Metric | Real Source (when implemented) |
|--------|-------------------------------|
| Study streak (days) | `study_sessions` — consecutive days with at least one session |
| This week completion % | `study_sessions` vs topics in current `weekly_plans` |
| Topics overdue | `learning_history WHERE next_review < today` |
| Subject avg quality | `AVG(quality_rating)` from `study_sessions` per subject |
| Total sessions per subject | `COUNT(*)` from `study_sessions` grouped by subject |

### Planned Fix (Phase 2)

Replace `MOCK_ANALYTICS` with real DB queries in a new `backend/crud/analytics.py` module, and pass results to `show_progress_report_page()`.
