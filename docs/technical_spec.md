# Technical Specification

## Tech Stack

| Layer | Technology | Version / Notes |
|-------|-----------|-----------------|
| **Language** | Python | 3.13 (per `__pycache__` naming) |
| **Frontend** | Streamlit | Latest (no pin in requirements.txt) |
| **Backend framework** | FastAPI | Listed in requirements; not yet wired as HTTP API in MVP |
| **ASGI server** | Uvicorn | Listed in requirements |
| **ORM** | SQLAlchemy | Latest |
| **DB driver** | psycopg2-binary | PostgreSQL adapter |
| **Database** | PostgreSQL | 15-alpine (Docker) |
| **Data validation** | Pydantic + pydantic-settings | v2 (uses `from_attributes = True`) |
| **AI orchestration** | LangChain | `langchain`, `langchain-ollama`, `langchain-anthropic` |
| **AI — Dev** | Ollama | llama3.2:latest, local at `http://localhost:11434` |
| **AI — Prod** | Claude API | claude-3-5-sonnet-20241022 |
| **CLI** | Typer + Rich | Latest |
| **Data processing** | pandas, openpyxl | For CSV/Excel newsletter parsing |
| **PDF generation** | reportlab | Listed; not yet used in MVP |
| **File upload** | python-multipart | For Streamlit file uploader |
| **Config** | python-dotenv / pydantic-settings | Loads `.env` from project root |

---

## Database Schema

### Table: `users`

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `id` | INTEGER (PK) | No | Auto-increment primary key |
| `name` | VARCHAR | No | Student's name (e.g., "Shubhi") |
| `grade` | VARCHAR | No | Grade level (e.g., "UKG", "Class 1") |
| `board` | VARCHAR | No | Education board (e.g., "CBSE") |
| `daily_duration_minutes` | INTEGER | No | How many minutes per study day |
| `weekly_frequency` | INTEGER | No | How many days per week to study |
| `subjects` | JSON | No | Array of subject strings, e.g. `["LITERACY","HINDI"]` |
| `study_time_preference` | VARCHAR | Yes | "Morning", "Afternoon", "Evening", or NULL |
| `created_at` | DATETIME | Yes | Row creation timestamp (UTC) |

**Relationships:** one-to-many with `newsletters`, `study_sessions`, `learning_history`.

---

### Table: `newsletters`

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `id` | INTEGER (PK) | No | Auto-increment primary key |
| `user_id` | INTEGER (FK → users.id) | Yes | Owning user |
| `month` | VARCHAR | No | Month name, e.g. "May" |
| `year` | INTEGER | No | Calendar year, e.g. 2026 |
| `file_path` | VARCHAR | Yes | Original upload path (temp file, may not persist) |
| `parsed_data` | JSON | Yes | Raw structured curriculum data from the parser |
| `uploaded_at` | DATETIME | Yes | Upload timestamp (UTC) |

**Relationships:** belongs to `users`; one-to-many with `curriculum_items`.

---

### Table: `curriculum_items`

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `id` | INTEGER (PK) | No | Auto-increment primary key |
| `newsletter_id` | INTEGER (FK → newsletters.id) | Yes | Source newsletter |
| `subject` | VARCHAR | No | Normalised subject name (e.g., "LITERACY") |
| `topic` | VARCHAR | No | Topic name exactly as it will be used in plans |
| `start_date` | DATE | No | When this topic begins in school |
| `end_date` | DATE | Yes | Optional end date from newsletter |

**Relationships:** belongs to `newsletters`. Referenced indirectly by `learning_history`.

---

