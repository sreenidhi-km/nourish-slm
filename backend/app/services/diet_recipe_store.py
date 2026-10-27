"""
diet_recipe_store.py
====================
Read-only access to data/processed/diet_recipes.db (built by scripts/build_diet_dataset.py).
All filtering and pagination happens here, in SQLite; the browser never receives the dataset.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from typing import Any, Dict, Iterable, List, Optional

from backend.app.core.config import settings

DIET_ALLOWED = {
    "vegan": ["vegan"],
    "vegetarian": ["vegan", "vegetarian"],
    "eggitarian": ["vegan", "vegetarian", "eggitarian"],
    "non_vegetarian": ["vegan", "vegetarian", "eggitarian", "non_vegetarian"],
    "no_preference": ["vegan", "vegetarian", "eggitarian", "non_vegetarian"],
}
ALLERGEN_KEYS = ["dairy", "egg", "peanut", "tree_nuts", "soy", "gluten", "fish", "shellfish", "sesame", "mustard"]
ALLERGEN_LABELS = {"dairy": "Dairy", "egg": "Egg", "peanut": "Peanut", "tree_nuts": "Tree nuts", "soy": "Soy",
                   "gluten": "Gluten (wheat/barley/rye)", "fish": "Fish", "shellfish": "Shellfish",
                   "sesame": "Sesame", "mustard": "Mustard"}
# Intolerances map onto allergen keys the recipes are tagged with
INTOLERANCE_TO_ALLERGEN = {"lactose": "dairy", "dairy": "dairy", "gluten": "gluten", "wheat": "gluten",
                           "egg": "egg", "soy": "soy", "nuts": "tree_nuts", "peanut": "peanut"}
DIET_LABELS = {"vegan": "Vegan", "vegetarian": "Vegetarian", "eggitarian": "Eggitarian",
               "non_vegetarian": "Non-Vegetarian", "no_preference": "No preference"}

SUMMARY_COLS = ("id, name, category, cuisines, diet, diet_verify, allergens, meal_types, focus_tags, image_url, ingredient_text, "
                "servings, serving_size_g, kcal, protein, carbs, fat, fiber, prep_min, cook_min, total_min, source_url")


_DIET_RANK = {"vegan": 0, "vegetarian": 1, "eggitarian": 2, "non_vegetarian": 3}
_ALLOWED = {"vegan": {"vegan"}, "vegetarian": {"vegan", "vegetarian"},
            "eggitarian": {"vegan", "vegetarian", "eggitarian"}}


def _recheck_diet(stored: str, ingredient_text: Optional[str], allergens: List[str]):
    """Re-classifies a recipe from its ingredient names with the current rules.

    The database labels were computed when it was built; rules added since (e.g. "feta" on its own is dairy)
    must still apply, so the stricter of the stored and the re-computed label is used."""
    if stored not in ("vegan", "vegetarian", "eggitarian") or not ingredient_text:
        return stored, allergens
    from backend.app.services.food_labels import classify_diet
    names = [n.strip() for n in ingredient_text.split("|") if n.strip()]
    diet, flags = classify_diet(names)
    if _DIET_RANK.get(diet, 0) <= _DIET_RANK.get(stored, 0):
        return stored, allergens
    extra = [a for a, f in (("dairy", flags.get("dairy")), ("egg", flags.get("egg"))) if f and a not in allergens]
    return diet, sorted(allergens + extra)


class RecipeStore:
    def __init__(self, path: Optional[str] = None):
        self.path = path or settings.DIET_DB_PATH
        self._local = threading.local()

    @property
    def available(self) -> bool:
        return os.path.exists(self.path)

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            if not self.available:
                raise FileNotFoundError(
                    f"Diet recipe database not found at {self.path}. Run: python scripts/build_diet_dataset.py")
            conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    # -- serialisation ---------------------------------------------------------------------
    @staticmethod
    def _split(v: str) -> List[str]:
        return [x for x in (v or "").split(",") if x]

    def to_summary(self, row: sqlite3.Row) -> Dict[str, Any]:
        verify = json.loads(row["diet_verify"] or "[]")
        diet, allergens = _recheck_diet(row["diet"], row["ingredient_text"], json.loads(row["allergens"] or "[]"))
        return {
            "id": row["id"], "name": row["name"], "category": row["category"],
            "cuisines": self._split(row["cuisines"]), "diet": diet,
            "diet_label": DIET_LABELS.get(diet, diet),
            "diet_verify": verify, "allergens": allergens,
            "meal_types": self._split(row["meal_types"]), "focus_tags": self._split(row["focus_tags"]),
            "image_url": row["image_url"], "servings": row["servings"], "serving_size_g": row["serving_size_g"],
            "nutrition_per_serving": {"kcal": row["kcal"], "protein": row["protein"], "carbs": row["carbs"],
                                      "fat": row["fat"], "fiber": row["fiber"]},
            "prep_min": row["prep_min"], "cook_min": row["cook_min"], "total_min": row["total_min"],
            "source_url": row["source_url"],
        }

    def to_full(self, row: sqlite3.Row) -> Dict[str, Any]:
        out = self.to_summary(row)
        out.update({
            "description": row["description"], "tags": json.loads(row["tags"] or "[]"),
            "images": json.loads(row["images"] or "[]"), "ingredients": json.loads(row["ingredients"] or "[]"),
            "ingredient_lines": json.loads(row["ingredient_lines"] or "[]"), "steps": json.loads(row["steps"] or "[]"),
            "nutrition_per_serving": {**out["nutrition_per_serving"], "sugar": row["sugar"], "sodium": row["sodium"],
                                      "sat_fat": row["sat_fat"]},
        })
        return out

    # -- queries ---------------------------------------------------------------------------
    def get(self, recipe_id: int) -> Optional[Dict[str, Any]]:
        row = self._conn().execute("SELECT * FROM recipes WHERE id = ?", (int(recipe_id),)).fetchone()
        return self.to_full(row) if row else None

    def lookup(self, recipe_id: int) -> Optional[Dict[str, Any]]:
        row = self._conn().execute("SELECT * FROM lookup WHERE id = ?", (int(recipe_id),)).fetchone()
        return dict(row) if row else None

    def find_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        nn = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower())).strip()
        if not nn:
            return None
        row = self._conn().execute("SELECT * FROM recipes WHERE name_norm = ? ORDER BY servings IS NULL LIMIT 1",
                                   (nn,)).fetchone()
        return self.to_full(row) if row else None

    def meta(self) -> Dict[str, str]:
        return {r["key"]: r["value"] for r in self._conn().execute("SELECT key, value FROM meta")}

    @staticmethod
    def _where(diet: Optional[str] = None, meal_type: Optional[str] = None, cuisine: Optional[str] = None,
               focus_any: Optional[Iterable[str]] = None, exclude_allergens: Optional[Iterable[str]] = None,
               dislikes: Optional[Iterable[str]] = None, include_ingredients: Optional[Iterable[str]] = None,
               q: Optional[str] = None, kcal_min: Optional[float] = None, kcal_max: Optional[float] = None,
               max_total_min: Optional[int] = None, exclude_ids: Optional[Iterable[int]] = None,
               require_servings: bool = False):
        clauses, params = [], []
        if diet:
            allowed = DIET_ALLOWED.get(diet, DIET_ALLOWED["no_preference"])
            clauses.append(f"diet IN ({','.join('?' * len(allowed))})")
            params += allowed
        if meal_type:
            clauses.append("meal_types LIKE ?")
            params.append(f"%,{meal_type},%")
        if cuisine and cuisine.lower() not in ("all", "any", "", "general"):
            clauses.append("cuisines LIKE ?")
            params.append(f"%,{cuisine.lower()},%")
        focus_any = [f for f in (focus_any or []) if f]
        if focus_any:
            clauses.append("(" + " OR ".join(["focus_tags LIKE ?"] * len(focus_any)) + ")")
            params += [f"%,{f},%" for f in focus_any]
        for a in exclude_allergens or []:
            clauses.append("allergens NOT LIKE ?")
            params.append(f'%"{a}"%')
        for d in dislikes or []:
            d = (d or "").strip().lower()
            if len(d) >= 3:
                clauses.append("ingredient_text NOT LIKE ?")
                params.append(f"%{d}%")
        for ing in include_ingredients or []:
            ing = (ing or "").strip().lower()
            if len(ing) >= 2:
                clauses.append("ingredient_text LIKE ?")
                params.append(f"%{ing}%")
        if q:
            clauses.append("(name LIKE ? OR ingredient_text LIKE ?)")
            params += [f"%{q.strip()}%", f"%{q.strip().lower()}%"]
        if kcal_min is not None:
            clauses.append("kcal >= ?")
            params.append(kcal_min)
        if kcal_max is not None:
            clauses.append("kcal <= ?")
            params.append(kcal_max)
        if max_total_min:
            clauses.append("total_min > 0 AND total_min <= ?")
            params.append(int(max_total_min))
        ids = [int(i) for i in (exclude_ids or [])]
        if ids:
            clauses.append(f"id NOT IN ({','.join('?' * len(ids))})")
            params += ids
        if require_servings:
            clauses.append("servings IS NOT NULL")
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    def search(self, page: int = 1, page_size: int = 12, order: str = "name", **filters) -> Dict[str, Any]:
        page = max(1, int(page))
        page_size = max(1, min(48, int(page_size)))
        where, params = self._where(**filters)
        conn = self._conn()
        total = conn.execute(f"SELECT COUNT(*) FROM recipes{where}", params).fetchone()[0]
        order_sql = {"name": "name", "protein": "protein DESC", "kcal": "kcal", "quick": "total_min",
                     "protein_density": "protein / kcal DESC"}.get(order, "name")
        rows = conn.execute(f"SELECT {SUMMARY_COLS} FROM recipes{where} ORDER BY {order_sql} LIMIT ? OFFSET ?",
                            params + [page_size, (page - 1) * page_size]).fetchall()
        items = [self.to_summary(r) for r in rows]
        return {"items": items, "total": total, "page": page, "page_size": page_size,
                "pages": (total + page_size - 1) // page_size}

    def candidates(self, seed: int = 1, limit: int = 250, **filters) -> List[Dict[str, Any]]:
        """Deterministic pseudo-random sample (seeded) of recipes matching the filters."""
        where, params = self._where(**filters)
        rows = self._conn().execute(
            f"SELECT * FROM recipes{where} ORDER BY ((id * ?) % 1000003) LIMIT ?",
            params + [int(seed) % 999983 + 7919, int(limit)]).fetchall()
        return [self.to_full(r) for r in rows]

    def count(self, **filters) -> int:
        where, params = self._where(**filters)
        return self._conn().execute(f"SELECT COUNT(*) FROM recipes{where}", params).fetchone()[0]


recipe_store = RecipeStore()


def verification_conflicts(recipe: Dict[str, Any], preference: str) -> List[Dict[str, Any]]:
    """Ingredients whose animal origin is uncertain for the given preference."""
    if preference in ("non_vegetarian", "no_preference", None, ""):
        return []
    out = [v for v in recipe.get("diet_verify", []) if preference in v.get("applies_to", [])]
    if preference in _ALLOWED and recipe.get("diet") not in _ALLOWED[preference]:
        out.append({"ingredient": recipe.get("name"), "applies_to": [preference],
                    "reason": f"contains ingredients that are not {preference} (re-checked from its ingredient list)"})
    return out
