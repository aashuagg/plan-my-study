from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base

class User(Base):
    """Student profile with study preferences"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    grade = Column(String, nullable=False)
    board = Column(String, nullable=False)  # CBSE, ICSE, etc.
    daily_duration_minutes = Column(Integer, nullable=False)
    weekly_frequency = Column(Integer, nullable=False)  # days per week
    subjects = Column(JSON, nullable=False)  # ["Math", "English", ...]
    study_time_preference = Column(String)  # "morning", "evening"
    created_at = Column(DateTime, default=datetime.utcnow)
    
    newsletters = relationship("Newsletter", back_populates="user")
    study_sessions = relationship("StudySession", back_populates="user")
    learning_history = relationship("LearningHistory", back_populates="user")
