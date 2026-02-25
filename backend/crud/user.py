from sqlalchemy.orm import Session
from backend.models import User
from backend.schemas import UserCreate
from typing import Optional

def create_user(db: Session, user: UserCreate) -> User:
    """Create a new user profile"""
    db_user = User(**user.model_dump())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID"""
    return db.query(User).filter(User.id == user_id).first()

def update_user(db: Session, user_id: int, user_data: dict) -> Optional[User]:
    """Update user profile"""
    db_user = get_user(db, user_id)
    if db_user:
        for key, value in user_data.items():
            setattr(db_user, key, value)
        db.commit()
        db.refresh(db_user)
    return db_user
