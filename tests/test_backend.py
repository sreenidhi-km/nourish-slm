"""
test_backend.py
===============
Unit and integration tests for FastAPI backend, database, dietary rules, and recipe validation.
"""

import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.services.ingredient_classifier import classify_recipe_diet
from backend.app.services.recipe_validator import validate_recipe_against_preference

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_dietary_classifier():
    assert classify_recipe_diet(["potato", "onion", "tomato"]).value == "vegan"
    assert classify_recipe_diet(["paneer", "butter", "onion"]).value == "vegetarian"
    assert classify_recipe_diet(["egg", "rice", "scallion"]).value == "eggitarian"
    assert classify_recipe_diet(["chicken breast", "rice"]).value == "non_vegetarian"

def test_recipe_validator():
    # Test Vegan check with butter
    res = validate_recipe_against_preference(["pasta", "tomato", "butter"], "vegan")
    assert res["passed"] == False
    assert len(res["conflicts"]) == 1
    assert "dairy" in res["conflicts"][0]["reason"]

    # Test Vegan check with pure plant items
    res_vegan = validate_recipe_against_preference(["pasta", "tomato", "olive oil"], "vegan")
    assert res_vegan["passed"] == True

def test_auth_and_chat_flow():
    # Register user
    reg_resp = client.post("/api/auth/register", json={
        "name": "Test User",
        "email": "testuser@foodslm.ai",
        "password": "Password123!"
    })
    if reg_resp.status_code == 400: # Already registered
        login_resp = client.post("/api/auth/login", json={
            "email": "testuser@foodslm.ai",
            "password": "Password123!"
        })
        token = login_resp.json()["access_token"]
    else:
        token = reg_resp.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    # Update Preference to Vegan
    pref_resp = client.put("/api/user/preferences", json={"dietary_preference": "vegan"}, headers=headers)
    assert pref_resp.status_code == 200
    assert pref_resp.json()["dietary_preference"] == "vegan"

    # Send Chat Request
    chat_resp = client.post("/api/chat", json={
        "message": "I have potatoes, onions and tomatoes",
        "preference": "vegan",
        "cuisine": "Indian"
    }, headers=headers)

    assert chat_resp.status_code == 200
    json_data = chat_resp.json()
    assert "chat_id" in json_data
    assert json_data["recipe"]["diet_type"] == "vegan"
    assert json_data["validation"]["passed"] == True
