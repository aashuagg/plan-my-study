# Student Profile

## Overview

The student profile is the root entity in the system. Everything — newsletters, curriculum items, weekly plans, learning history, and study sessions — is linked to a single user profile. In the current MVP there is one profile (user_id = 1).

---

## Profile Fields

The profile is stored in the `users` table. All fields are set at creation time via the **Setup Profile** form.

| Field | DB Column | Type | Required | Description |
|-------|-----------|------|----------|-------------|
| Name | `name` | VARCHAR | Yes | Child's name (e.g., "Shubhi") |
| Grade | `grade` | VARCHAR | Yes | One of: Nursery, LKG, **UKG**, Pre-Primary, Class 1–5 |
| Board | `board` | VARCHAR | Yes | One of: **CBSE**, ICSE, State Board, IB, IGCSE, Other |
| Daily study duration | `daily_duration_minutes` | INTEGER | Yes | Minutes per day (15–180, step 15; default 30) |
| Study days per week | `weekly_frequency` | INTEGER | Yes | 3–7 days; default 6 |
| Subjects | `subjects` | JSON | Yes | Array of subject name strings (see below) |
| Preferred study time | `study_time_preference` | VARCHAR | No | "Morning", "Afternoon", "Evening", or NULL |
| Created at | `created_at` | DATETIME | Auto | UTC timestamp set on row creation |

---

## How the Subjects List Works

`subjects` is stored as a **JSON array** of uppercase strings in PostgreSQL:

```json
["LITERACY", "NUMERACY", "HINDI", "KANNADA", "GENERAL AWARENESS"]
```

### Available Subject Options (from setup form)

```
LITERACY          NUMERACY          HINDI
KANNADA           ENGLISH           GRAMMAR
MATHS             SCIENCE           SOCIAL STUDIES    GENERAL AWARENESS
COMPUTER          ART & CRAFT       MUSIC
PHYSICAL EDUCATION
```

### How Subjects Flow Through the System

```
users.subjects (JSON array)
      │
      ├──▶ Shown in AI prompt: "Subjects: LITERACY, NUMERACY, HINDI..."
      │     The AI is instructed to ONLY use these subjects when generating plans
      │
      ├──▶ Compared against curriculum_items.subject on upload
      │     (mismatch = topic won't be matched in plans)
      │
      └──▶ Used as filter for learning_history display
```

### Editing Subjects

There is **no UI to edit subjects** after profile creation (see limitation below). To add or remove a subject:

**Option 1 — CLI (if implemented):**
```bash
python cli.py user update-subjects --user-id 1 --subjects "LITERACY,NUMERACY,HINDI,KANNADA"
```

**Option 2 — Direct DB:**
```sql
UPDATE users
SET subjects = '["LITERACY", "NUMERACY", "HINDI", "KANNADA", "GENERAL AWARENESS"]'
WHERE id = 1;
```

**Option 3 — Delete and recreate profile** (destructive — loses history linkage)

---

## Pydantic Schema

```python
class UserCreate(BaseModel):
    name: str
    grade: str
    board: str
    daily_duration_minutes: int
    weekly_frequency: int
    subjects: List[str]
    study_time_preference: Optional[str] = None
```

The `UserResponse` schema adds `id: int` and is used when reading back the created profile.

---

## How the Profile Is Used at Runtime

In `frontend/app.py`, the profile is loaded once at startup:

```python
user = get_user(db, st.session_state.user_id)   # user_id = 1 (hardcoded)
```

If no user exists (first run), the **Setup Profile** page is shown before anything else.

Once loaded, the profile data is passed to:
- **Weekly plan generator** — name, grade, board, daily duration, weekly frequency, subjects
- **Progress report** — name (display only in MVP)
- **Sidebar** — name, grade, board

---

## Current Limitation: No Edit UI

Once a profile is created, there is no in-app way to change any field. This affects:

| Scenario | Impact |
|----------|--------|
| Child moves from UKG to Class 1 | Grade is wrong but doesn't affect functionality |
| Parent wants to add a new subject | Must edit DB directly |
| Daily duration changes (e.g., longer sessions in summer) | Must edit DB directly |
| Study days change (e.g., 5 days instead of 6) | Must edit DB directly |

**Planned fix (Phase 2):** Add an edit profile page accessible from the sidebar. Fields should be pre-populated with current values and saved on submit.

---

## Planned: `academic_year` Tagging for Grade Transitions

### The Problem

When Aashu moves from **UKG to Class 1**, the historical study sessions and learning history from UKG remain in the database. Currently there is no way to:
- Know which sessions belong to which academic year
- Reset SM-2 state for subjects that are essentially starting fresh in Class 1
- Show progress reports scoped to "this year only"

### Planned Solution

Add an `academic_year` column to `study_sessions`:

```sql
ALTER TABLE study_sessions ADD COLUMN academic_year VARCHAR;
-- e.g., "2025-26" for UKG, "2026-27" for Class 1
```

At the start of each academic year:
1. Update the `grade` field in `users`
2. Set the new `academic_year` string in app config
3. All new sessions are tagged with the new year
4. Analytics can be filtered by `academic_year`

The `learning_history` SM-2 state would optionally be reset for subjects where the curriculum completely restarts (e.g., NUMERACY moving from counting to addition).

This feature is **not yet implemented** — it is planned for Phase 2 before the Class 1 transition.

---

## Session State (Streamlit)

The profile-related session state keys in `app.py`:

| Key | Default | Purpose |
|-----|---------|---------|
| `st.session_state.user_id` | `1` | Active user ID (hardcoded) |
| `st.session_state.completed_topics` | `{}` | Tracks topic completion state for the current page load |

The `completed_topics` dict is keyed by topic ID (an integer counter within the weekly plan) and holds:
```python
{
    1: {
        'completed': True,
        'quality': 4,
        'notes': 'Did well with blends',
        'learning_history_id': 23,
        'topic': 'Letter Blending',
        'date': '2026-05-19'
    }
}
```
