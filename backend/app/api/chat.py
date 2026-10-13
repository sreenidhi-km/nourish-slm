"""
chat.py
=======
FastAPI routes for Chat Sessions and Recipe Assistant Conversations.
Ensures strict preference, cuisine, and chat_id synchronization.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.api.auth import get_current_user
from backend.app.models.user import User
from backend.app.models.chat import ChatSession, Message
from backend.app.schemas.chat import ChatRequest, ChatResponse, ChatSessionSchema
from backend.app.services.model_service import generate_recipe_response, validate_cuisine, validate_preference

router = APIRouter(prefix="/chat", tags=["Chat & SLM Recipe Generator"])

ALLOWED_DIETARY_PREFERENCES = {"vegan", "vegetarian", "eggitarian", "non_vegetarian", "no_preference"}
ALLOWED_CUISINES = {"indian", "italian", "continental", "all", "general", "any", ""}


@router.post("", response_model=ChatResponse)
def post_chat_message(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Validate and normalize preference
    if req.preference and req.preference.lower().strip() in ALLOWED_DIETARY_PREFERENCES:
        pref = req.preference.lower().strip()
    else:
        pref = current_user.dietary_preference or "no_preference"

    # Validate cuisine
    cuisine = validate_cuisine(req.cuisine) if req.cuisine else "All"

    # Sync preference back to user record if changed
    if pref != current_user.dietary_preference:
        current_user.dietary_preference = pref
        db.commit()

    # 1. Get or Create ChatSession
    session = None
    if req.chat_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == req.chat_id,
            ChatSession.user_id == current_user.id
        ).first()

    if not session:
        session_id = req.chat_id if req.chat_id else f"chat_{uuid.uuid4().hex[:12]}"
        title_summary = req.message[:40] if len(req.message) > 40 else req.message
        session = ChatSession(
            id=session_id,
            user_id=current_user.id,
            title=title_summary.strip() or "New Recipe Chat"
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    # 2. Store User Message
    user_msg_db = Message(
        chat_id=session.id,
        role="user",
        content=req.message
    )
    db.add(user_msg_db)
    db.commit()

    # 3. Generate SLM Recipe Response + Validation
    slm_result = generate_recipe_response(
        user_message=req.message,
        preference=pref,
        requested_cuisine=cuisine,
        chat_id=session.id
    )

    # 4. Store Assistant Message & Structured Recipe
    assistant_msg_db = Message(
        chat_id=session.id,
        role="assistant",
        content=slm_result["message"],
        recipe_data=slm_result["recipe"]
    )
    db.add(assistant_msg_db)
    db.commit()

    return {
        "chat_id": session.id,
        "response_type": "recipe",
        "message": slm_result["message"],
        "recipe": slm_result["recipe"],
        "validation": slm_result["validation"]
    }


@router.get("/history")
def get_chat_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.updated_at.desc()).all()

    output = []
    for s in sessions:
        msgs = db.query(Message).filter(Message.chat_id == s.id).order_by(Message.created_at.asc()).all()
        output.append({
            "id": s.id,
            "title": s.title,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
            "messages_count": len(msgs)
        })
    return output


@router.get("/{chat_id}")
def get_chat_session(chat_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = db.query(ChatSession).filter(
        ChatSession.id == chat_id,
        ChatSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    messages = db.query(Message).filter(
        Message.chat_id == session.id
    ).order_by(Message.created_at.asc()).all()

    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "recipe_data": m.recipe_data,
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ]
    }


@router.delete("/{chat_id}")
def delete_chat_session(chat_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = db.query(ChatSession).filter(
        ChatSession.id == chat_id,
        ChatSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    db.delete(session)
    db.commit()
    return {"message": "Chat session deleted"}
