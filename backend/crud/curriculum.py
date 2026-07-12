from sqlalchemy.orm import Session
from sqlalchemy import extract
from backend.models import CurriculumItem, Newsletter
from datetime import date
from typing import List, Dict, Any

def get_current_curriculum(db: Session, user_id: int, current_date: date) -> List[CurriculumItem]:
    """Get curriculum topics for current date"""
    newsletters = db.query(Newsletter).filter(Newsletter.user_id == user_id).all()
    newsletter_ids = [n.id for n in newsletters]

    return db.query(CurriculumItem).filter(
        CurriculumItem.newsletter_id.in_(newsletter_ids),
        CurriculumItem.start_date <= current_date,
        (CurriculumItem.end_date >= current_date) | (CurriculumItem.end_date == None)
    ).all()


def get_curriculum_by_month(db: Session, user_id: int, month: int, year: int) -> List[Dict[str, Any]]:
    """Get all curriculum topics (newsletter + manual diary entries) whose start_date
    falls in the given month/year, tagged with their source."""
    newsletters = {n.id: n for n in db.query(Newsletter).filter(Newsletter.user_id == user_id).all()}

    items = db.query(CurriculumItem).filter(
        CurriculumItem.newsletter_id.in_(list(newsletters.keys())),
        extract("month", CurriculumItem.start_date) == month,
        extract("year", CurriculumItem.start_date) == year
    ).order_by(CurriculumItem.start_date.asc(), CurriculumItem.subject.asc()).all()

    result = []
    for item in items:
        newsletter = newsletters.get(item.newsletter_id)
        is_manual = bool(newsletter and newsletter.month == "Diary" and newsletter.year == 0)
        result.append({
            "date": item.start_date,
            "subject": item.subject,
            "topic": item.topic,
            "source": "Manual Entry" if is_manual else "Newsletter"
        })
    return result
