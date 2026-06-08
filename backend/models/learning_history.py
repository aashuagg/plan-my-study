from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base

class LearningHistory(Base):
    """SM-2 spaced repetition tracking per topic"""
    __tablename__ = "learning_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    subject = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    
    # SM-2 algorithm fields
    easiness_factor = Column(Float, default=2.5)  # EF: difficulty rating
    interval = Column(Integer, default=1)  # days until next review
    repetitions = Column(Integer, default=0)  # successful reviews count
    
    last_reviewed = Column(Date)
    next_review = Column(Date, nullable=False)
    
    user = relationship("User", back_populates="learning_history")
    study_sessions = relationship("StudySession", back_populates="learning_history")
