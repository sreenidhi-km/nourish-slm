"""
recipe_validator.py
===================
Validates an SLM-generated recipe against the user's active dietary preference.
Detects conflicts, lists violating ingredients, and suggests plant-based or allowed modifications.
"""

from typing import List, Dict, Any, Tuple
from backend.app.services.dietary_rules import (
    DietaryPreference,
    PLANT_BASED_ALTERNATIVES
)
from backend.app.services.ingredient_classifier import (
    classify_ingredient,
    normalize_ingredient_name
)

def validate_recipe_against_preference(
    ingredients: List[str],
    user_preference: str
) -> Dict[str, Any]:
    """
    Validates a list of recipe ingredients against a requested dietary preference.
    Returns:
    {
      "passed": bool,
      "conflicts": List[Dict[str, str]], # [{"ingredient": "butter", "reason": "dairy", "alternative": "olive oil"}]
      "violating_ingredients": List[str],
      "diet_type_found": str
    }
    """
    pref_str = user_preference.lower().strip()
    if pref_str not in [p.value for p in DietaryPreference]:
        pref_str = DietaryPreference.NO_PREFERENCE.value

    # If NO_PREFERENCE, always pass
    if pref_str == DietaryPreference.NO_PREFERENCE.value or pref_str == DietaryPreference.NON_VEGETARIAN.value:
        return {
            "passed": True,
            "conflicts": [],
            "violating_ingredients": [],
            "user_preference": pref_str
        }

    conflicts = []
    violating_ingredients = []

    for ing in ingredients:
        norm = normalize_ingredient_name(ing)
        cats = classify_ingredient(norm)

        reason = None
        alt = None

        if pref_str == DietaryPreference.VEGAN.value:
            if cats["is_meat"]:
                reason = "meat (violates Vegan)"
            elif cats["is_poultry"]:
                reason = "poultry (violates Vegan)"
            elif cats["is_fish"]:
                reason = "fish (violates Vegan)"
            elif cats["is_seafood"]:
                reason = "seafood (violates Vegan)"
            elif cats["is_egg"]:
                reason = "egg (violates Vegan)"
            elif cats["is_dairy"]:
                reason = "dairy (violates Vegan)"

        elif pref_str == DietaryPreference.VEGETARIAN.value:
            if cats["is_meat"]:
                reason = "meat (violates Vegetarian)"
            elif cats["is_poultry"]:
                reason = "poultry (violates Vegetarian)"
            elif cats["is_fish"]:
                reason = "fish (violates Vegetarian)"
            elif cats["is_seafood"]:
                reason = "seafood (violates Vegetarian)"
            elif cats["is_egg"]:
                reason = "egg (violates Vegetarian)"

        elif pref_str == DietaryPreference.EGGITARIAN.value:
            if cats["is_meat"]:
                reason = "meat (violates Eggitarian)"
            elif cats["is_poultry"]:
                reason = "poultry (violates Eggitarian)"
            elif cats["is_fish"]:
                reason = "fish (violates Eggitarian)"
            elif cats["is_seafood"]:
                reason = "seafood (violates Eggitarian)"

        if reason:
            violating_ingredients.append(ing)
            # Find substitution if available
            for orig, sub in PLANT_BASED_ALTERNATIVES.items():
                if orig in norm:
                    alt = sub
                    break
            conflicts.append({
                "ingredient": ing,
                "reason": reason,
                "suggested_alternative": alt
            })

    passed = (len(conflicts) == 0)
    return {
        "passed": passed,
        "conflicts": conflicts,
        "violating_ingredients": violating_ingredients,
        "user_preference": pref_str
    }
