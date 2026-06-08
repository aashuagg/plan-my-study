# Study Planner — Project Overview

## What Is This?

**Study Planner** is a personal, web-based spaced repetition study assistant built by a parent developer for their child (currently UKG / Class 1, CBSE board).

Every month the child's school sends home a newsletter with the upcoming curriculum — subjects, topics, and rough dates. The parent manually decodes this, figures out what needs to be revised, and tries to structure study sessions. This was taking significant mental load and wasn't systematic.

This app automates that process:
1. Upload the monthly newsletter (as a CSV derived from the school document)
2. The app ingests the curriculum, initialises SM-2 spaced repetition tracking for every topic
3. Each week, an AI model generates a balanced, constraint-aware study plan
4. The parent marks topics as done and rates quality (0–5)
5. SM-2 recalculates the next review date automatically

---

## Who Is It For?

| Role | Description |
|------|-------------|
| **Primary user** | Parent/guardian who manages the study schedule |
| **Beneficiary** | Child (UKG / Class 1, CBSE) |
| **Scope** | Single-child, single-household personal tool |

This is **not** a multi-tenant SaaS product. It is a personal tool with a single user profile (user_id = 1 by default).

---

## Key Features

### ✅ MVP — Done

| Feature | Status |
|---------|--------|
| Student profile creation (name, grade, board, subjects, schedule) | ✅ Done |
| Newsletter ingestion via CSV upload | ✅ Done |
| Curriculum items stored per newsletter with start/end dates | ✅ Done |
| SM-2 spaced repetition tracking initialised per topic | ✅ Done |
| AI-generated weekly study plan (6 days) | ✅ Done |
| Dual AI provider: Ollama (dev) / Claude API (prod) | ✅ Done |
| Weekly plan displayed day-by-day with expand/collapse | ✅ Done |
| Topic completion tracking with quality rating (0–5) | ✅ Done |
| Save progress → persists study sessions to DB | ✅ Done |
| SM-2 parameters updated after each session | ✅ Done |
| Generate next week's plan | ✅ Done |
| Progress report page (analytics) | ⚠️ Scaffolded — uses mock data |

### 🔜 Planned — Next Phase

| Feature | Priority |
|---------|----------|
| Automated newsletter parsing (screenshot → OCR → CSV, no manual Claude chat) | High |
| Real analytics using live DB data (replace mock) | High |
| Profile edit UI | Medium |
| `academic_year` field on sessions (UKG → Class 1 transitions) | Medium |
| Overdue topic drill-down view | Medium |
| CLI-based plan generation and session recording | Low |
| PDF export of weekly plan | Low |

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    PARENT'S BROWSER                     │
│                                                         │
│   ┌─────────────────────────────────────────────────┐   │
│   │           STREAMLIT FRONTEND                    │   │
│   │                                                 │   │
│   │  📅 This Week's Plan  (weekly_plan.py)          │   │
│   │  📊 Progress Report   (progress_report.py)      │   │
│   │  📤 Upload Newsletter (upload_newsletter.py)    │   │
│   │  🧑 Setup Profile     (setup_profile.py)        │   │
│   └──────────────┬──────────────────────────────────┘   │
└──────────────────│──────────────────────────────────────┘
                   │ SQLAlchemy ORM (direct DB access)
                   │
   ┌───────────────▼───────────────────────┐
   │           BACKEND (Python)            │
   │                                       │
   │  ┌─────────┐  ┌──────────┐           │
   │  │ SM-2    │  │Scheduler │           │
   │  │Algorithm│  │(LangChain│           │
   │  └────┬────┘  │ prompt)  │           │
   │       │       └────┬─────┘           │
   │       │            │                 │
   │  ┌────▼────────────▼──────────────┐  │
   │  │      SQLAlchemy ORM / CRUD     │  │
   │  └────────────────┬───────────────┘  │
   └───────────────────│──────────────────┘
                       │
   ┌───────────────────▼──────────────────┐
   │    PostgreSQL 15  (Docker)           │
   │                                      │
   │  users  │ newsletters │ curriculum   │
   │  learning_history  │ study_sessions  │
   │  weekly_plans                        │
   └──────────────────────────────────────┘
                       │
   ┌───────────────────▼──────────────────┐
   │           AI LAYER                   │
   │                                      │
   │  DEV:  Ollama  (llama3.2:latest)     │
   │  PROD: Claude  (claude-3-5-sonnet)   │
   │                                      │
   │  LangChain abstracts both providers  │
   └──────────────────────────────────────┘
```

> **Note:** There is no FastAPI HTTP layer active in the current MVP. The Streamlit frontend calls the backend CRUD layer and ORM directly via a shared database session. FastAPI is in the dependency list for a planned REST API layer.

---

## Roadmap

### Phase 1 — Current MVP (Complete)

- [x] Profile setup
- [x] Newsletter CSV upload and parsing
- [x] Curriculum ingestion and SM-2 init
- [x] AI weekly plan generation (Ollama + Claude)
- [x] Plan display and completion tracking
- [x] Session recording and SM-2 updates
- [x] Progress report scaffold

### Phase 2 — Next Features

- [ ] **Automated newsletter parsing** — eliminate 5–6 hour manual CSV prep
- [ ] **Live analytics** — replace all mock data with real DB queries
- [ ] **Profile edit UI** — change grade, duration, subjects without recreating profile
- [ ] **Academic year tagging** — tag sessions with `academic_year` so UKG history is preserved when transitioning to Class 1
- [ ] **Overdue topic detail view** — clickable list from progress report
- [ ] **CLI enhancements** — `plan generate`, `session record` via Typer CLI
- [ ] **PDF export** — printable weekly plan

---

## Known Limitations

| Limitation | Details |
|------------|---------|
| **Single-user** | `user_id = 1` hardcoded in `app.py`. No login, no multi-child support. |
| **No profile edit** | Once created, the profile cannot be edited through the UI. Must use CLI or DB directly. |
| **Analytics uses mock data** | The Progress Report page shows hardcoded fake numbers. Real query implementation is pending. |
| **Topic name mismatch** | If an AI-generated topic name differs even slightly from the `curriculum_items` name, the topic will have no `learning_history_id` and the session cannot be saved. |
| **Manual newsletter process** | Converting a school PDF/newsletter to the required CSV takes 5–6 hours of manual work using Claude chat. |
| **Ollama plan quality** | Ollama (llama3.2) frequently violates the 2-topic-per-day hard limit and subject-topic matching rules. Claude is significantly more reliable. |
| **No authentication** | No login screen. The app assumes a trusted home network environment. |