### Table: `learning_history`

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `id` | INTEGER (PK) | No | Auto-increment primary key |
| `user_id` | INTEGER (FK → users.id) | Yes | Owning student |
| `subject` | VARCHAR | No | Subject name (must match curriculum_items exactly) |
| `topic` | VARCHAR | No | Topic name (must match curriculum_items exactly) |
| `easiness_factor` | FLOAT | Yes | SM-2 EF value; default 2.5; range 1.3–∞ |
| `interval` | INTEGER | Yes | Current review interval in days; default 1 |
| `repetitions` | INTEGER | Yes | Count of successful consecutive reviews; default 0 |
| `last_reviewed` | DATE | Yes | Date of most recent study session; NULL if never reviewed |
| `next_review` | DATE | No | Next scheduled review date (set by SM-2 algorithm) |

**Relationships:** belongs to `users`; one-to-many with `study_sessions`.

---

### Table: `study_sessions`

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `id` | INTEGER (PK) | No | Auto-increment primary key |
| `user_id` | INTEGER (FK → users.id) | Yes | Student who did the session |
| `learning_history_id` | INTEGER (FK → learning_history.id) | Yes | Which topic was studied |
| `session_date` | DATE | No | Calendar date of the session |
| `session_type` | VARCHAR | No | `"study"` (first time) or `"review"` (repeat) |
| `quality_rating` | INTEGER | Yes | SM-2 quality score 0–5; required for review sessions |
| `notes` | VARCHAR | Yes | Parent's optional freetext notes |
| `created_at` | DATETIME | Yes | Row creation timestamp (UTC) |

**Relationships:** belongs to both `users` and `learning_history`.

---

### Table: `weekly_plans`

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `id` | INTEGER (PK) | No | Auto-increment primary key |
| `user_id` | INTEGER (FK → users.id) | Yes | Plan owner |
| `week_start_date` | DATE | No | Monday of the week this plan covers |
| `plan_data` | JSON | No | Full AI-generated schedule (list of `DailyPlan` objects) |
| `focus_request` | TEXT | Yes | Parent's optional emphasis request |
| `events` | TEXT | Yes | Upcoming events noted at generation time |
| `generated_at` | DATETIME | Yes | When the plan was generated (UTC) |

**Relationships:** belongs to `users`.

---

## Entity Relationships

```
users (1)
  ├──< newsletters (many)
  │       └──< curriculum_items (many)
  │
  ├──< learning_history (many)
  │       └──< study_sessions (many)
  │
  ├──< study_sessions (many)   [also FK on learning_history]
  │
  └──< weekly_plans (many)
```

**Key constraint:** `study_sessions.learning_history_id` is the link between a plan topic and SM-2 tracking. If the topic name in the AI plan does not exactly match a `learning_history` row, this foreign key cannot be resolved, and saving the session silently skips that topic.

---

## SM-2 Algorithm

### Overview

The app implements the classic **SuperMemo 2 (SM-2)** algorithm by Piotr Wozniak. Each topic tracked in `learning_history` carries three SM-2 state variables: `easiness_factor` (EF), `interval`, and `repetitions`.

### Parameter Definitions

| Parameter | Default | Range | Meaning |
|-----------|---------|-------|---------|
| `easiness_factor` (EF) | 2.5 | ≥ 1.3 | How "easy" the topic is; higher = longer intervals |
| `interval` | 1 | 1–∞ days | Current gap between reviews |
| `repetitions` | 0 | 0–∞ | Number of consecutive successful recalls |

### Calculation Logic (`backend/sm2.py`)

**Step 1 — Update EF based on quality rating:**
```
new_EF = EF + (0.1 − (5 − q) × (0.08 + (5 − q) × 0.02))
new_EF = max(new_EF, 1.3)   # floor at 1.3
```

| Quality | EF Change |
|---------|-----------|
| 5 (perfect) | +0.10 |
| 4 (correct, some hesitation) | +0.00 |
| 3 (correct, significant difficulty) | −0.14 |
| 2 (wrong, easy recall after) | −0.32 |
| 1 (wrong, hard recall) | −0.54 |
| 0 (complete blackout) | −0.80 |

**Step 2 — Determine new interval:**

```python
if quality < 3:            # Failed recall → reset
    repetitions = 0
    interval = 1
else:
    repetitions += 1
    if repetitions == 1:   interval = 1
    elif repetitions == 2: interval = 6
    else:                  interval = round(prev_interval × new_EF)
```

