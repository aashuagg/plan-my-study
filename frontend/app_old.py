import streamlit as st
from datetime import date, timedelta, datetime
import pandas as pd
import sys
import os
import tempfile

# Add parent directory to path to import backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database import SessionLocal, init_db
from backend.crud import (
    get_user, create_user, get_latest_weekly_plan, save_weekly_plan,
    record_study_session, get_learning_history,
    create_newsletter, add_curriculum_items,
    get_current_curriculum, get_due_topics
)
from backend.models import LearningHistory
from backend.schemas import NewsletterUpload, CurriculumItemSchema, PlanRequest, UserCreate
from backend.newsletter_parser import NewsletterParser
from backend.scheduler import get_scheduler

# Initialize database
init_db()

# ===================================================================
# HELPER FUNCTIONS
# ===================================================================

def prepare_user_profile(user):
    """Prepare user profile dictionary for plan generation"""
    return {
        "name": user.name,
        "grade": user.grade,
        "board": user.board,
        "daily_duration_minutes": user.daily_duration_minutes,
        "weekly_frequency": user.weekly_frequency,
        "subjects": user.subjects
    }

def prepare_curriculum_data(curriculum_items):
    """Convert curriculum items to scheduler format"""
    return [
        {"subject": item.subject, "topic": item.topic, "start_date": item.start_date.strftime("%Y-%m-%d")}
        for item in curriculum_items
    ]

def prepare_due_data(due_topics):
    """Convert due topics to scheduler format"""
    return [
        {"subject": item.subject, "topic": item.topic, "next_review": item.next_review, "easiness_factor": item.easiness_factor}
        for item in due_topics
    ]

def prepare_history_data(learning_history):
    """Convert learning history to scheduler format"""
    return [
        {"subject": item.subject, "topic": item.topic, "last_reviewed": item.last_reviewed, "easiness_factor": item.easiness_factor}
        for item in learning_history
    ]

def fix_ollama_response(plan):
    """Fix Ollama response structure - sometimes rationale is in the list"""
    weekly_plan_items = plan.get("weekly_plan", [])
    rationale = plan.get("rationale", "")
    
    if weekly_plan_items and isinstance(weekly_plan_items[-1], dict) and "rationale" in weekly_plan_items[-1] and "subjects" not in weekly_plan_items[-1]:
        rationale = weekly_plan_items[-1]["rationale"]
        weekly_plan_items = weekly_plan_items[:-1]
    
    return {"weekly_plan": weekly_plan_items, "rationale": rationale}

