"""
nutrition_service.py
====================
One shared nutrition engine for the whole app (general chatbot, Diet plans, diet assistants
and the "Check My Diet" assessment). The frontend never calculates nutrition itself.

Two kinds of numbers exist and are always labelled:

* ``source``   - per-serving values published with the Food.com recipe (verified source data),
                 scaled linearly when the user eats more or fewer servings.
* ``estimate`` - ingredient-level calculations from USDA FoodData Central (SR Legacy, plus a
                 few FNDDS / branded records), used when the user changes ingredients or
                 quantities. Only computed when the ingredient can be matched to a USDA food
                 AND its quantity converted to grams; otherwise the value is reported as
                 unavailable instead of being guessed.
"""

from __future__ import annotations

import json
import os
import re
import threading
from fractions import Fraction
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.config import settings

NUTRIENT_KEYS = ("kcal", "protein", "carbs", "fat", "fiber")

# ----------------------------------------------------------------------------------------------
# Quantity and unit parsing
# ----------------------------------------------------------------------------------------------
_UNICODE_FRACTIONS = {"½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4", "⅛": "1/8", "⅜": "3/8",
                      "⅝": "5/8", "⅞": "7/8", "⅕": "1/5"}

UNIT_ALIASES = {
    "g": "g", "gram": "g", "grams": "g", "gm": "g", "gms": "g", "gr": "g",
    "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg",
    "mg": "mg",
    "oz": "oz", "ounce": "oz", "ounces": "oz",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    "ml": "ml", "milliliter": "ml", "milliliters": "ml", "millilitre": "ml", "millilitres": "ml", "cc": "ml",
    "l": "l", "liter": "l", "liters": "l", "litre": "l", "litres": "l",
    "tsp": "tsp", "teaspoon": "tsp", "teaspoons": "tsp", "t": "tsp",
    "tbsp": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp", "tbs": "tbsp", "tbl": "tbsp", "tbsps": "tbsp",
    "cup": "cup", "cups": "cup", "c": "cup",
    "fl oz": "fl oz", "fluid ounce": "fl oz", "fluid ounces": "fl oz",
    "pint": "pint", "pints": "pint", "quart": "quart", "quarts": "quart", "gallon": "gallon", "gallons": "gallon",
    "pinch": "pinch", "pinches": "pinch", "dash": "dash", "dashes": "dash",
    "": "count", "whole": "count", "piece": "count", "pieces": "count", "each": "count", "item": "count",
    "large": "large", "big": "large", "medium": "medium", "small": "small",
    "clove": "clove", "cloves": "clove", "slice": "slice", "slices": "slice",
    "stalk": "stalk", "stalks": "stalk", "rib": "stalk", "ribs": "stalk",
    "sprig": "sprig", "sprigs": "sprig", "head": "head", "heads": "head", "ear": "ear", "ears": "ear",
    "stick": "stick", "sticks": "stick", "leaf": "leaf", "leaves": "leaf", "bunch": "bunch", "bunches": "bunch",
    "can": "can", "cans": "can", "package": "package", "packages": "package", "pkg": "package",
    "jar": "jar", "jars": "jar", "box": "box", "boxes": "box", "bag": "bag", "bags": "bag",
    "container": "container", "containers": "container", "packet": "package", "packets": "package",
    "envelope": "package", "envelopes": "package", "bottle": "bottle", "bottles": "bottle",
    "scoop": "scoop", "scoops": "scoop",
}
MASS_G = {"g": 1.0, "kg": 1000.0, "mg": 0.001, "oz": 28.3495, "lb": 453.592}
VOLUME_ML = {"ml": 1.0, "l": 1000.0, "tsp": 4.92892, "tbsp": 14.7868, "cup": 236.588, "fl oz": 29.5735,
             "pint": 473.176, "quart": 946.353, "gallon": 3785.41,
             # culinary conventions: pinch = 1/16 tsp, dash = 1/8 tsp
             "pinch": 4.92892 / 16, "dash": 4.92892 / 8}
COUNT_UNITS = {"count", "large", "medium", "small", "clove", "slice", "stalk", "sprig", "head", "ear", "stick",
               "leaf", "bunch", "scoop"}
PACKAGE_UNITS = {"can", "package", "jar", "box", "bag", "container", "bottle"}

# Units offered in the plan editor
EDITOR_UNITS = ["g", "kg", "ml", "l", "cup", "tbsp", "tsp", "oz", "lb", "count", "slice", "clove", "large",
                "medium", "small"]


def parse_quantity(text: Any) -> Tuple[Optional[float], bool]:
    """'1 1/2' -> 1.5, '1/2-1' -> 0.75 (range midpoint, flagged), '' -> None."""
    if text is None:
        return None, False
    if isinstance(text, (int, float)):
        return float(text), False
    s = str(text).strip().lower()
    for k, v in _UNICODE_FRACTIONS.items():
        s = s.replace(k, " " + v)
    s = s.replace("–", "-").replace(" to ", "-")
    if not s:
        return None, False

    def one(part: str) -> Optional[float]:
        part = part.strip()
        if not part:
            return None
        total = 0.0
        for tok in part.split():
            try:
                total += float(Fraction(tok))
            except (ValueError, ZeroDivisionError):
                return None
        return total

    if "-" in s:
        a, _, b = s.partition("-")
        va, vb = one(a), one(b)
        if va is not None and vb is not None and vb >= va:
            return (va + vb) / 2.0, True
        return va if va is not None else vb, False
    return one(s), False


def normalize_unit(unit: Any) -> str:
    u = (str(unit or "")).strip().lower().rstrip(".")
    return UNIT_ALIASES.get(u, u)


