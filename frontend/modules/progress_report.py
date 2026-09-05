"""Progress report / analytics dashboard page"""

import streamlit as st
import pandas as pd

from backend.crud import set_graduated


def show_progress_report_page(db, user_data, analytics):
    """Display learning progress and analytics"""
    st.title("📊 Learning Progress Report")
    st.markdown(f"### Insights for {user_data['name']}")

    _show_key_metrics(analytics)

    st.divider()

    _show_subject_performance(analytics)
    _show_recommendations(analytics)
    _show_overdue_topics(analytics)
    _show_graduated_topics(db, analytics)


def _show_key_metrics(analytics):
    """Display key metrics at the top"""
    col1, col2 = st.columns(2)
    with col1:
        st.metric("This Week", f"{analytics['this_week_completion']}% complete")
    with col2:
        st.metric("Topics Overdue", analytics['overdue_count'], delta="Need attention", delta_color="inverse")


def _show_subject_performance(analytics):
    """Display subject-wise performance bars"""
    st.subheader("📚 Subject-wise Performance")
    st.caption("Based on review quality ratings (sessions with a rating)")

    if not analytics['subject_performance']:
        st.info("No rated sessions yet. Complete topics and save progress to see performance data.")
        return

    df_subjects = pd.DataFrame(analytics['subject_performance'])

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


def _show_recommendations(analytics):
    """Show personalized recommendations based on performance"""
    st.subheader("💡 Recommendations")
    
    # Find weak and strong subjects
    weak_subjects = [s for s in analytics['subject_performance'] if s['avg_quality'] < 3.5]
    strong_subjects = [s for s in analytics['subject_performance'] if s['avg_quality'] >= 4.0]
    
    if weak_subjects:
        st.warning(f"**Focus needed:** {', '.join([s['subject'] for s in weak_subjects])}")
        st.markdown("- Consider extra practice sessions")
        st.markdown("- Break topics into smaller parts")
        st.markdown("- Use different teaching methods")
    
    if strong_subjects:
        st.success(f"**Doing great in:** {', '.join([s['subject'] for s in strong_subjects])}")
        st.markdown("- Maintain current pace")
        st.markdown("- Can increase difficulty slightly")


def _show_overdue_topics(analytics):
    """Display overdue topics section"""
    st.divider()
    st.subheader("⚠️ Topics Needing Review")

    overdue = analytics.get("overdue_topics", [])

    if not overdue:
        st.success("No overdue topics — all caught up!")
        return

    st.markdown(f"**{len(overdue)} topic(s)** are overdue for review")
    st.caption("These topics were studied earlier but their spaced repetition review date has passed.")

    df = pd.DataFrame(overdue)[["subject", "topic", "days_overdue"]]
    df.columns = ["Subject", "Topic", "Days Overdue"]
    df = df.sort_values("Days Overdue", ascending=False).reset_index(drop=True)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _show_graduated_topics(db, analytics):
    """Display topics marked mastered, with a way to undo — graduating a topic stops it
    competing for review slots, so this is the only place to reverse that decision."""
    st.divider()
    st.subheader("🎓 Graduated Topics")

    graduated = analytics.get("graduated_topics", [])

    if not graduated:
        st.caption("No topics graduated yet. Mark a topic mastered from This Week's Plan to stop scheduling it for review.")
        return

    st.caption(f"{len(graduated)} topic(s) marked mastered — excluded from review scheduling.")

    for item in graduated:
        col_subject, col_topic, col_date, col_undo = st.columns([1.5, 3, 1.5, 1.3])
        with col_subject:
            st.markdown(f"**{item['subject']}**")
        with col_topic:
            st.markdown(item['topic'])
        with col_date:
            st.caption(f"Since {item['graduated_at'].strftime('%b %d, %Y')}" if item['graduated_at'] else "")
        with col_undo:
            if st.button("↩️ Un-graduate", key=f"ungraduate_{item['id']}"):
                set_graduated(db, item['id'], False)
                st.rerun()
