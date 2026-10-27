"""
dietary_rules.py
================
Defines configurable ingredient categories and strict dietary rules for:
- Vegan
- Vegetarian
- Eggitarian
- Non-Vegetarian
- No Preference
"""

from enum import Enum
from typing import List, Set

class DietaryPreference(str, Enum):
    VEGAN = "vegan"
    VEGETARIAN = "vegetarian"
    EGGITARIAN = "eggitarian"
    NON_VEGETARIAN = "non_vegetarian"
    NO_PREFERENCE = "no_preference"

# Configurable ingredient category lists (normalized lowercase)
MEAT_INGREDIENTS: Set[str] = {
    "beef", "ground beef", "steak", "roast beef", "mutton", "lamb", "ground lamb", 
    "pork", "pork chop", "pork tenderloin", "bacon", "ham", "sausage", "pork sausage",
    "prosciutto", "lard", "venison", "bison", "veal", "pepperoni", "salami", "pancetta", 
    "chorizo", "tripe", "pastrami", "carnitas", "suet", "gelatin"
}

POULTRY_INGREDIENTS: Set[str] = {
    "chicken", "chicken breast", "chicken thigh", "chicken wing", "ground chicken",
    "turkey", "ground turkey", "duck", "duck breast", "goose", "fowl", "quail",
    "pheasant", "poultry"
}

FISH_INGREDIENTS: Set[str] = {
    "salmon", "tuna", "cod", "halibut", "trout", "bass", "snapper", "tilapia",
    "anchovy", "anchovies", "sardine", "sardines", "mackerel", "mahi mahi",
    "swordfish", "catfish", "haddock", "flounder", "herring", "fish", "fish sauce"
}

SEAFOOD_INGREDIENTS: Set[str] = {
    "prawn", "prawns", "shrimp", "shrimps", "crab", "crabmeat", "lobster", 
    "mussel", "mussels", "clam", "clams", "oyster", "oysters", "squid", 
    "octopus", "scallop", "scallops", "caviar", "calamari", "crawfish", "crayfish"
}

EGG_INGREDIENTS: Set[str] = {
    "egg", "eggs", "egg white", "egg whites", "egg yolk", "egg yolks", 
    "hard-boiled egg", "poached egg", "scrambled egg", "mayonnaise", "eggnog"
}

DAIRY_INGREDIENTS: Set[str] = {
    "milk", "whole milk", "skim milk", "low-fat milk", "cream", "heavy cream",
    "whipping cream", "sour cream", "half-and-half", "butter", "unsalted butter",
    "salted butter", "ghee", "clarified butter", "cheese", "cheddar cheese",
    "mozzarella cheese", "parmesan cheese", "ricotta cheese", "cream cheese",
    "feta cheese", "goat cheese", "swiss cheese", "provolone", "monterey jack",
    "paneer", "yogurt", "greek yogurt", "curd", "whey", "buttermilk", 
    "condensed milk", "evaporated milk", "condensed milk", "half and half",
    # Cheeses and dairy foods named on their own ("100 g feta" was previously not recognised)
    "feta", "parmesan", "parmigiano", "parmigiano-reggiano", "mozzarella", "bocconcini", "burrata", "ricotta",
    "cheddar", "romano", "pecorino", "halloumi", "gouda", "brie", "camembert", "mascarpone", "gruyere",
    "asiago", "gorgonzola", "blue cheese", "emmental", "havarti", "colby", "queso fresco", "cotija",
    "khoya", "khoa", "mawa", "malai", "chhena", "kefir", "ice cream", "custard", "milk powder", "skyr",
}

# Derived collections for fast lookup
ALL_MEAT_AND_SEAFOOD = MEAT_INGREDIENTS | POULTRY_INGREDIENTS | FISH_INGREDIENTS | SEAFOOD_INGREDIENTS
ALL_ANIMAL_NON_VEG = ALL_MEAT_AND_SEAFOOD
ALL_ANIMAL_NON_EGG = ALL_ANIMAL_NON_VEG
ALL_ANIMAL_PRODUCTS = ALL_MEAT_AND_SEAFOOD | EGG_INGREDIENTS | DAIRY_INGREDIENTS

# Plant-based alternatives for ingredient substitution/recommendations
PLANT_BASED_ALTERNATIVES = {
    "butter": "olive oil or coconut oil",
    "ghee": "vegetable oil or coconut oil",
    "milk": "almond milk or oat milk",
    "heavy cream": "coconut cream",
    "cream": "coconut cream",
    "yogurt": "coconut yogurt or soy yogurt",
    "cheese": "vegan cheese or nutritional yeast",
    "paneer": "tofu",
    "egg": "flax egg or chia egg",
    "eggs": "flax eggs",
    "mayonnaise": "vegan mayonnaise",
    "honey": "maple syrup or agave nectar",
    "chicken": "tofu or jackfruit or mushrooms",
    "beef": "tempeh or textured vegetable protein",
    "pork": "jackfruit or seitan",
    # Added so every common animal ingredient has a swap (previously these were flagged but left in)
    "mutton": "soya chunks or jackfruit", "lamb": "soya chunks or jackfruit", "goat": "soya chunks",
    "turkey": "tofu", "duck": "mushrooms", "bacon": "smoked tempeh", "ham": "smoked tofu",
    "sausage": "plant-based sausage", "pepperoni": "sun-dried tomatoes", "salami": "grilled vegetables",
    "ground beef": "soya mince", "lard": "vegetable oil", "suet": "vegetable shortening", "gelatin": "agar agar",
    "fish sauce": "soy sauce", "fish": "firm tofu", "salmon": "firm tofu", "tuna": "chickpeas", "cod": "firm tofu",
    "tilapia": "firm tofu", "anchovies": "capers", "anchovy": "capers", "sardines": "chickpeas",
    "prawns": "mushrooms", "prawn": "mushrooms", "shrimp": "mushrooms", "crab": "hearts of palm",
    "lobster": "king oyster mushrooms", "squid": "mushrooms",
    "clarified butter": "vegetable oil", "sour cream": "coconut yogurt", "cream cheese": "vegan cream cheese",
    "curd": "coconut yogurt", "buttermilk": "oat milk with lemon juice", "whey": "pea protein",
}

# Not covered by the category lists above: blocked only for vegans
VEGAN_EXTRA = {"honey": "maple syrup or agave nectar"}
