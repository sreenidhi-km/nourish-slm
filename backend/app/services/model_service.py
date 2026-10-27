"""
model_service.py
================
Orchestrates ingredient extraction, recipe retrieval knowledge lookup,
SLM model generation, dietary validation, and conversational conflict explanation.

Supported Cuisines (UI-exposed): Indian, Italian, Continental
Dietary Preferences: vegan, vegetarian, eggitarian, non_vegetarian, no_preference
"""

import re
from typing import List, Dict, Any, Tuple
from model.inference import slm_engine
from backend.app.services.retrieval_service import retrieval_service
from backend.app.services.recipe_validator import validate_recipe_against_preference
from backend.app.services.dietary_rules import DietaryPreference
from backend.app.services.recipe_enrichment import enrich_recipe
from backend.app.services.allergy_check import allergens_in_text, apply_allergy_check, normalize_allergies

# Only expose these three cuisines in the entire pipeline
ALLOWED_CUISINES = {"indian", "italian", "continental"}
ALLOWED_DIETARY_PREFERENCES = {"vegan", "vegetarian", "eggitarian", "non_vegetarian", "no_preference"}


def extract_ingredients_from_query(text: str) -> Tuple[List[str], str]:
    """
    Extracts raw ingredient names from natural language text.
    Only detects: Indian, Italian, Continental cuisines.

    Examples:
    - "I have potatoes, onions and tomatoes" -> ["potato", "onion", "tomato"], "General"
    - "Give me an Italian pasta recipe with garlic" -> ["pasta", "garlic"], "Italian"
    - "Indian vegan curry" -> ["curry"], "Indian"
    - "Continental grilled chicken" -> ["chicken"], "Continental"
    """
    cleaned = text.lower()

    # Only detect our three supported cuisines
    detected_cuisine = "General"
    if "italian" in cleaned:
        detected_cuisine = "Italian"
    elif "indian" in cleaned:
        detected_cuisine = "Indian"
    elif "continental" in cleaned:
        detected_cuisine = "Continental"

    # Strip conversational filler words AND cuisine names so they're not treated as ingredients
    fillers = [
        "i have", "give me a", "give me an", "recipe for", "what can i make with",
        "how to cook", "show me", "can you make", "with", "and", "some", "quick",
        "delicious", "healthy", "recipe", "dish", "food", "dinner", "lunch", "breakfast",
        "vegan", "vegetarian", "eggitarian", "non-vegetarian", "non vegetarian",
        "italian", "indian", "continental", "make me", "cook", "prepare", "please",
        "using", "any", "help me", "suggest", "a good", "something", "spicy", "fresh"
    ]
    for filler in fillers:
        cleaned = re.sub(r'\b' + re.escape(filler) + r'\b', ',', cleaned)

    tokens = re.split(r'[,;:\n]+', cleaned)
    extracted = []
    for tok in tokens:
        word = tok.strip()
        word = re.sub(r'^\d+(\.\d+)?\s*', '', word)  # remove leading numbers
        word = re.sub(r'[^a-z\s\-]', '', word).strip()
        if len(word) > 2 and word not in [
            "the", "for", "can", "you", "make", "food", "have", "get", "are",
            "this", "that", "what", "how", "why", "its", "use", "add", "put"
        ]:
            extracted.append(word)

    # "chickpeas onions tomatoes" (no commas): split a phrase into foods when every word is a known food
    split = []
    for word in extracted:
        split.extend(_segment_foods(word))
    extracted = list(dict.fromkeys(split))

    if not extracted:
        extracted = ["vegetables"]

    return extracted, detected_cuisine


_DISH_WORDS = {"curry", "masala", "stew", "soup", "salad", "bowl", "fry", "stir", "sabzi", "sabji", "gravy", "bake",
               "roast", "wrap", "sandwich", "pulao", "biryani", "dish", "meal", "tikka"}


def _segment_foods(phrase: str) -> List[str]:
    """Splits 'olive oil garlic pasta' into ['olive oil', 'garlic', 'pasta'] using known ingredient names
    (longest match first). Phrases that are themselves one ingredient, or contain unknown words, stay whole."""
    from backend.app.services.portion_estimator import is_known_food
    words = phrase.split()
    if len(words) < 2 or is_known_food(phrase):
        return [phrase]
    parts, i = [], 0
    while i < len(words):
        for j in range(len(words), i, -1):
            cand = " ".join(words[i:j])
            if is_known_food(cand):
                parts.append(cand)
                i = j
                break
        else:
            if words[i] not in _DISH_WORDS:
                return [phrase]       # an unknown word: keep the user's phrase as typed
            i += 1
    return parts if len(parts) > 1 else [phrase]


def validate_cuisine(cuisine: str) -> str:
    """Validates and normalizes cuisine. Returns 'All' if unsupported."""
    if not cuisine:
        return "All"
    c = cuisine.lower().strip()
    if c in ALLOWED_CUISINES:
        return cuisine.capitalize()
    if c in ["all", "general", "any", ""]:
        return "All"
    # Reject unsupported cuisines silently by falling back to All
    return "All"


