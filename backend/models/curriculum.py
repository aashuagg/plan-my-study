from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base

class CurriculumItem(Base):
    """Individual topic from newsletter curriculum"""
    __tablename__ = "curriculum_items"
    
    id = Column(Integer, primary_key=True, index=True)
    newsletter_id = Column(Integer, ForeignKey("newsletters.id"))
    subject = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    
    newsletter = relationship("Newsletter", back_populates="curriculum_items")
