from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.models import LearningHistory, StudySession, WeeklyPlan
from datetime import date, timedelta
from typing import List, Dict, Any


def _derive_status(avg_quality: float) -> str:
    if avg_quality >= 4.0:
        return "Excellent 🌟"
    elif avg_quality >= 3.5:
        return "Good ✅"
    elif avg_quality >= 3.0:
        return "OK 👍"
    else:
        return "Needs Revision ⚠️"


def get_subject_performance(db: Session, user_id: int) -> List[Dict[str, Any]]:
    rows = (
        db.query(
            LearningHistory.subject,
            func.avg(StudySession.quality_rating).label("avg_quality"),
            func.count(StudySession.id).label("total_sessions"),
        )
        .join(StudySession, StudySession.learning_history_id == LearningHistory.id)
        .filter(
            LearningHistory.user_id == user_id,
            StudySession.quality_rating.isnot(None),
        )
        .group_by(LearningHistory.subject)
        .order_by(LearningHistory.subject)
        .all()
    )

    return [
        {
            "subject": row.subject,
            "avg_quality": round(float(row.avg_quality), 1),
            "total_sessions": row.total_sessions,
            "status": _derive_status(round(float(row.avg_quality), 1)),
        }
        for row in rows
    ]


def get_overdue_topics(db: Session, user_id: int) -> List[Dict[str, Any]]:
    today = date.today()
    rows = (
        db.query(LearningHistory)
        .filter(
            LearningHistory.user_id == user_id,
            LearningHistory.next_review <= today,
            LearningHistory.last_reviewed.isnot(None),
        )
        .order_by(LearningHistory.next_review)
        .all()
    )

    return [
        {
            "subject": lh.subject,
            "topic": lh.topic,
            "days_overdue": (today - lh.next_review).days,
        }
        for lh in rows
    ]



def get_this_week_completion(db: Session, user_id: int) -> int:
    latest_plan = (
        db.query(WeeklyPlan)
        .filter(WeeklyPlan.user_id == user_id)
        .order_by(WeeklyPlan.generated_at.desc())
        .first()
    )

    if not latest_plan:
        return 0

    week_start = latest_plan.week_start_date
    week_end = week_start + timedelta(days=6)

    total_topics = sum(
        len(day.get("topics", []))
        for day in latest_plan.plan_data.get("weekly_plan", [])
    )

    if total_topics == 0:
        return 0

    completed = (
        db.query(func.count(StudySession.id))
        .filter(
            StudySession.user_id == user_id,
            StudySession.session_date >= week_start,
            StudySession.session_date <= week_end,
        )
        .scalar()
    )

    return min(100, round((completed / total_topics) * 100))


def get_analytics(db: Session, user_id: int) -> Dict[str, Any]:
    overdue_topics = get_overdue_topics(db, user_id)
    return {
        "subject_performance": get_subject_performance(db, user_id),
        "overdue_topics": overdue_topics,
        "overdue_count": len(overdue_topics),
        "this_week_completion": get_this_week_completion(db, user_id),
    }