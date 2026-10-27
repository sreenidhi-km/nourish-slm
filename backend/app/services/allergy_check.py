"""
allergy_check.py
================
Allergy checkpoint for the main Nourish chatbot.

Every recipe is checked against the allergies the user selected. Ingredients that contain one of
those allergens are swapped for a safe alternative (and the cooking steps are rewritten to match).
Anything that cannot be swapped is reported so the recipe card can show a clear warning.

Detection uses the same ingredient-name rules as the Diet section (food_labels.py), so it cannot
see hidden allergens in packaged products - the UI always tells users to check product labels.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

from backend.app.services.diet_recipe_store import ALLERGEN_KEYS, ALLERGEN_LABELS
from backend.app.services.food_labels import classify_diet, detect_allergens

# Ordered (pattern, replacement) pairs per allergen. Most specific phrases first.
# Replacements are plant based so they never break a vegetarian or vegan diet.
SUBSTITUTES: Dict[str, List[Tuple[str, str]]] = {
    "peanut": [
        (r"peanut butter", "sunflower seed butter"), (r"peanut oil", "sunflower oil"),
        (r"(roasted |salted )?(peanuts?|groundnuts?)", "roasted pumpkin seeds"),
    ],
    "tree_nuts": [
        (r"almond milk", ["oat milk", "rice milk"]), (r"almond (flour|meal)", ["oat flour", "rice flour"]), (r"cashew (cream|paste)", "sunflower seed paste"),
        (r"nutella", "sunflower seed butter"), (r"marzipan", "sunflower seed paste"),
        (r"(almond|cashew|walnut|pecan|pistachio|hazelnut|macadamia|mixed nut|nut) (butter|spread)", "sunflower seed butter"),
        (r"(almonds?|cashews?|walnuts?|pecans?|pistachios?|hazelnuts?|macadamias?|brazil nuts?|pine nuts?)",
         "pumpkin seeds"),
    ],
    "dairy": [
        (r"(heavy |whipping |fresh |sour )?cream cheese", "dairy-free cream cheese"),
        (r"(heavy |whipping |fresh |sour )?cream", "coconut cream"), (r"buttermilk", "oat milk with lemon juice"),
        (r"(clarified butter|ghee)", "vegetable oil"), (r"butter", "vegetable oil"),
        (r"(greek )?(yogh?urt|curd|dahi)", "coconut yogurt"), (r"paneer( cheese)?", ["firm tofu", "chickpeas"]),
        (r"(?:(?:parmesan|cheddar|mozzarella|ricotta|feta|cottage|swiss|goat|cream) )?cheese", ["dairy-free cheese", "nutritional yeast"]),
        (r"(condensed|evaporated|whole|skim|low-fat)? ?milk", ["oat milk", "rice milk"]), (r"whey", "pea protein"),
    ],
    "egg": [
        (r"mayonnaise|mayo", "egg-free mayonnaise"), (r"egg noodles", "rice noodles"),
        (r"(egg whites?|egg yolks?|eggs?)", "flax eggs"),
    ],
    "gluten": [
        (r"soy sauce", ["tamari (gluten-free soy sauce)", "coconut aminos"]),
        (r"(kecap|ketjap) manis", ["gluten-free tamari with jaggery", "coconut aminos with jaggery"]),
        (r"(teriyaki|hoisin)( sauce)?", ["gluten-free tamari", "coconut aminos"]),
        (r"(hokkien|udon|ramen|soba)( noodles)?", "rice noodles"),
        (r"(all[- ]purpose |plain |whole wheat |wheat |self[- ]raising |bread )?flour|maida|atta", "gluten-free flour blend"),
        (r"(bread ?crumbs|panko)", "gluten-free breadcrumbs"), (r"bread", "gluten-free bread"),
        (r"(spaghetti|penne|macaroni|fettuccine|linguine|lasagna|orzo|pasta)", "gluten-free pasta"),
        (r"(noodles|vermicelli)", "rice noodles"), (r"(couscous|bulgh?ur|farro|barley|spelt)", "quinoa"),
        (r"(semolina|sooji|suji|rava)", "rice rava"), (r"(roti|chapati|naan|pita|tortillas?)", "jowar roti"),
        (r"seitan", "chickpeas"), (r"crackers?", "rice crackers"),
    ],
    "soy": [
        (r"(kecap|ketjap) manis", "coconut aminos with jaggery"), (r"(teriyaki|hoisin)( sauce)?", "coconut aminos"),
        (r"black bean sauce", "coconut aminos with garlic"),
        (r"(soy sauce|tamari)", "coconut aminos"), (r"(soy ?milk|soya milk)", ["oat milk", "rice milk"]),
        (r"(firm |silken |extra firm )?tofu", ["chickpeas", "paneer"]), (r"tempeh", "chickpeas"), (r"edamame", "green peas"),
        (r"miso", "chickpea miso"), (r"(textured vegetable protein|tvp)", "lentils"),
    ],
    "fish": [
        (r"fish sauce", ["coconut aminos", "soy sauce"]),
        (r"(salmon|tuna|cod|tilapia|trout|mackerel|sardines?|anchov(y|ies)|halibut|haddock|snapper|fish)( fillets?)?",
         "chicken breast"),
    ],
    "shellfish": [
        (r"(shrimps?|prawns?|crab(meat)?|lobster|scallops?|mussels?|clams?|oysters?|squid|calamari|crayfish|crawfish)",
         "chicken"),
    ],
    "sesame": [
        (r"sesame oil", "sunflower oil"), (r"tahini", "sunflower seed butter"), (r"(sesame seeds?|til)", "pumpkin seeds"),
    ],
    "mustard": [
        (r"mustard oil", "vegetable oil"), (r"mustard seeds?", "cumin seeds"), (r"(dijon |yellow )?mustard", "lemon juice"),
    ],
}
_COMPILED = {k: [(re.compile(r"\b" + p + r"\b", re.I), [r] if isinstance(r, str) else r) for p, r in v]
             for k, v in SUBSTITUTES.items()}
_PRIORITY = {pat.pattern: i for v in _COMPILED.values() for i, (pat, _) in enumerate(v)}

# Aliases users (or the frontend) may send
_ALIASES = {"nuts": "tree_nuts", "tree nuts": "tree_nuts", "tree_nut": "tree_nuts", "peanuts": "peanut",
            "milk": "dairy", "lactose": "dairy", "eggs": "egg", "wheat": "gluten", "shellfish": "shellfish",
            "crustacean": "shellfish", "soya": "soy"}

NOTE = "Allergens are detected from ingredient names. Always check the labels of packaged products."


def normalize_allergies(values: Iterable[Any]) -> List[str]:
    out = []
    for v in values or []:
        k = str(v).strip().lower().replace("-", "_")
        k = _ALIASES.get(k, _ALIASES.get(k.replace("_", " "), k))
        if k in ALLERGEN_KEYS and k not in out:
            out.append(k)
    return out


def ingredient_allergens(ingredient: str) -> List[str]:
    _, flags = classify_diet([ingredient])
    return detect_allergens([ingredient], flags)


def _rewrite_steps(steps: List[str], swaps: List[Tuple["re.Pattern", str]], title_case: bool = False) -> List[str]:
    """Replaces swapped ingredients in the cooking steps in a single pass, so a replacement is never
    replaced again ("peanut butter" -> "sunflower seed butter" must not then lose its "butter")."""
    if not swaps:
        return list(steps)
    seen, parts, reps = set(), [], []
    # specific phrases ("almond milk") must be tried before general ones ("almonds?")
    for pat, rep in sorted(swaps, key=lambda t: _PRIORITY.get(t[0].pattern, 99)):
        if pat.pattern in seen:
            continue
        seen.add(pat.pattern)
        parts.append(f"(?P<g{len(reps)}>{pat.pattern})")
        reps.append(rep)
    combined = re.compile("|".join(parts), re.I)

    def _sub(m):
        for i, rep in enumerate(reps):
            if m.group(f"g{i}") is not None:
                return rep.title() if title_case else rep
        return m.group(0)
    return [combined.sub(_sub, step) for step in steps]


def _pick_replacement(ing: str, pat: "re.Pattern", options: List[str], allergies: List[str]) -> Tuple[str, str]:
    """First replacement that does not bring in another of the user's allergens -> (new ingredient, replacement)."""
    for rep in options:
        cand = pat.sub(rep, ing, count=1)
        if not set(ingredient_allergens(cand)) & set(allergies):
            return cand, rep
    return pat.sub(options[0], ing, count=1), options[0]


