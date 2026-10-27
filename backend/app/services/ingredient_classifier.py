"""
ingredient_classifier.py
========================
Classifies individual ingredients and entire recipes into dietary categories:
- Vegan
- Vegetarian
- Eggitarian
- Non-Vegetarian
"""

import re
from typing import List, Dict, Any, Tuple
from backend.app.services.dietary_rules import (
    DietaryPreference,
    MEAT_INGREDIENTS,
    POULTRY_INGREDIENTS,
    FISH_INGREDIENTS,
    SEAFOOD_INGREDIENTS,
    EGG_INGREDIENTS,
    DAIRY_INGREDIENTS,
    ALL_MEAT_AND_SEAFOOD
)

def normalize_ingredient_name(name: str) -> str:
    """Clean and normalize ingredient strings."""
    if not name:
        return ""
    text = name.lower().strip()
    # Remove special characters except hyphens and spaces
    text = re.sub(r'[^a-z0-9\s\-]', '', text)
    # Normalize extra whitespaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# Plant-based look-alikes that contain an animal-product word but are NOT animal products
# (e.g. "almond milk", "coconut cream", "peanut butter", "eggplant" is handled by word boundaries).
PLANT_BASED_PHRASES = re.compile(
    r"\b(?:almond|soy|soya|oat|coconut|rice|cashew|hazelnut|hemp|pea|flax|plant[- ]based|vegan|non[- ]dairy|"
    r"peanut|cocoa|cacao|shea|apple|nut|seeds?|sunflower|almond|tahini|pumpkin seed)\s+"
    r"(?:milk|cream|butter|yogh?urt|cheese|mayonnaise|mayo|egg)s?\b"
    r"|\bcream of tartar\b|\bcoconut\s+(?:milk|cream)\b|\bsoy milk\b",
    re.IGNORECASE,
)

_PATTERN_CACHE: Dict[int, "re.Pattern"] = {}

def _compile_targets(target_set: set) -> "re.Pattern":
    key = id(target_set)
    pat = _PATTERN_CACHE.get(key)
    if pat is None:
        # Longest phrases first; whole-word match with optional plural "s"/"es"
        alts = sorted((re.escape(t) for t in target_set if len(t) > 2), key=len, reverse=True)
        pat = re.compile(r"\b(?:" + "|".join(alts) + r")(?:e?s)?\b")
        _PATTERN_CACHE[key] = pat
    return pat

def is_match_ingredient(ingredient: str, target_set: set) -> bool:
    """Whole-word / whole-phrase match of an ingredient against a category set.

    Uses word boundaries (so "eggplant" does not match "egg") and ignores known
    plant-based look-alikes (so "almond milk" does not match "milk").
    """
    norm = normalize_ingredient_name(ingredient)
    if not norm:
        return False
    cleaned = PLANT_BASED_PHRASES.sub(" ", norm)
    return bool(_compile_targets(target_set).search(cleaned))

def classify_ingredient(ingredient: str) -> Dict[str, bool]:
    """
    Categorizes a single ingredient into animal product buckets.
    """
    return {
        "is_meat": is_match_ingredient(ingredient, MEAT_INGREDIENTS),
        "is_poultry": is_match_ingredient(ingredient, POULTRY_INGREDIENTS),
        "is_fish": is_match_ingredient(ingredient, FISH_INGREDIENTS),
        "is_seafood": is_match_ingredient(ingredient, SEAFOOD_INGREDIENTS),
        "is_egg": is_match_ingredient(ingredient, EGG_INGREDIENTS),
        "is_dairy": is_match_ingredient(ingredient, DAIRY_INGREDIENTS)
    }

def classify_recipe_diet(ingredients: List[str]) -> DietaryPreference:
    """
    Determines the strictest dietary classification for a recipe based on its ingredient list.
    Returns one of: VEGAN, VEGETARIAN, EGGITARIAN, NON_VEGETARIAN.
    """
    has_meat_seafood = False
    has_egg = False
    has_dairy = False

    for ing in ingredients:
        cats = classify_ingredient(ing)
        if cats["is_meat"] or cats["is_poultry"] or cats["is_fish"] or cats["is_seafood"]:
            has_meat_seafood = True
            break
        if cats["is_egg"]:
            has_egg = True
        if cats["is_dairy"]:
            has_dairy = True

    if has_meat_seafood:
        return DietaryPreference.NON_VEGETARIAN
    if has_egg:
        return DietaryPreference.EGGITARIAN
    if has_dairy:
        return DietaryPreference.VEGETARIAN
    return DietaryPreference.VEGAN
