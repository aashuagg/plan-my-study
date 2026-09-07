from sqlalchemy.orm import Session
from backend.models import LearningHistory
from backend.sm2 import SM2Algorithm
from datetime import date
from typing import List

def get_due_topics(db: Session, user_id: int) -> List[LearningHistory]:
    """Get all topics due for review, prioritized by overdue ratio (days_overdue /
    interval) rather than raw last_reviewed recency: a topic overdue relative to its own
    spacing stage ranks above one that's only marginally late in absolute terms. Without
    this, a topic deep into its SM-2 curve (e.g. interval=90, 8 days overdue = ~9% late)
    would outrank one still early in learning (interval=1, 3 days overdue = 300% late)
    just because its last_reviewed date is older — starving young topics of the
    reinforcement they need most. Ties (equal ratio — most commonly 0, i.e. due today but
    not yet overdue, as happens for an entire newsletter batch initialized together) fall
    back to last_reviewed ASC NULLS FIRST, then next_review ASC.

    Graduated topics are excluded entirely — a parent has manually declared them mastered,
    so they stop competing for review slots regardless of what SM-2 would schedule."""
    today = date.today()
    rows = db.query(LearningHistory).filter(
        LearningHistory.user_id == user_id,
        LearningHistory.next_review <= today,
        LearningHistory.graduated.is_(False)
    ).all()

    def sort_key(lh: LearningHistory):
        days_overdue = (today - lh.next_review).days
        overdue_ratio = days_overdue / max(lh.interval, 1)
        last_reviewed_key = lh.last_reviewed or date.min
        return (-overdue_ratio, last_reviewed_key, lh.next_review)

    return sorted(rows, key=sort_key)

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

def set_graduated(db: Session, learning_history_id: int, graduated: bool):
    """Manually mark a topic as graduated (mastered — stop surfacing it for review) or
    un-graduate it. Reversible; does not touch SM-2 fields, so if un-graduated the topic
    resumes exactly where its existing interval/easiness left off."""
    lh = db.query(LearningHistory).filter(LearningHistory.id == learning_history_id).first()
    if lh:
        lh.graduated = graduated
        lh.graduated_at = date.today() if graduated else None
        db.commit()
