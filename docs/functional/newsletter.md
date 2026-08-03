# Newsletter Ingestion

## Overview

The school sends home a monthly newsletter (typically a PDF or printed sheet) containing the upcoming curriculum: what subjects will be taught and when. This document is the single source of truth for the child's academic schedule.

The app ingests this curriculum via a CSV file uploaded through the **Upload Newsletter** page.

---

## Current Ingestion Flow

```
School newsletter (PDF / printed sheet)
        │
        ▼  [Manual step — ~5–6 hours]
Parent photographs or scans the newsletter
        │
        ▼
Parent pastes/uploads the image into a Claude chat session
        │
        ▼
Parent prompts Claude to extract curriculum data
  (subject, topic, dates) and format as CSV
        │
        ▼
Parent reviews and manually cleans the CSV:
  - Removes vague topics
  - Removes page references
  - Removes school-only activities
  - Corrects wrong subject assignments
  - (Subject name normalisation is now automatic on ingest for known
    variants — see Subject Normalisation Rules below — but new/unusual
    variants still need a manual fix or an addition to SUBJECT_ALIASES)
        │
        ▼
Cleaned CSV saved to local machine
        │
        ▼
Parent opens app → Upload Newsletter page
        │
        ▼
Selects Month + Year
Uploads CSV file
        │
        ▼
NewsletterParser.auto_parse() reads the CSV
        │
        ▼
Preview shown (first 10 rows)
        │
        ▼
Parent clicks "Process Newsletter"
        │
        ▼
Newsletter record created in DB (newsletters table)
Curriculum items saved (curriculum_items table)
SM-2 tracking initialised for each new topic (learning_history table)
```

---

## Expected CSV Format

The uploaded file must be a **CSV** (or Excel `.xlsx`) with the following columns:

| Column | Required | Type | Example |
|--------|----------|------|---------|
| `subject` | Yes | String | `LITERACY` |
| `topic` | Yes | String | `Letter Blending - bl, cl, fl` |
| `start_date` | Yes | Date | `2026-05-05` |
| `end_date` | No | Date | `2026-05-09` |

### Date Format Support

The parser attempts multiple date formats in order:

```
YYYY-MM-DD   →  2026-05-05
DD/MM/YYYY   →  05/05/2026
MM/DD/YYYY   →  05/05/2026
DD-MM-YYYY   →  05-05-2026
YYYY/MM/DD   →  2026/05/05
DD/MM/YY     →  05/05/26
```

If no format matches, the row is silently skipped.

### Minimal Valid Example

```csv
subject,topic,start_date
LITERACY,Letter Blending bl cl fl,2026-05-05
NUMERACY,Counting to 20,2026-05-05
HINDI,Vowels - aa ii uu,2026-05-07
KANNADA,Aksharagalu,2026-05-07
GENERAL AWARENESS,Plants and Animals,2026-05-12
```

---

## Cleaning Rules — What Gets Removed and Why

The raw newsletter contains content that is not useful as study topics for the child. These must be removed **before** uploading the CSV.

### 1. Vague or Non-Specific Topics

**Examples to remove:**
- "Revision"
- "Activities"
- "Project work"
- "Oral test"

**Why:** These are process instructions, not discrete study topics. SM-2 cannot track "Revision" meaningfully, and the AI cannot plan around it.

---

### 2. Page References

**Examples to remove:**
- "Pg 12-15"
- "Pages 45-50"
- "See workbook page 7"

**Why:** Page numbers are school-internal references for textbook exercises, not topics the child needs to recall. They clutter the plan without adding review value.

---

### 3. School-Only Activities

**Examples to remove:**
- "Sports Day practice"
- "Assembly presentation"
- "Field trip – Science Museum"
- "Teacher's Day celebration"

**Why:** These happen at school and require no home study. Including them in the plan confuses the AI and wastes plan slots.

---

### 4. Assessment Items

**Examples to remove:**
- "Unit test – all chapters"
- "FA1 examination"
- "Class test – numbers"

**Why:** Tests are events, not topics. They may warrant a note in the **Upcoming Events** field when generating a plan, but should not be curriculum items.

---

### 5. Wrong Subject Assignments

The school newsletter sometimes lists topics under the wrong subject heading (e.g., "Sentence formation" under "General Awareness" when it belongs under "LITERACY").

**Fix before upload:** Manually reassign to the correct subject. This is the most error-prone step in the cleaning process.

---

## Subject Normalisation Rules

The `subject` column must use the **exact names** that appear in the student's profile `subjects` JSON array.