def validate_preference(preference: str) -> str:
    """Validates dietary preference. Returns 'no_preference' if invalid."""
    if not preference:
        return "no_preference"
    p = preference.lower().strip()
    if p in ALLOWED_DIETARY_PREFERENCES:
        return p
    return "no_preference"


def generate_recipe_response(
    user_message: str,
    preference: str = "no_preference",
    requested_cuisine: str = "All",
    chat_id: str = None,
    allergies: List[str] = None,
) -> Dict[str, Any]:
    """
    Full recipe processing pipeline.
    """
    pref_clean = validate_preference(preference)
    cuisine_clean = validate_cuisine(requested_cuisine)

    # Debug Log
    print("=" * 60)
    print("CHAT REQUEST RECEIVED")
    print(f"  message: '{user_message}'")
    print(f"  preference: '{pref_clean}'")
    print(f"  cuisine: '{cuisine_clean}'")
    print(f"  chat_id: '{chat_id}'")

    extracted_ings, inferred_cuisine = extract_ingredients_from_query(user_message)

    # Use explicitly requested cuisine if valid, otherwise use inferred from message
    target_cuisine = cuisine_clean if cuisine_clean and cuisine_clean != "All" else (
        inferred_cuisine if inferred_cuisine != "General" else "All"
    )

    # Check if raw user input contains conflicting ingredients against preference
    initial_val = validate_recipe_against_preference(extracted_ings, pref_clean)
    has_input_conflict = not initial_val["passed"]

    # Structured Recipe Retrieval
    retrieved_recipes = retrieval_service.search_recipes(
        query_ingredients=extracted_ings,
        preference=pref_clean,
        cuisine=target_cuisine,
        top_k=1
    )

    retrieved_context = retrieved_recipes[0] if retrieved_recipes else None

    if retrieved_context:
        print(f"RETRIEVAL RESULT: Found '{retrieved_context['name']}' (Score: {retrieved_context['match_score']})")
    else:
        print("RETRIEVAL RESULT: No matching dataset recipe found. Triggering SLM dynamic recipe generator...")

    # SLM Model Generation
    recipe_output = slm_engine.generate_recipe(
        ingredients=extracted_ings,
        preference=pref_clean,
        cuisine=target_cuisine,
        retrieved_context=retrieved_context
    )

    # Force strict output metadata synchronization
    recipe_output["diet_type"] = pref_clean
    if target_cuisine and target_cuisine not in ["All", "General", ""]:
        recipe_output["cuisine"] = target_cuisine
    elif not recipe_output.get("cuisine"):
        recipe_output["cuisine"] = "General"

    # Allergy checkpoint: swap ingredients that contain the user's allergens, then re-check the diet
    allergies = normalize_allergies(allergies or [])
    if allergies:
        recipe_output = apply_allergy_check(recipe_output, allergies)
        recipe_output["validation"] = validate_recipe_against_preference(recipe_output["ingredients"], pref_clean)
        ac = recipe_output["allergy_check"]
        print(f"ALLERGY CHECK: {ac['checked']} passed={ac['passed']} swaps={len(ac['substitutions'])}")

    validation = recipe_output["validation"]
    print(f"VALIDATION RESULT: Passed = {validation['passed']}, Conflicts = {validation['conflicts']}")

    # Construct Conversational Text Message
    pref_label = pref_clean.replace('_', ' ').title()

    if has_input_conflict:
        violating = ", ".join(initial_val["violating_ingredients"])
        conversational_text = (
            f"Note: '{violating}' conflicts with your {pref_label} preference. "
            f"I've created a {pref_label} alternative recipe for you!"
        )
    else:
        cuisine_str = f" {recipe_output['cuisine']}" if recipe_output.get('cuisine') and recipe_output['cuisine'] not in ["General", "All"] else ""
        conversational_text = f"Here is your personalized{cuisine_str} {pref_label} recipe!"

    if allergies:
        typed = allergens_in_text(extracted_ings, allergies)
        ac = recipe_output["allergy_check"]
        if typed:
            conversational_text += (f" Heads up: what you typed contains {', '.join(typed).lower()}, which is on your "
                                    f"allergy list, so I replaced it.")
        elif ac["substitutions"]:
            conversational_text += f" I swapped {len(ac['substitutions'])} ingredient(s) to keep it free of your allergens."
        if not ac["passed"]:
            conversational_text += " Some ingredients could not be made allergen-free, so please check the warning on the card."

    # Attach nutrition, a matching photo and dietary labels (shared nutrition engine)
    recipe_output = enrich_recipe(recipe_output, retrieved_context, extracted_ings, pref_clean, target_cuisine,
                                  allergies=allergies)
    nut = recipe_output.get("nutrition") or {}
    print(f"NUTRITION: status={nut.get('status')} values={nut.get('values')}")

    print("FINAL RESPONSE CREATED SUCCESSFULLY")
    print("=" * 60)

    return {
        "message": conversational_text,
        "recipe": recipe_output,
        "validation": validation
    }
