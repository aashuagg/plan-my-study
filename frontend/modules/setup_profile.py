"""User profile setup page"""

import streamlit as st
import sys
import os

# Add parent directory to path to import backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.crud import create_user
from backend.schemas import UserCreate


def show_setup_page(db):
    """Display user profile setup form
    
    Args:
        db: Database session
    """
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
