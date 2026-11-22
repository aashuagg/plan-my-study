"""Helper functions for plan generation and data preparation"""

import sys
import os
import json
from langchain_core.exceptions import OutputParserException

# Add parent directory to path to import backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.crud import get_current_curriculum, get_due_topics, get_learning_history, save_weekly_plan
from backend.schemas import PlanRequest
from backend.scheduler import get_scheduler
from backend.plan_validation import correct_unambiguous_topics, validate_weekly_plan


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


def _keep_valid_days(previous_plan, corrected_plan, errors):
    """Keep already valid dates while replacing only dates with validation errors."""
    previous_days = previous_plan.get("weekly_plan", [])
    invalid_indices = {
        index for index in range(1, len(previous_days) + 1)
        if any(error.startswith(f"Day {index} (") or error.startswith(f"Day {index} ") for error in errors)
    }
    valid_days = {
        day["date"]: day for index, day in enumerate(previous_days, 1)
        if index not in invalid_indices and isinstance(day, dict) and isinstance(day.get("date"), str)
    }
    corrected_days = corrected_plan.get("weekly_plan", [])
    if not isinstance(corrected_days, list):
        return corrected_plan
    corrected_plan["weekly_plan"] = [
        valid_days.get(day.get("date"), day) if isinstance(day, dict) else day
        for day in corrected_days
    ]
    present_dates = {
        day.get("date") for day in corrected_days if isinstance(day, dict) and isinstance(day.get("date"), str)
    }
    corrected_plan["weekly_plan"].extend(
        day for day_date, day in valid_days.items() if day_date not in present_dates
    )
    return corrected_plan


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
        
        # Validate each model result before saving. Two correction calls make three
        # generation attempts in total, including the initial call.
        scheduler = get_scheduler()
        correction_instructions = ""
        previous_plan = None
        previous_errors = []
        for attempt in range(1, 4):
            try:
                plan = scheduler.generate_weekly_plan(
                    user_profile, curriculum_data, due_data, history_data, week_start,
                    focus_request, events, correction_instructions=correction_instructions
                )
                plan_fixed = fix_ollama_response(plan)
            except OutputParserException as exc:
                errors = [f"Response was not valid plan JSON: {exc}"]
                correction_instructions = "Return only valid JSON matching the requested weekly plan schema."
                continue
            if previous_plan is not None:
                plan_fixed = _keep_valid_days(previous_plan, plan_fixed, previous_errors)
            plan_fixed = correct_unambiguous_topics(plan_fixed, curriculum_data, due_data)
            errors = validate_weekly_plan(
                plan_fixed, user_profile, curriculum_data, due_data, week_start
            )
            if not errors:
                break
            previous_plan, previous_errors = plan_fixed, errors
            correction_instructions = (
                "Your previous plan failed these checks:\n- " + "\n- ".join(errors)
                + "\n\nPrevious plan:\n" + json.dumps(plan_fixed, ensure_ascii=False)
                + "\n\nCorrect only the invalid entries. Keep valid days and entries unchanged. "
                "Choose replacements only from the exact subject/topic pairs in the "
                "Current Curriculum and Topics Due for Review sets above. Each pair "
                "may appear at most once this week. Return the complete corrected JSON plan."
            )
        else:
            return False, (
                "Could not generate a valid plan after 3 attempts. No plan was saved. "
                + "Remaining issues: " + "; ".join(errors)
            )
        
        # Save plan
        plan_request = PlanRequest(
            user_id=user_id,
            week_start_date=week_start,
            focus_request=focus_request,
            events=events
        )
        save_weekly_plan(db, plan_request, plan_fixed)
        
        return True, (
            f"✓ Plan for week of {week_start.strftime('%B %d, %Y')} generated successfully "
            f"after {attempt} generation attempt(s)!"
        )
    except Exception as e:
        return False, f"Error generating plan: {str(e)}"