# ----------------------------------------------------------------------------------------------
# Ingredient name normalisation
# ----------------------------------------------------------------------------------------------
_DROP_WORDS = {
    "fresh", "freshly", "chopped", "finely", "roughly", "coarsely", "minced", "diced", "sliced", "thinly", "grated",
    "shredded", "crushed", "peeled", "seeded", "deseeded", "cubed", "halved", "quartered", "softened", "melted",
    "beaten", "lightly", "packed", "firmly", "organic", "large", "small", "medium", "extra", "about", "optional",
    "to", "taste", "for", "garnish", "serving", "of", "the", "a", "an", "and", "or", "into", "pieces", "piece",
    "cut", "cubes", "trimmed", "rinsed", "drained", "washed", "cleaned", "divided", "plus", "more", "needed",
    "room", "temperature", "cold", "warm", "hot", "boiling", "good", "quality", "best", "favorite", "your",
    "homemade", "store", "bought", "fine", "thick", "thin", "bite", "sized", "size", "inch", "inches", "cm",
    "approx", "approximately", "few", "some", "handful", "julienned", "torn", "pitted", "zested", "juiced",
    "uncooked", "dry", "dried_", "heaping", "level", "scant",
}
_SPICE_GROUND_RE = re.compile(r"\bground\s+(?=(cumin|coriander|cinnamon|ginger|nutmeg|cloves?|cardamom|turmeric|"
                              r"pepper|black pepper|white pepper|allspice|mustard|cayenne|paprika|fennel|mace|sage|"
                              r"thyme|flaxseed|flax|almonds?)\b)")
_SYNONYMS = {
    "curd": "yogurt plain whole milk", "curds": "yogurt plain whole milk", "dahi": "yogurt plain whole milk",
    "chick peas": "chickpeas", "garbanzo beans": "chickpeas", "garbanzos": "chickpeas", "chana": "chickpeas",
    "kabuli chana": "chickpeas", "rajma": "kidney beans", "atta": "whole wheat flour", "maida": "all purpose flour",
    "besan": "chickpea flour", "gram flour": "chickpea flour", "sooji": "semolina", "suji": "semolina",
    "rava": "semolina", "jeera": "cumin", "haldi": "turmeric", "dhania": "coriander", "dhaniya": "coriander",
    "methi": "fenugreek", "palak": "spinach", "aloo": "potato", "gobi": "cauliflower", "bhindi": "okra",
    "baingan": "eggplant", "brinjal": "eggplant", "aubergine": "eggplant", "capsicum": "bell pepper",
    "coriander leaves": "cilantro", "spring onion": "green onion", "spring onions": "green onions",
    "scallion": "green onion", "scallions": "green onions", "courgette": "zucchini", "pyaz": "onion",
    "pyaaz": "onion", "tamatar": "tomato", "adrak": "ginger", "lehsun": "garlic", "lasun": "garlic",
    "chawal": "rice", "dal": "lentils", "daal": "lentils", "dhal": "lentils", "moong": "moong dal",
    "confectioners sugar": "powdered sugar", "icing sugar": "powdered sugar", "caster sugar": "granulated sugar",
    "white sugar": "granulated sugar", "plain flour": "all purpose flour", "all-purpose flour": "all purpose flour",
    "flour": "all purpose flour", "cornflour": "cornstarch", "corn flour": "cornstarch",
    "evoo": "olive oil", "extra virgin olive oil": "olive oil", "extra-virgin olive oil": "olive oil",
    "canola oil": "canola oil", "vegetable oil": "vegetable oil", "cooking oil": "vegetable oil", "oil": "vegetable oil",
    "egg": "egg whole raw", "eggs": "egg whole raw", "egg whites": "egg white raw", "egg white": "egg white raw",
    "egg yolks": "egg yolk raw", "egg yolk": "egg yolk raw", "soya milk": "soy milk", "soymilk": "soy milk",
    "panir": "paneer", "cottage cheese": "cottage cheese", "salt and pepper": "salt", "salt pepper": "salt",
    "ice": "water", "ice cubes": "water", "ice cube": "water", "turmeric powder": "turmeric",
    "jeera powder": "cumin", "dhaniya powder": "coriander", "dhania powder": "coriander", "chilli powder": "chili powder",
    "red chilli powder": "chili powder", "green chillies": "green chilies", "green chilli": "green chili",
}


