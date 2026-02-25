# Study Planner

AI-powered study planning application for kids using spaced repetition (SM-2 algorithm) and Ollama for intelligent weekly plan generation.

## 📋 Features

- ✅ **Web Interface** - User-friendly Streamlit UI for daily use
- ✅ **Student profile management** - Multi-user support with customizable settings
- ✅ **Newsletter parsing** - Auto-parse curriculum from CSV/Excel files
- ✅ **SM-2 spaced repetition** - Automatic review scheduling based on learning performance
- ✅ **AI-powered weekly plans** - Intelligent plan generation using Ollama (llama3.2)
- ✅ **Progress tracking** - Record study sessions with quality ratings
- ✅ **Subject balancing** - Ensures no subject is neglected for >7 days
- ✅ **Custom focus requests** - Adapt plans based on upcoming events or focus areas
- ✅ **CLI tools** - Command-line interface for advanced operations

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- Ollama (for AI plan generation)

### Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd Plan-my-study
```

2. **Start PostgreSQL database:**
```bash
docker-compose up -d
```

3. **Create environment file:**
```bash
cp .env.example .env
# Edit .env if needed (default settings work for local development)
```

Example `.env`:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/study_planner
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest
```

4. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

5. **Install and start Ollama:**
```bash
# Install Ollama from https://ollama.ai
ollama pull llama3.2:latest
ollama serve
```

6. **Initialize the database:**
```bash
python cli.py init
```

## 💻 Usage

### Option 1: Web Interface (Recommended for Daily Use)

1. **Start the web app:**
```bash
cd frontend
python -m streamlit run app.py
```

2. **Access in browser:**
```
http://localhost:8501
```

3. **First-time setup:**
   - On first visit, you'll see a profile setup form
   - Fill in student details (name, grade, board, subjects, study schedule)
   - Click "Create Profile"

4. **Upload newsletters:**
   - Navigate to "📤 Upload Newsletter" page
   - Select month and year
   - Upload CSV/Excel file with curriculum
   - Click "Process Newsletter"

5. **Generate weekly plan:**
   - Go to "📅 This Week's Plan"
   - If no plan exists, fill in the generation form
   - Select week start date (Monday)
   - Optionally add focus request or upcoming events
   - Click "Generate Plan"

6. **Track progress:**
   - Check ✓ box next to completed topics
   - Select quality rating (0-5)
   - Add optional notes
   - Click "💾 Save Progress"

7. **View analytics:**
   - Navigate to "📊 Progress Report"
   - See subject-wise performance
   - Get personalized recommendations

### Option 2: Command Line Interface

#### Create Student Profile
```bash
python cli.py create-profile
# Follow prompts to enter: name, grade, board, duration, frequency, subjects
```

#### View Profile
#### View Profile
```bash
python cli.py view-profile <user_id>
```

#### Upload Newsletter
```bash
python cli.py upload-newsletter --user-id 1 --file-path "files/march_2026.csv" --month "March" --year 2026
```

#### Generate Weekly Plan
```bash
python cli.py generate-plan --user-id 1

# With options:
python cli.py generate-plan --user-id 1 \
  --start-date 2026-03-03 \
  --focus "extra Math this week" \
  --events "Olympiad on March 20"
```

#### View Plan
```bash
python cli.py view-plan <user_id>
```

#### Record Study Session
```bash
python cli.py record-session --user-id 1
# Follow prompts to select topic and enter quality rating
```

#### View Progress
```bash
python cli.py view-progress --user-id 1
```

#### Update Profile
```bash
python cli.py update-profile --user-id 1 --duration 45 --frequency 5
```

#### Reset Database (Caution!)
```bash
python cli.py reset-db
# This deletes ALL data and reinitializes the database
```

## 📁 Project Structure

```
Plan-my-study/
├── backend/
│   ├── models/              # Database models (User, Newsletter, Curriculum, etc.)
│   ├── crud/                # Database operations (CRUD functions)
│   ├── config.py            # Configuration and environment variables
│   ├── database.py          # Database connection and initialization
│   ├── schemas.py           # Pydantic schemas for validation
│   ├── sm2.py               # SM-2 spaced repetition algorithm
│   ├── newsletter_parser.py # Newsletter file parsing
│   └── ollama_scheduler.py  # AI-powered plan generation
├── frontend/
│   ├── app.py               # Main Streamlit application
│   ├── pages/               # Page modules
│   │   ├── setup_profile.py
│   │   ├── weekly_plan.py
│   │   ├── progress_report.py
│   │   └── upload_newsletter.py
│   └── utils/
│       └── helpers.py       # Helper functions for plan generation
├── files/                   # Sample newsletter files
├── cli.py                   # Command-line interface
├── docker-compose.yml       # PostgreSQL database setup
├── requirements.txt         # Python dependencies
└── README.md

```

## 📊 Newsletter Format

CSV/Excel file should have these columns:
- **`subject`** - Subject name (LITERACY, NUMERACY, HINDI, etc.)
- **`topic`** - Specific topic (e.g., "Phonics: ab family words")
- **`start_date`** or **`date`** - Start date in format: YYYY-MM-DD or DD/MM/YYYY
- **`end_date`** (optional) - End date

**Example CSV:**
```csv
subject,topic,start_date
LITERACY,Sight words: do go so to,2026-03-01
NUMERACY,Shapes: Circle & Square,2026-03-01
HINDI,वर्णमाला revision (अ to औ),2026-03-08
KANNADA,Swaragalu ಅ to ಐ,2026-03-08
GENERAL AWARENESS,My Family members,2026-03-15
```

