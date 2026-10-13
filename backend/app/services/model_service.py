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

    if not extracted:
        extracted = ["vegetables"]

    return extracted, detected_cuisine


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
    chat_id: str = None
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

    print("FINAL RESPONSE CREATED SUCCESSFULLY")
    print("=" * 60)

    return {
        "message": conversational_text,
        "recipe": recipe_output,
        "validation": validation
    }
