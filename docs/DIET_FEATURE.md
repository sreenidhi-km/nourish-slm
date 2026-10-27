# Diet Planning, Sports Nutrition and Nutrition Display

This document describes the Diet section added to Nourish SLM: what it does, where the data comes
from, how nutrition is calculated and checked, and how to run it.

## 1. What the user sees

* **Sidebar:** a **Diet** entry sits above *Recent Chats*. Under it, **My Diet Plans** lists saved plans.
  Chat history, Saved Recipes, Favorites, Settings and Sign Out work as before. On screens narrower than
  900 px the sidebar becomes a slide-in drawer, opened with the menu button in the header.
* **Diet dashboard:** 24 cards in three groups:
  * Dietary preferences: Vegetarian, Vegan, Non-Vegetarian, Eggetarian, Balanced.
  * Fitness goals: Weight Loss, Weight Gain, Muscle Building, High-Protein, Low-Carbohydrate, Endurance
    and Stamina, Recovery and General Fitness.
  * Sports: Cricket, Football, Basketball, Tennis, Badminton, Swimming, Running and Marathon, Cycling, Gym
    and Strength, Bodybuilding, Yoga and General Fitness, Other Sports.

  Each card shows a real dish photo from the dataset (the dish is named under the photo), a description,
  the nutritional focus, the goal, and an **Explore Plan** button.
* **Plan page:**
  * A plan overview, plus daily totals compared with the user's own targets.
  * The daily meal schedule. Each meal has a photo, its time, servings, and nutrition labelled
    *Recipe data*, *Calculated estimate* or *Not available*. Its details hold the ingredients with
    quantities, the instructions, the dietary and allergen labels, and why the meal was chosen.
  * **Personalise:** a form where everything is optional.
  * **Check My Diet.**
  * **Save plan**, **Add a meal**, **Different meals**, and **Start another plan**.
  * The plan's own assistant, in a side panel on wide screens or a collapsible panel below the plan on
    smaller ones.
* **General chatbot:** recipe answers now include:
  * nutrition per serving (calories, protein, carbohydrate, fat, fibre);
  * the recipe photo, when it is the same recipe;
  * dietary and allergen labels;
  * ingredient quantities, when the recipe comes from the dataset.

  The model writes recipes without quantities. For those, nutrition is shown as *Not available*, with the
  reason, and the closest database recipe with verified nutrition is offered alongside. Greetings and
  "thanks" get a short text reply instead of a recipe card.

## 2. Datasets

| Dataset | Used for | Licence / terms |
| --- | --- | --- |
| Food.com *Recipes and Reviews* (2020 crawl, 522k recipes; parsed copy `Karo8870/food.com-parsed-dataset` on Hugging Face) | Structured ingredient quantities, servings, serving size, per-serving nutrition in grams (calories, protein, carbohydrate, fat, **fibre**, sugar, sodium), photo URLs | Original Kaggle release (irkaal) is CC0 1.0. Photos belong to their Food.com authors; the app links to them (hotlinking) and credits Food.com, it does not copy them. |
| Food.com *Recipes and Interactions* (`RAW_recipes.csv`, Majumder et al., EMNLP 2019) | Step-by-step instructions, tags (main ingredient / meal type), %DV nutrition for recipes outside the 2020 crawl | Research dataset already used to fine-tune Nourish SLM |
| USDA FoodData Central SR Legacy (2018-04) | Per-100 g nutrient values and household portion weights for ingredient-level recalculation | Public domain (CC0) |
| 12 supplementary FDC records (FNDDS and Branded): paneer, soya chunks/TVP, whey protein, idli, dosa, urad/toor/moong/masoor/chana dal, jaggery, poha | Indian and sports staples missing from SR Legacy | Public domain; branded entries are manufacturer label data and are marked as such (`data/reference/fdc_supplement_foods.json`) |

