"""Monthly topics overview - combined view of newsletter + manual diary entries"""

import streamlit as st
import pandas as pd
from datetime import datetime

from backend.crud import get_user, get_curriculum_by_month

MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


def show_monthly_topics_tab(db):
    """Show all curriculum topics (newsletter + manual diary entries) for a selected month,
    so it's easy to spot subjects/topics that may have been missed."""
    st.markdown("### 📋 Monthly Topics Overview")
    st.info("All topics scheduled for the selected month, from newsletter uploads and manual "
            "diary entries combined. Use this to spot subjects that may be missing.")

    user_id = st.session_state.get('user_id', 1)
    user = get_user(db, user_id)

    if not user:
        st.error("Student profile not found. Please create a student profile first.")
        return

    today = datetime.today().date()

    col1, col2 = st.columns(2)
    with col1:
        selected_month_name = st.selectbox(
            "Month", MONTH_NAMES, index=today.month - 1, key="monthly_topics_month"
        )
    with col2:
        selected_year = st.number_input(
            "Year", min_value=2020, max_value=2030, value=today.year, key="monthly_topics_year"
        )

    selected_month = MONTH_NAMES.index(selected_month_name) + 1
    topics = get_curriculum_by_month(db, user_id, selected_month, selected_year)

    if not topics:
        st.warning(f"No topics found for {selected_month_name} {selected_year} — "
                    "check if the newsletter for this month was uploaded.")
        return

    available_subjects = sorted(set(t["subject"] for t in topics) | set(user.subjects or []))
    selected_subjects = st.multiselect(
        "Filter by subject", available_subjects, default=[], key="monthly_topics_subject_filter"
    )

    filtered_topics = (
        [t for t in topics if t["subject"] in selected_subjects] if selected_subjects else topics
    )

    data = [
        {
            "Date": t["date"].strftime("%Y-%m-%d"),
            "Subject": t["subject"],
            "Topic": t["topic"],
            "Source": t["source"]
        }
        for t in filtered_topics
    ]
    st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("**Subject coverage this month:**")

    subject_counts = {}
    for t in topics:
        subject_counts[t["subject"]] = subject_counts.get(t["subject"], 0) + 1

    all_subjects = user.subjects or []
    if all_subjects:
        cols = st.columns(len(all_subjects))
        for i, subj in enumerate(all_subjects):
            with cols[i]:
                count = subject_counts.get(subj, 0)
                st.metric(subj, count, delta="missing" if count == 0 else None,
                          delta_color="inverse" if count == 0 else "normal")

    missing_subjects = set(all_subjects) - set(subject_counts.keys())
    if missing_subjects:
        st.warning(
            f"⚠️ No topics found this month for: {', '.join(sorted(missing_subjects))}. "
            "If these were covered at school, add them via the Add Diary Entry tab."
        )
    else:
        st.success("✅ All subjects have at least one topic this month.")
