#!/usr/bin/env python3
"""
build_diet_dataset.py
=====================
Builds the recipe + nutrition data used by the Diet Planning feature and by the
nutrition panel of the general Nourish chatbot. Standard library only, so it runs
with any Python 3.10+ (no pandas needed) and finishes in a few minutes.

Inputs (see data/raw/diet/README.md for download links and licences)
  data/raw/diet/parsed_recipes.csv   Food.com "Recipes and Reviews" (2020 crawl) in a parsed
                                     form: structured ingredient quantities, per-serving
                                     nutrition in grams (incl. fibre), servings, photo URLs.
  data/raw/RAW_recipes.csv           Food.com "Recipes and Interactions" (already used by
                                     the SLM): recipe ids, step-by-step instructions, tags,
                                     per-serving nutrition (%DV).
  data/processed/foodcom_cleaned.csv Existing cleaned data (cuisine label per recipe id).
  data/raw/diet/usda_sr_legacy/...   USDA FoodData Central SR Legacy CSV (public domain).
  data/reference/fdc_supplement_foods.json  A few FDC (FNDDS / Branded) foods missing from SR Legacy.

Outputs
  data/processed/diet_recipes.db     SQLite: `recipes` (clean, classified, plan-ready recipes),
                                     `lookup` (per-serving nutrition + photo for every Food.com
                                     recipe id, used by the general chatbot), `meta` (build stats).
  data/processed/usda_foods.json     Compact USDA nutrient table (kcal, protein, fat, carbs,
                                     fibre per 100 g + household portion weights).

Nothing is invented: every number is copied from a source record. Rows whose source
values are missing or internally inconsistent are dropped from the plan pool.
"""

import ast
import csv
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from backend.app.services.food_labels import (  # noqa: E402
    ALCOHOL_RE, classify_diet, detect_allergens, diet_verification, metadata_says_meat, title_meat_warning,
)

csv.field_size_limit(10 ** 9)

PARSED_CSV = os.environ.get("DIET_PARSED_CSV", os.path.join(ROOT, "data", "raw", "diet", "parsed_recipes.csv"))
RAW_CSV = os.environ.get("RAW_DATA_PATH", os.path.join(ROOT, "data", "raw", "RAW_recipes.csv"))
CLEANED_CSV = os.path.join(ROOT, "data", "processed", "foodcom_cleaned.csv")
USDA_ZIP = os.path.join(ROOT, "data", "raw", "diet", "FoodData_Central_sr_legacy_food_csv_2018-04.zip")
USDA_DIR = os.path.join(ROOT, "data", "raw", "diet", "usda_sr_legacy", "FoodData_Central_sr_legacy_food_csv_2018-04")
SUPPLEMENT_JSON = os.path.join(ROOT, "data", "reference", "fdc_supplement_foods.json")
OUT_DB = os.environ.get("DIET_DB_PATH", os.path.join(ROOT, "data", "processed", "diet_recipes.db"))
OUT_USDA = os.environ.get("USDA_FOODS_PATH", os.path.join(ROOT, "data", "processed", "usda_foods.json"))

# Food.com %DV reference amounts (2,000 kcal label reference). Verified empirically against the
# gram values of the 2020 crawl: median ratio grams/%DV = 0.50 protein, 0.65 fat, 3.0 carbohydrate.
PDV_REFERENCE_G = {"fat": 65.0, "protein": 50.0, "carbs": 300.0, "sugar": 25.0, "sat_fat": 20.0}

