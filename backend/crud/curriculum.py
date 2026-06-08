from sqlalchemy.orm import Session
from backend.models import CurriculumItem, Newsletter
from datetime import date
from typing import List

def get_current_curriculum(db: Session, user_id: int, current_date: date) -> List[CurriculumItem]:
    """Get curriculum topics for current date"""
    newsletters = db.query(Newsletter).filter(Newsletter.user_id == user_id).all()
    newsletter_ids = [n.id for n in newsletters]
    
    return db.query(CurriculumItem).filter(
        CurriculumItem.newsletter_id.in_(newsletter_ids),
        CurriculumItem.start_date <= current_date,
        (CurriculumItem.end_date >= current_date) | (CurriculumItem.end_date == None)
    ).all()
