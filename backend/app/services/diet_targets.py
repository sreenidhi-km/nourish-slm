"""
diet_targets.py
===============
Transparent, individual estimates of daily nutritional targets. Every target carries the method
and assumptions behind it, and nothing is calculated from data the user did not provide:
without age, height and weight there is no energy estimate, only proportion-based guidance.

Reference values used (general guidance, not prescriptions):
* Energy: Mifflin-St Jeor resting energy x physical activity level (PAL).
* Protein: 0.8 g/kg RDA for adults; 1.2-2.0 g/kg for athletes (ACSM / AND / DC joint position stand,
  Thomas et al., 2016); 1.6-2.2 g/kg to support muscle gain (ISSN position stand, Jager et al., 2017;
  Morton et al., 2018); 20-40 g (0.25-0.40 g/kg) per meal spread through the day (ISSN).
* Carbohydrate for training days (Thomas et al., 2016 / Burke et al., 2011): light 3-5 g/kg,
  moderate ~1 h/day 5-7 g/kg, high 1-3 h/day 6-10 g/kg, very high >4-5 h/day 8-12 g/kg.
* Acceptable Macronutrient Distribution Ranges (US Institute of Medicine): carbohydrate 45-65 %,
  fat 20-35 %, protein 10-35 % of energy. Low-carbohydrate: below ~26 % of energy (<130 g/day).
* Fibre: 14 g per 1,000 kcal (Dietary Guidelines for Americans 2020-2025).
* Hydration: 5-7 ml/kg about 4 h before exercise (Thomas et al., 2016).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend.app.services.diet_catalog import ACTIVITY_LEVELS

REFERENCES = [
    "Thomas DT, Erdman KA, Burke LM. Nutrition and Athletic Performance. Joint position statement of the ACSM, "
    "Academy of Nutrition and Dietetics and Dietitians of Canada. Med Sci Sports Exerc. 2016.",
    "Jager R et al. ISSN Position Stand: protein and exercise. J Int Soc Sports Nutr. 2017.",
    "Mifflin MD, St Jeor ST et al. A new predictive equation for resting energy expenditure. Am J Clin Nutr. 1990.",
    "Institute of Medicine. Dietary Reference Intakes for Energy, Carbohydrate, Fiber, Fat, Fatty Acids, "
    "Cholesterol, Protein, and Amino Acids. 2005 (AMDR, fibre AI).",
    "U.S. Dietary Guidelines for Americans 2020-2025 (14 g fibre per 1,000 kcal).",
]

CARB_LOAD_G_PER_KG = {"light": (3, 5), "moderate": (5, 7), "high": (6, 10), "very_high": (8, 12)}
LOAD_LABEL = {"light": "light", "moderate": "moderate (about 1 hour a day)", "high": "high (1-3 hours a day)",
              "very_high": "very high (4+ hours a day)"}


def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def training_load(profile: Dict[str, Any]) -> Optional[str]:
    if not profile.get("sport"):
        return None
    minutes = _num(profile.get("session_minutes")) or 0
    intensity = profile.get("intensity") or "moderate"
    if minutes >= 240:
        return "very_high"
    if minutes >= 90 and intensity != "light":
        return "high"
    if minutes >= 45 and intensity != "light":
        return "moderate"
    return "light"


def activity_factor(profile: Dict[str, Any]) -> Tuple[float, str, bool]:
    """Returns (PAL, explanation, assumed?)."""
    level = profile.get("activity_level")
    if level in ACTIVITY_LEVELS:
        desc, pal = ACTIVITY_LEVELS[level]
        return pal, f"activity level '{desc}' (PAL {pal})", False
    if profile.get("sport"):
        days = _num(profile.get("training_days_per_week")) or 0
        minutes = _num(profile.get("session_minutes")) or 0
        hours = days * minutes / 60.0
        if hours < 3:
            pal = 1.375
        elif hours < 6:
            pal = 1.55
        elif hours < 10:
            pal = 1.725
        else:
            pal = 1.9
        return pal, f"about {hours:.1f} h of training a week (PAL {pal})", False
    return 1.375, "light activity (PAL 1.375) - assumed because no activity level was given", True


def compute_targets(profile: Dict[str, Any], category: Dict[str, Any]) -> Dict[str, Any]:
    w = _num(profile.get("weight_kg"))
    h = _num(profile.get("height_cm"))
    age = _num(profile.get("age"))
    sex = (profile.get("sex") or "").lower() or None
    goal = profile.get("goal") or "maintain"
    style = category.get("macro_style", "balanced")
    if goal == "muscle_gain" and style in ("balanced", "sport"):
        style = "strength"
    if goal == "weight_loss" and style == "balanced":
        style = "weight_loss"
    is_training_day = bool(profile.get("sport")) and (profile.get("day_type") or "training") == "training"
    load = training_load(profile) if is_training_day else None

    assumptions: List[str] = []
    missing: List[str] = []
    notes: List[str] = []

    # ---------------- Energy ----------------
    energy = None
    pal, pal_text, pal_assumed = activity_factor(profile)
    if profile.get("sport") and not is_training_day:
        pal = round(max(1.2, pal - 0.175), 3)
        pal_text += f", reduced to PAL {pal} for a rest day"
    if pal_assumed:
        assumptions.append(pal_text)
    if w and h and age:
        bmr_m = 10 * w + 6.25 * h - 5 * age + 5
        bmr_f = 10 * w + 6.25 * h - 5 * age - 161
        if sex in ("male", "m"):
            bmr_lo = bmr_hi = bmr_m
            sex_text = "male equation"
        elif sex in ("female", "f"):
            bmr_lo = bmr_hi = bmr_f
            sex_text = "female equation"
        else:
            bmr_lo, bmr_hi = bmr_f, bmr_m
            sex_text = "average of the male and female equations (sex not provided)"
            assumptions.append("Sex not provided: the energy range spans both Mifflin-St Jeor equations.")
        bmr = (bmr_lo + bmr_hi) / 2
        tdee = bmr * pal
        adj = {"weight_loss": (0.80, 0.85, 0.90, "a moderate 10-20 % deficit"),
               "weight_gain": (1.05, 1.10, 1.15, "a 5-15 % surplus"),
               "muscle_gain": (1.05, 1.10, 1.15, "a 5-15 % surplus to support muscle gain")}.get(
            goal, (0.95, 1.00, 1.05, "maintenance (+/- 5 %)"))
        target = tdee * adj[1]
        low = bmr_lo * pal * adj[0]
        high = bmr_hi * pal * adj[2]
        energy = {"target": round(target), "low": round(low), "high": round(high), "unit": "kcal",
                  "basis": (f"Mifflin-St Jeor resting energy {round(bmr)} kcal ({sex_text}) x {pal_text} = "
                            f"{round(tdee)} kcal, adjusted for {adj[3]}")}
        if target < bmr:
            notes.append("The estimated target is below your resting energy needs. Please discuss intakes this low "
                         "with a qualified healthcare professional.")
    else:
        for k, label in (("age", "age"), ("height_cm", "height"), ("weight_kg", "weight")):
            if not _num(profile.get(k)):
                missing.append(label)

    def pct_range(lo_pct, hi_pct, kcal_per_g):
        if not energy:
            return None
        return (round(energy["target"] * lo_pct / 100 / kcal_per_g), round(energy["target"] * hi_pct / 100 / kcal_per_g))

    # ---------------- Protein ----------------
    protein_gkg = {"strength": (1.6, 2.2), "endurance": (1.2, 1.6), "sport": (1.4, 1.8), "high_protein": (1.2, 1.6),
                   "weight_loss": (1.2, 1.6), "weight_gain": (1.0, 1.6), "low_carb": (1.0, 1.5)}.get(style)
    if goal == "recovery":
        protein_gkg = (1.0, 1.4)
    if protein_gkg is None:
        protein_gkg = (1.2, 1.6) if profile.get("sport") else (0.8, 1.0)
    protein_pct = {"high_protein": (25, 35), "strength": (20, 35), "low_carb": (20, 35)}.get(style, (10, 35))
    protein = None
    if w:
        protein = {"low": round(protein_gkg[0] * w), "high": round(protein_gkg[1] * w), "unit": "g",
                   "basis": f"{protein_gkg[0]}-{protein_gkg[1]} g per kg body weight for this goal"}
        if style == "high_protein" and energy:
            lo, hi = pct_range(25, 35, 4)
            protein["low"] = max(protein["low"], lo)
            protein["high"] = max(protein["high"], hi)
            protein["basis"] += " and at least 25 % of energy"
    elif energy:
        lo, hi = pct_range(*protein_pct, 4)
        protein = {"low": lo, "high": hi, "unit": "g", "basis": f"{protein_pct[0]}-{protein_pct[1]} % of energy"}
    protein_share = {"low": protein_pct[0], "high": protein_pct[1]}

    # ---------------- Carbohydrate ----------------
    carbs = None
    carb_pct = (45, 65)
    if style == "low_carb":
        carb_pct = (0, 26)
        carbs = {"low": None, "high": pct_range(0, 26, 4)[1] if energy else 130, "unit": "g",
                 "basis": "below about 26 % of energy (under 130 g a day) for a low-carbohydrate pattern"}
    elif load and w:
        lo, hi = CARB_LOAD_G_PER_KG[load]
        if style == "strength":
            lo, hi = min(lo, 4), min(hi, 7)
        carbs = {"low": round(lo * w), "high": round(hi * w), "unit": "g",
                 "basis": f"{lo}-{hi} g per kg for a {LOAD_LABEL[load]} training day"}
        carb_pct = (40, 70)
    elif profile.get("sport") and not is_training_day and w:
        carbs = {"low": round(3 * w), "high": round(5 * w), "unit": "g", "basis": "3-5 g per kg on a rest / light day"}
        carb_pct = (40, 65)
    elif energy:
        lo, hi = pct_range(45, 65, 4)
        carbs = {"low": lo, "high": hi, "unit": "g", "basis": "45-65 % of energy (AMDR)"}
    carb_share = {"low": carb_pct[0], "high": carb_pct[1]}

    # ---------------- Fat ----------------
    fat_pct = (30, 65) if style == "low_carb" else (20, 35)
    fat = None
    if energy:
        lo, hi = pct_range(*fat_pct, 9)
        fat = {"low": lo, "high": hi, "unit": "g",
               "basis": ("remaining energy after protein and carbohydrate (about 30-65 %)" if style == "low_carb"
                         else "20-35 % of energy (AMDR)")}
    fat_share = {"low": fat_pct[0], "high": fat_pct[1]}

    # ---------------- Fibre ----------------
    if energy:
        fiber = {"low": round(14 * energy["target"] / 1000), "high": None, "unit": "g", "basis": "14 g per 1,000 kcal"}
    else:
        fiber = {"low": 25, "high": None, "unit": "g", "basis": "at least about 25 g a day (adult adequate intake 25-38 g)"}

    # ---------------- Per-meal protein & hydration ----------------
    per_meal_protein = None
    if style in ("strength", "sport", "endurance", "high_protein") or goal in ("muscle_gain", "recovery"):
        per_meal_protein = ({"low": round(0.25 * w), "high": round(0.40 * w), "basis": "0.25-0.40 g/kg per meal"}
                            if w else {"low": 20, "high": 40, "basis": "20-40 g per main meal"})
    hydration = ["Drink regularly through the day; pale-yellow urine is a simple check."]
    if profile.get("sport"):
        if w:
            hydration.append(f"About {round(5 * w)}-{round(7 * w)} ml of fluid roughly 4 hours before training "
                             f"(5-7 ml per kg).")
        hydration.append("After training, replace about 1.25-1.5 litres for every kg of body weight lost during the session.")
        if (_num(profile.get("session_minutes")) or 0) >= 60:
            hydration.append("For sessions over an hour, especially in heat, fluids with sodium and carbohydrate can help.")

    if not energy:
        notes.append("Add your age, height and weight to get personal energy and gram targets. Until then the plan is "
                     "checked against healthy proportions of energy.")
    if profile.get("sport") and not w:
        notes.append("Sports carbohydrate and protein targets are set per kg of body weight; add your weight for them.")

    return {
        "energy": energy, "protein": protein, "carbs": carbs, "fat": fat, "fiber": fiber,
        "shares": {"protein": protein_share, "carbs": carb_share, "fat": fat_share},
        "per_meal_protein": per_meal_protein, "training_load": load, "is_training_day": is_training_day,
        "pal": pal, "hydration": hydration, "assumptions": assumptions, "missing": missing, "notes": notes,
        "macro_style": style, "references": REFERENCES,
        "disclaimer": ("These are estimates for general guidance. Specialised needs, medical conditions or clinical "
                       "diets should be discussed with a qualified healthcare professional or sports dietitian."),
    }
