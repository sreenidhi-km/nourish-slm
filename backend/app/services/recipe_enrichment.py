"""
recipe_enrichment.py
====================
Adds nutrition, a photo and dietary labels to recipes returned by the general Nourish chatbot,
using the same data and nutrition engine as the Diet section.

* Dataset (retrieval) recipes: Food.com per-serving values by recipe id (grams; or derived from the
  published %DV when grams are not available) and the recipe's own photo.
* Model-generated recipes: the model does not write ingredient quantities. When every line has a
  quantity the exact USDA calculation is used; otherwise each ingredient gets its typical amount
  per serving from Food.com recipes (portion_estimator.py). Those amounts are shown as suggested
  quantities and the nutrition is labelled approximate. The closest database recipe with
  verified nutrition (free of the user's allergens) is still shown alongside.
* A photo is only attached when it is of the same recipe (same id, or an identical title).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from backend.app.services.diet_recipe_store import ALLERGEN_LABELS, DIET_LABELS, recipe_store, verification_conflicts
from backend.app.services.food_labels import classify_diet, detect_allergens
from backend.app.services.nutrition_service import estimate_recipe_from_lines
from backend.app.services.portion_estimator import estimate_with_typical_portions

SOURCE_LABELS = {
    "foodcom_grams": "Food.com published nutrition per serving",
    "foodcom_pdv_derived": "Food.com published nutrition per serving (grams derived from %DV; fibre not published)",
    "estimate": "Estimated from USDA ingredient data",
}


def _labels(ingredients: List[str], preference: str) -> Dict[str, Any]:
    diet, flags = classify_diet(ingredients)
    allergens = detect_allergens(ingredients, flags)
    return {"diet": diet, "diet_label": DIET_LABELS.get(diet, diet),
            "allergens": [ALLERGEN_LABELS.get(a, a) for a in allergens],
            "basis": "Detected from the ingredient names; check product labels for allergens."}


def _nutrition_from_row(row: Dict[str, Any], basis: str) -> Dict[str, Any]:
    vals = {k: row.get(k) for k in ("kcal", "protein", "carbs", "fat", "fiber")}
    if vals["kcal"] is not None:
        vals["kcal"] = round(vals["kcal"])
    for k in ("protein", "carbs", "fat", "fiber"):
        if vals[k] is not None:
            vals[k] = round(vals[k], 1)
    return {"status": "source", "per": "serving", "values": vals, "basis": basis,
            "source_label": SOURCE_LABELS.get(basis, basis),
            "missing": [k for k, v in vals.items() if v is None]}


def _approximate(out: Dict[str, Any], reason_if_none: str) -> None:
    """Typical-portion estimate; also fills suggested quantities for the ingredient list."""
    est = estimate_with_typical_portions(out.get("ingredients") or [], out.get("servings"))
    if est["status"] == "estimate":
        out["nutrition"] = est
        out["ingredient_quantities"] = est["suggested_lines"]
        out["quantities_are_suggested"] = True
    else:
        out["nutrition"] = {"status": "unavailable", "reason": reason_if_none}


def _recalculate_swapped(out: Dict[str, Any], full: Optional[Dict[str, Any]], allergies: Optional[List[str]]) -> bool:
    """For a dataset recipe whose ingredients were swapped for allergies: apply the same swaps to the
    recipe's quantity lines and calculate the nutrition exactly with USDA data."""
    from backend.app.services.allergy_check import apply_allergy_check
    ac = out.get("allergy_check") or {}
    diet_swapped = len(out.get("ingredients") or []) and not ac.get("substitutions")
    if not full or not full.get("ingredient_lines") or not full.get("servings") or diet_swapped or not allergies:
        return False
    swapped = apply_allergy_check({"ingredients": list(full["ingredient_lines"]), "instructions": []}, allergies)
    est = estimate_recipe_from_lines(swapped["ingredients"], full["servings"])
    if est["status"] != "estimate":
        return False
    out["ingredient_quantities"] = swapped["ingredients"]
    out["servings"] = f"{full['servings']:g}"
    out["nutrition"] = {**est, "per": "serving", "source_label": SOURCE_LABELS["estimate"] +
                        " (recipe quantities, with your allergy swaps)"}
    return True


