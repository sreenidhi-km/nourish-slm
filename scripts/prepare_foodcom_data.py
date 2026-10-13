#!/usr/bin/env python3
import os
import sys
import pandas as pd
import ast
import re
import json

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_PATH = os.environ.get("RAW_DATA_PATH", os.path.join(PROJECT_ROOT, "data", "raw", "RAW_recipes.csv"))
CLEANED_CSV_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "foodcom_cleaned.csv")
DIET_EVAL_PATH = os.path.join(PROJECT_ROOT, "data", "diet_eval.jsonl")

os.makedirs(os.path.join(PROJECT_ROOT, "data", "processed"), exist_ok=True)

print("--- Preprocessing Food.com Dataset ---")
df_raw = pd.read_csv(RAW_PATH)

total_raw = len(df_raw)
cols = list(df_raw.columns)
num_cols = len(cols)
dtypes_dict = {k: str(v) for k, v in df_raw.dtypes.items()}
missing_dict = df_raw.isnull().sum().to_dict()

# Deduplication by ID
df = df_raw.drop_duplicates(subset=['id']).copy()
after_dedup = len(df)

# Parse list fields
def parse_list(val):
    if not isinstance(val, str):
        return []
    try:
        res = ast.literal_eval(val)
        if isinstance(res, list):
            return [str(x).strip() for x in res if str(x).strip()]
    except Exception:
        pass
    return []

df['parsed_ingredients'] = df['ingredients'].apply(parse_list)
df['parsed_steps'] = df['steps'].apply(parse_list)
df['parsed_tags'] = df['tags'].apply(parse_list)
df['clean_name'] = df['name'].fillna('').astype(str).str.strip()
df['clean_description'] = df['description'].fillna('').astype(str).str.strip()

# Invalid recipe removal
valid_mask = (
    (df['clean_name'].str.len() > 0) & 
    (df['parsed_ingredients'].apply(len) >= 2) & 
    (df['parsed_steps'].apply(len) >= 2)
)
df_clean = df[valid_mask].copy()
after_invalid_removal = len(df_clean)

# Dietary Classification
MEAT_PATTERNS = re.compile(
    r'\b(beef|ground beef|steak|pork|bacon|ham|sausage|pepperoni|prosciutto|salami|pork chop|pork tenderloin|'
    r'chicken|chicken breast|chicken thigh|turkey|duck|lamb|veal|mutton|venison|'
    r'fish|salmon|tuna|cod|trout|halibut|shrimp|prawn|crab|lobster|scallop|clam|mussel|oyster|squid|octopus|anchovy|anchovies|anchovy paste|'
    r'gelatin|lard|suet|chicken broth|beef broth|chicken stock|beef stock|fish stock|fish sauce|oyster sauce|worcestershire sauce)\b',
    re.IGNORECASE
)

EGG_PATTERNS = re.compile(
    r'\b(egg|eggs|egg white|egg whites|egg yolk|egg yolks|hard-boiled egg|scrambled egg|mayonnaise|mayo)\b',
    re.IGNORECASE
)

DAIRY_PATTERNS = re.compile(
    r'\b(milk|whole milk|skim milk|buttermilk|condensed milk|evaporated milk|'
    r'butter|ghee|heavy cream|whipping cream|light cream|sour cream|cream cheese|'
    r'cheese|cheddar|mozzarella|parmesan|ricotta|feta|swiss cheese|provolone|gouda|monterey jack|colby|brie|camembert|blue cheese|'
    r'yogurt|greek yogurt|curd|paneer|half-and-half|ice cream)\b',
    re.IGNORECASE
)

def classify_diet(row):
    ings_text = " ".join(row['parsed_ingredients']).lower()
    tags_text = " ".join(row['parsed_tags']).lower()
    
    has_meat = bool(MEAT_PATTERNS.search(ings_text)) or ('meat' in tags_text and 'vegetarian' not in tags_text and 'vegan' not in tags_text)
    has_egg = bool(EGG_PATTERNS.search(ings_text))
    has_dairy = bool(DAIRY_PATTERNS.search(ings_text))

    if has_meat:
        return "Non-Vegetarian"
    elif has_egg:
        return "Eggitarian"
    elif has_dairy:
        return "Vegetarian"
    else:
        return "Vegan"

df_clean['dietary_attribute'] = df_clean.apply(classify_diet, axis=1)

# Format ingredients & steps back to JSON strings for CSV storage
df_clean['ingredients_json'] = df_clean['parsed_ingredients'].apply(json.dumps)
df_clean['steps_json'] = df_clean['parsed_steps'].apply(json.dumps)
df_clean['tags_json'] = df_clean['parsed_tags'].apply(json.dumps)

