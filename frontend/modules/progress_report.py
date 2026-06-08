"""Progress report / analytics dashboard page"""

import streamlit as st
import pandas as pd


def show_progress_report_page(user_data, mock_analytics):
    """Display learning progress and analytics
    
    Args:
        user_data: User profile dictionary
        mock_analytics: Mock analytics data (to be replaced with real data)
    """
    st.write("DEBUG: Progress report page called")  # Debug line
    st.title("📊 Learning Progress Report")
    st.markdown(f"### Insights for {user_data['name']}")
    
    # Key metrics
    _show_key_metrics(mock_analytics)
    
    st.divider()
    
    # Subject-wise performance
    _show_subject_performance(mock_analytics)
    
    # Recommendations
    _show_recommendations(mock_analytics)
    
    # Overdue topics section
    _show_overdue_topics(mock_analytics)


def _show_key_metrics(analytics):
    """Display key metrics at the top"""
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Study Streak", f"{analytics['study_streak']} days", delta="🔥")
    with col2:
        st.metric("This Week", f"{analytics['this_week_completion']}% complete")
    with col3:
        st.metric("Topics Overdue", analytics['overdue_count'], delta="Need attention", delta_color="inverse")


def _show_subject_performance(analytics):
    """Display subject-wise performance bars"""
    st.subheader("📚 Subject-wise Performance")
    st.caption("Based on recent review quality ratings")
    
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
    st.markdown(f"**{analytics['overdue_count']} topics** are overdue for review")
    st.caption("These topics were learned earlier but need revision according to spaced repetition schedule")
    
    if st.button("📋 View All Overdue Topics"):
        st.info("Detailed overdue list coming soon...")
