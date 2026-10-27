"""
chat.py
=======
Pydantic schemas for chat requests and responses.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    preference: str = "no_preference"
    cuisine: Optional[str] = "All"
    chat_id: Optional[str] = Field(None, max_length=64)
    allergies: Optional[List[str]] = None  # when sent, also saved as the user's allergies

class RecipeData(BaseModel):
    title: str
    diet_type: str
    cuisine: str
    ingredients: List[str]
    instructions: List[str]
    prep_time: str
    cook_time: str
    servings: str
    source: Optional[str] = None  # "slm" | "retrieval" | "template"
    # Added for nutrition display (all optional so older saved recipes still validate)
    nutrition: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    image_alt: Optional[str] = None
    source_url: Optional[str] = None
    labels: Optional[Dict[str, Any]] = None
    ingredient_quantities: Optional[List[str]] = None
    related_recipe: Optional[Dict[str, Any]] = None
    allergy_check: Optional[Dict[str, Any]] = None
    quantities_are_suggested: Optional[bool] = None

class ValidationData(BaseModel):
    passed: bool
    conflicts: List[Dict[str, Any]] = []

class ChatResponse(BaseModel):
    chat_id: str
    response_type: str = "recipe"
    message: str
    recipe: Optional[RecipeData] = None
    validation: Optional[ValidationData] = None

class MessageSchema(BaseModel):
    id: int
    role: str
    content: str
    recipe_data: Optional[Dict[str, Any]] = None
    created_at: str

class ChatSessionSchema(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[MessageSchema] = []
