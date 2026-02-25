from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base

class Newsletter(Base):
    """Monthly newsletter with curriculum schedule"""
    __tablename__ = "newsletters"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    month = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    file_path = Column(String)
    parsed_data = Column(JSON)  # structured curriculum data
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="newsletters")
    curriculum_items = relationship("CurriculumItem", back_populates="newsletter")
