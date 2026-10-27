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
from backend.app.schemas.auth import UserProfileResponse, PreferenceUpdateRequest, AllergyUpdateRequest
from backend.app.services.allergy_check import normalize_allergies
from backend.app.services.diet_recipe_store import ALLERGEN_KEYS, ALLERGEN_LABELS

router = APIRouter(prefix="/user", tags=["User & Preferences"])

@router.get("/profile", response_model=UserProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "dietary_preference": current_user.dietary_preference,
        "allergies": normalize_allergies(current_user.allergies or []),
    }

@router.get("/allergies")
def get_allergies(current_user: User = Depends(get_current_user)):
    return {"allergies": normalize_allergies(current_user.allergies or []),
            "options": [{"key": k, "label": ALLERGEN_LABELS[k]} for k in ALLERGEN_KEYS]}

@router.put("/allergies")
def update_allergies(req: AllergyUpdateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    current_user.allergies = normalize_allergies(req.allergies)
    db.commit()
    return {"allergies": current_user.allergies}

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
