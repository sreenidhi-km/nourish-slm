"""
diet_catalog.py
===============
Definitions of the Diet categories shown on the Diet dashboard. A category only supplies
defaults and soft preferences (what to look for when choosing recipes); every number in a plan
comes from the user's own answers and from the recipe / USDA data.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

GOALS = {
    "maintain": "Maintain current weight and eat well",
    "weight_loss": "Lose weight gradually",
    "weight_gain": "Gain weight",
    "muscle_gain": "Build muscle",
    "performance": "Fuel training and performance",
    "endurance": "Build endurance and stamina",
    "recovery": "Recover well and stay generally fit",
}
ACTIVITY_LEVELS = {
    "sedentary": ("Mostly sitting, little exercise", 1.2),
    "light": ("Light exercise 1-3 days a week", 1.375),
    "moderate": ("Moderate exercise 3-5 days a week", 1.55),
    "very_active": ("Hard exercise 6-7 days a week", 1.725),
    "extra_active": ("Very hard training or a physical job plus training", 1.9),
}
INTENSITIES = {"light": "Light / skill-based", "moderate": "Moderate", "high": "High / hard sessions"}

BASE_QUESTIONS = ["diet_preference", "goal", "activity_level", "age", "sex", "height_cm", "weight_kg", "allergies",
                  "intolerances", "dislikes", "cuisine", "meals_per_day", "max_prep_minutes"]
TRAINING_QUESTIONS = ["sport", "training_days_per_week", "session_minutes", "intensity", "training_time", "day_type"]


def _cat(key, group, name, description, focus, goal_text, defaults, macro_style, slot_focus=None,
         image_keywords=None, notes=None, questions=None, assistant=None):
    return {
        "key": key, "group": group, "name": name, "description": description, "focus": focus, "goal_text": goal_text,
        "defaults": defaults, "macro_style": macro_style, "slot_focus": slot_focus or {},
        "image_keywords": image_keywords or [], "notes": notes or [],
        "questions": questions or (BASE_QUESTIONS + (TRAINING_QUESTIONS if group in ("sports", "goals") else [])),
        "assistant_name": assistant or f"{name} Diet Assistant",
    }


SPORT_DEFAULTS = dict(goal="performance", activity_level=None, training_days_per_week=4, session_minutes=90,
                      intensity="moderate", training_time="17:00", day_type="training")

CATEGORIES: List[Dict[str, Any]] = [
    # ---------------- General dietary preferences ----------------
    _cat("vegetarian", "preferences", "Vegetarian", "Plant foods with dairy; no meat, fish or eggs.",
         "Plant proteins (dal, legumes, paneer, yoghurt) with whole grains and vegetables",
         "Balanced nutrition without meat, fish or eggs",
         {"diet_preference": "vegetarian", "goal": "maintain"}, "balanced",
         {"main": ["high_fiber", "high_protein"]}, ["dal", "paneer", "chickpea", "lentil"],
         ["Dairy, legumes and soy are useful protein sources on a vegetarian diet."]),
    _cat("vegan", "preferences", "Vegan", "Entirely plant based: no meat, fish, eggs, dairy or honey.",
         "Legumes, tofu, whole grains, nuts and seeds for protein and fibre",
         "Fully plant-based eating",
         {"diet_preference": "vegan", "goal": "maintain"}, "balanced",
         {"main": ["high_fiber", "high_protein"]}, ["chickpea", "lentil", "tofu", "bean"],
         ["Vitamin B12 is not provided by plant foods; discuss supplementation with a health professional."]),
    _cat("non_vegetarian", "preferences", "Non-Vegetarian", "Includes meat, poultry, fish and eggs alongside plant foods.",
         "Lean meats, fish and eggs combined with grains and vegetables", "Varied, balanced eating",
         {"diet_preference": "non_vegetarian", "goal": "maintain"}, "balanced",
         {"main": ["high_protein"]}, ["chicken", "fish", "salmon"]),
    _cat("eggetarian", "preferences", "Eggetarian", "Vegetarian plus eggs; no meat or fish.",
         "Eggs, dairy and legumes for protein with whole grains and vegetables",
         "Vegetarian eating that includes eggs",
         {"diet_preference": "eggitarian", "goal": "maintain"}, "balanced",
         {"breakfast": ["high_protein"], "main": ["high_protein", "high_fiber"]}, ["egg", "omelet", "frittata"]),
    _cat("balanced", "preferences", "Balanced Diet", "A bit of everything in sensible proportions.",
         "Carbohydrate, protein and fat within the usual healthy ranges, plenty of fibre",
         "Everyday healthy eating", {"goal": "maintain"}, "balanced",
         {"main": ["high_fiber"]}, ["salad", "rice", "vegetable"]),

    # ---------------- Fitness and body goals ----------------
    _cat("weight_loss", "goals", "Weight Loss", "A moderate energy deficit with filling, high-fibre, protein-rich meals.",
         "Lower energy density, adequate protein, plenty of fibre", "Gradual, sustainable weight loss",
         {"goal": "weight_loss"}, "weight_loss",
         {"main": ["low_energy_density", "high_protein", "high_fiber"], "breakfast": ["high_protein", "high_fiber"],
          "snack": ["low_energy_density"]}, ["salad", "soup", "grilled"],
         ["A slow rate of loss is easier to sustain. Very low intakes should only be followed with medical supervision."]),
    _cat("weight_gain", "goals", "Weight Gain", "An energy surplus from nutrient-dense meals and snacks.",
         "Higher energy intake with balanced protein and carbohydrate", "Healthy weight gain",
         {"goal": "weight_gain"}, "weight_gain",
         {"main": ["high_carb", "high_protein"], "snack": ["post_workout"]}, ["peanut", "rice", "pasta"]),
    _cat("muscle_building", "goals", "Muscle Building", "Enough energy and protein, spread across the day, to support resistance training.",
         "Protein in every meal, sufficient total energy", "Support muscle gain alongside training",
         {"goal": "muscle_gain", **SPORT_DEFAULTS, "sport": "gym", "session_minutes": 60, "intensity": "high"},
         "strength", {"main": ["high_protein"], "breakfast": ["high_protein"], "snack": ["high_protein", "post_workout"]},
         ["chicken", "egg", "tofu", "paneer"]),
    _cat("high_protein", "goals", "High-Protein Diet", "Meals chosen for a high share of energy from protein.",
         "Protein-rich meals and snacks", "Higher protein intake",
         {"goal": "maintain"}, "high_protein",
         {"main": ["high_protein"], "breakfast": ["high_protein"], "snack": ["high_protein"]},
         ["chicken", "paneer", "lentil", "egg"]),
    _cat("low_carb", "goals", "Low-Carbohydrate Diet", "Fewer starchy foods and sugars; more protein, vegetables and healthy fats.",
         "Carbohydrate at or below about a quarter of energy", "Lower carbohydrate intake",
         {"goal": "maintain"}, "low_carb",
         {"main": ["low_carb"], "breakfast": ["low_carb"], "snack": ["low_carb"]}, ["salad", "grilled", "egg"],
         ["Low-carbohydrate diets are not suitable for everyone (for example some people taking diabetes medication); "
          "check with a health professional first."]),
    _cat("endurance", "goals", "Endurance and Stamina", "Carbohydrate-focused meals to fuel longer sessions.",
         "Carbohydrate availability for training, steady protein", "Build endurance and stamina",
         {"goal": "endurance", **SPORT_DEFAULTS, "sport": "running", "session_minutes": 75}, "endurance",
         {"main": ["high_carb"], "breakfast": ["high_carb"], "snack": ["pre_workout"]}, ["pasta", "oat", "rice"]),
    _cat("recovery", "goals", "Recovery and General Fitness", "Balanced meals with protein and carbohydrate after activity.",
         "Protein + carbohydrate around activity, fibre and variety", "Recover well and stay fit",
         {"goal": "recovery", **SPORT_DEFAULTS, "sport": "general_fitness", "session_minutes": 45, "intensity": "light",
          "training_days_per_week": 3}, "balanced",
         {"main": ["post_workout", "high_fiber"], "snack": ["post_workout"]}, ["smoothie", "yogurt", "quinoa"]),

    # ---------------- Sports ----------------
    _cat("cricket", "sports", "Cricket", "Long practice days and matches with bursts of activity.",
         "Steady carbohydrate across long days, protein for recovery, hydration in heat",
         "Training energy, concentration over long days, recovery",
         {**SPORT_DEFAULTS, "sport": "cricket", "session_minutes": 150, "training_time": "09:00"}, "sport",
         {"main": ["post_workout", "high_carb"], "snack": ["pre_workout"]}, ["dal", "rice", "curry"],
         ["Practice and match days can last many hours: portable snacks and regular fluids help.",
          "Match-day meals can be adjusted once you know the playing schedule."]),
    _cat("football", "sports", "Football", "High-intensity intermittent running over 90 minutes.",
         "Carbohydrate for training and match days, protein for recovery",
         "Match-day energy and recovery", {**SPORT_DEFAULTS, "sport": "football", "session_minutes": 90, "intensity": "high"},
         "sport", {"main": ["high_carb", "post_workout"], "snack": ["pre_workout"]}, ["pasta", "chicken", "rice"]),
    _cat("basketball", "sports", "Basketball", "Repeated sprints and jumps in fast-paced sessions.",
         "Carbohydrate for repeated high-intensity efforts, protein for recovery",
         "Energy for high-intensity play", {**SPORT_DEFAULTS, "sport": "basketball", "intensity": "high"},
         "sport", {"main": ["high_carb", "post_workout"], "snack": ["pre_workout"]}, ["wrap", "rice", "chicken"]),
    _cat("tennis", "sports", "Tennis", "Long rallies, matches of unpredictable length, often in the heat.",
         "Carbohydrate and fluids for long matches, protein for recovery", "Sustained match energy",
         {**SPORT_DEFAULTS, "sport": "tennis", "session_minutes": 90}, "sport",
         {"main": ["high_carb"], "snack": ["pre_workout"]}, ["pasta", "banana", "quinoa"]),
    _cat("badminton", "sports", "Badminton", "Fast, explosive movement in short rallies.",
         "Light, carbohydrate-based pre-training snacks; balanced recovery meals",
         "Speed and recovery between sessions", {**SPORT_DEFAULTS, "sport": "badminton", "session_minutes": 75, "intensity": "high"},
         "sport", {"main": ["post_workout"], "snack": ["pre_workout"]}, ["poha", "upma", "rice"]),
    _cat("swimming", "sports", "Swimming", "High training volume, often with early-morning sessions.",
         "Energy to match training volume, carbohydrate before sessions, protein after",
         "Fuel high training volume and recovery", {**SPORT_DEFAULTS, "sport": "swimming", "session_minutes": 90, "training_time": "06:00"},
         "sport", {"main": ["high_carb", "post_workout"], "breakfast": ["post_workout"], "snack": ["pre_workout"]},
         ["oat", "banana", "pancake"],
         ["Early sessions: a small, easily digested snack beforehand and a proper breakfast afterwards often works well."]),
    _cat("running", "sports", "Running and Marathon Training", "Endurance training from 5K to marathon.",
         "Carbohydrate availability for long runs, protein for recovery, hydration",
         "Endurance and race preparation", {**SPORT_DEFAULTS, "sport": "running", "session_minutes": 75, "training_time": "06:30"},
         "endurance", {"main": ["high_carb"], "breakfast": ["high_carb"], "snack": ["pre_workout"]},
         ["pasta", "oat", "potato"], ["Carbohydrate needs rise with distance; long-run days need more than easy days."]),
    _cat("cycling", "sports", "Cycling", "Long rides and interval sessions on the bike.",
         "Carbohydrate for long rides, fluids, protein for recovery", "Endurance and power on the bike",
         {**SPORT_DEFAULTS, "sport": "cycling", "session_minutes": 120, "training_time": "07:00"}, "endurance",
         {"main": ["high_carb"], "breakfast": ["high_carb"], "snack": ["pre_workout"]}, ["rice", "pasta", "banana"]),
    _cat("gym", "sports", "Gym and Strength Training", "Resistance training for strength and fitness.",
         "Adequate protein spread over the day, enough total energy", "Strength and fitness",
         {**SPORT_DEFAULTS, "sport": "gym", "session_minutes": 60, "intensity": "high"}, "strength",
         {"main": ["high_protein"], "breakfast": ["high_protein"], "snack": ["post_workout", "high_protein"]},
         ["chicken", "egg", "paneer", "tofu"]),
    _cat("bodybuilding", "sports", "Bodybuilding", "Hypertrophy-focused training with planned eating phases.",
         "High protein, energy matched to your phase (gain or cut)", "Muscle size and definition",
         {**SPORT_DEFAULTS, "sport": "bodybuilding", "session_minutes": 75, "intensity": "high", "goal": "muscle_gain"},
         "strength", {"main": ["high_protein"], "breakfast": ["high_protein"], "snack": ["high_protein"]},
         ["chicken", "egg", "tuna", "paneer"]),
    _cat("yoga", "sports", "Yoga and General Fitness", "Yoga, walking and light, regular activity.",
         "Light, balanced, fibre-rich meals; nothing heavy before practice", "General fitness and wellbeing",
         {**SPORT_DEFAULTS, "sport": "yoga", "session_minutes": 60, "intensity": "light", "training_time": "07:00",
          "goal": "maintain"}, "balanced", {"main": ["high_fiber"], "snack": ["pre_workout"]}, ["salad", "quinoa", "smoothie"]),
    _cat("other_sport", "sports", "Other Sports", "Tell us your sport and how you train.",
         "Built from your sport, training load and goal", "Tailored to your activity",
         {**SPORT_DEFAULTS, "sport": "other"}, "sport", {"main": ["post_workout"], "snack": ["pre_workout"]},
         ["rice", "chicken", "pasta"]),
]
CATEGORY_BY_KEY = {c["key"]: c for c in CATEGORIES}
GROUP_TITLES = {"preferences": "General Dietary Preferences", "goals": "Fitness and Body Goals",
                "sports": "Sports-Based Diet Plans"}


def get_category(key: str) -> Optional[Dict[str, Any]]:
    return CATEGORY_BY_KEY.get(key)


def default_profile(category: Dict[str, Any], user_preference: Optional[str] = None) -> Dict[str, Any]:
    d = dict(category["defaults"])
    profile = {
        "diet_preference": d.get("diet_preference") or (user_preference if user_preference and user_preference != "no_preference" else "no_preference"),
        "goal": d.get("goal", "maintain"),
        "activity_level": d.get("activity_level"),
        "sport": d.get("sport"),
        "training_days_per_week": d.get("training_days_per_week"),
        "session_minutes": d.get("session_minutes"),
        "intensity": d.get("intensity"),
        "training_time": d.get("training_time"),
        "day_type": d.get("day_type", "training" if d.get("sport") else "rest"),
        "age": None, "sex": None, "height_cm": None, "weight_kg": None,
        "allergies": [], "intolerances": [], "dislikes": [], "cuisine": "any",
        "meals_per_day": 5 if d.get("sport") else 4, "max_prep_minutes": None, "other_sport_name": None,
    }
    return profile


def is_training_plan(profile: Dict[str, Any]) -> bool:
    return bool(profile.get("sport")) and (profile.get("day_type") or "training") == "training"