**Why this choice.** No single public dataset offers real instructions, ingredient quantities, gram-based
nutrition including fibre, and photos all at once. The 2020 Food.com crawl supplies quantities,
nutrition and photos. Its parsed copy lost the instructions, so each recipe is joined, by Food.com recipe
id (taken from the photo URL), to `RAW_recipes.csv`, which supplies the instructions. Joins whose names
disagree are rejected. Food.com covers Indian, Italian and Continental recipes, the cuisines the app
already supports. USDA FDC is the reference food-composition database for ingredient-level estimates.

**Cross-check.** For the 40,000 recipes present in both Food.com files, calories agree exactly, and the
%DV values convert to grams with a median factor of 0.50 (protein), 0.65 (fat) and 3.0 (carbohydrate).
These are the 2,000 kcal label references of 50 g, 65 g and 300 g. That conversion is used only for
`RAW_recipes.csv` recipes that have no gram values, and it is labelled as derived.

## 3. Processing (`scripts/build_diet_dataset.py`)

Uses the standard library only and takes about 2 minutes. Outputs:

* `data/processed/diet_recipes.db` (SQLite, about 260 MB)
* `data/processed/usda_foods.json`

The steps:

1. Index `RAW_recipes.csv` by id. Stream the 490k parsed rows and keep those with a photo whose id joins
   to a RAW recipe with matching name and at least 2 steps.
2. Drop invalid or duplicate rows. The nutrition must be present, the calories must be 50–1300 per
   serving, and protein, carbohydrate and fat must be consistent with the calories (Atwater
   4/4/9 ± 25 %). Implausible fibre is excluded. Recipes with alcohol and non-meal items (desserts,
   sauces, drinks other than smoothies) are left out of plan generation.
3. **Diet classification from ingredients**, never from the title:
   * the app's existing classifier;
   * an extra list of meat and fish cuts it did not cover (fryer, rump roast, sirloin, game hens…);
   * Food.com's own main-ingredient tags and categories.

   Ingredients of uncertain origin are stored as **needs verification** (Worcestershire sauce, unspecified
   broth, marshmallows, honey for vegans…). A title that mentions meat missing from the ingredient list
   is also flagged. Flagged recipes are kept out of plans for the diets they affect.
4. **Allergen detection** from ingredient names: dairy, egg, peanut, tree nuts, soy, gluten, fish,
   shellfish, sesame and mustard.
5. Meal-type tags (breakfast, main, snack), cuisine tags (Indian, Italian, Continental) and focus tags:
   * high_protein: at least 25 % of energy from protein
   * low_carb: at most 20 % of energy from carbohydrate
   * high_carb, high_fiber, low_energy_density
   * pre_workout: carbohydrate-rich, low in fat and fibre
   * post_workout: protein and carbohydrate
6. A `lookup` table holds per-serving nutrition and a photo for **all** 269k Food.com ids, so the
   general chatbot can attach nutrition to any recipe it retrieves.

Result: **46,514 plan-ready recipes**:

| Diet | Recipes |
| --- | --- |
| Vegan | 3,822 |
| Vegetarian | 6,972 |
| Eggetarian | 5,476 |
| Non-vegetarian | 30,244 |

| Cuisine | Recipes |
| --- | --- |
| Indian | 1,140 |
| Italian | 4,489 |
| Continental | 11,688 |

In addition, the USDA table holds 7,805 foods.

## 4. How nutrition is calculated (`backend/app/services/nutrition_service.py`)

One engine serves the chatbot, the plans, the assistants and Check My Diet. The frontend only displays
what the backend returns.

* **Recipe data:** the Food.com per-serving values multiplied by the servings eaten, in steps of 0.25.
* **Calculated estimate:** used when ingredients are changed. The meal's value is computed as:

  ```
  meal = published per-serving values × servings eaten
       + Σ (USDA[new ingredient] − USDA[original ingredient]) ÷ recipe servings × servings eaten
  ```

  Each ingredient is matched to a USDA food. The match comes from a curated table of about 200 common
  ingredients, a scored text search that refuses ambiguous single words such as "cheese", or the exact
  USDA record the user picks in the editor. Quantities are converted to grams as follows:
  * weights directly;
  * volumes through the USDA portion weight for that food (for example 1 cup of tofu = 252 g);
  * counts through USDA portion weights (1 large egg = 50 g, 1 clove of garlic = 3 g);
  * cans and packages only when the recipe states their size.
