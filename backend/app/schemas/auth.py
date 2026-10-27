"""
auth.py
=======
Pydantic schemas for authentication and user management.
"""

from typing import List, Optional
from pydantic import BaseModel, EmailStr

class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class UserProfileResponse(BaseModel):
    id: int
    name: str
    email: str
    dietary_preference: str
    allergies: List[str] = []

class AllergyUpdateRequest(BaseModel):
    allergies: List[str]

class PreferenceUpdateRequest(BaseModel):
    dietary_preference: str