## 🎯 Complete Workflow Example

### Using Web Interface

1. **Start the application:**
```bash
# Terminal 1: Start database
docker-compose up -d

# Terminal 2: Start Ollama
ollama serve

# Terminal 3: Start web app
cd frontend
python -m streamlit run app.py
```

2. **First-time setup (http://localhost:8501):**
   - Fill in student profile form
   - Name: Shubhi
   - Grade: Pre-Primary
   - Board: CBSE
   - Daily Duration: 30 minutes
   - Study Days: 6 days/week
   - Subjects: LITERACY, NUMERACY, HINDI, KANNADA, GENERAL AWARENESS

3. **Upload curriculum:**
   - Go to "📤 Upload Newsletter"
   - Upload `files/march_2026.csv`
   - Click "Process Newsletter"
   - Repeat for all months

4. **Generate weekly plan:**
   - Go to "📅 This Week's Plan"
   - Select week start date
   - Click "Generate Plan"
   - Wait for AI to create balanced weekly schedule

5. **Track daily progress:**
   - Each day, check ✓ for completed topics
   - Rate learning quality (0-5)
   - Add notes if needed
   - Click "💾 Save Progress"

6. **Generate next week's plan:**
   - At end of week, click "🔄 Generate Next Week's Plan"
   - System automatically accounts for completed sessions

### Using CLI

```bash
# 1. Initialize
python cli.py init

# 2. Create profile
python cli.py create-profile

# 3. Upload newsletters (batch)
for month in june july august september october november december; do
  python cli.py upload-newsletter \
    --user-id 1 \
    --file-path "files/${month}_2025.csv" \
    --month "$(echo $month | sed 's/.*/\u&/')" \
    --year 2025
done

# 4. Generate this week's plan
python cli.py generate-plan --user-id 1

# 5. View the plan
python cli.py view-plan 1

# 6. Record study session
python cli.py record-session --user-id 1

# 7. View progress and due topics
python cli.py view-progress --user-id 1
```

## 🧠 How It Works

### SM-2 Spaced Repetition Algorithm

The app uses the SuperMemo-2 (SM-2) algorithm to determine optimal review intervals:

1. **Initial Learning**: Topic is marked for review after 1 day
2. **First Review**: If quality ≥ 3, next review in 6 days
3. **Subsequent Reviews**: Interval multiplies by "easiness factor" (1.3-2.5)
4. **Quality Impact**: Low ratings (0-2) reset the topic; high ratings (4-5) increase intervals

### AI Plan Generation

Ollama (llama3.2) generates weekly plans that:
- Balance **60% new topics** with **40% review topics**
- Ensure **no subject gap >7 days**
- Respect **daily time limits** and **weekly frequency**
- Prioritize **overdue reviews** (SM-2 scheduled)
- Adapt to **focus requests** and **upcoming events**
- Distribute subjects evenly across the week

## 🛠️ Development

### Database Schema

- **User**: Student profiles
- **Newsletter**: Monthly curriculum uploads
- **Curriculum**: Individual curriculum items from newsletters
- **LearningHistory**: SM-2 tracking for each topic
- **StudySession**: Record of completed study/review sessions
- **WeeklyPlan**: AI-generated weekly study plans

### Adding New Features

**Example: Add a new page to web UI**

1. Create page module in `frontend/pages/my_new_page.py`:
```python
def show_my_new_page(db, user):
    st.title("My New Page")
    # Your page logic here
```

2. Import and route in `frontend/app.py`:
```python
from pages.my_new_page import show_my_new_page

# In sidebar
page = st.sidebar.radio(
    "Navigate",
    ["📅 This Week's Plan", "📊 Progress Report", "📤 Upload Newsletter", "✨ My New Page"]
)

# In routing section
elif page == "✨ My New Page":
    show_my_new_page(db, user)
```

## 🐛 Troubleshooting

### Database connection issues
```bash
# Check if PostgreSQL is running
docker-compose ps

# Restart database
docker-compose restart

# View logs
docker-compose logs -f
```

### Ollama not generating plans
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama
ollama serve

# Re-pull model
ollama pull llama3.2:latest
```

### Import errors in Streamlit
```bash
# Make sure you're running from frontend directory
cd frontend
python -m streamlit run app.py
```

### Reset everything and start fresh
```bash
# Stop database
docker-compose down -v

# Restart
docker-compose up -d

# Reinitialize
python cli.py init
```

## 📝 Configuration

### AI Provider Selection

The app supports two AI providers - easily switch between them in `.env`:

**For Development (Local):**
```env
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest
```

**For Production (Cloud):**
```env
AI_PROVIDER=claude
CLAUDE_API_KEY=your_api_key_here
CLAUDE_MODEL=claude-3-5-sonnet-20241022
```

**Why This Matters:**
- **Ollama** (llama3.2): Free, runs locally, no API costs, but smaller model may generate slightly mismatched topic names
- **Claude API**: Production-grade accuracy, perfect topic matching, but requires API key and incurs costs (~$3-5/month for typical use)

**Switching is Easy:** Just change `AI_PROVIDER` in `.env` - no code changes needed!

### Other Settings

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/study_planner
```

## 🤝 Contributing

Contributions are welcome! Areas for improvement:
- Real analytics queries (replace MOCK_ANALYTICS)
- Export plans to PDF
- Mobile-responsive UI improvements
- Additional AI models support
- Performance optimizations

## 📄 License

MIT License - feel free to use for personal or educational purposes.

---

**Built with:** Python, Streamlit, PostgreSQL, Ollama/Claude, LangChain, SQLAlchemy, Pydantic
