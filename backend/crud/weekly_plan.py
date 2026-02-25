from sqlalchemy.orm import Session
from backend.models import WeeklyPlan
from backend.schemas import PlanRequest
from typing import Optional

def save_weekly_plan(db: Session, plan_request: PlanRequest, plan_data: dict) -> WeeklyPlan:
    """Save generated weekly plan"""
    db_plan = WeeklyPlan(
        user_id=plan_request.user_id,
        week_start_date=plan_request.week_start_date,
        plan_data=plan_data,
        focus_request=plan_request.focus_request,
        events=plan_request.events
    )
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    return db_plan

def get_latest_weekly_plan(db: Session, user_id: int) -> Optional[WeeklyPlan]:
    """Get most recent weekly plan"""
    return db.query(WeeklyPlan).filter(
        WeeklyPlan.user_id == user_id
    ).order_by(WeeklyPlan.generated_at.desc()).first()
