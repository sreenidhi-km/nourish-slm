"""
user.py
=======
SQLAlchemy model for User table.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON
from backend.app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    dietary_preference = Column(String(50), default="no_preference", nullable=False)
    allergies = Column(JSON, nullable=True)  # e.g. ["peanut", "gluten"]; checked on every chatbot recipe
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
