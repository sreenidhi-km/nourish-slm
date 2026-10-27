"""
portion_estimator.py
====================
Approximate nutrition for recipes the fine-tuned model writes.

The model lists ingredient *names* without quantities, so an exact calculation is impossible.
Instead each ingredient gets a typical amount: the median amount per serving that real Food.com
recipes use (data/reference/typical_portions.json, built by scripts/build_typical_portions.py).
Those amounts are shown to the user as suggested quantities, and the nutrition per serving is
calculated from them with the USDA nutrient table. The result is clearly labelled as approximate.
"""

from __future__ import annotations

import json
import os
import re
from fractions import Fraction
from typing import Any, Dict, List, Optional

from backend.app.services.nutrition_service import (
    NUTRIENT_KEYS, normalize_ingredient_text, parse_quantity, usda_db, _round_nutrients, _singular,
)

_PORTIONS_PATH = os.environ.get(
    "TYPICAL_PORTIONS_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "reference", "typical_portions.json"),
)

# Common ingredients (mostly Indian pantry items) that are rare in Food.com, with typical grams per serving.
_FALLBACK_G_PER_SERVING = {
    "paneer": 50, "ghee": 5, "yogurt plain whole milk": 40, "lentils": 40, "moong dal": 40, "toor dal": 40,
    "chana dal": 40, "urad dal": 30, "masoor dal": 40, "rice": 60, "basmati rice": 60, "chickpeas": 80,
    "kidney beans": 70, "tofu": 80, "potato": 75, "cauliflower": 70, "okra": 60, "eggplant": 70,
    "chicken": 120, "mutton": 110, "fish": 110, "egg whole raw": 50, "coconut milk": 40,
    "whole wheat flour": 40, "chickpea flour": 25, "semolina": 30, "pasta": 60, "noodles": 60,
    "bread": 40, "spinach": 40, "peas": 30, "mushroom": 40, "cashew": 8, "almond": 8, "peanuts": 10,
    "coconut": 10, "gluten-free flour blend": 15, "rice flour": 15, "oat flour": 15, "flax eggs": 15,
    "pumpkin seeds": 8, "sunflower seed butter": 8, "coconut yogurt": 40, "coconut cream": 20, "oat milk": 60,
    "nutritional yeast": 3, "dairy-free cheese": 15, "soya chunks": 25, "jackfruit": 60, "seitan": 60,
}
# Condiments and sauces: a spoonful, not a main-ingredient amount
_CONDIMENT = re.compile(r"\b(sauce|tamari|aminos|manis|vinegar|ketchup|mustard|extract|essence|syrup|honey|juice)\b", re.I)
_MODIFIERS = re.compile(r"^(gluten[- ]free|dairy[- ]free|egg[- ]free|vegan|plant[- ]based|low[- ]sodium|reduced[- ]fat|"
                        r"unsweetened|sweetened|organic|amul|frozen|canned|cooked|raw|roasted|toasted|salted|unsalted)\s+", re.I)
_SPICE_HINT = re.compile(r"\b(powder|masala|seeds?|spice|cumin|turmeric|chili|chilli|cardamom|cloves?|cinnamon|saffron|"
                         r"pepper|paprika|oregano|thyme|basil|cilantro|coriander|mint|curry leaves|bay lea)", re.I)
_NEGLIGIBLE = re.compile(r"^(salt|water|ice|.*\bto taste\b.*|.*\bfor garnish\b.*)$")
_DEFAULT_G = 30.0      # unknown main ingredient
_SPICE_G = 0.8         # unknown spice / herb

_TABLE: Optional[Dict[str, Dict[str, Any]]] = None


def _table() -> Dict[str, Dict[str, Any]]:
    global _TABLE
    if _TABLE is None:
        try:
            with open(_PORTIONS_PATH) as f:
                _TABLE = json.load(f)["ingredients"]
        except (OSError, ValueError, KeyError):
            _TABLE = {}
    return _TABLE


def _lookup_exact(key: str) -> Optional[Dict[str, Any]]:
    t = _table()
    if key in t:
        return t[key]
    for variant in (key[:-1] if key.endswith("s") else key + "s", key[:-2] if key.endswith("es") else None):
        if variant and variant in t:
            return t[variant]
    return None


def _candidates(key: str) -> List[str]:
    """'unsweetened dried shredded coconut' -> itself, 'dried shredded coconut', 'shredded coconut', 'coconut'."""
    out, k = [key], key
    while _MODIFIERS.match(k):
        k = _MODIFIERS.sub("", k, count=1)
        out.append(k)
    words = k.split()
    out += [" ".join(words[i:]) for i in range(1, len(words))]
    return [c for c in dict.fromkeys(out) if c]


def _lookup(key: str) -> Optional[Dict[str, Any]]:
    for cand in _candidates(key):
        hit = _lookup_exact(cand)
        if hit:
            return hit
    return None


def _fallback_grams(key: str) -> Optional[float]:
    for cand in _candidates(key):
        if cand in _FALLBACK_G_PER_SERVING:
            return float(_FALLBACK_G_PER_SERVING[cand])
    return None


def is_known_food(name: str) -> bool:
    """True when `name` is an ingredient that real recipes use (or a common pantry item)."""
    key = normalize_ingredient_text(name)
    return bool(key) and (_lookup_exact(key) is not None or key in _FALLBACK_G_PER_SERVING)


