from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base

class StudySession(Base):
    """Record of a study/review session for a topic"""
    __tablename__ = "study_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    learning_history_id = Column(Integer, ForeignKey("learning_history.id"))
    
    session_date = Column(Date, nullable=False)
    session_type = Column(String, nullable=False)  # "study" or "review"
    quality_rating = Column(Integer)  # 0-5, only for review sessions
    notes = Column(String)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="study_sessions")
    learning_history = relationship("LearningHistory", back_populates="study_sessions")
