"""
diet.py
=======
SQLAlchemy models for saved diet plans and their plan-specific assistant conversations.
Each DietPlan owns its own DietChatMessage rows, so assistants never share context.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


class DietPlan(Base):
    __tablename__ = "diet_plans"

    id = Column(String(40), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category_key = Column(String(40), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    is_saved = Column(Boolean, default=False, nullable=False)
    profile = Column(JSON, nullable=False)
    plan = Column(JSON, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    messages = relationship("DietChatMessage", back_populates="plan", cascade="all, delete-orphan")


class DietChatMessage(Base):
    __tablename__ = "diet_chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(String(40), ForeignKey("diet_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' | 'assistant'
    content = Column(Text, nullable=False)
    proposals = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    plan = relationship("DietPlan", back_populates="messages")
