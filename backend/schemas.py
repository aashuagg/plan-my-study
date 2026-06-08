from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class UserCreate(BaseModel):
    """Schema for creating user profile"""
    name: str
    grade: str
    board: str
    daily_duration_minutes: int
    weekly_frequency: int
    subjects: List[str]
    study_time_preference: Optional[str] = None

class UserResponse(UserCreate):
    """Schema for user profile response"""
    id: int
    
    class Config:
        from_attributes = True

class NewsletterUpload(BaseModel):
    """Schema for newsletter upload"""
    user_id: int
    month: str
    year: int
    file_path: str

class CurriculumItemSchema(BaseModel):
    """Schema for curriculum item"""
    subject: str
    topic: str
    start_date: date
    end_date: Optional[date] = None

class PlanRequest(BaseModel):
    """Schema for weekly plan generation request"""
    user_id: int
    week_start_date: date
    focus_request: Optional[str] = None
    events: Optional[str] = None

class DailyPlanItem(BaseModel):
    """Schema for single day in weekly plan"""
    date: date
    subjects: List[str]
    topics: List[str]
    duration_minutes: int
