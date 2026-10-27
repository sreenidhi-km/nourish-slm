"""
build_typical_portions.py
=========================
Builds data/reference/typical_portions.json: for each common ingredient, how much of it a
Food.com recipe typically uses *per serving* (median grams, plus the most common kitchen unit).

The fine-tuned model writes ingredient names without quantities, so the chatbot uses this table to
(1) suggest amounts for each ingredient and (2) estimate the recipe's nutrition with the USDA data.
The values are medians over the 46K Food.com recipes in data/processed/diet_recipes.db, so they
reflect how real recipes use each ingredient - they are typical amounts, not exact ones.

Run (after scripts/build_diet_dataset.py):
    python scripts/build_typical_portions.py
"""

import json
import os
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.app.core.config import settings  # noqa: E402
from backend.app.services.nutrition_service import (  # noqa: E402
    normalize_ingredient_text, normalize_unit, parse_quantity, usda_db,
)

MIN_RECIPES = 8          # ignore ingredients seen in fewer recipes than this
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "reference", "typical_portions.json")


def main():
    con = sqlite3.connect(f"file:{settings.DIET_DB_PATH}?mode=ro", uri=True)
    grams_ps = defaultdict(list)          # key -> [grams per serving]
    units = defaultdict(Counter)          # key -> Counter(unit)
    unit_qty_ps = defaultdict(lambda: defaultdict(list))  # key -> unit -> [qty per serving]
    match_cache = {}
    rows = con.execute("SELECT ingredients, servings FROM recipes WHERE servings > 0").fetchall()
    for n, (ings_json, servings) in enumerate(rows):
        try:
            ings = json.loads(ings_json or "[]")
        except ValueError:
            continue
        for ing in ings:
            key = normalize_ingredient_text(ing.get("name", ""))
            if not key or len(key) < 3:
                continue
            qty, _ = parse_quantity(ing.get("quantity"))
            if not qty or qty <= 0:
                continue
            if key not in match_cache:
                match_cache[key] = usda_db.match(key)
            match = match_cache[key]
            if not match or not match.get("food"):
                continue
            unit = normalize_unit(ing.get("unit", "")) or "count"
            grams, _ = usda_db.grams_for(match["food"], qty, ing.get("unit", ""), ing.get("description", ""), key)
            if grams is None or grams <= 0:
                continue
            grams_ps[key].append(grams / servings)
            units[key][unit] += 1
            unit_qty_ps[key][unit].append(qty / servings)
        if n % 10000 == 0:
            print(f"  processed {n:,} / {len(rows):,} recipes")

    table = {}
    for key, vals in grams_ps.items():
        if len(vals) < MIN_RECIPES:
            continue
        unit, _ = units[key].most_common(1)[0]
        table[key] = {
            "g_per_serving": round(statistics.median(vals), 1),
            "unit": unit,
            "qty_per_serving": round(statistics.median(unit_qty_ps[key][unit]), 4),
            "recipes": len(vals),
        }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump({"source": "Median per-serving amounts across Food.com recipes (diet_recipes.db)",
                   "ingredients": dict(sorted(table.items()))}, f, indent=0, separators=(",", ":"))
    print(f"Wrote {len(table):,} ingredients to {os.path.normpath(OUT_PATH)}")


if __name__ == "__main__":
    main()
