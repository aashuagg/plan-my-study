from sqlalchemy.orm import Session
from sqlalchemy import nullsfirst
from backend.models import LearningHistory
from backend.sm2 import SM2Algorithm
from datetime import date
from typing import List

def get_due_topics(db: Session, user_id: int) -> List[LearningHistory]:
    """Get all topics due for review, prioritized by neglect: topics never reviewed or
    not touched in the longest time come first, so a subject that was just practiced
    doesn't crowd out one that's been sitting untouched. Ties (e.g. an entire newsletter
    batch due on the same day) are broken by how long the topic has been overdue."""
    return db.query(LearningHistory).filter(
        LearningHistory.user_id == user_id,
        LearningHistory.next_review <= date.today()
    ).order_by(
        nullsfirst(LearningHistory.last_reviewed.asc()),
        LearningHistory.next_review.asc()
    ).all()

def get_learning_history(db: Session, user_id: int) -> List[LearningHistory]:
    """Get all learning history for user"""
    return db.query(LearningHistory).filter(
        LearningHistory.user_id == user_id
    ).all()

def update_topic_review(db: Session, learning_history_id: int, quality: int = 4):
    """Update SM-2 parameters after topic review"""
    lh = db.query(LearningHistory).filter(LearningHistory.id == learning_history_id).first()
    if lh:
        new_ef, new_interval, new_reps, next_review = SM2Algorithm.calculate_next_review(
            lh.easiness_factor,
            lh.interval,
            lh.repetitions,
            quality
        )
        lh.easiness_factor = new_ef
        lh.interval = new_interval
        lh.repetitions = new_reps
        lh.last_reviewed = date.today()
        lh.next_review = next_review
        db.commit()
