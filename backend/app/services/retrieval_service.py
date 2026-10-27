"""
retrieval_service.py
====================
Structured Recipe Knowledge Retrieval Service.
Searches the processed recipes dataset based on:
- Strict dietary compliance filter
- Cuisine match filter (using both cuisine and category columns)
- Ingredient overlap score (requires at least 1 matching ingredient)
- Popularity rating tie-breaker
Returns None if no relevant recipe matches constraints, avoiding unrelated random fallbacks.

Cuisine Mapping for UI-exposed cuisines (Indian / Italian / Continental):
- Indian: cuisine == 'Indian'
- Italian: detected from recipe name/category keywords (pasta, pizza, risotto, lasagna, etc.)
- Continental: European/Western style recipes from 'General' or 'American' cuisine bucket

Note: The Food.com dataset uses 'General' for most Western/European recipes,
so Italian and Continental are mapped via keyword matching on name+category.
"""

import sys
import os
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional

from backend.app.core.config import settings
from backend.app.services.formatting import format_duration, format_servings

# Cuisine keyword maps for categories not explicitly labeled
CUISINE_KEYWORD_MAP = {
    "italian": [
        "pasta", "spaghetti", "pizza", "risotto", "lasagna", "linguine",
        "fettuccine", "penne", "gnocchi", "focaccia", "calzone", "minestrone",
        "bruschetta", "tiramisu", "parmigiana", "carbonara", "bolognese",
        "marinara", "cannelloni", "ravioli", "arrabbiata", "frittata",
        "ribollita", "ossobuco", "polenta", "pecorino", "prosciutto"
    ],
    "continental": [
        "steak", "roast", "grilled", "baked", "casserole", "quiche",
        "crepe", "croissant", "baguette", "soufflé", "ratatouille",
        "coq au vin", "boeuf bourguignon", "potatoes au gratin",
        "pot roast", "beef stew", "lamb chops", "pork tenderloin",
        "chicken marsala", "chicken cordon bleu", "veal scallopini",
        "hollandaise", "béarnaise", "french onion", "bisque",
        "bread pudding", "custard", "shepherd's pie", "yorkshire pudding",
        "english muffin", "scones", "clafoutis", "crepes suzette"
    ]
}

# Supported UI cuisines
SUPPORTED_CUISINES = {"indian", "italian", "continental"}