# Create display cuisine helper
def detect_cuisine(row):
    tags_str = " ".join(row['parsed_tags']).lower()
    name_str = row['clean_name'].lower()
    if 'indian' in tags_str or 'curry' in name_str or 'masala' in name_str or 'paneer' in name_str:
        return 'Indian'
    elif 'italian' in tags_str or 'pasta' in name_str or 'pizza' in name_str or 'risotto' in name_str:
        return 'Italian'
    elif 'french' in tags_str or 'european' in tags_str or 'steak' in name_str or 'roast' in name_str:
        return 'Continental'
    return 'General'

df_clean['cuisine'] = df_clean.apply(detect_cuisine, axis=1)

# Format output dataframe
export_df = pd.DataFrame({
    'recipe_id': df_clean['id'],
    'name': df_clean['clean_name'],
    'minutes': df_clean['minutes'],
    'cuisine': df_clean['cuisine'],
    'dietary_attribute': df_clean['dietary_attribute'],
    'ingredients': df_clean['ingredients_json'],
    'instructions': df_clean['steps_json'],
    'description': df_clean['clean_description'],
    'tags': df_clean['tags_json']
})

print(f"Saving cleaned dataset to {CLEANED_CSV_PATH}...")
export_df.to_csv(CLEANED_CSV_PATH, index=False)

cat_counts = df_clean['dietary_attribute'].value_counts().to_dict()

print(f"\n--- DATASET SUMMARY ---")
print(f"Raw recipes: {total_raw}")
print(f"After duplicate removal: {after_dedup}")
print(f"After invalid recipe removal: {after_invalid_removal}")
print(f"Final usable recipes: {after_invalid_removal}")
print(f"Vegan: {cat_counts.get('Vegan', 0)}")
print(f"Vegetarian: {cat_counts.get('Vegetarian', 0)}")
print(f"Eggitarian: {cat_counts.get('Eggitarian', 0)}")
print(f"Non-Vegetarian: {cat_counts.get('Non-Vegetarian', 0)}")
print(f"Unclassified: 0")

