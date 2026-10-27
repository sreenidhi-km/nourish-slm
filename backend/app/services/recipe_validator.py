"""
recipe_validator.py
===================
Validates an SLM-generated recipe against the user's active dietary preference.
Detects conflicts, lists violating ingredients, and suggests plant-based or allowed modifications.
"""

from typing import List, Dict, Any, Tuple
import re

from backend.app.services.dietary_rules import (
    DietaryPreference,
    PLANT_BASED_ALTERNATIVES,
    VEGAN_EXTRA,
)

# Longest phrase first, whole words only ("cream cheese" before "cream"; "ham" never matches "graham")
_ALT_PATTERNS = [(re.compile(r"\b" + re.escape(k) + r"(e?s)?\b"), k, v)
                 for k, v in sorted(PLANT_BASED_ALTERNATIVES.items(), key=lambda kv: -len(kv[0]))]
_VEGAN_EXTRA_PATTERNS = [(re.compile(r"\b" + re.escape(k) + r"\b"), k, v) for k, v in VEGAN_EXTRA.items()]
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
            elif any(p.search(norm) for p, _, _ in _VEGAN_EXTRA_PATTERNS):
                reason = "honey (violates Vegan)"

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
            # Find substitution if available (and which words in the ingredient it replaces)
            matched = None
            for pat, key, sub in _ALT_PATTERNS + _VEGAN_EXTRA_PATTERNS:
                if pat.search(norm):
                    alt, matched = sub, key
                    break
            conflicts.append({
                "ingredient": ing,
                "reason": reason,
                "suggested_alternative": alt,
                "matched_term": matched,
            })

    passed = (len(conflicts) == 0)
    return {
        "passed": passed,
        "conflicts": conflicts,
        "violating_ingredients": violating_ingredients,
        "user_preference": pref_str
    }
