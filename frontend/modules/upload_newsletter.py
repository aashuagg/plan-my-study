"""Newsletter upload page"""

import streamlit as st
import pandas as pd
import os
import sys
import tempfile
from datetime import datetime

# Add parent directory to path to import backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.crud import create_newsletter, add_curriculum_items
from backend.schemas import NewsletterUpload, CurriculumItemSchema
from backend.newsletter_parser import NewsletterParser


def show_upload_newsletter_page(db):
    """Display newsletter upload interface
    
    Args:
        db: Database session
    """
    st.write("DEBUG: Upload newsletter page called")  # Debug line
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
        _process_uploaded_file(db, uploaded_file, month, year)


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