* **Not available:** shown whenever a match or conversion is missing, or the recipe doesn't state its
  number of servings. Values are never guessed. The reason is shown, and the daily total is marked as
  partial.
* Daily totals are the sum of the meals, and tests check this. Removing an ingredient can never push a
  value below 0; if it would, the app says so.

## 5. Targets (`diet_targets.py`)

Targets are individual. They are calculated only from what the user provides, and every target shows how
it was derived.

* **Energy:** Mifflin-St Jeor × physical activity level. The activity level is taken from the user's
  answer or from their training hours per week, and a rest day uses one level lower. The goal then
  adjusts it: −10 to 20 % for weight loss, +5 to 15 % for gain, ±5 % for maintenance. Without age, height
  and weight there is **no** energy target, and the review says *More Information Needed*. If sex is not
  given, the range spans both equations.
* **Protein:** g/kg depending on the goal:
  * general: 0.8–1.0
  * athletes: 1.2–2.0 (ACSM/AND/DC 2016)
  * strength and muscle gain: 1.6–2.2 (ISSN 2017)
  * weight loss: 1.2–1.6

  Plus a per-meal guide of 0.25–0.40 g/kg.
* **Carbohydrate for training days** follows ACSM 2016: 3–5, 5–7, 6–10 or 8–12 g/kg by training load,
  based on session length and intensity. Other plans use 45–65 % of energy (AMDR). Low-carb plans use
  ≤ 26 % of energy.
* **Fat** 20–35 % of energy. **Fibre** 14 g per 1,000 kcal. Hydration guidance is given in ml/kg.

## 6. Plan generation and editing (`diet_planner.py`)

* **Meal slots and timing** come from meals per day, training time and session length:
  * a main meal 1–4 h before training doubles as the pre-training meal;
  * otherwise a pre-training snack is placed 45–75 min before;
  * a recovery meal comes after the session, or the next main meal is used for recovery.
* **Recipe selection:**
  * Hard filters, applied in SQL: diet, allergies, intolerances, disliked foods, cuisine and maximum
    cooking time. Cuisine and cooking time are relaxed only if too few recipes match, and the plan says so.
  * Soft preferences: the category's focus tags.
  * A greedy optimiser then picks recipe options and portions so that energy, protein, carbohydrate and
    fat fall inside the user's ranges.
* **Edit operations** (all validated server-side and saved immediately, with version checks against
  edits from two windows):
  * replace, add or remove a meal; change servings or time; rename;
  * edit, add, remove or restore an ingredient; reset a meal;
  * update the profile, with or without rebuilding; get different meals.

  Every edit recalculates nutrition and totals and **re-runs the assessment**.
* Saved plans live in the existing database (new tables `diet_plans` and `diet_chat_messages`), linked to
  the logged-in user. Nothing beyond what the plan needs is stored. Body measurements are kept only inside
  the plan's profile, and only when the user enters them.

## 7. Check My Diet (`diet_assessment.py`)

Checks the current plan for:

* calories against the estimated range;
* protein, carbohydrate and fat against gram targets, or against energy shares when the weight is unknown;
* fibre;
* protein distribution across meals;
* pre-training meal composition and timing, and the recovery meal;
* conflicts with the diet, allergens and disliked foods, using ingredient-based detection;
* ingredients that need verification;
* missing or estimated data.

Each finding is typed so they are never confused: **restriction** (a detected conflict), **nutrient gap**
(a calculated difference) or **data / timing**. Each comes with an explanation.

The overall label is one of: *Well Aligned With Your Goals*, *Minor Adjustments Recommended*, *Significant
Gaps Identified* or *More Information Needed*. No single score is used. Suggestions are practical, and the
results claim no guaranteed outcome.

## 8. Plan-specific assistants (`diet_assistant.py`)

* **Separate contexts.** Every plan has its own conversation, stored per plan id in
  `diet_chat_messages`. The assistant receives only that plan: category, goal, diet, exclusions, meals,
  quantities, totals and the latest assessment. Plans are scoped to their owner (another user gets 404).
  Opening a plan again restores its chat.
