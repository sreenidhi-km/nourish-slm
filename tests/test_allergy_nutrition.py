"""
test_allergy_nutrition.py
=========================
Tests for the chatbot's allergy checkpoint, approximate nutrition for model-written recipes,
the extra diet substitutions, and the auth requirement on the direct recipe endpoints.
"""

import os
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.services.allergy_check import apply_allergy_check, normalize_allergies
from backend.app.services.portion_estimator import estimate_with_typical_portions
from backend.app.services.recipe_validator import validate_recipe_against_preference
from backend.app.services.nutrition_service import usda_db

client = TestClient(app)
needs_usda = pytest.mark.skipif(not usda_db.load(), reason="USDA nutrient table not downloaded")


def test_allergy_swaps_ingredients_and_steps():
    recipe = {"title": "Paneer Cashew Curry", "ingredients": ["200 g paneer", "cashews", "2 tbsp butter", "peanut butter"],
              "instructions": ["Fry the paneer in butter.", "Blend the cashews.", "Stir in peanut butter."]}
    out = apply_allergy_check(recipe, ["dairy", "tree nuts", "peanut"])
    ac = out["allergy_check"]
    assert ac["passed"] is True
    assert out["ingredients"][0] == "200 g firm tofu"           # quantity kept
    assert "pumpkin seeds" in out["ingredients"]
    assert out["instructions"][0] == "Fry the firm tofu in vegetable oil."
    assert out["instructions"][2] == "Stir in sunflower seed butter."   # replacement never replaced again
    assert "Paneer" not in out["title"]


def test_allergy_replacement_avoids_other_allergies():
    # paneer -> tofu would add soy; with a soy allergy the next option (chickpeas) is used
    out = apply_allergy_check({"ingredients": ["paneer"], "instructions": []}, ["dairy", "soy"])
    assert out["ingredients"] == ["chickpeas"]
    assert out["allergy_check"]["passed"] is True


def test_no_allergies_means_no_report():
    out = apply_allergy_check({"ingredients": ["peanuts"], "instructions": []}, [])
    assert "allergy_check" not in out


def test_normalize_allergies_aliases():
    assert normalize_allergies(["Nuts", "lactose", "Peanuts", "wheat", "unknown"]) == ["tree_nuts", "dairy", "peanut", "gluten"]


def test_eggplant_and_almond_milk_are_not_false_positives():
    out = apply_allergy_check({"ingredients": ["eggplant", "almond milk"], "instructions": []}, ["egg", "dairy"])
    assert out["ingredients"] == ["eggplant", "almond milk"]
    assert out["allergy_check"]["passed"] is True


def test_honey_blocked_for_vegans_only():
    assert validate_recipe_against_preference(["honey", "oats"], "vegan")["passed"] is False
    assert validate_recipe_against_preference(["honey", "oats"], "vegetarian")["passed"] is True


def test_new_diet_substitutions_exist():
    res = validate_recipe_against_preference(["salmon fillets", "2 prawns", "lamb"], "vegetarian")
    assert all(c["suggested_alternative"] for c in res["conflicts"])
    assert res["conflicts"][0]["matched_term"] == "salmon"


@needs_usda
def test_typical_portion_nutrition():
    est = estimate_with_typical_portions(["chickpeas", "onion", "tomatoes", "olive oil", "garam masala", "salt"], "4")
    assert est["status"] == "estimate" and est["approximate"] is True
    v = est["values"]
    assert 100 < v["kcal"] < 600 and v["protein"] > 3
    assert len(est["suggested_lines"]) == 6 and est["suggested_lines"][-1] == "salt (to taste)"


def _token():
    email = f"allergy_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/api/auth/register", json={"name": "A", "email": email, "password": "secret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_allergies_endpoints_and_chat():
    h = _token()
    assert client.get("/api/user/allergies", headers=h).json()["allergies"] == []
    r = client.put("/api/user/allergies", headers=h, json={"allergies": ["peanuts", "gluten"]})
    assert r.json()["allergies"] == ["peanut", "gluten"]
    assert client.get("/api/user/profile", headers=h).json()["allergies"] == ["peanut", "gluten"]
    chat = client.post("/api/chat", headers=h, json={"message": "peanuts and pasta", "preference": "vegan"}).json()
    rec = chat["recipe"]
    assert rec["allergy_check"]["passed"] is True
    assert not any("peanut" in i.lower() for i in rec["ingredients"])
    assert "allerg" in chat["message"].lower()


def test_chat_message_length_limit():
    h = _token()
    assert client.post("/api/chat", headers=h, json={"message": "x" * 1001}).status_code == 422


def test_direct_recipe_endpoints_require_login(monkeypatch):
    from backend.app.core.config import settings
    monkeypatch.setattr(settings, "ALLOW_DEMO_USER", False)
    r = client.post("/api/recipes/generate", json={"ingredients": ["rice"], "preference": "vegan", "cuisine": "Indian"})
    assert r.status_code == 401