class RecipeRetrievalService:
    def __init__(self, processed_csv_path: str = settings.PROCESSED_CSV_PATH):
        self.csv_path = processed_csv_path
        self.df = None
        self.is_loaded = False

    def load_dataset(self):
        if self.is_loaded:
            return
        if not os.path.exists(self.csv_path):
            print(f"Warning: Processed dataset not found at {self.csv_path}.")
            return

        print(f"Loading recipe retrieval index from {self.csv_path}...")
        self.df = pd.read_csv(self.csv_path)
        import json
        def parse_json(v):
            if isinstance(v, str):
                try: return json.loads(v)
                except: return []
            return v if isinstance(v, list) else []

        if 'ingredients' in self.df.columns and isinstance(self.df['ingredients'].iloc[0], str):
            self.df['ingredients'] = self.df['ingredients'].apply(parse_json)
        if 'instructions' in self.df.columns and isinstance(self.df['instructions'].iloc[0], str):
            self.df['instructions'] = self.df['instructions'].apply(parse_json)

        self.df['_name_lower'] = self.df['name'].str.lower().fillna('')
        self.df['_category_lower'] = self.df['tags'].astype(str).str.lower().fillna('') if 'tags' in self.df.columns else self.df['name'].str.lower().fillna('')
        self.df['_cuisine_lower'] = self.df['cuisine'].astype(str).str.lower().fillna('')
        # Precomputed once so each search is a few vectorised string checks instead of a Python loop
        self.df['_diet_lower'] = self.df['dietary_attribute'].astype(str).str.lower().str.strip()
        self.df['_ing_text'] = self.df['ingredients'].apply(
            lambda v: "|" + "|".join(str(x).lower().strip() for x in v) + "|" if isinstance(v, (list, np.ndarray)) else "")
        self.is_loaded = True
        print(f"Retrieval service initialized with {len(self.df):,} clean recipes.")

    def _apply_cuisine_filter(self, filtered: pd.DataFrame, cuisine_str: str) -> pd.DataFrame:
        """
        Apply cuisine filter. Handles dataset label mismatch:
        - Indian: matches cuisine == 'Indian' directly
        - Italian: no 'Italian' in cuisine column → keyword match on name/category
        - Continental: no 'Continental' in cuisine column → keyword match on name/category
        - General/All: no filtering
        """
        c = cuisine_str.lower().strip()

        if c == "indian":
            matches = filtered[filtered['_cuisine_lower'] == 'indian']
            if len(matches) > 0:
                return matches
            # Fallback: name contains indian cuisine keywords
            kw_mask = (
                filtered['_name_lower'].str.contains('curry|masala|dal|biryani|tikka|korma|samosa|chutney|chapati|naan|paneer', na=False) |
                filtered['_category_lower'].str.contains('indian|curry', na=False)
            )
            return filtered[kw_mask]

        elif c == "italian":
            # Dataset has no Italian cuisine label - use keyword matching
            keywords = "|".join(CUISINE_KEYWORD_MAP["italian"])
            kw_mask = (
                filtered['_name_lower'].str.contains(keywords, na=False) |
                filtered['_category_lower'].str.contains(keywords, na=False)
            )
            return filtered[kw_mask]

        elif c == "continental":
            # Continental = Western/European recipes (General + American buckets)
            # Filter out explicitly Indian/Asian cuisines first
            non_asian = filtered[~filtered['_cuisine_lower'].isin(['indian', 'chinese', 'thai', 'japanese', 'asian', 'mexican', 'greek', 'spanish'])]
            keywords = "|".join(CUISINE_KEYWORD_MAP["continental"])
            kw_mask = (
                non_asian['_name_lower'].str.contains(keywords, na=False) |
                non_asian['_category_lower'].str.contains('european|french|american|western|british|english', na=False)
            )
            matches = non_asian[kw_mask]
            if len(matches) > 0:
                return matches
            # Broader fallback: General cuisine non-Asian recipes
            return non_asian[non_asian['_cuisine_lower'].isin(['general', 'american'])]

        else:
            # Unknown cuisine: return as-is
            return filtered

    def search_recipes(
        self,
        query_ingredients: List[str],
        preference: str = "no_preference",
        cuisine: Optional[str] = None,
        top_k: int = 1
    ) -> List[Dict[str, Any]]:
        self.load_dataset()
        if self.df is None or len(self.df) == 0:
            return []

        filtered = self.df  # filtered below with boolean masks (no full copy of the 229K-row table)

        # 1. Strict Dietary Attribute Filter
        pref_str = preference.lower().strip() if preference else "no_preference"
        diet_col = filtered['_diet_lower']
        if pref_str == "vegan":
            filtered = filtered[diet_col == "vegan"]
        elif pref_str == "vegetarian":
            filtered = filtered[diet_col.isin(["vegan", "vegetarian"])]
        elif pref_str == "eggitarian":
            filtered = filtered[diet_col.isin(["vegan", "vegetarian", "eggitarian"])]

        if len(filtered) == 0:
            print(f"RETRIEVAL: No candidates found for preference '{pref_str}'")
            return []

        # 2. Cuisine Filter
        cuisine_label = "General"
        if cuisine and cuisine not in ["All", "General", "Any", ""]:
            c_lower = cuisine.lower().strip()
            cuisine_matches = self._apply_cuisine_filter(filtered, c_lower)
            if len(cuisine_matches) > 0:
                filtered = cuisine_matches
                cuisine_label = cuisine.capitalize()
            else:
                print(f"RETRIEVAL: No dataset match found for cuisine '{cuisine}' under preference '{pref_str}'")
                return []
        else:
            cuisine_label = cuisine.capitalize() if cuisine and cuisine not in ["All", "General", "Any", ""] else "General"

        # 3. Calculate Ingredient Overlap Match Score
        clean_query_ings = [ing.lower().strip() for ing in query_ingredients if ing.strip()]
        query_set = set(clean_query_ings)

        if query_set:
            # One point per query ingredient found in the recipe ("onion" matches "red onion"; a query
            # like "red onion" also matches a recipe's plain "onion" through its main word).
            text = filtered['_ing_text']
            score = pd.Series(0, index=filtered.index)
            for q in query_set:
                terms = [q] + [w for w in q.split() if len(w) > 3 and w != q]
                hit = pd.Series(False, index=filtered.index)
                for t in terms:
                    hit |= text.str.contains(t, regex=False)
                score += hit.astype(int)
            filtered = filtered.assign(match_score=score)
            # Require AT LEAST 1 matching ingredient
            filtered = filtered[filtered['match_score'] > 0]
            if len(filtered) == 0:
                print(f"RETRIEVAL: Zero ingredient overlap found for query ingredients: {query_ingredients}")
                return []

            if 'rating' in filtered.columns:
                filtered = filtered.sort_values(by=['match_score', 'rating'], ascending=[False, False])
            else:
                filtered = filtered.sort_values(by='match_score', ascending=False)
        else:
            if 'rating' in filtered.columns:
                filtered = filtered.sort_values(by='rating', ascending=False)

        top_results = filtered.head(top_k)

        results = []
        for _, row in top_results.iterrows():
            # Determine display cuisine label
            raw_cuisine = str(row.get('cuisine', 'General'))
            if cuisine and cuisine not in ["All", "General", "Any", ""]:
                display_cuisine = cuisine.capitalize()
            elif raw_cuisine and raw_cuisine != "General":
                display_cuisine = raw_cuisine
            else:
                display_cuisine = "General"

            prep_t = f"{row.get('minutes', 15)} mins" if 'minutes' in row else str(row.get('prep_time', '15 mins'))

            results.append({
                "recipe_id": str(row.get('recipe_id', row.get('id', ''))),
                "name": str(row['name']),
                "category": str(row.get('category', 'Main Dish')),
                "cuisine": display_cuisine,
                "dietary_attribute": str(row.get('dietary_attribute', 'no_preference')),
                "ingredients": list(row['ingredients']) if isinstance(row['ingredients'], (list, np.ndarray)) else [],
                "instructions": list(row['instructions']) if isinstance(row['instructions'], (list, np.ndarray)) else [],
                "prep_time": format_duration(str(prep_t)),
                "cook_time": format_duration(str(row.get('cook_time', '15 mins'))),
                "servings": format_servings(row.get('servings', 4)),
                "match_score": int(row.get('match_score', 0)),
                "rating": float(row.get('rating', 5.0))
            })

        print(f"RETRIEVAL SUCCESS: Found match '{results[0]['name']}' (Score: {results[0]['match_score']}, Diet: {results[0]['dietary_attribute']}, Cuisine: {results[0]['cuisine']})")
        return results

retrieval_service = RecipeRetrievalService()
