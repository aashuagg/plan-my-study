from sqlalchemy import Column, Integer, Date, DateTime, Text, ForeignKey, JSON
from datetime import datetime
from backend.database import Base

class WeeklyPlan(Base):
    """Generated weekly study plans"""
    __tablename__ = "weekly_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    week_start_date = Column(Date, nullable=False)
    plan_data = Column(JSON, nullable=False)  # full week schedule
    focus_request = Column(Text)  # user's custom emphasis
    events = Column(Text)  # upcoming events
    generated_at = Column(DateTime, default=datetime.utcnow)