def _related(query_ings: List[str], preference: str, cuisine: Optional[str],
             allergies: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    if not recipe_store.available:
        return None
    ings = [i for i in query_ings if len(i) > 2][:3]
    c = cuisine if cuisine and cuisine.lower() not in ("all", "general", "") else None
    for use_ings, use_c in ((ings[:2], c), (ings[:1], c), (ings[:1], None)):
        if not use_ings:
            continue
        res = recipe_store.search(page=1, page_size=6, order="protein_density", diet=preference or "no_preference",
                                  include_ingredients=use_ings, cuisine=use_c, exclude_allergens=allergies or None)
        items = [i for i in res["items"] if not verification_conflicts(i, preference)]
        if items:
            full = recipe_store.get(items[0]["id"])
            if full:
                return {
                    "id": full["id"], "name": full["name"], "image_url": full["image_url"], "source_url": full["source_url"],
                    "servings": full["servings"], "ingredient_lines": full["ingredient_lines"], "steps": full["steps"],
                    "prep_min": full["prep_min"], "cook_min": full["cook_min"],
                    "nutrition": _nutrition_from_row(full["nutrition_per_serving"], "foodcom_grams"),
                    "labels": {"diet": full["diet"], "diet_label": DIET_LABELS.get(full["diet"], full["diet"]),
                               "allergens": [ALLERGEN_LABELS.get(a, a) for a in full["allergens"]]},
                }
    return None


def enrich_recipe(recipe: Dict[str, Any], retrieved: Optional[Dict[str, Any]], query_ingredients: List[str],
                  preference: str, cuisine: Optional[str], allergies: Optional[List[str]] = None) -> Dict[str, Any]:
    out = dict(recipe)
    out["labels"] = _labels(out.get("ingredients") or [], preference)
    if not recipe_store.available:
        _approximate(out, "Nutrition data has not been built on this server (run scripts/build_diet_dataset.py).")
        return out
    try:
        if out.get("source") == "retrieval" and retrieved and retrieved.get("recipe_id"):
            rid = int(float(retrieved["recipe_id"]))
            full = recipe_store.get(rid)
            look = recipe_store.lookup(rid)
            original = {str(i).lower().strip() for i in retrieved.get("ingredients") or []}
            current = {str(i).lower().strip() for i in out.get("ingredients") or []}
            substituted = bool(original) and original != current
            if look and look.get("image_url"):
                out["image_url"] = look["image_url"]
                out["image_alt"] = f"Photo of {out.get('title')} from Food.com"
                out["source_url"] = f"https://www.food.com/recipe/{rid}"
            if full and not substituted:
                out["ingredient_quantities"] = full["ingredient_lines"]
                if full.get("servings"):
                    out["servings"] = f"{full['servings']:g}"
            if substituted:
                # Recalculate from the recipe's own quantities with the same swaps applied, when possible
                if not _recalculate_swapped(out, full, allergies):
                    _approximate(out, "Some ingredients were substituted to fit your diet or allergies, so the "
                                      "recipe's published nutrition no longer applies.")
            elif full:
                out["nutrition"] = _nutrition_from_row(full["nutrition_per_serving"], "foodcom_grams")
            elif look:
                out["nutrition"] = _nutrition_from_row(look, look["basis"])
            else:
                out["nutrition"] = {"status": "unavailable", "reason": "No nutrition record for this recipe."}
        else:
            est = estimate_recipe_from_lines(out.get("ingredients") or [], out.get("servings"))
            if est["status"] == "estimate":
                out["nutrition"] = {**est, "per": "serving", "source_label": SOURCE_LABELS["estimate"]}
            else:
                _approximate(out, "None of the ingredients could be matched to USDA nutrient data.")
            same = recipe_store.find_by_name(out.get("title") or "")
            if same and not verification_conflicts(same, preference) and same["diet"] in (
                    {"vegan": ["vegan"], "vegetarian": ["vegan", "vegetarian"],
                     "eggitarian": ["vegan", "vegetarian", "eggitarian"]}.get(preference, [same["diet"]])):
                out["image_url"] = same["image_url"]
                out["image_alt"] = f"Photo of {same['name']} (a Food.com recipe with the same name)"
                out["source_url"] = same["source_url"]
            ac = out.get("allergy_check") or {}
            base_ings = out.get("ingredients") if ac.get("substitutions") else query_ingredients
            related = _related(base_ings or query_ingredients, preference, cuisine, allergies)
            if related:
                out["related_recipe"] = related
    except Exception as e:  # enrichment must never break the existing chatbot
        print(f"Recipe enrichment failed: {e}")
        out.setdefault("nutrition", {"status": "unavailable", "reason": "Nutrition lookup failed."})
    return out


_SMALL_TALK = [
    (re.compile(r"^\s*(hi|hello|hey|hiya|namaste|good (morning|afternoon|evening))\b[\s!.,]*(there|nourish)?[\s!.]*$", re.I),
     "Hello! Tell me what ingredients you have or what you'd like to cook, and I'll suggest a recipe that fits your "
     "diet - with its nutrition. You can also open **Diet** in the sidebar for full meal plans."),
    (re.compile(r"^\s*(thanks|thank you|thx|ty|cheers|great|awesome|perfect|nice|cool|ok(ay)?|got it)\b[\s!.,a-z]*$", re.I),
     "You're welcome! Ask me for another recipe any time."),
    (re.compile(r"^\s*(bye|goodbye|see you|good night)\b", re.I), "Goodbye - happy cooking!"),
    (re.compile(r"^\s*(who are you|what are you|what can you do|help|how does this work|what is this)\b[\s?!.]*$", re.I),
     "I'm Nourish, a recipe assistant running on a fine-tuned small language model. Tell me your ingredients "
     "(e.g. \"paneer and tomatoes\") and I'll give you a recipe that respects your dietary preference, with "
     "ingredients, steps and nutrition per serving. For complete daily plans by goal or sport, open **Diet** in the sidebar."),
]
_FOOD_HINT = re.compile(r"\b(recipe|cook|make|have|with|using|dinner|lunch|breakfast|snack|meal|curry|pasta|rice|dal|"
                        r"paneer|chicken|egg|tofu|salad|soup)\b", re.I)


def small_talk_reply(message: str) -> Optional[str]:
    """Short conversational replies so that not every message becomes a recipe card."""
    text = (message or "").strip()
    if not text or len(text) > 80 or _FOOD_HINT.search(text):
        return None
    for pat, reply in _SMALL_TALK:
        if pat.search(text):
            return reply
    return None
