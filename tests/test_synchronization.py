"""
test_synchronization.py
========================
Automated Verification Suite for User Input -> Preference -> Cuisine -> Retrieval -> Validation -> Response Synchronization.
Executes all 8 exact test cases requested in prompt.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.model_service import generate_recipe_response
from backend.app.services.recipe_validator import validate_recipe_against_preference

def test_case_1_vegan_potatoes_tomatoes():
    """TEST 1: Vegan preference with potatoes, onions, tomatoes."""
    res = generate_recipe_response(
        user_message="I have potatoes, onions and tomatoes",
        preference="vegan",
        requested_cuisine="All"
    )
    recipe = res["recipe"]
    val = res["validation"]

    assert recipe["diet_type"] == "vegan"
    assert val["passed"] == True
    
    # Verify no animal products in ingredients
    plant_milks = ["soymilk", "soy milk", "almond milk", "coconut milk", "oat milk", "rice milk", "cashew milk"]
    for ing in recipe["ingredients"]:
        ing_lower = ing.lower()
        if any(pm in ing_lower for pm in plant_milks):
            continue
        for forbidden in ["chicken", "beef", "pork", "fish", "shrimp", "egg", "milk", "butter", "paneer", "cheese"]:
            assert forbidden not in ing_lower, f"Forbidden animal ingredient '{forbidden}' found in Vegan recipe!"

def test_case_2_vegetarian_chicken_conflict():
    """TEST 2: Vegetarian preference with chicken query -> Must explain conflict & suggest vegetarian alt."""
    res = generate_recipe_response(
        user_message="I have chicken, rice and onions",
        preference="vegetarian",
        requested_cuisine="All"
    )
    recipe = res["recipe"]
    val = res["validation"]

    assert recipe["diet_type"] == "vegetarian"
    assert val["passed"] == True
    
    # Must NOT contain chicken in final ingredients
    for ing in recipe["ingredients"]:
        assert "chicken" not in ing.lower()

    # Must explain conflict in message
    assert "conflicts with your Vegetarian preference" in res["message"]

def test_case_3_non_veg_chicken_allowed():
    """TEST 3: Non-Vegetarian preference with chicken -> Chicken allowed."""
    res = generate_recipe_response(
        user_message="I have chicken, rice and onions",
        preference="non_vegetarian",
        requested_cuisine="All"
    )
    recipe = res["recipe"]
    val = res["validation"]

    assert recipe["diet_type"] == "non_vegetarian"
    assert val["passed"] == True

def test_case_4_eggitarian_eggs_allowed():
    """TEST 4: Eggitarian preference with eggs, rice -> Egg allowed, no meat/fish."""
    res = generate_recipe_response(
        user_message="I have eggs, rice and vegetables",
        preference="eggitarian",
        requested_cuisine="All"
    )
    recipe = res["recipe"]
    val = res["validation"]

    assert recipe["diet_type"] == "eggitarian"
    assert val["passed"] == True
    for ing in recipe["ingredients"]:
        ing_l = ing.lower()
        for forbidden in ["chicken", "beef", "pork", "salmon", "shrimp"]:
            assert forbidden not in ing_l

def test_case_5_no_preference_chicken():
    """TEST 5: No Preference -> Chicken allowed."""
    res = generate_recipe_response(
        user_message="I have chicken, rice and onions",
        preference="no_preference",
        requested_cuisine="All"
    )
    recipe = res["recipe"]
    val = res["validation"]
    assert val["passed"] == True

def test_case_6_vegan_italian_pasta():
    """TEST 6: Vegan + Italian -> Italian vegan pasta. NOT Indian, NOT Chaat Masala."""
    res = generate_recipe_response(
        user_message="Give me an Italian pasta recipe",
        preference="vegan",
        requested_cuisine="Italian"
    )
    recipe = res["recipe"]
    val = res["validation"]

    assert recipe["diet_type"] == "vegan"
    assert recipe["cuisine"] == "Italian"
    assert val["passed"] == True
    assert "chaat" not in recipe["title"].lower()
    assert "biryani" not in recipe["title"].lower()

def test_case_7_vegetarian_indian_paneer():
    """TEST 7: Vegetarian + Indian -> Indian vegetarian recipe using paneer/tomatoes."""
    res = generate_recipe_response(
        user_message="I have paneer and tomatoes",
        preference="vegetarian",
        requested_cuisine="Indian"
    )
    recipe = res["recipe"]
    val = res["validation"]

    assert recipe["diet_type"] == "vegetarian"
    assert recipe["cuisine"] == "Indian"
    assert val["passed"] == True

def test_case_8_vegan_paneer_masala_conflict():
    """TEST 8: Vegan + paneer butter masala -> Explain dairy conflict & provide vegan alternative."""
    res = generate_recipe_response(
        user_message="I have paneer butter masala",
        preference="vegan",
        requested_cuisine="All"
    )
    recipe = res["recipe"]
    val = res["validation"]

    assert recipe["diet_type"] == "vegan"
    assert val["passed"] == True
    assert "conflicts with your Vegan preference" in res["message"]
