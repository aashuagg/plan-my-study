from sqlalchemy.orm import Session
from backend.models import Newsletter, LearningHistory
from backend.schemas import NewsletterUpload, CurriculumItemSchema
from backend.sm2 import SM2Algorithm
from typing import List

def create_newsletter(db: Session, newsletter: NewsletterUpload) -> Newsletter:
    """Create newsletter record"""
    db_newsletter = Newsletter(**newsletter.model_dump())
    db.add(db_newsletter)
    db.commit()
    db.refresh(db_newsletter)
    return db_newsletter

def add_curriculum_items(db: Session, newsletter_id: int, items: List[CurriculumItemSchema]):
    """Add curriculum items from parsed newsletter"""
    from backend.models import CurriculumItem
    
    for item in items:
        db_item = CurriculumItem(
            newsletter_id=newsletter_id,
            **item.model_dump()
        )
        db.add(db_item)
        
        # Initialize SM-2 tracking for new topics
        user = db.query(Newsletter).filter(Newsletter.id == newsletter_id).first().user
        existing = db.query(LearningHistory).filter(
            LearningHistory.user_id == user.id,
            LearningHistory.subject == item.subject,
            LearningHistory.topic == item.topic
        ).first()
        
        if not existing:
            # Use curriculum item's start_date as reference for SM-2 initialization
            ef, interval, reps, next_review = SM2Algorithm.initialize_topic(reference_date=item.start_date)
            learning_history = LearningHistory(
                user_id=user.id,
                subject=item.subject,
                topic=item.topic,
                easiness_factor=ef,
                interval=interval,
                repetitions=reps,
                next_review=next_review
            )
            db.add(learning_history)
    
    db.commit()