**Step 3 — Set next_review date:**
```
next_review = today + timedelta(days=new_interval)
```

### Initialisation for New Topics

When a newsletter is uploaded, every new curriculum item gets a `learning_history` row with:
- `easiness_factor = 2.5`
- `interval = 1`
- `repetitions = 0`
- `next_review = today + 1 day`

### Helper Methods

| Method | Purpose |
|--------|---------|
| `is_due_for_review(next_review_date)` | Returns `True` if `today >= next_review` |
| `get_days_overdue(next_review_date)` | Returns `(today - next_review).days` or 0 if not overdue |

---

## AI Provider Setup

The active AI provider is controlled by the `AI_PROVIDER` environment variable.

### Factory pattern (`backend/scheduler.py`)

```python
def get_scheduler():
    if settings.ai_provider.lower() == "claude":
        return ClaudeScheduler()
    else:
        return OllamaScheduler()
```

### OllamaScheduler (development)

```python
ChatOllama(
    model=settings.ollama_model,        # "llama3.2:latest"
    base_url=settings.ollama_base_url,  # "http://localhost:11434"
    temperature=0.0,
    format="json"                       # forces JSON output mode
)
```

### ClaudeScheduler (production)

```python
ChatAnthropic(
    model=settings.claude_model,        # "claude-3-5-sonnet-20241022"
    api_key=settings.claude_api_key,
    temperature=0.0
)
```

> **Note:** The `ClaudeScheduler` import (`from langchain_anthropic import ChatAnthropic`) is commented out in the current codebase. Uncomment it before switching `AI_PROVIDER=claude`.

Both schedulers inherit from `BaseScheduler` which builds the same prompt and uses `JsonOutputParser` to parse the response into a `WeeklyPlanOutput` Pydantic model.

---

## Environment Variables

Create a `.env` file in the **project root** (alongside `docker-compose.yml`):

```dotenv
# ── Database ──────────────────────────────────────────────────────────
DATABASE_URL=postgresql://studyplanner:studyplanner123@localhost:5432/study_planner

# ── AI Provider ───────────────────────────────────────────────────────
# Options: "ollama" (default, local dev) or "claude" (production)
AI_PROVIDER=ollama

# ── Ollama settings (used when AI_PROVIDER=ollama) ────────────────────
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest

# ── Claude settings (used when AI_PROVIDER=claude) ────────────────────
CLAUDE_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-3-5-sonnet-20241022
```

Config is loaded by `pydantic-settings` (`backend/config.py`) and the `.env` path is resolved relative to the project root automatically.

---

## How to Run Locally

### 1. Start PostgreSQL (Docker)

```bash
# From project root
docker compose up -d

# Verify it's running
docker ps
```

This starts `study_planner_db` on port `5432` with:
- User: `studyplanner`
- Password: `studyplanner123`
- Database: `study_planner`

### 2. Install Python Dependencies

```bash
# Recommended: use a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### 3. Create the `.env` File

Copy the template above and save as `.env` in the project root.

### 4. Start Ollama (for dev mode)

```bash
# Pull the model if not already downloaded
ollama pull llama3.2:latest

# Ollama runs as a background service automatically on most systems
# Verify: curl http://localhost:11434
```

### 5. Run the Streamlit App

```bash
# From project root
streamlit run frontend/app.py
```

The app opens at `http://localhost:8501`.

The database tables are auto-created on first run via `init_db()` in `backend/database.py`.

### 6. First-Time Setup

On first load (no user profile exists):
1. The app shows the **Setup Profile** form
2. Enter student name, grade, board, daily duration, weekly frequency, and subjects
3. Click **Create Profile**
4. Navigate to **Upload Newsletter** to add the first curriculum

---

## CLI

A Typer-based CLI is available via `cli.py` in the project root. It provides commands for database operations and plan generation without opening the browser.

```bash
python cli.py --help
```
