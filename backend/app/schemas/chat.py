"""
chat.py
=======
Pydantic schemas for chat requests and responses.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    preference: str = "no_preference"
    cuisine: Optional[str] = "All"
    chat_id: Optional[str] = None

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