def normalize_ingredient_text(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = s.split(",")[0]
    s = re.sub(r"\bor\b.*$", "", s)  # "butter or margarine" -> "butter"
    s = _SPICE_GROUND_RE.sub("", s)
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z\s\-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s in _SYNONYMS:
        return _SYNONYMS[s]
    words = [w for w in s.split() if w not in _DROP_WORDS]
    s = " ".join(words)
    return _SYNONYMS.get(s, s)


def _singular(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith(("oes", "ches", "shes", "sses")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def _tokens(s: str) -> List[str]:
    return [_singular(t) for t in re.findall(r"[a-z]+", s.lower())]


# Curated matches for frequent recipe ingredients. Values are exact USDA descriptions; the
# loader resolves them to fdc_ids and ignores (and reports) any that do not exist.
CURATED_MATCHES: Dict[str, str] = {
    "butter": "Butter, salted", "unsalted butter": "Butter, without salt", "salted butter": "Butter, salted",
    "ghee": "Butter, Clarified butter (ghee)", "clarified butter": "Butter, Clarified butter (ghee)",
    "granulated sugar": "Sugars, granulated", "sugar": "Sugars, granulated", "brown sugar": "Sugars, brown",
    "light brown sugar": "Sugars, brown", "dark brown sugar": "Sugars, brown", "powdered sugar": "Sugars, powdered",
    "honey": "Honey", "maple syrup": "Syrups, maple",
    "all purpose flour": "Wheat flour, white, all-purpose, enriched, bleached",
    "whole wheat flour": "Wheat flour, whole-grain (Includes foods for USDA's Food Distribution Program)", "bread flour": "Wheat flour, white, bread, enriched",
    "chickpea flour": "Chickpea flour (besan)", "semolina": "Semolina, unenriched", "cornstarch": "Cornstarch",
    "olive oil": "Oil, olive, salad or cooking", "vegetable oil": "Oil, vegetable, soybean, refined",
    "canola oil": "Oil, canola", "coconut oil": "Oil, coconut", "sesame oil": "Oil, sesame, salad or cooking",
    "peanut oil": "Oil, peanut, salad or cooking", "sunflower oil": "Oil, sunflower, linoleic, (approx. 65%)",
    "milk": "Milk, whole, 3.25% milkfat, with added vitamin D", "whole milk": "Milk, whole, 3.25% milkfat, with added vitamin D",
    "skim milk": "Milk, nonfat, fluid, with added vitamin A and vitamin D (fat free or skim)",
    "low fat milk": "Milk, lowfat, fluid, 1% milkfat, with added vitamin A and vitamin D",
    "soy milk": "Soymilk (all flavors), unsweetened, with added calcium, vitamins A and D",
    "almond milk": "Beverages, almond milk, unsweetened, shelf stable",
    "coconut milk": "Nuts, coconut milk, canned (liquid expressed from grated meat and water)",
    "heavy cream": "Cream, fluid, heavy whipping", "whipping cream": "Cream, fluid, heavy whipping",
    "heavy whipping cream": "Cream, fluid, heavy whipping", "sour cream": "Cream, sour, cultured",
    "cream cheese": "Cheese, cream", "cheddar cheese": "Cheese, cheddar (Includes foods for USDA's Food Distribution Program)", "sharp cheddar cheese": "Cheese, cheddar (Includes foods for USDA's Food Distribution Program)",
    "mozzarella cheese": "Cheese, mozzarella, whole milk", "parmesan cheese": "Cheese, parmesan, grated",
    "feta cheese": "Cheese, feta", "ricotta cheese": "Cheese, ricotta, whole milk",
    "cottage cheese": "Cheese, cottage, creamed, large or small curd", "swiss cheese": "Cheese, swiss",
    "yogurt": "Yogurt, plain, whole milk", "plain yogurt": "Yogurt, plain, whole milk",
    "yogurt plain whole milk": "Yogurt, plain, whole milk", "greek yogurt": "Yogurt, Greek, plain, nonfat (Includes foods for USDA's Food Distribution Program)",
    "egg whole raw": "Egg, whole, raw, fresh", "egg white raw": "Egg, white, raw, fresh",
    "egg yolk raw": "Egg, yolk, raw, fresh",
    "onion": "Onions, raw", "red onion": "Onions, raw", "yellow onion": "Onions, raw", "white onion": "Onions, raw",
    "green onion": "Onions, spring or scallions (includes tops and bulb), raw",
    "garlic": "Garlic, raw", "garlic clove": "Garlic, raw", "ginger": "Ginger root, raw",
    "tomato": "Tomatoes, red, ripe, raw, year round average", "cherry tomato": "Tomatoes, red, ripe, raw, year round average",
    "potato": "Potatoes, flesh and skin, raw", "sweet potato": "Sweet potato, raw, unprepared (Includes foods for USDA's Food Distribution Program)",
    "carrot": "Carrots, raw", "celery": "Celery, raw", "spinach": "Spinach, raw", "cauliflower": "Cauliflower, raw",
    "broccoli": "Broccoli, raw", "cabbage": "Cabbage, raw", "cucumber": "Cucumber, with peel, raw",
    "zucchini": "Squash, summer, zucchini, includes skin, raw", "eggplant": "Eggplant, raw", "okra": "Okra, raw",
    "bell pepper": "Peppers, sweet, green, raw", "green bell pepper": "Peppers, sweet, green, raw",
    "red bell pepper": "Peppers, sweet, red, raw", "mushroom": "Mushrooms, white, raw", "peas": "Peas, green, raw",
    "frozen peas": "Peas, green, frozen, unprepared (Includes foods for USDA's Food Distribution Program)", "green beans": "Beans, snap, green, raw", "corn": "Corn, sweet, yellow, raw",
    "lettuce": "Lettuce, cos or romaine, raw", "kale": "Kale, raw", "avocado": "Avocados, raw, all commercial varieties",
    "lemon juice": "Lemon juice, raw", "lime juice": "Lime juice, raw", "lemon": "Lemons, raw, without peel",
    "lime": "Limes, raw", "banana": "Bananas, raw", "apple": "Apples, raw, with skin (Includes foods for USDA's Food Distribution Program)",
    "orange": "Oranges, raw, all commercial varieties", "mango": "Mangos, raw", "blueberries": "Blueberries, raw",
    "blueberry": "Blueberries, raw", "strawberry": "Strawberries, raw", "raisin": "Raisins, dark, seedless (Includes foods for USDA's Food Distribution Program)",
    "date": "Dates, medjool", "cilantro": "Coriander (cilantro) leaves, raw", "parsley": "Parsley, fresh",
    "basil": "Basil, fresh", "mint": "Spearmint, fresh",
    "rice": "Rice, white, long-grain, regular, raw, enriched", "basmati rice": "Rice, white, long-grain, regular, raw, enriched",
    "white rice": "Rice, white, long-grain, regular, raw, enriched", "long grain rice": "Rice, white, long-grain, regular, raw, enriched",
    "brown rice": "Rice, brown, long-grain, raw (Includes foods for USDA's Food Distribution Program)", "cooked rice": "Rice, white, long-grain, regular, enriched, cooked",
    "rolled oats": "Oats (Includes foods for USDA's Food Distribution Program)", "oats": "Oats (Includes foods for USDA's Food Distribution Program)",
    "old fashioned oats": "Oats (Includes foods for USDA's Food Distribution Program)",
    "quinoa": "Quinoa, uncooked", "pasta": "Pasta, dry, enriched", "spaghetti": "Pasta, dry, enriched",
    "penne": "Pasta, dry, enriched", "macaroni": "Pasta, dry, enriched", "egg noodles": "Noodles, egg, dry, enriched",
    "bread": "Bread, whole-wheat, commercially prepared", "whole wheat bread": "Bread, whole-wheat, commercially prepared",
    "white bread": "Bread, white, commercially prepared (includes soft bread crumbs)",
    "tortilla": "Tortillas, ready-to-bake or -fry, flour, refrigerated", "flour tortilla": "Tortillas, ready-to-bake or -fry, flour, refrigerated",
    "corn tortilla": "Tortillas, ready-to-bake or -fry, corn", "roti": "Bread, chapati or roti, plain, commercially prepared",
    "chapati": "Bread, chapati or roti, plain, commercially prepared", "naan": "Bread, naan, plain, commercially prepared, refrigerated",
    "lentils": "Lentils, raw", "lentil": "Lentils, raw", "red lentils": "Lentils, raw",
    "chickpeas": "Chickpeas (garbanzo beans, bengal gram), mature seeds, canned, drained solids",
    "black beans": "Beans, black, mature seeds, canned, low sodium",
    "kidney beans": "Beans, kidney, red, mature seeds, canned, drained solids",
    "tofu": "Tofu, raw, firm, prepared with calcium sulfate", "firm tofu": "Tofu, raw, firm, prepared with calcium sulfate",
    "extra firm tofu": "Tofu, raw, firm, prepared with calcium sulfate", "silken tofu": "MORI-NU, Tofu, silken, firm",
    "tempeh": "Tempeh", "seitan": "Vital wheat gluten", "edamame": "Edamame, frozen, unprepared",
    "peanut butter": "Peanut butter, smooth style, without salt", "peanuts": "Peanuts, all types, raw",
    "peanut": "Peanuts, all types, raw", "almonds": "Nuts, almonds", "almond": "Nuts, almonds",
    "walnuts": "Nuts, walnuts, english", "walnut": "Nuts, walnuts, english", "cashews": "Nuts, cashew nuts, raw",
    "cashew": "Nuts, cashew nuts, raw", "pecans": "Nuts, pecans", "chia seeds": "Seeds, chia seeds, dried",
    "flax seeds": "Seeds, flaxseed", "flaxseed": "Seeds, flaxseed", "sesame seeds": "Seeds, sesame seeds, whole, dried",
    "pumpkin seeds": "Seeds, pumpkin and squash seed kernels, dried", "sunflower seeds": "Seeds, sunflower seed kernels, dried",
    "chicken breast": "Chicken, broiler or fryers, breast, skinless, boneless, meat only, raw",
    "boneless skinless chicken breast": "Chicken, broiler or fryers, breast, skinless, boneless, meat only, raw",
    "boneless skinless chicken breasts": "Chicken, broiler or fryers, breast, skinless, boneless, meat only, raw",
    "chicken breasts": "Chicken, broiler or fryers, breast, skinless, boneless, meat only, raw",
    "chicken thigh": "Chicken, broilers or fryers, dark meat, thigh, meat only, raw",
    "chicken": "Chicken, broilers or fryers, meat only, raw", "ground beef": "Beef, ground, 85% lean meat / 15% fat, raw (Includes foods for USDA's Food Distribution Program)",
    "lean ground beef": "Beef, ground, 90% lean meat / 10% fat, raw", "ground turkey": "Turkey, ground, raw",
    "salmon": "Fish, salmon, Atlantic, farmed, raw", "salmon fillet": "Fish, salmon, Atlantic, farmed, raw",
    "tuna": "Fish, tuna, light, canned in water, drained solids (Includes foods for USDA's Food Distribution Program)", "shrimp": "Crustaceans, shrimp, raw",
    "cod": "Fish, cod, Atlantic, raw", "tilapia": "Fish, tilapia, raw", "bacon": "Pork, cured, bacon, unprepared",
    "salt": "Salt, table", "black pepper": "Spices, pepper, black", "pepper": "Spices, pepper, black",
    "cumin": "Spices, cumin seed", "cumin seed": "Spices, cumin seed", "turmeric": "Spices, turmeric, ground",
    "coriander": "Spices, coriander seed", "cinnamon": "Spices, cinnamon, ground", "paprika": "Spices, paprika",
    "chili powder": "Spices, chili powder", "red chili powder": "Spices, chili powder", "curry powder": "Spices, curry powder",
    "garam masala": "Spices, curry powder", "garlic powder": "Spices, garlic powder", "cayenne pepper": "Spices, pepper, red or cayenne",
    "cardamom": "Spices, cardamom", "cloves": "Spices, cloves, ground", "nutmeg": "Spices, nutmeg, ground",
    "oregano": "Spices, oregano, dried", "dried oregano": "Spices, oregano, dried", "thyme": "Spices, thyme, dried",
    "baking powder": "Leavening agents, baking powder, double-acting, sodium aluminum sulfate",
    "baking soda": "Leavening agents, baking soda", "vanilla extract": "Vanilla extract", "vanilla": "Vanilla extract",
    "soy sauce": "Soy sauce made from soy and wheat (shoyu)", "tomato paste": "Tomato products, canned, paste, without salt added (Includes foods for USDA's Food Distribution Program)",
    "tomato sauce": "Tomato products, canned, sauce", "diced tomatoes": "Tomatoes, red, ripe, canned, packed in tomato juice",
    "crushed tomatoes": "Tomatoes, crushed, canned", "ketchup": "Catsup", "mustard": "Mustard, prepared, yellow",
    "dijon mustard": "Mustard, prepared, yellow", "mayonnaise": "Salad dressing, mayonnaise, regular",
    "vinegar": "Vinegar, distilled", "balsamic vinegar": "Vinegar, balsamic", "water": "Water, bottled, generic",
    "vegetable broth": "Soup, vegetable broth, ready to serve", "chicken broth": "Soup, chicken broth, ready-to-serve",
    "chicken stock": "Soup, stock, chicken, home-prepared", "beef broth": "Soup, beef broth or bouillon canned, ready-to-serve",
    "cocoa powder": "Cocoa, dry powder, unsweetened", "unsweetened cocoa powder": "Cocoa, dry powder, unsweetened",
    "dark chocolate": "Chocolate, dark, 70-85% cacao solids", "chocolate chips": "Candies, semisweet chocolate",
    "coconut": "Nuts, coconut meat, dried (desiccated), not sweetened", "tamarind": "Tamarinds, raw",
    "millet": "Millet, raw", "barley": "Barley, pearled, raw", "couscous": "Couscous, dry", "corn meal": "Cornmeal, whole-grain, yellow",
    "cornmeal": "Cornmeal, whole-grain, yellow", "breadcrumbs": "Bread, crumbs, dry, grated, plain",
    "bread crumbs": "Bread, crumbs, dry, grated, plain", "jalapeno": "Peppers, jalapeno, raw", "green chili": "Peppers, hot chili, green, raw",
    "green chilies": "Peppers, hot chili, green, raw", "chili": "Peppers, hot chili, green, raw",
    "pineapple": "Pineapple, raw, all varieties", "grape": "Grapes, red or green (European type, such as Thompson seedless), raw",
    "watermelon": "Watermelon, raw", "pomegranate": "Pomegranates, raw", "papaya": "Papayas, raw", "pear": "Pears, raw",
    "peach": "Peaches, yellow, raw", "kiwi": "Kiwifruit, green, raw", "berries": "Blueberries, raw",
    "mixed berries": "Blueberries, raw", "raspberries": "Raspberries, raw", "raspberry": "Raspberries, raw",
    "whey protein": "Beverages, Protein powder whey based",
    "buttermilk": "Milk, buttermilk, fluid, cultured, lowfat", "cream": "Cream, fluid, light (coffee cream or table cream)",
    "light cream": "Cream, fluid, light (coffee cream or table cream)", "half-and-half": "Cream, fluid, half and half",
    "half and half": "Cream, fluid, half and half", "onion powder": "Spices, onion powder", "bay leaf": "Spices, bay leaf",
    "bay leaves": "Spices, bay leaf", "red pepper flakes": "Spices, pepper, red or cayenne",
    "crushed red pepper flakes": "Spices, pepper, red or cayenne", "cayenne": "Spices, pepper, red or cayenne",
    "monterey jack cheese": "Cheese, monterey", "black olives": "Olives, ripe, canned (small-extra large)",
    "dried cranberries": "Cranberries, dried, sweetened (Includes foods for USDA's Food Distribution Program)",
    "allspice": "Spices, allspice, ground", "tomato puree": "Tomato products, canned, puree, without salt added",
    "pork tenderloin": "Pork, fresh, loin, tenderloin, separable lean only, raw",
    "pork chops": "Pork, fresh, loin, center loin (chops), bone-in, separable lean only, raw",
    "lemon zest": "Lemon peel, raw", "orange zest": "Orange peel, raw", "salsa": "Sauce, salsa, ready-to-serve",
    "orange juice": "Orange juice, raw (Includes foods for USDA's Food Distribution Program)",
    "pineapple juice": "Pineapple juice, canned or bottled, unsweetened, with added ascorbic acid",
    "barbecue sauce": "Sauce, barbecue", "vegetable stock": "Soup, vegetable broth, ready to serve",
    "cooked chicken": "Chicken, broilers or fryers, meat only, cooked, roasted",
    "active dry yeast": "Leavening agents, yeast, baker's, active dry", "yeast": "Leavening agents, yeast, baker's, active dry",
    "panko breadcrumbs": "Bread, crumbs, dry, grated, plain", "panko": "Bread, crumbs, dry, grated, plain",
    "oatmeal": "Oats (Includes foods for USDA's Food Distribution Program)", "gingerroot": "Ginger root, raw",
    "celery rib": "Celery, raw", "celery ribs": "Celery, raw", "cinnamon stick": "Spices, cinnamon, ground",
    "basil leaves": "Basil, fresh", "apple cider vinegar": "Vinegar, cider", "cider vinegar": "Vinegar, cider",
    "shredded cheddar cheese": "Cheese, cheddar (Includes foods for USDA's Food Distribution Program)",
    "grated parmesan cheese": "Cheese, parmesan, grated",
    "chicken breast halves": "Chicken, broiler or fryers, breast, skinless, boneless, meat only, raw",
    "boneless skinless chicken breast halves": "Chicken, broiler or fryers, breast, skinless, boneless, meat only, raw",
    "boneless chicken breasts": "Chicken, broiler or fryers, breast, skinless, boneless, meat only, raw",
}


class UsdaFoodDB:
    def __init__(self, path: Optional[str] = None):
        self.path = path or settings.USDA_FOODS_PATH
        self._lock = threading.Lock()
        self.loaded = False
        self.foods: Dict[int, Dict[str, Any]] = {}
        self.alias: Dict[str, int] = {}
        self.token_index: Dict[str, set] = {}
        self.missing_curated: List[str] = []

    def load(self) -> bool:
        if self.loaded:
            return True
        with self._lock:
            if self.loaded:
                return True
            if not os.path.exists(self.path):
                print(f"Warning: USDA nutrient table not found at {self.path}. Run scripts/build_diet_dataset.py")
                return False
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            by_desc: Dict[str, int] = {}
            for food in data["foods"]:
                fid = int(food["fdc_id"])
                food["tokens"] = _tokens(food["description"])
                food["head"] = _tokens(food["description"].split(",")[0])
                self.foods[fid] = food
                by_desc[food["description"].lower()] = fid
                for t in set(food["tokens"]):
                    self.token_index.setdefault(t, set()).add(fid)
                for a in food.get("aliases", []) or []:
                    self.alias[normalize_ingredient_text(a)] = fid
                    self.alias[a.lower()] = fid
            for key, desc in CURATED_MATCHES.items():
                fid = by_desc.get(desc.lower())
                if fid is None:
                    self.missing_curated.append(desc)
                    continue
                self.alias.setdefault(key, fid)
            if self.missing_curated:
                print(f"USDA curated matches not found ({len(self.missing_curated)}): {self.missing_curated[:8]}")
            self.loaded = True
            print(f"USDA nutrient table loaded: {len(self.foods):,} foods")
            return True

    def get(self, fdc_id: Any) -> Optional[Dict[str, Any]]:
        if not self.load():
            return None
        try:
            return self.foods.get(int(fdc_id))
        except (TypeError, ValueError):
            return None

    # -- searching -------------------------------------------------------------------------
    _PENALTY_WORDS = {"babyfood": 8, "infant": 8, "restaurant": 5, "fast": 4, "candies": 4, "cereals": 3,
                      "snacks": 3, "frozen": 1, "canned": 1, "dehydrated": 2, "dried": 1, "imitation": 4,
                      "prepared": 1, "cooked": 1, "fried": 2, "breaded": 3, "mix": 2, "formula": 6,
                      "school": 3, "lunch": 2, "usda": 1, "commodity": 2, "glaze": 2, "industrial": 3,
                      "pickled": 2, "sweetened": 1, "salted": 1}

    def _score(self, q_tokens: List[str], food: Dict[str, Any]) -> float:
        toks = food["tokens"]
        tset = set(toks)
        if not all(t in tset for t in q_tokens):
            return -1e9
        score = 10.0
        head = set(food["head"])
        if q_tokens and q_tokens[-1] in head:
            score += 6
        score += 2 * sum(1 for t in q_tokens if t in head)
        extra_head = [t for t in food["head"] if t not in q_tokens]
        score -= 3 * len(extra_head)
        if not extra_head and len(head) > 0:
            score += 3
        if "raw" in tset:
            score += 2
        score -= 0.35 * max(0, len(toks) - len(q_tokens))
        for w, p in self._PENALTY_WORDS.items():
            if w in tset and w not in q_tokens:
                score -= p
        desc = food["description"]
        if re.search(r"\b[A-Z]{3,}\b", desc):  # brand names are written in capitals in SR Legacy
            score -= 4
        return score

    def search(self, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        if not self.load():
            return []
        q = normalize_ingredient_text(query) or (query or "").lower().strip()
        q_tokens = [t for t in _tokens(q) if len(t) > 1]
        if not q_tokens:
            return []
        results: Dict[int, float] = {}
        exact = self.alias.get(q)
        if exact:
            results[exact] = 1e6
        cand = None
        for t in q_tokens:
            ids = self.token_index.get(t, set())
            cand = ids if cand is None else cand & ids
        for fid in cand or set():
            s = self._score(q_tokens, self.foods[fid])
            if s > -1e8:
                results[fid] = max(results.get(fid, -1e9), s)
        ranked = sorted(results.items(), key=lambda kv: -kv[1])[:limit]
        return [self.public_food(self.foods[fid], score=s) for fid, s in ranked]

    def match(self, name: str) -> Optional[Dict[str, Any]]:
        """Best USDA food for a free-text ingredient name, or None when no confident match exists."""
        if not self.load():
            return None
        q = normalize_ingredient_text(name)
        if not q:
            return None
        if q in self.alias:
            return {"food": self.foods[self.alias[q]], "method": "curated", "confidence": "high", "query": q}
        q_tokens = [t for t in _tokens(q) if len(t) > 1]
        if not q_tokens:
            return None
        # try the full phrase, then drop leading modifiers ("organic baby spinach" -> "spinach")
        for start in range(0, len(q_tokens)):
            sub = q_tokens[start:]
            key = " ".join(sub)
            if key in self.alias:
                conf = "high" if start == 0 else "medium"
                return {"food": self.foods[self.alias[key]], "method": "curated", "confidence": conf, "query": key}
            cand = None
            for t in sub:
                ids = self.token_index.get(t, set())
                cand = ids if cand is None else cand & ids
            if not cand:
                continue
            best_id, best = None, -1e9
            for fid in cand:
                s = self._score(sub, self.foods[fid])
                if s > best:
                    best_id, best = fid, s
            # A single generic word ("cheese", "nuts") matches many different foods: refuse to guess.
            if len(sub) == 1 and len(cand) > 15:
                continue
            if best_id is not None and best >= 16 and start == 0:
                return {"food": self.foods[best_id], "method": "search", "confidence": "medium", "query": " ".join(sub)}
        return None

    @staticmethod
    def public_food(food: Dict[str, Any], score: float = None) -> Dict[str, Any]:
        out = {"fdc_id": food["fdc_id"], "description": food["description"], "source": food["source"],
               "category": food.get("category", ""),
               "per_100g": {k: food.get(k) for k in NUTRIENT_KEYS},
               "portions": [{"amount": p[0], "unit": p[1], "modifier": p[2], "grams": p[3]} for p in food.get("portions", [])][:8]}
        return out

    # -- grams ----------------------------------------------------------------------------
    def grams_for(self, food: Dict[str, Any], quantity: Optional[float], unit: str, description: str = "",
                  name: str = "") -> Tuple[Optional[float], str]:
        """Converts a quantity of `food` to grams. Returns (grams, note) or (None, reason)."""
        if quantity is None:
            return None, "no quantity given"
        if quantity <= 0:
            return 0.0, "zero quantity"
        u = normalize_unit(unit)
        if u in MASS_G:
            return quantity * MASS_G[u], "weight"
        portions = food.get("portions") or []
        if u in VOLUME_ML:
            ml = quantity * VOLUME_ML[u]
            for unit_names, ml_per in ((("cup",), VOLUME_ML["cup"]), (("tbsp", "tablespoon"), VOLUME_ML["tbsp"]),
                                       (("tsp", "teaspoon"), VOLUME_ML["tsp"]), (("fl oz",), VOLUME_ML["fl oz"]),
                                       (("ml",), 1.0)):
                for amount, pu, modifier, grams in portions:
                    pu_l, mod_l = (pu or "").lower(), (modifier or "").lower()
                    if pu_l in unit_names or any(mod_l.startswith(n) for n in unit_names):
                        if amount and grams:
                            g_per_ml = grams / (amount * ml_per)
                            return ml * g_per_ml, (f"USDA portion weight: {amount:g} {pu or modifier} = {grams:g} g")
            d = food["description"].lower()
            if food.get("category") == "Beverages" or re.search(r"\b(water|juice|broth|stock|milk|soymilk)\b", d):
                return ml * 1.0, "assumed density 1 g/ml for a water-like liquid"
            return None, f"no USDA volume-to-weight conversion for '{food['description']}'"
        if u in COUNT_UNITS:
            if u == "count":
                m_word = re.search(r"\b(clove|slice|stalk|rib|sprig|head|leaf|leaves|stick|ear|fillet|breast|thigh|wing|"
                                   r"tortilla|roti|chapati|bun|roll)s?\b", (name or "").lower())
                if m_word:
                    word = {"rib": "stalk", "leaves": "leaf"}.get(m_word.group(1), m_word.group(1))
                    for amount, pu, modifier, grams in portions:
                        if re.search(r"\b" + word, f"{pu} {modifier}".lower()) and amount and grams:
                            return quantity * grams / amount, f"USDA portion weight: 1 {word} = {grams / amount:.0f} g"
                if food["description"].lower().startswith("egg"):
                    u = "large"
            wanted = {"count": ["medium", "whole", "large", "small", "fruit", "piece", "each", "item", "egg"],
                      "large": ["large"], "medium": ["medium"], "small": ["small"], "clove": ["clove"],
                      "slice": ["slice"], "stalk": ["stalk"], "sprig": ["sprig"], "head": ["head"], "ear": ["ear"],
                      "stick": ["stick"], "leaf": ["leaf", "leaves"], "bunch": ["bunch"], "scoop": ["scoop"]}[u]
            for w in wanted:
                for amount, pu, modifier, grams in portions:
                    text = f"{pu} {modifier}".lower()
                    if re.search(r"\b" + re.escape(w), text) and amount and grams:
                        return quantity * grams / amount, f"USDA portion weight: 1 {(modifier or pu)[:40]} = {grams / amount:.0f} g"
            return None, f"no USDA weight for '{unit or 'piece'}' of '{food['description']}'"
        if u in PACKAGE_UNITS:
            m = re.search(r"(\d+(?:\.\d+)?(?:\s+\d/\d)?)\s*(ounce|oz|g|gram|grams|lb)\b", (description or "").lower())
            if m:
                size, _ = parse_quantity(m.group(1))
                pu = normalize_unit(m.group(2))
                if size and pu in MASS_G:
                    return quantity * size * MASS_G[pu], f"package size from recipe ({m.group(0)})"
            return None, f"package size of '{unit}' not stated"
        return None, f"unit '{unit}' cannot be converted to grams"

    def nutrients_for(self, food: Dict[str, Any], grams: float) -> Dict[str, Optional[float]]:
        f = grams / 100.0
        return {k: (round(food[k] * f, 2) if food.get(k) is not None else None) for k in NUTRIENT_KEYS}


usda_db = UsdaFoodDB()


# ----------------------------------------------------------------------------------------------
# Ingredient + meal nutrition
# ----------------------------------------------------------------------------------------------
def ingredient_nutrition(name: str, quantity: Any, unit: str, description: str = "",
                         fdc_id: Optional[int] = None) -> Dict[str, Any]:
    """USDA estimate for one ingredient line. Never guesses: returns status='unavailable' with a reason."""
    qty, is_range = parse_quantity(quantity)
    if fdc_id:
        food = usda_db.get(fdc_id)
        match = {"food": food, "method": "user_selected", "confidence": "high"} if food else None
    else:
        match = usda_db.match(name)
    if not match or not match.get("food"):
        return {"status": "unavailable", "reason": f"no reliable USDA match for '{name}'", "match": None}
    food = match["food"]
    grams, note = usda_db.grams_for(food, qty, unit, description, name)
    match_info = {"fdc_id": food["fdc_id"], "description": food["description"], "source": food["source"],
                  "method": match["method"], "confidence": match["confidence"]}
    if grams is None:
        return {"status": "unavailable", "reason": note, "match": match_info}
    out = {"status": "ok", "grams": round(grams, 1), "conversion": note, "match": match_info,
           "nutrients": usda_db.nutrients_for(food, grams), "range_midpoint": is_range}
    return out


def _round_nutrients(n: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
    out = {}
    for k, v in n.items():
        if v is None:
            out[k] = None
        elif k == "kcal":
            out[k] = round(v)
        else:
            out[k] = round(v, 1)
    return out


def compute_meal_nutrition(meal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nutrition of one plan meal for the portion the user eats.

    base   = Food.com per-serving values x servings eaten          (verified source data)
    edits  = sum over changed ingredients of USDA(new) - USDA(old) (calculated estimate)
             divided by the recipe's servings and multiplied by the servings eaten.
    If any change cannot be calculated, the meal's nutrition is reported as unavailable.
    """
    src = meal.get("source_per_serving") or {}
    servings_eaten = float(meal.get("servings") or 1.0)
    base = {k: (src.get(k) * servings_eaten if src.get(k) is not None else None) for k in NUTRIENT_KEYS}
    changes = [i for i in meal.get("ingredients", []) if i.get("status") in ("modified", "added", "removed")]
    if not changes:
        return {"status": "source", "values": _round_nutrients(base),
                "basis": f"Food.com recipe nutrition per serving x {servings_eaten:g} serving(s)",
                "missing": [k for k in NUTRIENT_KEYS if base[k] is None], "changes": []}

    recipe_servings = meal.get("recipe_servings")
    if not recipe_servings:
        return {"status": "unavailable", "values": {k: None for k in NUTRIENT_KEYS},
                "reason": "This recipe does not state how many servings it makes, so ingredient changes cannot be "
                          "converted to a per-serving amount. Reset the ingredients or choose another recipe.",
                "changes": []}

    delta = {k: 0.0 for k in NUTRIENT_KEYS}
    fiber_ok = base["fiber"] is not None
    change_report = []
    problems = []
    for ing in changes:
        old_n = new_n = None
        rep = {"name": ing.get("name"), "status": ing["status"]}
        if ing["status"] in ("modified", "removed"):
            orig = ing.get("original") or {}
            old_n = ingredient_nutrition(orig.get("name", ""), orig.get("quantity"), orig.get("unit", ""),
                                         orig.get("description", ""), orig.get("fdc_id"))
            rep["before"] = old_n
            if old_n["status"] != "ok":
                problems.append(f"original '{orig.get('name')}': {old_n['reason']}")
        if ing["status"] in ("modified", "added"):
            new_n = ingredient_nutrition(ing.get("name", ""), ing.get("quantity"), ing.get("unit", ""),
                                         ing.get("description", ""), ing.get("fdc_id"))
            rep["after"] = new_n
            if new_n["status"] != "ok":
                problems.append(f"'{ing.get('name')}': {new_n['reason']}")
        change_report.append(rep)
        if problems:
            continue
        for k in NUTRIENT_KEYS:
            nv = (new_n or {}).get("nutrients", {}).get(k, 0.0) if new_n else 0.0
            ov = (old_n or {}).get("nutrients", {}).get(k, 0.0) if old_n else 0.0
            if (new_n and nv is None) or (old_n and ov is None):
                if k == "fiber":
                    fiber_ok = False
                    continue
                problems.append(f"USDA record lacks {k}")
                continue
            delta[k] += (nv or 0.0) - (ov or 0.0)
    if problems:
        return {"status": "unavailable", "values": {k: None for k in NUTRIENT_KEYS},
                "reason": "Could not recalculate after your changes: " + "; ".join(problems[:3]),
                "changes": change_report}
    per_serving_factor = servings_eaten / float(recipe_servings)
    values = {}
    clamped = False
    for k in NUTRIENT_KEYS:
        if base[k] is None or (k == "fiber" and not fiber_ok):
            values[k] = None
            continue
        v = base[k] + delta[k] * per_serving_factor
        if v < 0:
            v, clamped = 0.0, True
        values[k] = v
    notes = ["Adjusted with USDA ingredient estimates for your changes"]
    if clamped:
        notes.append("A value fell below zero after removing an ingredient and was shown as 0; "
                     "the original recipe's value for that ingredient may differ from the USDA estimate.")
    return {"status": "estimate", "values": _round_nutrients(values),
            "basis": (f"Food.com per-serving values x {servings_eaten:g}, adjusted by USDA estimates for "
                      f"{len(changes)} changed ingredient(s) (recipe makes {recipe_servings:g} servings)"),
            "notes": notes, "changes": change_report}


def sum_nutrition(meals: List[Dict[str, Any]]) -> Dict[str, Any]:
    totals = {k: 0.0 for k in NUTRIENT_KEYS}
    complete = {k: True for k in NUTRIENT_KEYS}
    unavailable = []
    estimated = []
    for m in meals:
        n = m.get("nutrition") or {}
        if n.get("status") == "unavailable":
            unavailable.append(m.get("label") or m.get("name"))
            for k in NUTRIENT_KEYS:
                complete[k] = False
            continue
        if n.get("status") == "estimate":
            estimated.append(m.get("label") or m.get("name"))
        for k in NUTRIENT_KEYS:
            v = (n.get("values") or {}).get(k)
            if v is None:
                complete[k] = False
            else:
                totals[k] += v
    return {"values": _round_nutrients(totals), "complete": complete, "meals_unavailable": unavailable,
            "meals_estimated": estimated, "meal_count": len(meals)}


# ----------------------------------------------------------------------------------------------
# Recipe-level estimate for model-generated recipes (used by the general chatbot)
# ----------------------------------------------------------------------------------------------
_NEGLIGIBLE_RE = re.compile(r"^(salt|pepper|black pepper|salt and pepper|salt pepper|water|ice|ice cubes|.*\bto taste\b.*|.*\bfor garnish\b.*)$")
_LINE_RE = re.compile(r"^\s*(?P<qty>[\d\s/\.\-½⅓⅔¼¾⅛]+)?\s*(?P<unit>[a-zA-Z\.]+)?\s+(?P<name>.+)$")


def parse_ingredient_line(line: str) -> Dict[str, str]:
    """'1 1/2 cups cooked rice' -> {quantity:'1 1/2', unit:'cups', name:'cooked rice'}"""
    s = (line or "").strip()
    m = re.match(r"^\s*([\d\s/\.\-½⅓⅔¼¾⅛]+)\s+(.*)$", s)
    if not m:
        return {"quantity": "", "unit": "", "name": s}
    qty, rest = m.group(1).strip(), m.group(2).strip()
    parts = rest.split(" ", 1)
    if len(parts) == 2 and normalize_unit(parts[0]) in set(UNIT_ALIASES.values()) - {"count"} and parts[0].lower() in UNIT_ALIASES:
        return {"quantity": qty, "unit": parts[0], "name": parts[1]}
    return {"quantity": qty, "unit": "", "name": rest}


def estimate_recipe_from_lines(lines: List[str], servings: Any) -> Dict[str, Any]:
    serv, _ = parse_quantity(servings)
    if not serv or serv <= 0:
        return {"status": "unavailable", "reason": "number of servings not stated"}
    totals = {k: 0.0 for k in NUTRIENT_KEYS}
    missing = []
    for line in lines:
        p = parse_ingredient_line(line)
        if _NEGLIGIBLE_RE.match(normalize_ingredient_text(p["name"]) or p["name"].lower()):
            continue
        r = ingredient_nutrition(p["name"], p["quantity"] or None, p["unit"])
        if r["status"] != "ok":
            missing.append(line)
            continue
        for k in NUTRIENT_KEYS:
            v = r["nutrients"].get(k)
            if v is None:
                totals[k] = None if k == "fiber" else totals[k]
            elif totals[k] is not None:
                totals[k] += v
    if missing:
        return {"status": "unavailable",
                "reason": "quantities or USDA matches are missing for: " + ", ".join(missing[:4])
                          + ("..." if len(missing) > 4 else "")}
    per = {k: (v / serv if v is not None else None) for k, v in totals.items()}
    return {"status": "estimate", "values": _round_nutrients(per), "basis": "USDA ingredient estimate per serving"}