def _nice_fraction(x: float) -> str:
    """0.75 -> '3/4', 1.5 -> '1 1/2' (rounded to the nearest quarter)."""
    q = Fraction(round(x * 4), 4)
    if q <= 0:
        q = Fraction(1, 4)
    whole, rem = divmod(q.numerator, q.denominator)
    rem_txt = f"{rem}/{q.denominator}" if rem else ""
    return " ".join(p for p in (str(whole) if whole else "", rem_txt) if p)


def _display_amount(name: str, entry: Optional[Dict[str, Any]], grams: float, servings: float,
                    spoon: bool = False) -> str:
    unit = (entry or {}).get("unit", "")
    qty = (entry or {}).get("qty_per_serving", 0) * servings
    if unit in ("tsp", "tbsp", "cup") and qty > 0:
        amount = _nice_fraction(qty)
        plural = "s" if unit == "cup" and Fraction(round(qty * 4), 4) > 1 else ""
        return f"{amount} {unit}{plural} {name}"
    if unit in ("clove", "count", "large", "medium", "small", "slice", "stalk", "sprig") and qty > 0:
        n = max(1, round(qty))
        if n == 1 and " " not in name and name.endswith("s") and not name.endswith("ss"):
            name = _singular(name)
        word = "" if unit == "count" else f"{unit}{'s' if n > 1 and unit in ('clove', 'slice', 'stalk', 'sprig') else ''} "
        return f"{n} {word}{name}"
    if "saffron" in name.lower():
        return f"a pinch of {name}"
    if grams < 3 or (spoon and grams < 40):
        tsp = grams / (2.5 if grams < 3 else 5.0)       # ~2.5 g per tsp of dried spice, ~5 g of a sauce or paste
        if tsp >= 3:
            return f"{_nice_fraction(tsp / 3)} tbsp {name}"
        return f"{_nice_fraction(max(tsp, 0.25))} tsp {name}"
    step = 5 if grams < 60 else (10 if grams < 250 else 25)
    return f"{int(max(step, round(grams / step) * step))} g {name}"


def estimate_with_typical_portions(ingredients: List[str], servings: Any) -> Dict[str, Any]:
    """Suggested amounts + approximate per-serving nutrition for ingredient names without quantities."""
    serv, _ = parse_quantity(servings)
    serv = serv if serv and serv > 0 else 4.0
    totals = {k: 0.0 for k in NUTRIENT_KEYS}
    fiber_known = True
    lines, assumed, not_counted = [], [], []
    for raw in ingredients:
        name = (raw or "").strip()
        if not name:
            continue
        key = normalize_ingredient_text(name)
        if "saffron" in name.lower():
            lines.append(f"a pinch of {name}")
            continue
        if _NEGLIGIBLE.match(key or name.lower()):
            lines.append(f"{name} (as needed)" if key in ("water", "ice") else f"{name} (to taste)")
            continue
        entry = _lookup(key)
        if entry:
            g_ps, basis = entry["g_per_serving"], f"median of {entry['recipes']:,} Food.com recipes"
        elif _fallback_grams(key) is not None:
            g_ps, basis = _fallback_grams(key), "typical serving"
        elif _CONDIMENT.search(name):
            g_ps, basis = 4.0, "typical condiment amount"
        elif re.search(r"\bpaste\b", name, re.I) and "tomato" not in name.lower():
            g_ps, basis = 4.0, "typical amount of a spice paste"
        elif _SPICE_HINT.search(name):
            g_ps, basis = _SPICE_G, "typical spice amount"
        else:
            g_ps, basis = _DEFAULT_G, "default amount"
        grams = g_ps * serv
        spoon = basis in ("typical spice amount", "typical condiment amount", "typical amount of a spice paste")
        lines.append(_display_amount(name, entry, grams, serv, spoon=spoon))
        match = None
        for cand in _candidates(key) if key else []:
            match = usda_db.match(cand)
            if match and match.get("food"):
                break
        if not match or not match.get("food"):
            not_counted.append(name)
            continue
        n = usda_db.nutrients_for(match["food"], grams)
        for k in NUTRIENT_KEYS:
            v = n.get(k)
            if v is None:
                if k == "fiber":
                    fiber_known = False
                continue
            totals[k] += v
        assumed.append({"ingredient": name, "grams_total": round(grams, 1), "basis": basis,
                        "usda": match["food"]["description"]})
    if not assumed:
        return {"status": "unavailable", "reason": "none of the ingredients could be matched to USDA nutrient data",
                "suggested_lines": lines}
    per = {k: totals[k] / serv for k in NUTRIENT_KEYS}
    if not fiber_known:
        per["fiber"] = None
    return {
        "status": "estimate",
        "approximate": True,
        "per": "serving",
        "values": _round_nutrients(per),
        "servings_assumed": serv,
        "basis": "typical amounts per serving from Food.com recipes, nutrient values from USDA FoodData Central",
        "source_label": "Approximate - based on typical ingredient amounts (Food.com) and USDA nutrient data",
        "assumed_amounts": assumed,
        "not_counted": not_counted,
        "suggested_lines": lines,
    }
