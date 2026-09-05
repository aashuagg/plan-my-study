from backend.crud.user import create_user, get_user, update_user
from backend.crud.newsletter import create_newsletter, add_curriculum_items
from backend.crud.curriculum import get_current_curriculum, get_curriculum_by_month
from backend.crud.learning_history import (
    get_due_topics,
    get_learning_history,
    update_topic_review,
    set_graduated
)
from backend.crud.weekly_plan import save_weekly_plan, get_latest_weekly_plan
from backend.crud.study_session import (
    record_study_session,
    get_study_sessions,
    get_sessions_by_date
)
from backend.crud.analytics import get_analytics, get_graduated_topics

__all__ = [
    "create_user",
    "get_user",
    "update_user",
    "create_newsletter",
    "add_curriculum_items",
    "get_current_curriculum",
    "get_curriculum_by_month",
    "get_due_topics",
    "get_learning_history",
    "update_topic_review",
    "set_graduated",
    "save_weekly_plan",
    "get_latest_weekly_plan",
    "record_study_session",
    "get_study_sessions",
    "get_sessions_by_date",
    "get_analytics",
    "get_graduated_topics",
]
