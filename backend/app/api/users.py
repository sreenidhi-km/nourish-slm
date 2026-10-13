"""
users.py
========
FastAPI routes for user profile and preference management.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.api.auth import get_current_user
from backend.app.models.user import User
from backend.app.schemas.auth import UserProfileResponse, PreferenceUpdateRequest

router = APIRouter(prefix="/user", tags=["User & Preferences"])

@router.get("/profile", response_model=UserProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "dietary_preference": current_user.dietary_preference
    }

@router.get("/preferences")
def get_preferences(current_user: User = Depends(get_current_user)):
    return {"dietary_preference": current_user.dietary_preference}

@router.put("/preferences")
def update_preferences(req: PreferenceUpdateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pref = req.dietary_preference.lower().strip()
    valid_prefs = ["vegan", "vegetarian", "eggitarian", "non_vegetarian", "no_preference"]
    if pref not in valid_prefs:
        raise HTTPException(status_code=400, detail=f"Invalid preference. Must be one of: {valid_prefs}")

    current_user.dietary_preference = pref
    db.commit()
    db.refresh(current_user)
    return {
        "message": f"Preference updated to {pref.replace('_', ' ').capitalize()}",
        "dietary_preference": current_user.dietary_preference
    }