IMG_ID_RE = re.compile(r"/img/recipes/([\d/]+)/[^/]+$")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def norm_name(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def to_float(v):
    try:
        if v is None or v == "":
            return None
        f = float(v)
        return f if f == f else None  # NaN guard
    except (TypeError, ValueError):
        return None


def parse_list(v):
    if not isinstance(v, str) or not v.strip():
        return []
    try:
        out = json.loads(v)
    except (ValueError, TypeError):
        try:
            out = ast.literal_eval(v)
        except (ValueError, SyntaxError):
            return []
    if isinstance(out, str):  # double-encoded
        return parse_list(out)
    return out if isinstance(out, list) else []


# ----------------------------------------------------------------------------------------------
# Classification helpers (deterministic, ingredient based — never from the title alone)
# ----------------------------------------------------------------------------------------------
DESSERT_TAGS = {"desserts", "cakes", "cookies-and-brownies", "pies-and-tarts", "candy", "frozen-desserts",
                "cheesecake", "puddings-and-mousses", "ice-cream", "cupcakes", "chocolate", "brownies",
                "bar-cookies", "drop-cookies", "fudge"}
COMPONENT_TAGS = {"sauces", "condiments-etc", "salad-dressings", "spreads", "jams-and-preserves",
                  "marinades-and-rubs", "cocktails", "dips", "seasoning", "herb-and-spice-mixes",
                  "breads", "yeast", "quick-breads", "rolls-biscuits", "canning", "garnishes", "gravies"}
DESSERT_CATS = {"Dessert", "Pie", "Candy", "Cheesecake", "Bar Cookie", "Drop Cookies", "Frozen Desserts", "Tarts",
                "Gelatin", "Ice Cream", "Pie Crusts", "Bread Pudding", "Lemon Cake", "Coconut Cream Pie",
                "Chocolate Chip Cookies", "Key Lime Pie", "Peanut Butter Pie", "Cherry Pie", "Apple Pie",
                "Pumpkin Pie", "Sweet Pie", "Tarts", "Mousse"}
COMPONENT_CATS = {"Sauces", "Spreads", "Salad Dressings", "Breads", "Quick Breads", "Yeast Breads", "Beverages",
                  "Punch Beverage", "Shakes", "Chutneys", "Jellies", "Low Protein", "Canning", "Sourdough Breads",
                  "Bread Machine", "Marinades", "Spaghetti Sauce", "Gravy", "Dips", "Margarita"}
BREAKFAST_CATS = {"Breakfast", "Smoothies", "Oatmeal", "Breakfast Eggs", "Breakfast Casseroles"}
MAIN_CATS = {"One Dish Meal", "Chicken", "Chicken Breast", "Meat", "Pork", "Poultry", "Steak", "Stew", "Curries",
             "Beans", "Rice", "Lamb/Sheep", "Grains", "Spaghetti", "Chicken Thigh & Leg", "Vegetable", "Whole Chicken",
             "Lentil", "Tuna", "Salmon", "Tilapia", "Halibut", "Catfish", "Trout", "Bass", "Crab", "Lobster",
             "Mussels", "Tofu", "Soy/Tofu", "Chowders", "Clear Soup", "Black Beans", "Chicken Livers", "Roast Beef",
             "Meatloaf", "Meatballs", "Penne", "Savory Pies", "Potato", "Yam/Sweet Potato", "Brown Rice",
             "White Rice", "Long Grain Rice", "Spinach", "Greens", "Chick Peas - Garbanzos", "Lentils", "Turkey Breasts",
             "Ham", "Pork Chops", "Pork Loin", "Duck", "Deer", "Veal", "Crawfish", "Shrimp", "Scallop", "Squid",
             "Quinoa", "Wild Game", "Cauliflower"}
SNACK_CATS = {"Lunch/Snacks", "Smoothies", "Fruit", "Shakes", "Peanut Butter", "Nuts", "Trail Mix"}

MAIN_TAGS = {"main-dish", "lunch", "one-dish-meal", "curries", "stews", "soups-stews", "pasta", "beans",
             "rice", "lentils", "chicken", "beef", "pork", "fish", "seafood", "tofu", "casseroles", "stir-fry"}
SNACK_TAGS = {"snacks", "appetizers", "smoothies", "shakes", "fruit", "nuts"}
BREAKFAST_TAGS = {"breakfast", "brunch"}

def classify_cuisine(cleaned_cuisine, raw_tags, karo_tags, name_low):
    tags = set(raw_tags)
    kt = {t.lower() for t in karo_tags}
    out = set()
    if (cleaned_cuisine or "").lower() == "indian" or "indian" in tags or "indian" in kt:
        out.add("indian")
    if (cleaned_cuisine or "").lower() == "italian" or "italian" in tags or "italian" in kt or re.search(
            r"\b(pasta|risotto|lasagna|gnocchi|marinara|bolognese|minestrone|bruschetta|frittata|polenta|pesto|penne)\b", name_low):
        out.add("italian")
    if tags & {"european", "french", "english", "british", "german", "scandinavian", "irish", "scottish",
               "swiss", "dutch", "portuguese", "spanish", "greek"} or kt & {"european", "french", "english", "german"} \
            or re.search(r"\b(roast|casserole|quiche|gratin|stew|grilled|baked|crepe|omelet|omelette)\b", name_low):
        out.add("continental")
    return sorted(out)


def meal_types_for(category, raw_tags, karo_tags, kcal, sugar, carbs, ingredients_low):
    tags = set(raw_tags)
    kt = {t.lower() for t in karo_tags}
    if tags & DESSERT_TAGS or category in DESSERT_CATS or "dessert" in kt:
        return set()
    is_drink = "beverages" in tags or category in {"Beverages", "Punch Beverage", "Shakes", "Smoothies"}
    is_smoothie = bool(tags & {"smoothies", "shakes"}) or category in {"Smoothies", "Shakes"}
    if is_drink and not is_smoothie:
        return set()
    if (tags & COMPONENT_TAGS or category in COMPONENT_CATS) and not is_smoothie and "breakfast" not in tags:
        return set()
    if kcal and sugar is not None and kcal > 0 and (sugar * 4.0) / kcal > 0.5 and not is_smoothie:
        return set()
    types = set()
    if tags & BREAKFAST_TAGS or category in BREAKFAST_CATS or "breakfast" in kt:
        if 120 <= kcal <= 900:
            types.add("breakfast")
    if (tags & MAIN_TAGS or category in MAIN_CATS or "one dish meal" in kt) and 200 <= kcal <= 1100:
        types.add("main")
    if (tags & SNACK_TAGS or category in SNACK_CATS or is_smoothie or "lunch/snacks" in kt) and 80 <= kcal <= 450:
        types.add("snack")
    return types


def focus_tags_for(kcal, protein, carbs, fat, fiber, serving_g):
    tags = set()
    if not kcal or kcal <= 0:
        return tags
    p_share = protein * 4.0 / kcal
    c_share = carbs * 4.0 / kcal
    if p_share >= 0.25 and protein >= 12:
        tags.add("high_protein")
    if c_share <= 0.20:
        tags.add("low_carb")
    if c_share >= 0.55:
        tags.add("high_carb")
    if fiber is not None and fiber >= 5:
        tags.add("high_fiber")
    if serving_g and serving_g > 0 and kcal / serving_g <= 1.5:
        tags.add("low_energy_density")
    if c_share >= 0.55 and fat <= 10 and (fiber is None or fiber <= 6) and 100 <= kcal <= 450:
        tags.add("pre_workout")
    if protein >= 15 and carbs >= 20:
        tags.add("post_workout")
    return tags


def format_ingredient_line(g):
    q = (g.get("quantity") or "").strip()
    u = (g.get("unit") or "").strip()
    n = (g.get("name") or "").strip()
    d = (g.get("description") or "").strip()
    line = " ".join(x for x in [q, u, n] if x)
    if d:
        line += f", {d}" if not d.startswith("(") else f" {d}"
    return line


# ----------------------------------------------------------------------------------------------
# USDA
# ----------------------------------------------------------------------------------------------
def build_usda():
    if not os.path.isdir(USDA_DIR):
        if not os.path.exists(USDA_ZIP):
            raise SystemExit(f"USDA SR Legacy not found at {USDA_ZIP}. See data/raw/diet/README.md")
        log("Extracting USDA SR Legacy zip...")
        with zipfile.ZipFile(USDA_ZIP) as z:
            z.extractall(os.path.dirname(USDA_DIR))
    log("Building USDA nutrient table...")
    wanted = {"1008": "kcal", "2047": "kcal_atwater_general", "2048": "kcal_atwater_specific",
              "1003": "protein", "1004": "fat", "1005": "carbs", "1079": "fiber"}
    foods = {}
    with open(os.path.join(USDA_DIR, "food.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            foods[row["fdc_id"]] = {"fdc_id": int(row["fdc_id"]), "description": row["description"],
                                    "category_id": int(row["food_category_id"] or 0), "nutrients": {}, "portions": []}
    with open(os.path.join(USDA_DIR, "food_nutrient.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = wanted.get(row["nutrient_id"])
            if key and row["fdc_id"] in foods:
                v = to_float(row["amount"])
                if v is not None:
                    foods[row["fdc_id"]]["nutrients"][key] = v
    units = {}
    with open(os.path.join(USDA_DIR, "measure_unit.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            units[row["id"]] = row["name"]
    with open(os.path.join(USDA_DIR, "food_portion.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["fdc_id"] not in foods:
                continue
            grams = to_float(row["gram_weight"])
            amount = to_float(row["amount"]) or 1.0
            if not grams:
                continue
            unit_name = units.get(row["measure_unit_id"], "")
            if unit_name == "undetermined":
                unit_name = ""
            foods[row["fdc_id"]]["portions"].append([amount, unit_name, (row["modifier"] or "").strip(), grams])
    cats = {}
    with open(os.path.join(USDA_DIR, "food_category.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cats[int(row["id"])] = row["description"]
    out_foods = []
    for food in foods.values():
        n = food["nutrients"]
        kcal = n.get("kcal", n.get("kcal_atwater_general", n.get("kcal_atwater_specific")))
        if kcal is None or "protein" not in n or "fat" not in n or "carbs" not in n:
            continue
        out_foods.append({
            "fdc_id": food["fdc_id"], "description": food["description"],
            "category": cats.get(food["category_id"], ""), "source": "USDA SR Legacy (2018-04)",
            "kcal": kcal, "protein": n["protein"], "fat": n["fat"], "carbs": n["carbs"],
            "fiber": n.get("fiber"), "portions": food["portions"],
        })
    with open(SUPPLEMENT_JSON, encoding="utf-8") as f:
        supp = json.load(f)
    for s in supp["foods"]:
        out_foods.append({
            "fdc_id": s["fdc_id"], "description": s["description"], "category": "Supplementary (FoodData Central)",
            "source": f"USDA FoodData Central, {s['data_type']}", "kcal": s["kcal"], "protein": s["protein"],
            "fat": s["fat"], "carbs": s["carbs"], "fiber": s.get("fiber"), "portions": [], "aliases": s["aliases"],
        })
    os.makedirs(os.path.dirname(OUT_USDA), exist_ok=True)
    with open(OUT_USDA, "w", encoding="utf-8") as f:
        json.dump({"source": "USDA FoodData Central SR Legacy 2018-04 (public domain) + supplementary FDC records",
                   "units": "per 100 g; portions = [amount, unit, modifier, gram_weight]", "foods": out_foods}, f)
    log(f"USDA foods written: {len(out_foods)} -> {OUT_USDA}")
    return len(out_foods)


# ----------------------------------------------------------------------------------------------
# Recipes
# ----------------------------------------------------------------------------------------------
def build_recipes(tmpdir):
    stats = {"parsed_rows": 0, "with_photo_id": 0, "joined_raw": 0, "name_mismatch": 0, "no_steps": 0,
             "no_servings": 0, "bad_nutrition": 0, "alcohol": 0, "not_meal": 0, "duplicates": 0, "plan_ready": 0,
             "lookup_grams": 0, "lookup_pdv": 0}

    log("Indexing RAW_recipes.csv (steps, tags, %DV nutrition)...")
    tmp_raw = os.path.join(tmpdir, "raw_index.db")
    rdb = sqlite3.connect(tmp_raw)
    rdb.execute("CREATE TABLE raw (id INTEGER PRIMARY KEY, name TEXT, minutes INTEGER, tags TEXT, nutrition TEXT, "
                "steps TEXT, ingredients TEXT, description TEXT)")
    batch = []
    with open(RAW_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                rid = int(row["id"])
            except (TypeError, ValueError):
                continue
            batch.append((rid, row["name"], int(to_float(row["minutes"]) or 0), row["tags"], row["nutrition"],
                          row["steps"], row["ingredients"], row["description"]))
            if len(batch) >= 5000:
                rdb.executemany("INSERT OR IGNORE INTO raw VALUES (?,?,?,?,?,?,?,?)", batch)
                batch = []
    if batch:
        rdb.executemany("INSERT OR IGNORE INTO raw VALUES (?,?,?,?,?,?,?,?)", batch)
    rdb.commit()
    log(f"RAW rows indexed: {rdb.execute('SELECT COUNT(*) FROM raw').fetchone()[0]:,}")

    cleaned_cuisine = {}
    if os.path.exists(CLEANED_CSV):
        with open(CLEANED_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    cleaned_cuisine[int(row["recipe_id"])] = row.get("cuisine", "")
                except (TypeError, ValueError):
                    pass

    tmp_out = os.path.join(tmpdir, "diet_recipes.db")
    if os.path.exists(tmp_out):
        os.remove(tmp_out)
    db = sqlite3.connect(tmp_out)
    db.executescript("""
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        CREATE TABLE recipes (
            id INTEGER PRIMARY KEY, name TEXT, name_norm TEXT, description TEXT, category TEXT, tags TEXT,
            cuisines TEXT, diet TEXT, diet_flags TEXT, diet_verify TEXT, allergens TEXT, meal_types TEXT,
            focus_tags TEXT, image_url TEXT, images TEXT, ingredients TEXT, ingredient_lines TEXT,
            ingredient_text TEXT, steps TEXT, servings REAL, serving_size_g REAL,
            kcal REAL, protein REAL, carbs REAL, fat REAL, fiber REAL, sugar REAL, sodium REAL, sat_fat REAL,
            prep_min INTEGER, cook_min INTEGER, total_min INTEGER, source_url TEXT
        );
        CREATE TABLE lookup (
            id INTEGER PRIMARY KEY, name_norm TEXT, image_url TEXT, servings REAL,
            kcal REAL, protein REAL, carbs REAL, fat REAL, fiber REAL, sugar REAL, sodium REAL, sat_fat REAL,
            basis TEXT, in_recipes INTEGER DEFAULT 0
        );
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
    """)

    log("Joining parsed Food.com crawl with RAW recipes...")
    seen = set()
    rec_batch, look_batch = [], []
    with open(PARSED_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            stats["parsed_rows"] += 1
            images = [u for u in parse_list(row.get("images")) if isinstance(u, str) and u.startswith("http")]
            if not images:
                continue
            m = IMG_ID_RE.search(images[0])
            if not m:
                continue
            rid = int(m.group(1).replace("/", ""))
            stats["with_photo_id"] += 1
            raw = rdb.execute("SELECT name, minutes, tags, nutrition, steps, ingredients, description FROM raw WHERE id=?",
                              (rid,)).fetchone()
            kcal = to_float(row["calories"])
            protein = to_float(row["protein"])
            carbs = to_float(row["carbohydrates"])
            fat = to_float(row["total_fat"])
            fiber = to_float(row["fiber"])
            sugar = to_float(row["sugar"])
            sodium = to_float(row["sodium"])
            sat_fat = to_float(row["saturated_fat"])
            servings = to_float(row["servings"])
            serving_g = to_float(row["serving_size"])
            name = (row["name"] or "").strip()
            nn = norm_name(name)
            if rid in seen:
                stats["duplicates"] += 1
                continue
            # Lookup entry (photo + gram nutrition) even for recipes that are not plan-ready
            if kcal is not None and protein is not None and carbs is not None and fat is not None:
                look_batch.append((rid, nn, images[0], servings, kcal, protein, carbs, fat, fiber, sugar, sodium, sat_fat,
                                   "foodcom_grams"))
                stats["lookup_grams"] += 1
            seen.add(rid)
            if not raw:
                continue
            stats["joined_raw"] += 1
            raw_name, minutes, raw_tags_s, raw_nut_s, raw_steps_s, raw_ings_s, raw_desc = raw
            # Validate the join: the two crawls must describe the same recipe.
            a, b = set(norm_name(raw_name).split()), set(nn.split())
            if not a or not b or len(a & b) / max(1, min(len(a), len(b))) < 0.5:
                stats["name_mismatch"] += 1
                continue
            steps = [s.strip() for s in parse_list(raw_steps_s) if isinstance(s, str) and s.strip()]
            if len(steps) < 2:
                stats["no_steps"] += 1
                continue
            if not servings or servings <= 0:
                # Per-serving nutrition is still valid; only ingredient-level edits need the serving count.
                stats["no_servings"] += 1
                servings = None
            if None in (kcal, protein, carbs, fat) or kcal < 50 or kcal > 1300 or min(protein, carbs, fat) < 0 or \
                    (fiber is not None and (fiber > 45 or fiber * 1000.0 / kcal > 60)):
                stats["bad_nutrition"] += 1
                continue
            atwater = 4 * protein + 4 * carbs + 9 * fat
            if abs(atwater - kcal) / kcal > 0.25:
                stats["bad_nutrition"] += 1
                continue
            ings = [g for g in parse_list(row["ingredients"]) if isinstance(g, dict) and (g.get("name") or "").strip()]
            if len(ings) < 2:
                stats["bad_nutrition"] += 1
                continue
            raw_ings = [s for s in parse_list(raw_ings_s) if isinstance(s, str)]
            names = [g["name"].strip() for g in ings] + raw_ings
            names_low = [n.lower() for n in names]
            if any(ALCOHOL_RE.search(n) for n in names_low):
                stats["alcohol"] += 1
                continue
            raw_tags = [t for t in parse_list(raw_tags_s) if isinstance(t, str)]
            karo_tags = [t for t in parse_list(row.get("tags")) if isinstance(t, str)]
            category = (row.get("RecipeCategory") or "").strip()
            mtypes = meal_types_for(category, raw_tags, karo_tags, kcal, sugar, carbs, names_low)
            if not mtypes:
                stats["not_meal"] += 1
                continue
            diet, flags = classify_diet(names)
            if diet != "non_vegetarian" and metadata_says_meat(raw_tags, category):
                # Food.com's own main-ingredient tags/category say meat or fish even if the list omits it
                diet = "non_vegetarian"
                flags["meat_or_fish"] = True
                flags["from_metadata"] = True
                stats["diet_from_metadata"] = stats.get("diet_from_metadata", 0) + 1
            verify = diet_verification(names, diet)
            if diet != "non_vegetarian":
                tw = title_meat_warning(name)
                if tw:
                    verify.append(tw)
                    stats["title_verify"] = stats.get("title_verify", 0) + 1
            allergens = detect_allergens(names, flags)
            cuisines = classify_cuisine(cleaned_cuisine.get(rid, ""), raw_tags, karo_tags, nn)
            focus = focus_tags_for(kcal, protein, carbs, fat, fiber, serving_g)
            prep = int(to_float(row.get("preparation_time")) or 0)
            cook = int(to_float(row.get("cooking_time")) or 0)
            total = prep + cook if (prep + cook) > 0 else int(minutes or 0)
            clean_ings = [{"quantity": (g.get("quantity") or "").strip(), "unit": (g.get("unit") or "").strip(),
                           "name": g["name"].strip(), "description": (g.get("description") or "").strip()} for g in ings]
            steps_fmt = [s[0].upper() + s[1:] if s else s for s in steps]
            rec_batch.append((
                rid, name, nn, (row.get("description") or raw_desc or "").strip()[:600], category,
                json.dumps(sorted(set(raw_tags))[:40]), "," + ",".join(cuisines) + ",", diet, json.dumps(flags),
                json.dumps(verify), json.dumps(allergens), "," + ",".join(sorted(mtypes)) + ",",
                "," + ",".join(sorted(focus)) + ",", images[0], json.dumps(images[:4]), json.dumps(clean_ings),
                json.dumps([format_ingredient_line(g) for g in clean_ings]), " | ".join(names_low),
                json.dumps(steps_fmt), servings, serving_g, kcal, protein, carbs, fat, fiber, sugar, sodium, sat_fat,
                prep, cook, total, f"https://www.food.com/recipe/{rid}"))
            stats["plan_ready"] += 1
            if len(rec_batch) >= 2000:
                db.executemany("INSERT OR IGNORE INTO recipes VALUES (" + ",".join(["?"] * 33) + ")", rec_batch)
                rec_batch = []
            if len(look_batch) >= 5000:
                db.executemany("INSERT OR IGNORE INTO lookup (id,name_norm,image_url,servings,kcal,protein,carbs,fat,fiber,"
                               "sugar,sodium,sat_fat,basis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", look_batch)
                look_batch = []
            if stats["parsed_rows"] % 100000 == 0:
                log(f"  ... {stats['parsed_rows']:,} rows, plan-ready {stats['plan_ready']:,}")
    if rec_batch:
        db.executemany("INSERT OR IGNORE INTO recipes VALUES (" + ",".join(["?"] * 33) + ")", rec_batch)
    if look_batch:
        db.executemany("INSERT OR IGNORE INTO lookup (id,name_norm,image_url,servings,kcal,protein,carbs,fat,fiber,"
                       "sugar,sodium,sat_fat,basis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", look_batch)
    db.commit()

    log("Adding %DV-derived nutrition for Food.com recipes that have no gram values...")
    have = {r[0] for r in db.execute("SELECT id FROM lookup")}
    batch = []
    for rid, name, nut_s in rdb.execute("SELECT id, name, nutrition FROM raw"):
        if rid in have:
            continue
        nut = parse_list(nut_s)
        if len(nut) != 7:
            continue
        try:
            kcal, fat_pdv, sugar_pdv, sodium_pdv, protein_pdv, satfat_pdv, carb_pdv = [float(x) for x in nut]
        except (TypeError, ValueError):
            continue
        if kcal <= 0:
            continue
        batch.append((rid, norm_name(name), None, None, kcal,
                      round(protein_pdv * PDV_REFERENCE_G["protein"] / 100, 1),
                      round(carb_pdv * PDV_REFERENCE_G["carbs"] / 100, 1),
                      round(fat_pdv * PDV_REFERENCE_G["fat"] / 100, 1),
                      None, None, None, None, "foodcom_pdv_derived"))
        stats["lookup_pdv"] += 1
        if len(batch) >= 5000:
            db.executemany("INSERT OR IGNORE INTO lookup (id,name_norm,image_url,servings,kcal,protein,carbs,fat,fiber,"
                           "sugar,sodium,sat_fat,basis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
            batch = []
    if batch:
        db.executemany("INSERT OR IGNORE INTO lookup (id,name_norm,image_url,servings,kcal,protein,carbs,fat,fiber,"
                       "sugar,sodium,sat_fat,basis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
    db.execute("UPDATE lookup SET in_recipes = 1 WHERE id IN (SELECT id FROM recipes)")
    db.executescript("""
        CREATE INDEX idx_recipes_diet ON recipes(diet);
        CREATE INDEX idx_recipes_kcal ON recipes(kcal);
        CREATE INDEX idx_recipes_name_norm ON recipes(name_norm);
        CREATE INDEX idx_lookup_name_norm ON lookup(name_norm);
    """)
    for k, v in stats.items():
        db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (k, str(v)))
    db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", ("built_at", time.strftime("%Y-%m-%d %H:%M:%S")))
    db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", ("pdv_reference_g", json.dumps(PDV_REFERENCE_G)))
    db.commit()
    counts = {d: db.execute("SELECT COUNT(*) FROM recipes WHERE diet=?", (d,)).fetchone()[0]
              for d in ("vegan", "vegetarian", "eggitarian", "non_vegetarian")}
    for mt in ("breakfast", "main", "snack"):
        counts[mt] = db.execute("SELECT COUNT(*) FROM recipes WHERE meal_types LIKE ?", (f"%,{mt},%",)).fetchone()[0]
    for c in ("indian", "italian", "continental"):
        counts[c] = db.execute("SELECT COUNT(*) FROM recipes WHERE cuisines LIKE ?", (f"%,{c},%",)).fetchone()[0]
    db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", ("counts", json.dumps(counts)))
    db.commit()
    db.execute("VACUUM")
    db.close()
    rdb.close()
    log(f"Stats: {json.dumps(stats)}")
    log(f"Counts: {json.dumps(counts)}")
    return tmp_out


def main():
    for p in (PARSED_CSV, RAW_CSV):
        if not os.path.exists(p):
            raise SystemExit(f"Missing input {p}. See data/raw/diet/README.md")
    build_usda()
    tmpdir = tempfile.mkdtemp(prefix="nourish_diet_build_")
    try:
        built = build_recipes(tmpdir)
        os.makedirs(os.path.dirname(OUT_DB), exist_ok=True)
        shutil.copyfile(built, OUT_DB)
        log(f"Recipe database written -> {OUT_DB} ({os.path.getsize(OUT_DB) / 1e6:.1f} MB)")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
