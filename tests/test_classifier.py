"""Regression tests for the dietary ingredient classifier (false positives / negatives)."""
import os, sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.app.services.ingredient_classifier import classify_recipe_diet
from backend.app.services.recipe_validator import validate_recipe_against_preference


@pytest.mark.parametrize("ings", [
    ["eggplant", "zucchini"], ["almond milk", "oats"], ["coconut milk", "cauliflower"],
    ["peanut butter", "bread"], ["butternut squash"], ["cream of tartar", "flour"], ["soy sauce", "tofu"],
])
def test_plant_based_items_are_vegan(ings):
    assert classify_recipe_diet(ings).value == "vegan"


@pytest.mark.parametrize("ings,expected", [
    (["butter"], "vegetarian"), (["heavy cream"], "vegetarian"), (["paneer", "spinach"], "vegetarian"),
    (["eggs"], "eggitarian"), (["egg whites", "spinach"], "eggitarian"),
    (["chicken breasts"], "non_vegetarian"), (["fish sauce"], "non_vegetarian"), (["shrimp"], "non_vegetarian"),
])
def test_animal_products_detected(ings, expected):
    assert classify_recipe_diet(ings).value == expected


def test_vegan_validator_rejects_dairy_and_accepts_plant_milk():
    assert not validate_recipe_against_preference(["milk", "oats"], "vegan")["passed"]
    assert validate_recipe_against_preference(["almond milk", "oats"], "vegan")["passed"]