* **What it understands:**
  * why a meal is included;
  * ingredient alternatives ("alternative to paneer", "replace X with Y");
  * replacing a meal (higher protein, lighter, low carb, Indian / Italian / Continental);
  * increasing a nutrient in a meal;
  * whether a snack suits eating before training;
  * what to eat after a workout;
  * whether the plan meets requirements and what to change;
  * rest-day adjustments and hydration.
* **Proposals, not silent changes.** A requested change comes back as a proposal: the operation plus a
  preview computed by applying it to a copy of the plan, which gives the new meal nutrition, the change to
  daily totals and the review label after the change. Candidates already respect the diet, allergies and
  dislikes. The plan changes only when the user presses **Apply**. The confirmation ("Your plan has been
  saved…") is written only after the database commit succeeds, and a proposal cannot be applied twice.
* **Model use.** Free-form questions use the **same loaded Qwen3-4B**, with the recipe LoRA temporarily
  disabled (PEFT `disable_adapter`) and the plan summary as context. No extra model is loaded, and one
  lock serialises generation. Any sentence in its reply that states calorie or gram figures is removed,
  so the model cannot invent nutrition values. If the model is unavailable (`SLM_GENERATE=false`), a
  deterministic help reply is used and everything else keeps working.

## 9. API (all under `/api/diet`, JWT protected)

| Method & path | Purpose |
| --- | --- |
| `GET /categories`, `GET /categories/{key}` | Diet cards (with dataset photo), detail, default profile, latest plan |
| `GET /options`, `GET /meta`, `POST /targets` | Form options, dataset info and licences, target preview |
| `GET /recipes`, `GET /recipes/{id}` | Search and filter recipes (diet, meal type, cuisine, focus, ingredients, allergens, time), paginated |
| `GET /ingredients/search`, `POST /nutrition/ingredient` | USDA food search, ingredient nutrition |
| `POST /plans`, `GET /plans`, `GET/PUT/DELETE /plans/{id}` | Create (generate), list, get, save/rename, delete |
| `POST /plans/{id}/edit` | Any edit operation (or a batch), with version check |
| `POST /plans/{id}/assess` | Check My Diet |
| `GET /plans/{id}/alternatives` | Replacement candidates that respect the plan's restrictions |
| `GET/POST /plans/{id}/chat`, `POST /plans/{id}/chat/{message_id}/apply` | Plan assistant history, message, apply a proposal |

Existing endpoints are unchanged. `POST /api/chat` now adds `nutrition`, `image_url`, `labels`,
`ingredient_quantities` and `related_recipe` to the recipe; these are optional fields, so older saved
recipes still load.

## 10. Running

```bash
# one-time: build the diet data (downloads ~690 MB, needs data/raw/RAW_recipes.csv)
bash scripts/download_diet_data.sh

# run as before
./run_on_mac.command          # also builds the diet data automatically if it is missing

# tests
SLM_GENERATE=false python -m pytest tests/test_classifier.py tests/test_backend.py \
    tests/test_synchronization.py tests/test_diet.py
```

Optional environment variables: `DIET_DB_PATH`, `USDA_FOODS_PATH` (default `data/processed/…`). No API
keys are required. The USDA data is bundled offline, so nothing is exposed to the frontend.

## 11. Limitations

* Diet and allergen labels come from ingredient names. A recipe whose ingredient list omits its main
  ingredient, and has no tag or title saying so, can still be mislabelled. Branded products can contain
  hidden animal products or allergens. Users with allergies should always check labels.
* Food.com is mostly North American. Indian recipes number about 1,140, so Indian-only plans sometimes
  fall back to other cuisines, and the plan says when this happens.
* Ingredient-level estimates depend on USDA matches. Unusual ingredients, unstated package sizes or
  recipes without a serving count make edited meals show *Not available* rather than a guess.
* Food.com photos are linked from Food.com's image CDN. They need an internet connection and remain the
  property of their authors.
* Targets are population equations and general sports-nutrition guidance, not individual prescriptions.
