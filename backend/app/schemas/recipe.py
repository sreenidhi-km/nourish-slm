"""
recipe.py
=========
Pydantic schemas for recipe generation, validation, saving, and favorites.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class RecipeGenerateRequest(BaseModel):
    ingredients: List[str]
    preference: str = "no_preference"
    cuisine: Optional[str] = "All"

class RecipeValidateRequest(BaseModel):
    ingredients: List[str]
    preference: str

class SaveRecipeRequest(BaseModel):
    title: str
    recipe_data: Dict[str, Any]

class FavoriteRequest(BaseModel):
    title: str
    recipe_data: Dict[str, Any]
