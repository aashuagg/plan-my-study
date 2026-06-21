"""Newsletter upload page"""

import streamlit as st
import pandas as pd
import os
import sys
import tempfile
from datetime import datetime

# Add parent directory to path to import backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.crud import create_newsletter, add_curriculum_items, get_user
from backend.schemas import NewsletterUpload, CurriculumItemSchema
from backend.newsletter_parser import NewsletterParser
from backend.models import Newsletter, CurriculumItem, LearningHistory
from backend.sm2 import SM2Algorithm


def show_upload_newsletter_page(db):
    """Display newsletter upload interface
    
    Args:
        db: Database session
    """
    st.title("📤 Upload Monthly Newsletter")
    
    tab1, tab2 = st.tabs(["Upload Newsletter", "Add Diary Entry"])
    
    with tab1:
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
            _process_uploaded_file(db, uploaded_file, month, year)
            
    with tab2:
        _show_diary_entry_tab(db)


def _process_uploaded_file(db, uploaded_file, month, year):
    """Process the uploaded newsletter file"""
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
            _save_newsletter_to_database(db, temp_path, raw_items, month, year)
    
    except Exception as e:
        st.error(f"Error parsing file: {str(e)}")
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _save_newsletter_to_database(db, temp_path, raw_items, month, year):
    """Save newsletter data to database"""
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


def _show_diary_entry_tab(db):
    """Render diary entry form and recent entries list"""
    if 'diary_success' in st.session_state:
        st.success(st.session_state.diary_success)
        del st.session_state.diary_success
        
    if 'diary_form_counter' not in st.session_state:
        st.session_state.diary_form_counter = 0
        
    st.markdown("### 📝 Add Diary Entry")
    st.info("Manually log a topic your child studied at school or for homework to add it to their curriculum schedule.")

    user_id = st.session_state.get('user_id', 1)
    user = get_user(db, user_id)
    
    if not user:
        st.error("Student profile not found. Please create a student profile first.")
        return

    subjects = user.subjects if user.subjects else []
    
    if not subjects:
        st.warning("No subjects configured in the student profile. Please add subjects to the profile first.")
        return

    with st.form(key=f"diary_entry_form_{st.session_state.diary_form_counter}"):
        diary_date = st.date_input("Date", value=datetime.today().date())
        diary_subject = st.selectbox("Subject", options=subjects)
        diary_topic = st.text_input("Topic", placeholder="e.g., Chapter 3: Fractions, Reading practice")
        
        submitted = st.form_submit_button("Submit Entry", type="primary")

    if submitted:
        if not diary_topic.strip():
            st.error("Topic cannot be empty. Please enter a studied topic.")
        else:
            try:
                # 1. Retrieve or create the special "Diary" newsletter for the user
                diary_newsletter = db.query(Newsletter).filter(
                    Newsletter.user_id == user_id,
                    Newsletter.month == "Diary",
                    Newsletter.year == 0
                ).first()
                
                if not diary_newsletter:
                    diary_newsletter = Newsletter(
                        user_id=user_id,
                        month="Diary",
                        year=0,
                        file_path="manual_entry"
                    )
                    db.add(diary_newsletter)
                    db.commit()
                    db.refresh(diary_newsletter)
                
                # 2. Check if this curriculum topic is already saved under this date
                existing_item = db.query(CurriculumItem).filter(
                    CurriculumItem.newsletter_id == diary_newsletter.id,
                    CurriculumItem.subject == diary_subject,
                    CurriculumItem.topic == diary_topic.strip(),
                    CurriculumItem.start_date == diary_date
                ).first()
                
                if existing_item:
                    st.warning("This topic has already been entered for this date.")
                else:
                    # Save directly to Curriculum table
                    db_item = CurriculumItem(
                        newsletter_id=diary_newsletter.id,
                        subject=diary_subject,
                        topic=diary_topic.strip(),
                        start_date=diary_date
                    )
                    db.add(db_item)
                    
                    # 3. Initialize SM-2 tracking if not already tracked
                    existing_lh = db.query(LearningHistory).filter(
                        LearningHistory.user_id == user_id,
                        LearningHistory.subject == diary_subject,
                        LearningHistory.topic == diary_topic.strip()
                    ).first()
                    
                    if not existing_lh:
                        ef, interval, reps, next_review = SM2Algorithm.initialize_topic(reference_date=diary_date)
                        lh = LearningHistory(
                            user_id=user_id,
                            subject=diary_subject,
                            topic=diary_topic.strip(),
                            easiness_factor=ef,
                            interval=interval,
                            repetitions=reps,
                            next_review=next_review
                        )
                        db.add(lh)
                    
                    db.commit()
                    st.session_state.diary_success = f"✅ Diary entry saved successfully! Added '{diary_topic}' to {diary_subject} curriculum."
                    st.session_state.diary_form_counter += 1
                    st.rerun()
                    
            except Exception as e:
                db.rollback()
                st.error(f"Error saving diary entry: {str(e)}")

    # Show last 5 diary entries added
    try:
        diary_newsletter = db.query(Newsletter).filter(
            Newsletter.user_id == user_id,
            Newsletter.month == "Diary",
            Newsletter.year == 0
        ).first()
        
        st.markdown("---")
        st.markdown("### 📋 Recent Diary Entries")
        
        if diary_newsletter:
            recent_entries = db.query(CurriculumItem).filter(
                CurriculumItem.newsletter_id == diary_newsletter.id
            ).order_by(CurriculumItem.id.desc()).limit(5).all()
            
            if recent_entries:
                data = []
                for entry in recent_entries:
                    data.append({
                        "Date": entry.start_date.strftime("%Y-%m-%d"),
                        "Subject": entry.subject,
                        "Topic": entry.topic
                    })
                st.table(pd.DataFrame(data))
            else:
                st.info("No diary entries recorded yet.")
        else:
            st.info("No diary entries recorded yet.")
    except Exception as e:
        st.error(f"Error loading recent diary entries: {str(e)}")
