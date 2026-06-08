"""Helper functions for plan generation and data preparation"""

import sys
import os

# Add parent directory to path to import backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.crud import get_current_curriculum, get_due_topics, get_learning_history, save_weekly_plan
from backend.schemas import PlanRequest
from backend.scheduler import get_scheduler


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
