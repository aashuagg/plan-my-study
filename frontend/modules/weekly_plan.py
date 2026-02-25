"""Weekly study plan page - main home page of the app"""

import streamlit as st
from datetime import date, timedelta, datetime
import sys
import os

# Add parent directory to path to import backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.crud import get_latest_weekly_plan, get_learning_history, record_study_session
from backend.models import LearningHistory, StudySession
from utils.helpers import generate_weekly_plan_for_date


def show_weekly_plan_page(db, user):
    """Display weekly study plan with progress tracking
    
    Args:
        db: Database session
        user: User object
    """
    st.title("📅 Weekly Study Plan")
    
    # Get latest weekly plan from backend
    weekly_plan = get_latest_weekly_plan(db, st.session_state.user_id)
    
    if not weekly_plan:
        _show_plan_generation_form(db, user)
        st.stop()
    
    _show_weekly_plan_content(db, user, weekly_plan)


def _show_plan_generation_form(db, user):
    """Show form to generate a new weekly plan"""
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


def _show_weekly_plan_content(db, user, weekly_plan):
    """Display the weekly plan with topics and progress tracking"""
    # Parse plan data
    plan_data = weekly_plan.plan_data
    week_start = weekly_plan.week_start_date
    
    st.markdown(f"### Week of {week_start.strftime('%B %d, %Y')}")
    
    # Get topics from plan - need to match with learning_history
    all_learning_topics = get_learning_history(db, st.session_state.user_id)
    topic_lookup = {f"{t.subject}|{t.topic}": t for t in all_learning_topics}
    
    # Build topics list from weekly plan
    weekly_topics = _build_weekly_topics(plan_data, topic_lookup)
    
    # Load already completed sessions from database for this week
    _load_completed_sessions_from_db(db, weekly_topics, week_start)
    
    # Show week summary metrics
    _show_week_summary(weekly_topics)
    
    # Display topics by day
    _show_topics_by_day(weekly_topics)
    
    # Show action buttons
    _show_action_buttons(db, user, weekly_plan)


def _build_weekly_topics(plan_data, topic_lookup):
    """Build list of weekly topics from plan data"""
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
    
    return weekly_topics


def _load_completed_sessions_from_db(db, weekly_topics, week_start):
    """Load completed sessions from database for this week and mark in session state"""
    from datetime import timedelta
    
    week_end = week_start + timedelta(days=6)
    
    # Get all study sessions for this week
    sessions = db.query(StudySession).filter(
        StudySession.user_id == st.session_state.user_id,
        StudySession.session_date >= week_start,
        StudySession.session_date <= week_end
    ).all()
    
    # Create lookup by learning_history_id and date
    completed_lookup = {}
    for session in sessions:
        key = f"{session.learning_history_id}_{session.session_date}"
        completed_lookup[key] = {
            'quality': session.quality_rating,
            'notes': session.notes
        }
    
    # Mark topics as completed in session state if they have a study session
    for topic in weekly_topics:
        topic_id = topic['id']
        if topic['learning_history_id']:
            key = f"{topic['learning_history_id']}_{topic['date']}"
            
            # Initialize in session state if not exists
            if topic_id not in st.session_state.completed_topics:
                st.session_state.completed_topics[topic_id] = {
                    'completed': False,
                    'quality': None,
                    'notes': '',
                    'learning_history_id': topic['learning_history_id'],
                    'topic': topic['topic'],
                    'date': topic['date']
                }
            
            # Mark as completed if session exists in database
            if key in completed_lookup:
                st.session_state.completed_topics[topic_id].update({
                    'completed': True,
                    'quality': completed_lookup[key]['quality'],
                    'notes': completed_lookup[key]['notes'] or ''
                })


def _show_week_summary(weekly_topics):
    """Display week summary metrics"""
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


def _show_topics_by_day(weekly_topics):
    """Display topics grouped by day"""
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
                _show_topic_row(topic, day_date)


def _show_topic_row(topic, day_date):
    """Display a single topic row with checkbox, rating, and notes"""
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
            # Get current quality from session state
            current_quality = st.session_state.completed_topics[topic_id]['quality']
            options = [None, 0, 1, 2, 3, 4, 5]
            
            # Set index based on current quality
            if current_quality is not None and current_quality in options:
                selected_index = options.index(current_quality)
            else:
                selected_index = 0
            
            quality = st.selectbox(
                "Rating",
                options=options,
                index=selected_index,
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


def _show_action_buttons(db, user, weekly_plan):
    """Display save progress and generate next week buttons"""
    st.markdown("---")
    col_a, col_b = st.columns(2)
    
    with col_a:
        if st.button("💾 Save Progress", type="primary", use_container_width=True):
            _save_progress(db)
    
    with col_b:
        if st.button("🔄 Generate Next Week's Plan", use_container_width=True):
            _generate_next_week(db, user, weekly_plan)


def _save_progress(db):
    """Save completed topics to database"""
    saved_count = 0
    errors = []
    skipped_topics = []
    
    # Get completed items
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
            # Check if session already exists for this date
            session_date = datetime.strptime(data['date'], "%Y-%m-%d").date()
            existing_session = db.query(StudySession).filter(
                StudySession.user_id == st.session_state.user_id,
                StudySession.learning_history_id == data['learning_history_id'],
                StudySession.session_date == session_date
            ).first()
            
            if existing_session:
                # Session already saved, skip
                saved_count += 1
                continue
            
            # Determine session type
            session_type = "study"  # Default
            lh = db.query(LearningHistory).filter(
                LearningHistory.id == data['learning_history_id']
            ).first()
            if lh and lh.repetitions > 0:
                session_type = "review"
            
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
        st.rerun()
    else:
        st.warning("No completed topics to save.")
    
    if errors:
        st.error("Some sessions failed to save:")
        for err in errors:
            st.caption(f"- {err}")
    
    if skipped_topics:
        st.info(f"Skipped {len(skipped_topics)} topic(s) not in learning history. They may be from future curriculum.")


def _generate_next_week(db, user, weekly_plan):
    """Generate plan for next week"""
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