# Create diet_eval.jsonl if not exists
if not os.path.exists(DIET_EVAL_PATH):
    print(f"\nCreating evaluation dataset at {DIET_EVAL_PATH}...")
    test_cases = [
        # VEGAN
        {"id": 1, "preference": "Vegan", "ingredients": ["tomato", "onion", "garlic", "rice"], "cuisine": "Indian", "expected_diet": "Vegan"},
        {"id": 2, "preference": "Vegan", "ingredients": ["black beans", "corn", "avocado", "lime"], "cuisine": "Mexican", "expected_diet": "Vegan"},
        {"id": 3, "preference": "Vegan", "ingredients": ["pasta", "olive oil", "garlic", "basil"], "cuisine": "Italian", "expected_diet": "Vegan"},
        {"id": 4, "preference": "Vegan", "ingredients": ["tofu", "broccoli", "soy sauce", "ginger"], "cuisine": "Chinese", "expected_diet": "Vegan"},
        {"id": 5, "preference": "Vegan", "ingredients": ["chickpeas", "tahini", "lemon juice", "garlic"], "cuisine": "Middle Eastern", "expected_diet": "Vegan"},
        {"id": 6, "preference": "Vegan", "ingredients": ["spinach", "lentils", "cumin", "turmeric"], "cuisine": "Indian", "expected_diet": "Vegan"},
        {"id": 7, "preference": "Vegan", "ingredients": ["quinoa", "cucumber", "cherry tomatoes", "olive oil"], "cuisine": "Mediterranean", "expected_diet": "Vegan"},
        {"id": 8, "preference": "Vegan", "ingredients": ["sweet potato", "black beans", "bell pepper"], "cuisine": "Mexican", "expected_diet": "Vegan"},
        {"id": 9, "preference": "Vegan", "ingredients": ["oats", "banana", "almond milk", "cinnamon"], "cuisine": "American", "expected_diet": "Vegan"},
        {"id": 10, "preference": "Vegan", "ingredients": ["eggplant", "zucchini", "bell pepper", "tomato sauce"], "cuisine": "French", "expected_diet": "Vegan"},
        {"id": 11, "preference": "Vegan", "ingredients": ["cauliflower", "coconut milk", "curry powder"], "cuisine": "Thai", "expected_diet": "Vegan"},
        {"id": 12, "preference": "Vegan", "ingredients": ["mushrooms", "garlic", "thyme", "olive oil"], "cuisine": "Italian", "expected_diet": "Vegan"},

        # VEGETARIAN
        {"id": 13, "preference": "Vegetarian", "ingredients": ["paneer", "spinach", "cream", "garlic"], "cuisine": "Indian", "expected_diet": "Vegetarian"},
        {"id": 14, "preference": "Vegetarian", "ingredients": ["pasta", "heavy cream", "parmesan", "garlic"], "cuisine": "Italian", "expected_diet": "Vegetarian"},
        {"id": 15, "preference": "Vegetarian", "ingredients": ["mozzarella", "tomato", "basil", "balsamic vinegar"], "cuisine": "Italian", "expected_diet": "Vegetarian"},
        {"id": 16, "preference": "Vegetarian", "ingredients": ["rice", "yogurt", "mustard seeds", "curry leaves"], "cuisine": "Indian", "expected_diet": "Vegetarian"},
        {"id": 17, "preference": "Vegetarian", "ingredients": ["tortilla", "cheddar cheese", "black beans", "sour cream"], "cuisine": "Mexican", "expected_diet": "Vegetarian"},
        {"id": 18, "preference": "Vegetarian", "ingredients": ["butter", "paneer", "tomato puree", "kasuri methi"], "cuisine": "Indian", "expected_diet": "Vegetarian"},
        {"id": 19, "preference": "Vegetarian", "ingredients": ["feta cheese", "olives", "cucumber", "red onion"], "cuisine": "Greek", "expected_diet": "Vegetarian"},
        {"id": 20, "preference": "Vegetarian", "ingredients": ["ricotta cheese", "spinach", "lasagna sheets", "marinara"], "cuisine": "Italian", "expected_diet": "Vegetarian"},
        {"id": 21, "preference": "Vegetarian", "ingredients": ["potato", "butter", "milk", "chives"], "cuisine": "American", "expected_diet": "Vegetarian"},

        # EGGITARIAN
        {"id": 22, "preference": "Eggitarian", "ingredients": ["eggs", "bread", "butter", "black pepper"], "cuisine": "American", "expected_diet": "Eggitarian"},
        {"id": 23, "preference": "Eggitarian", "ingredients": ["eggs", "rice", "soy sauce", "scallions"], "cuisine": "Chinese", "expected_diet": "Eggitarian"},
        {"id": 24, "preference": "Eggitarian", "ingredients": ["eggs", "tomato", "onion", "green chilies"], "cuisine": "Indian", "expected_diet": "Eggitarian"},
        {"id": 25, "preference": "Eggitarian", "ingredients": ["egg whites", "spinach", "feta cheese"], "cuisine": "Mediterranean", "expected_diet": "Eggitarian"},
        {"id": 26, "preference": "Eggitarian", "ingredients": ["eggs", "potatoes", "onion", "olive oil"], "cuisine": "Spanish", "expected_diet": "Eggitarian"},
        {"id": 27, "preference": "Eggitarian", "ingredients": ["eggs", "cream", "nutmeg", "pie crust"], "cuisine": "French", "expected_diet": "Eggitarian"},

        # NON-VEGETARIAN
        {"id": 28, "preference": "Non-Vegetarian", "ingredients": ["chicken breast", "rice", "onion", "spices"], "cuisine": "Indian", "expected_diet": "Non-Vegetarian"},
        {"id": 29, "preference": "Non-Vegetarian", "ingredients": ["ground beef", "taco shells", "lettuce", "cheddar cheese"], "cuisine": "Mexican", "expected_diet": "Non-Vegetarian"},
        {"id": 30, "preference": "Non-Vegetarian", "ingredients": ["salmon fillet", "lemon", "dill", "butter"], "cuisine": "American", "expected_diet": "Non-Vegetarian"},
        {"id": 31, "preference": "Non-Vegetarian", "ingredients": ["chicken thighs", "soy sauce", "mirin", "sugar"], "cuisine": "Japanese", "expected_diet": "Non-Vegetarian"},
        {"id": 32, "preference": "Non-Vegetarian", "ingredients": ["shrimp", "garlic", "butter", "white wine"], "cuisine": "Italian", "expected_diet": "Non-Vegetarian"},
        {"id": 33, "preference": "Non-Vegetarian", "ingredients": ["pork chops", "apples", "rosemary", "olive oil"], "cuisine": "American", "expected_diet": "Non-Vegetarian"}
    ]
    with open(DIET_EVAL_PATH, "w") as f:
        for tc in test_cases:
            record = {
                "instruction": f"Create a {tc['preference']} recipe using ingredients: {', '.join(tc['ingredients'])}.",
                "input": {
                    "ingredients": tc["ingredients"],
                    "preference": tc["preference"],
                    "cuisine": tc["cuisine"]
                },
                "expected_diet": tc["expected_diet"]
            }
            f.write(json.dumps(record) + "\n")
    print(f"Created {len(test_cases)} evaluation records in {DIET_EVAL_PATH}.")

print("Preprocessing complete.")