def apply_allergy_check(recipe: Dict[str, Any], allergies: Iterable[str]) -> Dict[str, Any]:
    """Returns a copy of `recipe` with allergen ingredients swapped and an `allergy_check` report attached."""
    allergies = normalize_allergies(allergies)
    out = dict(recipe)
    if not allergies:
        return out
    ingredients = list(out.get("ingredients") or [])
    original = list(ingredients)
    swaps: List[Tuple["re.Pattern", str]] = []   # (pattern that matched, replacement used)
    reasons: Dict[int, List[str]] = {}
    for _ in range(3):  # a swap may still contain another of the user's allergens
        changed = False
        for idx, ing in enumerate(ingredients):
            for allergen in [a for a in ingredient_allergens(ing) if a in allergies]:
                for pat, options in _COMPILED.get(allergen, []):
                    m = pat.search(ing)
                    if not m:
                        continue
                    new_ing, rep = _pick_replacement(ing, pat, options, allergies)
                    if new_ing == ing:
                        continue
                    swaps.append((pat, rep))
                    reasons.setdefault(idx, []).append(ALLERGEN_LABELS.get(allergen, allergen))
                    ingredients[idx] = ing = new_ing
                    changed = True
                    break
        if not changed:
            break
    substitutions = [{"ingredient": original[i], "replacement": ingredients[i], "allergen": ", ".join(dict.fromkeys(r))}
                     for i, r in sorted(reasons.items()) if original[i] != ingredients[i]]
    remaining = []
    for ing in ingredients:
        hits = [a for a in ingredient_allergens(ing) if a in allergies]
        if hits:
            remaining.append({"ingredient": ing, "allergens": [ALLERGEN_LABELS.get(a, a) for a in hits]})
    out["ingredients"] = ingredients
    out["instructions"] = _rewrite_steps(list(out.get("instructions") or []), swaps)
    if out.get("title") and swaps:
        title = out["title"]
        words = [w for w in re.findall(r"[A-Za-z]+", title) if len(w) > 3]
        is_title_case = bool(words) and sum(w[0].isupper() for w in words) >= len(words) / 2
        out["title"] = _rewrite_steps([title], swaps, title_case=is_title_case)[0]
    out["allergy_check"] = {
        "checked": [ALLERGEN_LABELS.get(a, a) for a in allergies],
        "checked_keys": allergies,
        "passed": not remaining,
        "substitutions": substitutions,
        "remaining": remaining,
        "note": NOTE,
    }
    return out


def allergens_in_text(ingredients: List[str], allergies: Iterable[str]) -> List[str]:
    """Allergens from `allergies` that appear in the user's own ingredient list."""
    allergies = normalize_allergies(allergies)
    found = []
    for ing in ingredients:
        for a in ingredient_allergens(ing):
            if a in allergies and ALLERGEN_LABELS.get(a, a) not in found:
                found.append(ALLERGEN_LABELS.get(a, a))
    return found
