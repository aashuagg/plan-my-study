"""Study Planner - Main application file"""

import streamlit as st
import sys
import os

# Add parent directory to path to import backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database import SessionLocal, init_db
from backend.crud import get_user, get_analytics

# Import page modules
from modules.setup_profile import show_setup_page
from modules.weekly_plan import show_weekly_plan_page
from modules.progress_report import show_progress_report_page
from modules.upload_newsletter import show_upload_newsletter_page

# Initialize database
init_db()

# ===================================================================
# PAGE CONFIGURATION & SESSION STATE
# ===================================================================

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

# ===================================================================
# USER PROFILE CHECK
# ===================================================================

# Get user info
user = get_user(db, st.session_state.user_id)
if not user:
    # Show profile setup page if no user exists
    show_setup_page(db)
    st.stop()

USER_DATA = {
    "id": user.id,
    "name": user.name,
    "grade": user.grade,
    "board": user.board
}

analytics = get_analytics(db, st.session_state.user_id)

# ===================================================================
# SIDEBAR NAVIGATION
# ===================================================================

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
# PAGE ROUTING
# ===================================================================

if page == "📅 This Week's Plan":
    show_weekly_plan_page(db, user)

elif page == "📊 Progress Report":
    try:
        show_progress_report_page(db, USER_DATA, analytics)
    except Exception as e:
        st.error(f"Error loading Progress Report: {e}")
        import traceback
        st.code(traceback.format_exc())

elif page == "📤 Upload Newsletter":
    try:
        show_upload_newsletter_page(db)
    except Exception as e:
        st.error(f"Error loading Upload Newsletter: {e}")
        import traceback
        st.code(traceback.format_exc())

# ===================================================================
# FOOTER
# ===================================================================

st.sidebar.divider()
st.sidebar.caption("Study Planner v1.0")
st.sidebar.caption("Powered by SM-2 Algorithm")