def generate_weekly_plan_for_date(db, user, user_id, week_start, focus_request=None, events=None):
    """Generate a weekly plan for a specific date
    
    Args:
        db: Database session
        user: User object
        user_id: User ID
        week_start: Week start date
        focus_request: Optional focus request string
        events: Optional events string
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Gather data
        current_curriculum = get_current_curriculum(db, user_id, week_start)
        due_topics = get_due_topics(db, user_id)
        all_learning_topics = get_learning_history(db, user_id)
        
        # Prepare data for scheduler
        user_profile = prepare_user_profile(user)
        curriculum_data = prepare_curriculum_data(current_curriculum)
        due_data = prepare_due_data(due_topics)
        history_data = prepare_history_data(all_learning_topics)
        
        # Generate plan with Ollama
        scheduler = get_scheduler()
        plan = scheduler.generate_weekly_plan(
            user_profile, curriculum_data, due_data, history_data, week_start, 
            focus_request, events
        )
        
        # Fix Ollama response structure
        plan_fixed = fix_ollama_response(plan)
        
        # Save plan
        plan_request = PlanRequest(
            user_id=user_id,
            week_start_date=week_start,
            focus_request=focus_request,
            events=events
        )
        save_weekly_plan(db, plan_request, plan_fixed)
        
        return True, f"✓ Plan for week of {week_start.strftime('%B %d, %Y')} generated successfully!"
    except Exception as e:
        return False, f"Error generating plan: {str(e)}"

# ===================================================================
# PAGE CONFIGURATION & SESSION STATE
# ===================================================================

# Page config
st.set_page_config(
    page_title="Study Planner",
    page_icon="📚",
    layout="wide"
)

# Initialize session state for tracking completions
if 'completed_topics' not in st.session_state:
    st.session_state.completed_topics = {}

if 'user_id' not in st.session_state:
    st.session_state.user_id = 1  # Default user, can be made configurable

# Get database session
@st.cache_resource
def get_db():
    return SessionLocal()

db = get_db()

# Get user info
user = get_user(db, st.session_state.user_id)
if not user:
    # Show user profile setup page
    st.title("📚 Welcome to Study Planner!")
    st.markdown("### Let's set up your child's profile")
    
    with st.form("user_setup_form"):
        st.subheader("Student Information")
        
        name = st.text_input("Student Name *", placeholder="e.g., Shubhi")
        
        col1, col2 = st.columns(2)
        with col1:
            grade = st.selectbox(
                "Grade/Class *",
                options=["Nursery", "LKG", "UKG", "Pre-Primary", "Class 1", "Class 2", "Class 3", "Class 4", "Class 5"]
            )
        with col2:
            board = st.selectbox(
                "Board *",
                options=["CBSE", "ICSE", "State Board", "IB", "IGCSE", "Other"]
            )
        
        st.subheader("Study Schedule")
        
        col3, col4 = st.columns(2)
        with col3:
            daily_duration = st.number_input(
                "Daily Study Duration (minutes) *",
                min_value=15,
                max_value=180,
                value=30,
                step=15,
                help="How many minutes per day for structured study?"
            )
        with col4:
            weekly_frequency = st.number_input(
                "Study Days Per Week *",
                min_value=3,
                max_value=7,
                value=6,
                help="How many days per week to study?"
            )
        
        st.subheader("Subjects")
        st.caption("Select all subjects your child is learning")
        
        subjects = st.multiselect(
            "Subjects *",
            options=[
                "LITERACY", "NUMERACY", "HINDI", "KANNADA", "ENGLISH",
                "MATHEMATICS", "SCIENCE", "SOCIAL STUDIES", "GENERAL AWARENESS",
                "COMPUTER", "ART & CRAFT", "MUSIC", "PHYSICAL EDUCATION"
            ],
            default=["LITERACY", "NUMERACY", "HINDI", "KANNADA", "GENERAL AWARENESS"]
        )
        
        study_time = st.selectbox(
            "Preferred Study Time (optional)",
            options=["Morning", "Afternoon", "Evening", "Not Specified"],
            index=3
        )
        
        submitted = st.form_submit_button("Create Profile", type="primary", use_container_width=True)
    
    if submitted:
        # Validation
        if not name:
            st.error("Please enter student name")
        elif not subjects:
            st.error("Please select at least one subject")
        else:
            try:
                # Create user profile
                user_data = UserCreate(
                    name=name,
                    grade=grade,
                    board=board,
                    daily_duration_minutes=daily_duration,
                    weekly_frequency=weekly_frequency,
                    subjects=subjects,
                    study_time_preference=study_time if study_time != "Not Specified" else None
                )
                
                new_user = create_user(db, user_data)
                st.session_state.user_id = new_user.id
                
                st.success(f"✅ Profile created for {name}!")
                st.balloons()
                st.info("Redirecting to home page...")
                st.rerun()
            except Exception as e:
                st.error(f"Error creating profile: {str(e)}")
    
    st.stop()

USER_DATA = {
    "id": user.id,
    "name": user.name,
    "grade": user.grade,
    "board": user.board
}

# Analytics mock data
MOCK_ANALYTICS = {
    "subject_performance": [
        {"subject": "LITERACY", "avg_quality": 4.2, "total_sessions": 25, "status": "Good ✅"},
        {"subject": "NUMERACY", "avg_quality": 3.8, "total_sessions": 22, "status": "Good ✅"},
        {"subject": "HINDI", "avg_quality": 2.9, "total_sessions": 18, "status": "Needs Revision ⚠️"},
        {"subject": "KANNADA", "avg_quality": 3.5, "total_sessions": 15, "status": "OK 👍"},
        {"subject": "GENERAL AWARENESS", "avg_quality": 4.5, "total_sessions": 20, "status": "Excellent 🌟"},
    ],
    "overdue_count": 428,
    "study_streak": 5,
    "this_week_completion": 40  # percentage
}

# Sidebar navigation
st.sidebar.title("📚 Study Planner")
st.sidebar.markdown(f"**Student:** {USER_DATA['name']}")
st.sidebar.markdown(f"**Grade:** {USER_DATA['grade']}")
st.sidebar.markdown(f"**Board:** {USER_DATA['board']}")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    ["📅 This Week's Plan", "📊 Progress Report", "📤 Upload Newsletter"]
)

# ===================================================================
# PAGE 1: THIS WEEK'S PLAN (HOME PAGE)
# ===================================================================
if page == "📅 This Week's Plan":
    st.title(f"📅 Weekly Study Plan")
    
    # Get latest weekly plan from backend
    weekly_plan = get_latest_weekly_plan(db, st.session_state.user_id)
    
    if not weekly_plan:
        st.warning("No weekly plan found. Generate one using the form below.")
        
        # Plan generation form
        with st.form("generate_plan_form"):
            st.subheader("Generate New Weekly Plan")
            
            # Calculate default week start (upcoming Monday)
            today = date.today()
            if today.weekday() == 0:  # If today is Monday
                default_start = today
            else:
                days_ahead = (7 - today.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                default_start = today + timedelta(days=days_ahead)
            
            # Date picker for week start
            selected_date = st.date_input(
                "Week Start Date (Monday)",
                value=default_start,
                min_value=today,
                help="Select a Monday to start the week. Only current or future weeks allowed."
            )
            
            # Validate it's a Monday
            if selected_date.weekday() != 0:
                st.warning("⚠️ Please select a Monday as the week start date.")
            
            # Show week range
            if selected_date.weekday() == 0:
                week_end = selected_date + timedelta(days=4)  # Friday
                st.info(f"📅 Planning week: {selected_date.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}")
            
            # Optional fields
            focus_request = st.text_input("Focus Request (optional)", placeholder="e.g., Extra Math practice")
            events = st.text_input("Upcoming Events (optional)", placeholder="e.g., Science test on March 5")
            
            submitted = st.form_submit_button("Generate Plan", type="primary")
            
        if submitted and selected_date.weekday() == 0:
            with st.spinner("Generating plan with AI... This may take a moment..."):
                success, message = generate_weekly_plan_for_date(
                    db, user, st.session_state.user_id, selected_date,
                    focus_request if focus_request else None,
                    events if events else None
                )
                
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
        st.stop()
    
    # Parse plan data
    plan_data = weekly_plan.plan_data
    week_start = weekly_plan.week_start_date
    
    st.markdown(f"### Week of {week_start.strftime('%B %d, %Y')}")
    
    # Get topics from plan - need to match with learning_history
    all_learning_topics = get_learning_history(db, st.session_state.user_id)
    topic_lookup = {f"{t.subject}|{t.topic}": t for t in all_learning_topics}
    
    # Build topics list from weekly plan
    weekly_topics = []
    topic_counter = 1
    
    for day in plan_data.get("weekly_plan", []):
        day_date = day["date"]
        subjects = day.get("subjects", [])
        topics = day.get("topics", [])
        duration = day.get("duration_minutes", 30)
        
        # Try to match topics with learning history
        for i, topic_name in enumerate(topics):
            subject = subjects[i] if i < len(subjects) else subjects[0] if subjects else "UNKNOWN"
            
            # Try to find matching learning history entry
            lookup_key = f"{subject}|{topic_name}"
            learning_entry = topic_lookup.get(lookup_key)
            
            # Determine if new or review
            topic_type = "new"
            if learning_entry and learning_entry.repetitions > 0:
                topic_type = "review"
            
            weekly_topics.append({
                "id": topic_counter,
                "date": day_date,
                "subject": subject,
                "topic": topic_name,
                "duration": duration // len(topics) if topics else duration,
                "type": topic_type,
                "learning_history_id": learning_entry.id if learning_entry else None
            })
            topic_counter += 1
    
    # Week summary
    total_topics = len(weekly_topics)
    completed = len([t for t in st.session_state.completed_topics.values() if t.get('completed')])
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Topics", total_topics)
    with col2:
        st.metric("Completed", completed)
    with col3:
        completion_pct = int((completed / total_topics) * 100) if total_topics > 0 else 0
        st.metric("Progress", f"{completion_pct}%")
    
    st.progress(completion_pct / 100)
    st.divider()
    
    # Group topics by date
    dates = sorted(set(topic['date'] for topic in weekly_topics))
    
    for day_date in dates:
        # Get day name
        day_obj = datetime.strptime(day_date, "%Y-%m-%d")
        day_name = day_obj.strftime("%A, %B %d")
        
        # Get topics for this day
        day_topics = [t for t in weekly_topics if t['date'] == day_date]
        
        # Day header
        is_today = day_date == date.today().strftime("%Y-%m-%d")
        header_text = f"{'🔔 ' if is_today else ''}{day_name}"
        
        with st.expander(header_text, expanded=is_today):
            for topic in day_topics:
                topic_id = topic['id']
                
                # Initialize state if not exists
                if topic_id not in st.session_state.completed_topics:
                    st.session_state.completed_topics[topic_id] = {
                        'completed': False,
                        'quality': None,
                        'notes': '',
                        'learning_history_id': topic['learning_history_id'],
                        'date': day_date,
                        'subject': topic['subject'],
                        'topic': topic['topic']
                    }
                
                # Topic row
                col_check, col_subject, col_topic, col_rating, col_notes = st.columns([0.5, 1.5, 3, 1.5, 2])
                
                with col_check:
                    completed = st.checkbox(
                        "✓",
                        value=st.session_state.completed_topics[topic_id]['completed'],
                        key=f"check_{topic_id}",
                        label_visibility="collapsed"
                    )
                    st.session_state.completed_topics[topic_id]['completed'] = completed
                
                with col_subject:
                    badge_color = "🟢" if topic['type'] == "new" else "🔵"
                    st.markdown(f"{badge_color} **{topic['subject']}**")
                    st.caption(f"{topic['duration']} min")
                
                with col_topic:
                    st.markdown(f"{topic['topic']}")
                    st.caption(f"{'📖 New Topic' if topic['type'] == 'new' else '🔄 Review'}")
                
                with col_rating:
                    if completed:
                        quality = st.selectbox(
                            "Rating",
                            options=[None, 0, 1, 2, 3, 4, 5],
                            format_func=lambda x: "Select..." if x is None else f"{x} - {['😰', '😟', '😕', '😐', '🙂', '😄'][x]}",
                            key=f"quality_{topic_id}",
                            label_visibility="collapsed"
                        )
                        st.session_state.completed_topics[topic_id]['quality'] = quality
                    else:
                        st.caption("Complete first")
                
                with col_notes:
                    if completed:
                        notes = st.text_input(
                            "Notes",
                            value=st.session_state.completed_topics[topic_id]['notes'],
                            placeholder="Optional notes...",
                            key=f"notes_{topic_id}",
                            label_visibility="collapsed"
                        )
                        st.session_state.completed_topics[topic_id]['notes'] = notes
                
                st.divider()
    
    # Quick actions
    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("💾 Save Progress", type="primary", use_container_width=True):
            # Save all completed topics to database
            saved_count = 0
            errors = []
            skipped_topics = []
            
            # Debug: Show what we're processing
            completed_items = [(k, v) for k, v in st.session_state.completed_topics.items() if v['completed']]
            
            if not completed_items:
                st.warning("No topics marked as completed. Check the ✓ box next to topics you've finished.")
                st.stop()
            
            for topic_id, data in completed_items:
                if not data['learning_history_id']:
                    skipped_topics.append(data['topic'])
                    continue
                
                # Validate quality rating is provided
                if data['quality'] is None:
                    errors.append(f"{data['topic']}: Please select a quality rating (0-5)")
                    continue
                    
                    try:
                        # Determine session type
                        session_type = "study"  # Default
                        lh = db.query(LearningHistory).filter(
                            LearningHistory.id == data['learning_history_id']
                        ).first()
                        if lh and lh.repetitions > 0:
                            session_type = "review"
                        
                        # Parse date
                        session_date = datetime.strptime(data['date'], "%Y-%m-%d").date()
                        
                        # Record session
                        record_study_session(
                            db,
                            user_id=st.session_state.user_id,
                            learning_history_id=data['learning_history_id'],
                            session_date=session_date,
                            session_type=session_type,
                            quality_rating=data['quality'],
                            notes=data['notes'] if data['notes'] else None
                        )
                        saved_count += 1
                    except Exception as e:
                        errors.append(f"{data['topic']}: {str(e)}")
            
            if saved_count > 0:
                st.success(f"✅ Saved {saved_count} completed session(s)!")
                # Clear completed items
                st.session_state.completed_topics = {
                    k: v for k, v in st.session_state.completed_topics.items() 
                    if not v['completed']
                }
                st.rerun()
            else:
                st.warning("No completed topics to save.")
            
            if errors:
                st.error("Some sessions failed to save:")
                for err in errors:
                    st.caption(f"- {err}")
            
            if skipped_topics:
                st.info(f"Skipped {len(skipped_topics)} topic(s) not in learning history. They may be from future curriculum.")
    
    with col_b:
        if st.button("🔄 Generate Next Week's Plan", use_container_width=True):
            # Calculate next week's Monday
            current_week_start = weekly_plan.week_start_date
            next_week_start = current_week_start + timedelta(days=7)
            
            with st.spinner("Generating next week's plan with AI..."):
                success, message = generate_weekly_plan_for_date(
                    db, user, st.session_state.user_id, next_week_start
                )
                
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

# ===================================================================
# PAGE 2: PROGRESS REPORT (ANALYTICS DASHBOARD)
# ===================================================================
elif page == "📊 Progress Report":
    st.title("📊 Learning Progress Report")
    st.markdown(f"### Insights for {USER_DATA['name']}")
    
    # Key metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Study Streak", f"{MOCK_ANALYTICS['study_streak']} days", delta="🔥")
    with col2:
        st.metric("This Week", f"{MOCK_ANALYTICS['this_week_completion']}% complete")
    with col3:
        st.metric("Topics Overdue", MOCK_ANALYTICS['overdue_count'], delta="Need attention", delta_color="inverse")
    
    st.divider()
    
    # Subject-wise performance
    st.subheader("📚 Subject-wise Performance")
    st.caption("Based on recent review quality ratings")
    
    df_subjects = pd.DataFrame(MOCK_ANALYTICS['subject_performance'])
    
    for _, row in df_subjects.iterrows():
        col_name, col_bar, col_stats, col_status = st.columns([2, 3, 2, 1])
        
        with col_name:
            st.markdown(f"**{row['subject']}**")
        
        with col_bar:
            progress_val = row['avg_quality'] / 5.0
            color = "🟢" if progress_val >= 0.8 else "🟡" if progress_val >= 0.6 else "🔴"
            st.progress(progress_val, text=f"{color} {row['avg_quality']:.1f}/5.0")
        
        with col_stats:
            st.caption(f"{row['total_sessions']} sessions")
        
        with col_status:
            st.markdown(row['status'])
        
        st.divider()
    
    # Recommendations
    st.subheader("💡 Recommendations")
    
    # Find weak subject
    weak_subjects = [s for s in MOCK_ANALYTICS['subject_performance'] if s['avg_quality'] < 3.5]
    strong_subjects = [s for s in MOCK_ANALYTICS['subject_performance'] if s['avg_quality'] >= 4.0]
    
    if weak_subjects:
        st.warning(f"**Focus needed:** {', '.join([s['subject'] for s in weak_subjects])}")
        st.markdown("- Consider extra practice sessions")
        st.markdown("- Break topics into smaller parts")
        st.markdown("- Use different teaching methods")
    
    if strong_subjects:
        st.success(f"**Doing great in:** {', '.join([s['subject'] for s in strong_subjects])}")
        st.markdown("- Maintain current pace")
        st.markdown("- Can increase difficulty slightly")
    
    # Overdue topics section
    st.divider()
    st.subheader("⚠️ Topics Needing Review")
    st.markdown(f"**{MOCK_ANALYTICS['overdue_count']} topics** are overdue for review")
    st.caption("These topics were learned earlier but need revision according to spaced repetition schedule")
    
    if st.button("📋 View All Overdue Topics"):
        st.info("Detailed overdue list coming soon...")

# ===================================================================
# PAGE 3: UPLOAD NEWSLETTER
# ===================================================================
elif page == "📤 Upload Newsletter":
    st.title("📤 Upload Monthly Newsletter")
    
    st.markdown("### Upload curriculum CSV/Excel file")
    
    col1, col2 = st.columns(2)
    
    with col1:
        month = st.selectbox("Month", ["January", "February", "March", "April", "May", "June", 
                                       "July", "August", "September", "October", "November", "December"])
        year = st.number_input("Year", min_value=2020, max_value=2030, value=2026)
    
    with col2:
        st.info("**Expected Format:**\n\nCSV with columns:\n- subject\n- topic\n- start_date")
    
    # File uploader
    uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        st.success(f"File uploaded: {uploaded_file.name}")
        
        # Save file temporarily
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, uploaded_file.name)
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # Parse newsletter
        try:
            raw_items = NewsletterParser.auto_parse(temp_path)
            
            # Show preview
            df = pd.DataFrame(raw_items)
            
            st.markdown("### Preview")
            st.dataframe(df.head(10), use_container_width=True)
            
            st.markdown(f"**Total items:** {len(df)}")
            
            if st.button("Process Newsletter", type="primary", use_container_width=True):
                with st.spinner("Processing newsletter..."):
                    try:
                        # Create newsletter record
                        newsletter_data = NewsletterUpload(
                            user_id=st.session_state.user_id,
                            month=month,
                            year=year,
                            file_path=temp_path
                        )
                        newsletter = create_newsletter(db, newsletter_data)
                        
                        # Add curriculum items - convert dates
                        curriculum_items = []
                        for item in raw_items:
                            # Parse date string to date object
                            if isinstance(item.get("start_date"), str):
                                date_str = item["start_date"]
                                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y"]:
                                    try:
                                        item["start_date"] = datetime.strptime(date_str, fmt).date()
                                        break
                                    except ValueError:
                                        continue
                            
                            if item.get("end_date") and isinstance(item["end_date"], str):
                                date_str = item["end_date"]
                                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y"]:
                                    try:
                                        item["end_date"] = datetime.strptime(date_str, fmt).date()
                                        break
                                    except ValueError:
                                        continue
                            
                            # Skip if no valid start date
                            if not item.get("start_date") or isinstance(item["start_date"], str):
                                continue
                            
                            curriculum_items.append(CurriculumItemSchema(**item))
                        
                        add_curriculum_items(db, newsletter.id, curriculum_items)
                        
                        st.success(f"✅ Newsletter processed successfully!")
                        st.success(f"Added {len(curriculum_items)} topics to curriculum")
                        st.success(f"Initialized SM-2 tracking for new topics")
                        st.balloons()
                        
                        # Clean up temp file
                        os.remove(temp_path)
                        
                    except Exception as e:
                        st.error(f"Error processing newsletter: {str(e)}")
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
        
        except Exception as e:
            st.error(f"Error parsing file: {str(e)}")
            if os.path.exists(temp_path):
                os.remove(temp_path)

# Footer
st.sidebar.divider()
st.sidebar.caption("Study Planner v1.0")
st.sidebar.caption("Powered by SM-2 Algorithm")