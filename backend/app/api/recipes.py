"""
recipes.py
==========
FastAPI routes for recipe generation, dietary validation, saved recipes, and favorites.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.api.auth import get_current_user
from backend.app.models.user import User
from backend.app.models.recipe import SavedRecipe, Favorite
from backend.app.schemas.recipe import (
    RecipeGenerateRequest,
    RecipeValidateRequest,
    SaveRecipeRequest,
    FavoriteRequest
)
from backend.app.services.model_service import slm_engine
from backend.app.services.recipe_validator import validate_recipe_against_preference

router = APIRouter(prefix="", tags=["Recipes & Saved Items"])

@router.post("/recipes/generate")
def generate_recipe_direct(req: RecipeGenerateRequest):
    res = slm_engine.generate_recipe(
        ingredients=req.ingredients,
        preference=req.preference,
        cuisine=req.cuisine
    )
    return res

@router.post("/recipes/validate")
def validate_recipe_direct(req: RecipeValidateRequest):
    res = validate_recipe_against_preference(
        ingredients=req.ingredients,
        user_preference=req.preference
    )
    return res

@router.post("/recipes/save")
def save_recipe(
    req: SaveRecipeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    saved = SavedRecipe(
        user_id=current_user.id,
        title=req.title,
        recipe_json=req.recipe_data
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return {"message": "Recipe saved successfully", "id": saved.id}

@router.get("/recipes/saved")
def get_saved_recipes(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    recipes = db.query(SavedRecipe).filter(
        SavedRecipe.user_id == current_user.id
    ).order_by(SavedRecipe.saved_at.desc()).all()
    
    return [
        {
            "id": r.id,
            "title": r.title,
            "recipe_data": r.recipe_json,
            "saved_at": r.saved_at.isoformat()
        }
        for r in recipes
    ]

@router.delete("/recipes/saved/{saved_id}")
def delete_saved_recipe(
    saved_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    recipe = db.query(SavedRecipe).filter(
        SavedRecipe.id == saved_id,
        SavedRecipe.user_id == current_user.id
    ).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Saved recipe not found")
    db.delete(recipe)
    db.commit()
    return {"message": "Recipe deleted"}

@router.post("/favorites")
def add_favorite(
    req: FavoriteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    fav = Favorite(
        user_id=current_user.id,
        title=req.title,
        recipe_json=req.recipe_data
    )
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return {"message": "Added to favorites", "id": fav.id}

@router.get("/favorites")
def get_favorites(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    favs = db.query(Favorite).filter(
        Favorite.user_id == current_user.id
    ).order_by(Favorite.created_at.desc()).all()

    return [
        {
            "id": f.id,
            "title": f.title,
            "recipe_data": f.recipe_json,
            "created_at": f.created_at.isoformat()
        }
        for f in favs
    ]

@router.delete("/favorites/{fav_id}")
def delete_favorite(
    fav_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    fav = db.query(Favorite).filter(
        Favorite.id == fav_id,
        Favorite.user_id == current_user.id
    ).first()
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")
    db.delete(fav)
    db.commit()
    return {"message": "Removed from favorites"}
