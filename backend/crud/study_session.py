from sqlalchemy.orm import Session
from backend.models import StudySession, LearningHistory
from backend.sm2 import SM2Algorithm
from datetime import date
from typing import List, Optional

def record_study_session(
    db: Session,
    user_id: int,
    learning_history_id: int,
    session_date: date,
    session_type: str,
    quality_rating: Optional[int] = None,
    notes: Optional[str] = None
) -> StudySession:
    """
    Record a study/review session and update SM-2 parameters.
    
    Args:
        session_type: "study" (first time learning) or "review" (spaced repetition)
        quality_rating: Required for "review", optional for "study"
    """
    # Create session record
    session = StudySession(
        user_id=user_id,
        learning_history_id=learning_history_id,
        session_date=session_date,
        session_type=session_type,
        quality_rating=quality_rating,
        notes=notes
    )
    db.add(session)
    
    # Update learning history
    lh = db.query(LearningHistory).filter(LearningHistory.id == learning_history_id).first()
    if lh:
        # Update SM-2 parameters based on quality rating to ensure spaced repetition cycle after first completion
        new_ef, new_interval, new_reps, next_review = SM2Algorithm.calculate_next_review(
            lh.easiness_factor,
            lh.interval,
            lh.repetitions,
            quality_rating,
            reference_date=session_date
        )
        lh.easiness_factor = new_ef
        lh.interval = new_interval
        lh.repetitions = new_reps
        lh.last_reviewed = session_date
        lh.next_review = next_review
    
    db.commit()
    db.refresh(session)
    return session

def get_study_sessions(db: Session, user_id: int, limit: int = 50) -> List[StudySession]:
    """Get recent study sessions for a user"""
    return db.query(StudySession).filter(
        StudySession.user_id == user_id
    ).order_by(StudySession.session_date.desc()).limit(limit).all()

def get_sessions_by_date(db: Session, user_id: int, session_date: date) -> List[StudySession]:
    """Get all sessions for a specific date"""
    return db.query(StudySession).filter(
        StudySession.user_id == user_id,
        StudySession.session_date == session_date
    ).all()