**Automated (Jul 2026):** `NewsletterParser.normalize_subject()` uppercases the subject and
maps known variants via a `SUBJECT_ALIASES` table, applied on every ingest path (CSV, Excel,
PDF) and on manual diary entries indirectly (those use the profile's subject list directly,
so they're already canonical). Currently mapped:

| Raw newsletter text | Normalised subject name |
|--------------------|------------------------|
| Mathematics / Math | `MATHS` |
| EVS / Environmental Studies | `GENERAL AWARENESS` |
| Computer Science | `COMPUTER` |

Anything not in the alias table passes through as uppercased-only. Newly seen variants
(e.g. "English Language", "G.K.") should be added to `SUBJECT_ALIASES` in
`backend/newsletter_parser.py` rather than cleaned by hand in the CSV.

> **Important:** Subject names in `curriculum_items` must exactly match subjects in `learning_history`. A mismatch (e.g., `MATHEMATICS` vs `MATHS`) silently splits one subject into two everywhere — coverage view, due-topics query, weekly plan — with no error. This exact bug existed undetected for weeks before being caught via the Monthly Topics tab and fixed Jul 2026 (10 existing rows backfilled from `MATHEMATICS` to `MATHS`).

---

## What Happens After Upload

1. A `Newsletter` row is created in the database (month, year, file_path, parsed_data)
2. Each CSV row becomes a `CurriculumItem` row linked to that newsletter
3. For each new curriculum item, a `LearningHistory` row is initialised with:
   - `easiness_factor = 2.5`
   - `interval = 1`
   - `repetitions = 0`
   - `next_review = today + 1 day`
4. These topics immediately become eligible for inclusion in the next weekly plan

---

## Manually Adding Diary Entries

To bypass the CSV upload process for individual or missed topics (e.g., homework or extra school practice), parents can use the **Add Diary Entry** tab on the Upload Newsletter page.

### How it works:
1. **Inputs**: The parent selects a **Date**, chooses a **Subject** (from the options configured in the student's profile), enters the **Topic** text, and optionally picks a **Quality Rating** (0-5, same scale as the weekly plan — see `docs/functional/progress_tracking.md`).
2. **Special Newsletter**: These manual entries are automatically grouped under a virtual newsletter with month `"Diary"` and year `0`.
3. **Database Insertion**:
   - Saves a new `CurriculumItem` linked to the `"Diary"` newsletter.
   - Initializes a new `LearningHistory` record for the topic with default SM-2 parameters (`easiness_factor = 2.5`, `interval = 1`, `repetitions = 0`, `next_review = entry_date`) if it is not already tracked.
   - **If a quality rating was given** (fixed Jul 2026): records a real `StudySession` via `record_study_session()` — the same path the weekly plan's "Save Progress" uses — so SM-2 actually advances (`easiness_factor`, `interval`, `repetitions`, `next_review`) to reflect that a revision genuinely happened. Session type (`study` vs `review`) is inferred from the topic's current `repetitions`, same logic as the weekly plan.
   - **If no rating was given**, the topic is just added to the curriculum at its SM-2 baseline (or left untouched if already tracked) — for logging something as "covered at school" without claiming a revision took place.

   Previously, submitting a diary entry for a topic **already tracked** in `learning_history` silently did nothing to its SM-2 state — no rating field even existed, so a real revision (e.g. "she practiced this dictation list again at home") went unrecorded, and the topic kept surfacing as overdue in weekly plans despite genuinely having been revised. The quality-rating field closes that gap.
4. **Form Reset and Feedback**: On a successful submit, a green success banner is displayed, the page is reloaded, and the form fields are automatically reset and cleaned to accept the next manual entry.
5. **Recent Entries List**: Displays the last 5 manually added diary entries in a table for reference and verification.

---

## Monthly Topics Audit Tab (Added Jul 2026)

A third tab on the Upload Newsletter page (`frontend/modules/monthly_topics.py`,
`get_curriculum_by_month()` in `backend/crud/curriculum.py`) shows every curriculum item —
newsletter and diary entries combined — for a selected month, tagged by source, with a
subject filter and a per-subject coverage check that flags any subject with zero topics
that month.

**Why it exists:** the parent had no way to see the full combined picture of what had been
ingested, so gaps (a subject the school covered but the parent forgot to log, or a
newsletter row that failed silent CSV parsing) went unnoticed until a topic turned out to
have never appeared in any weekly plan. This tab is now the first place to check when a
topic seems to be missing — before assuming it's a scheduling bug (see
`docs/functional/plan_generation.md` Issue 3 for the scheduling-side counterpart).

---

## Known Limitation: Manual Process

**Current state:** Converting the school newsletter into a usable CSV takes approximately **5–6 hours** of manual work per month:

- Photographing/scanning the newsletter
- Pasting into Claude chat
- Reviewing Claude's extraction for errors
- Manually cleaning (removing invalid topics, fixing subject assignments)
- Date formatting

**Planned automation (Phase 2):**
- Direct PDF/image upload to the app
- OCR + AI extraction pipeline within the app
- Automated cleaning suggestions with a human review step
- Target: reduce to < 30 minutes per month

---

## Edge Cases

| Situation | Behaviour |
|-----------|-----------|
| Duplicate topic (same subject + topic already in DB) | Creates a second `learning_history` row; may cause duplicates in plans |
| Row with no valid start_date | Row is silently skipped |
| Row with missing `subject` or `topic` | Will fail Pydantic validation and skip |
| Excel `.xlsx` file | Supported via openpyxl (pandas read_excel) |
| File > 200MB | Streamlit default upload limit applies |
