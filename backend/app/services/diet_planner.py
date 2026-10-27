"""
diet_planner.py
===============
Builds and edits personalised meal plans from real recipes in diet_recipes.db.

* Meal slots (number and timing) come from the user's meals-per-day, training time and session length.
* Recipes are chosen with hard filters (diet, allergies, intolerances, disliked foods, cuisine, prep time)
  and soft preferences (the category's nutritional focus, closeness to the slot's energy share).
* Portions are whole recipe servings scaled in quarter steps; nutrition is always recomputed by
  nutrition_service, and every edit triggers recalculation and a fresh assessment.
"""

from __future__ import annotations

import copy
import hashlib
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.app.services.diet_catalog import get_category, is_training_plan
from backend.app.services.diet_recipe_store import (
    ALLERGEN_LABELS, DIET_LABELS, INTOLERANCE_TO_ALLERGEN, recipe_store, verification_conflicts,
)
from backend.app.services.diet_targets import compute_targets
from backend.app.services.nutrition_service import (
    NUTRIENT_KEYS, compute_meal_nutrition, parse_quantity, sum_nutrition, usda_db,
)

SLOT_LABELS = {"breakfast": "Breakfast", "morning_snack": "Mid-morning snack", "lunch": "Lunch",
               "pre_workout": "Pre-training snack", "post_workout": "Post-training meal",
               "evening_snack": "Evening snack", "dinner": "Dinner", "custom": "Meal"}
SLOT_KIND = {"breakfast": "breakfast", "morning_snack": "snack", "lunch": "main", "pre_workout": "snack",
             "post_workout": "post", "evening_snack": "snack", "dinner": "main", "custom": "main"}
SLOT_SHARE = {"breakfast": 0.25, "morning_snack": 0.09, "lunch": 0.30, "pre_workout": 0.08,
              "post_workout": 0.15, "evening_snack": 0.09, "dinner": 0.28, "custom": 0.15}
PORTIONS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
EDIT_OPS = ["replace_meal", "add_meal", "remove_meal", "set_servings", "set_time", "set_label", "update_ingredient",
            "remove_ingredient", "restore_ingredient", "add_ingredient", "reset_meal", "update_profile", "regenerate",
            "batch"]


class PlanError(ValueError):
    pass


# ----------------------------------------------------------------------------------------------
# Time helpers
# ----------------------------------------------------------------------------------------------
def _to_min(t: Optional[str], default: int) -> int:
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", t or "")
    if not m:
        return default
    return max(0, min(23 * 60 + 59, int(m.group(1)) * 60 + int(m.group(2))))


def _to_hhmm(m: int) -> str:
    m = max(0, min(23 * 60 + 59, int(round(m / 5.0) * 5)))
    return f"{m // 60:02d}:{m % 60:02d}"


def valid_time(t: str) -> bool:
    return bool(re.match(r"^([01]\d|2[0-3]):[0-5]\d$", t or ""))


# ----------------------------------------------------------------------------------------------
# Slots
# ----------------------------------------------------------------------------------------------
def build_slots(profile: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    notes: List[str] = []
    n = int(profile.get("meals_per_day") or 4)
    n = max(3, min(6, n))
    slots = [{"slot": "breakfast", "time": 8 * 60}, {"slot": "lunch", "time": 13 * 60},
             {"slot": "dinner", "time": 20 * 60}]
    training_extra = 0
    if is_training_plan(profile):
        t = _to_min(profile.get("training_time"), 17 * 60)
        dur = int(parse_quantity(profile.get("session_minutes"))[0] or 60)
        end = t + dur
        post_t = end + 30
        # Main meals that overlap the session move before it (if there is room) or after it
        for s in slots:
            if t - 60 <= s["time"] <= end + 15:
                before = t - 150
                others = [o["time"] for o in slots if o is not s]
                if before >= 6 * 60 and all(abs(before - o) >= 120 for o in others):
                    s["time"] = before
                else:
                    s["time"] = post_t
        # A main meal 1-4 h before the session already acts as the pre-training meal
        pre_meal = next((s for s in slots if t - 240 <= s["time"] <= t - 60), None)
        if pre_meal:
            pre_meal["pre"] = True
        else:
            slots.append({"slot": "pre_workout", "time": max(5 * 60, t - (45 if t < 8 * 60 else 75))})
            training_extra += 1
        merged = next((s for s in slots if s["slot"] != "pre_workout" and abs(s["time"] - post_t) <= 90), None)
        if merged:
            merged["post"] = True
            merged["time"] = max(merged["time"], post_t - 15)
        else:
            slots.append({"slot": "post_workout", "time": post_t})
            training_extra += 1
    snacks = max(0, n - 3 - training_extra)
    if n < 3 + training_extra:
        notes.append(f"Training adds {training_extra} eating occasion(s), so the plan has {3 + training_extra} instead of {n}.")
    for slot_name, at in (("morning_snack", 10 * 60 + 30), ("evening_snack", 16 * 60 + 30), ("evening_snack", 22 * 60)):
        if snacks <= 0:
            break
        if any(abs(s["time"] - at) < 90 for s in slots):
            alt = at + 120 if at + 120 < 22 * 60 + 30 else at - 120
            if any(abs(s["time"] - alt) < 75 for s in slots):
                continue
            at = alt
        slots.append({"slot": slot_name, "time": at})
        snacks -= 1
    slots.sort(key=lambda s: s["time"])
    shares = {}
    for s in slots:
        share = SLOT_SHARE[s["slot"]]
        if s.get("post"):
            share += 0.03
        shares[id(s)] = share
    total = sum(shares.values())
    out = []
    for s in slots:
        label = SLOT_LABELS[s["slot"]]
        if s.get("post"):
            label += " (post-training recovery)"
        elif s.get("pre"):
            label += " (pre-training)"
        out.append({"slot": s["slot"], "label": label, "time": _to_hhmm(s["time"]),
                    "kind": "post" if s.get("post") else SLOT_KIND[s["slot"]], "share": shares[id(s)] / total,
                    "post_training": bool(s.get("post")) or s["slot"] == "post_workout",
                    "pre_training": bool(s.get("pre")) or s["slot"] == "pre_workout"})
    return out, notes


# ----------------------------------------------------------------------------------------------
# Restrictions
# ----------------------------------------------------------------------------------------------
def excluded_allergens(profile: Dict[str, Any]) -> List[str]:
    out = set()
    for a in profile.get("allergies") or []:
        key = (a or "").strip().lower().replace(" ", "_")
        if key in ALLERGEN_LABELS:
            out.add(key)
        elif key in INTOLERANCE_TO_ALLERGEN:
            out.add(INTOLERANCE_TO_ALLERGEN[key])
    for i in profile.get("intolerances") or []:
        key = (i or "").strip().lower()
        if key in INTOLERANCE_TO_ALLERGEN:
            out.add(INTOLERANCE_TO_ALLERGEN[key])
    return sorted(out)


def dislike_terms(profile: Dict[str, Any]) -> List[str]:
    terms = []
    for d in profile.get("dislikes") or []:
        d = re.sub(r"[^a-z\s]", "", (d or "").lower()).strip()
        if len(d) >= 3:
            terms.append(d)
    # non-ingredient allergies typed by the user ("mango") are treated like dislikes for filtering
    for a in profile.get("allergies") or []:
        key = (a or "").strip().lower()
        if key and key.replace(" ", "_") not in ALLERGEN_LABELS and key not in INTOLERANCE_TO_ALLERGEN and len(key) >= 3:
            terms.append(re.sub(r"[^a-z\s]", "", key))
    return terms


# ----------------------------------------------------------------------------------------------
# Recipe selection
# ----------------------------------------------------------------------------------------------
def _seed(*parts) -> int:
    return int(hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:8], 16)


def _shares(r: Dict[str, Any]) -> Tuple[float, float, float]:
    n = r["nutrition_per_serving"]
    kcal = n["kcal"] or 1
    return (n["protein"] or 0) * 4 / kcal, (n["carbs"] or 0) * 4 / kcal, (n["fat"] or 0) * 9 / kcal


def _score(r: Dict[str, Any], slot: Dict[str, Any], target_kcal: Optional[float], prefer: List[str],
           style: str) -> Tuple[float, float]:
    n = r["nutrition_per_serving"]
    kcal = n["kcal"] or 0
    portions = PORTIONS if slot["kind"] in ("main", "breakfast", "post") else [0.5, 0.75, 1.0, 1.25, 1.5]
    if target_kcal and kcal > 0:
        m = min(portions, key=lambda p: abs(kcal * p - target_kcal))
        score = -10.0 * abs(kcal * m - target_kcal) / target_kcal
        score -= 1.5 * abs(m - 1.0)
    else:
        m = 1.0
        score = 0.0
    tags = set(r.get("focus_tags", []))
    score += 3.0 * sum(1 for f in prefer if f in tags)
    if r.get("servings"):
        score += 2.0
    p_share, c_share, f_share = _shares(r)
    if style in ("strength", "high_protein"):
        score += 12 * p_share
    elif style == "endurance":
        score += 6 * c_share
    elif style == "low_carb":
        score -= 15 * c_share
    elif style == "weight_loss":
        if r.get("serving_size_g"):
            score -= 2.0 * min(3.0, kcal / r["serving_size_g"])
        score += 6 * p_share
    elif style == "sport":
        score += 3 * c_share + 4 * p_share
    if slot["slot"] == "pre_workout":
        score -= 0.4 * (n["fat"] or 0) + 0.3 * (n["fiber"] or 0)
    if slot.get("post_training") or slot["kind"] == "post":
        score += 0.15 * min(40, n["protein"] or 0)
    return score, m


def find_recipes_for_slot(profile: Dict[str, Any], category: Dict[str, Any], slot: Dict[str, Any],
                          target_kcal: Optional[float], exclude_ids: List[int], seed: int, extra: Dict[str, Any] = None,
                          limit: int = 5) -> Tuple[List[Tuple[Dict[str, Any], float, float]], List[str]]:
    """Returns ranked (recipe, score, portion) tuples plus notes about relaxed filters."""
    extra = extra or {}
    notes: List[str] = []
    pref = profile.get("diet_preference") or "no_preference"
    kind = slot["kind"]
    meal_types = {"breakfast": ["breakfast"], "main": ["main"], "snack": ["snack"], "post": ["main", "snack"]}[kind]
    prefer = list(category.get("slot_focus", {}).get(kind if kind != "post" else "main", []))
    if slot["slot"] == "pre_workout":
        prefer = ["pre_workout"] + prefer
    elif slot.get("pre_training"):
        prefer = ["high_carb"] + prefer
    if slot.get("post_training"):
        prefer = ["post_workout"] + prefer
    prefer += extra.get("prefer", [])
    style = category.get("macro_style", "balanced")
    if profile.get("goal") == "muscle_gain" and style in ("balanced", "sport"):
        style = "strength"
    if profile.get("goal") == "weight_loss" and style == "balanced":
        style = "weight_loss"
    base = dict(diet=pref, exclude_allergens=excluded_allergens(profile), dislikes=dislike_terms(profile),
                exclude_ids=exclude_ids, cuisine=extra.get("cuisine", profile.get("cuisine")),
                max_total_min=profile.get("max_prep_minutes") or None,
                include_ingredients=extra.get("include_ingredients"))
    if target_kcal:
        lo, hi = target_kcal * 0.4, target_kcal * 1.5
        if kind == "snack":
            lo, hi = 60, max(180, target_kcal * 1.8)
        base.update(kcal_min=lo, kcal_max=hi)
    if extra.get("kcal_max"):
        base["kcal_max"] = extra["kcal_max"]
    must_focus = extra.get("must_focus")

    def gather(filters):
        out = []
        for mt in meal_types:
            out += recipe_store.candidates(seed=seed, limit=220, meal_type=mt,
                                           focus_any=must_focus, **filters)
        return [r for r in out if not verification_conflicts(r, pref)]

    cands = gather(base)
    if len(cands) < 8 and base.get("cuisine") not in (None, "", "any", "all"):
        relaxed = dict(base, cuisine=None)
        more = gather(relaxed)
        if more:
            notes.append(f"Few {base['cuisine'].title()} recipes matched every requirement for {slot['label'].lower()}, "
                         f"so other cuisines were included.")
            cands += more
    if len(cands) < 8 and base.get("max_total_min"):
        more = gather(dict(base, max_total_min=None, cuisine=None))
        if more:
            notes.append(f"Some {slot['label'].lower()} options take longer than your preferred preparation time.")
            cands += more
    if len(cands) < 8 and target_kcal:
        cands += gather(dict(base, kcal_min=None, kcal_max=None, cuisine=None))
    seen, uniq = set(), []
    for r in cands:
        if r["id"] not in seen:
            seen.add(r["id"])
            uniq.append(r)
    ranked = []
    for r in uniq:
        s, m = _score(r, slot, target_kcal, prefer, style)
        ranked.append((r, s, m))
    ranked.sort(key=lambda x: -x[1])
    return ranked[:max(limit, 1)], notes


def meal_reason(meal: Dict[str, Any], profile: Dict[str, Any], category: Dict[str, Any]) -> str:
    n = (meal.get("nutrition") or {}).get("values") or {}
    src = meal["source_per_serving"]
    servings = meal.get("servings", 1)
    vals = n if n.get("kcal") is not None else {k: (src.get(k) or 0) * servings for k in NUTRIENT_KEYS}
    parts = [f"{round(vals.get('kcal') or 0)} kcal, {round(vals.get('protein') or 0)} g protein and "
             f"{round(vals.get('carbs') or 0)} g carbohydrate for {servings:g} serving(s)"]
    slot = meal.get("slot")
    if slot == "pre_workout" or meal.get("pre_training"):
        parts.append(f"carbohydrate-based with {round(vals.get('fat') or 0)} g fat"
                     + (f" and {round(vals['fiber'])} g fibre" if vals.get("fiber") is not None else "")
                     + ", which is usually easier to digest before exercise")
    elif meal.get("post_training"):
        parts.append("combines protein and carbohydrate to support recovery after training")
    tags = set(meal.get("focus_tags", []))
    if "high_protein" in tags:
        parts.append("a high share of its energy comes from protein")
    if "high_fiber" in tags:
        parts.append("it is high in fibre")
    if "low_energy_density" in tags and profile.get("goal") == "weight_loss":
        parts.append("it is filling for relatively few calories")
    if "low_carb" in tags and category.get("macro_style") == "low_carb":
        parts.append("it is low in carbohydrate")
    pref = profile.get("diet_preference") or "no_preference"
    if pref != "no_preference":
        parts.append(f"it fits your {DIET_LABELS.get(pref, pref).lower()} preference (classified from its ingredients)")
    return "Included because it provides " + "; ".join(parts) + "."


def make_meal(recipe: Dict[str, Any], slot: Dict[str, Any], servings: float) -> Dict[str, Any]:
    ings = []
    for i, g in enumerate(recipe.get("ingredients", [])):
        line = recipe["ingredient_lines"][i] if i < len(recipe.get("ingredient_lines", [])) else g.get("name")
        ings.append({"idx": i, "quantity": g.get("quantity", ""), "unit": g.get("unit", ""), "name": g.get("name", ""),
                     "description": g.get("description", ""), "line": line, "status": "original"})
    n = recipe["nutrition_per_serving"]
    return {
        "id": f"m_{uuid.uuid4().hex[:10]}", "slot": slot["slot"], "label": slot["label"], "time": slot["time"],
        "kind": slot["kind"], "post_training": bool(slot.get("post_training")),
        "pre_training": bool(slot.get("pre_training")),
        "recipe_id": recipe["id"], "name": recipe["name"], "image_url": recipe.get("image_url"),
        "source_url": recipe.get("source_url"), "category": recipe.get("category"), "cuisines": recipe.get("cuisines", []),
        "diet": recipe.get("diet"), "allergens": recipe.get("allergens", []), "diet_verify": recipe.get("diet_verify", []),
        "focus_tags": recipe.get("focus_tags", []), "recipe_servings": recipe.get("servings"),
        "serving_size_g": recipe.get("serving_size_g"), "servings": servings,
        "source_per_serving": {k: n.get(k) for k in ("kcal", "protein", "carbs", "fat", "fiber", "sugar", "sodium")},
        "ingredients": ings, "steps": recipe.get("steps", []), "prep_min": recipe.get("prep_min"),
        "cook_min": recipe.get("cook_min"), "total_min": recipe.get("total_min"),
    }


# ----------------------------------------------------------------------------------------------
# Plan lifecycle
# ----------------------------------------------------------------------------------------------
def recalculate(plan: Dict[str, Any]) -> Dict[str, Any]:
    from backend.app.services.diet_assessment import assess_plan  # local import to avoid a cycle
    category = get_category(plan["category_key"])
    plan["targets"] = compute_targets(plan["profile"], category)
    for m in plan["meals"]:
        m["nutrition"] = compute_meal_nutrition(m)
        if not m.get("reason_locked"):
            m["reason"] = meal_reason(m, plan["profile"], category)
    plan["meals"].sort(key=lambda m: m.get("time") or "99:99")
    plan["totals"] = sum_nutrition(plan["meals"])
    plan["assessment"] = assess_plan(plan)
    plan["updated_at"] = datetime.utcnow().isoformat()
    return plan


def _range_loss(v: float, rng: Optional[Dict[str, Any]]) -> float:
    if not rng:
        return 0.0
    lo, hi = rng.get("low"), rng.get("high")
    if lo is not None and v < lo:
        return ((lo - v) / max(lo, 1)) ** 2
    if hi is not None and v > hi:
        return ((v - hi) / max(hi, 1)) ** 2
    return 0.0


def optimise_choices(options, slots, targets) -> List[Tuple[int, float]]:
    """Greedy coordinate search over (recipe option, portion) per slot so that the day's totals fall
    inside the user's target ranges; falls back to the best-scored option when there are no targets."""
    choice = [(0, opts[0][2]) for opts in options]
    energy = targets.get("energy")
    if not energy or not options:
        return choice
    ranges = {"kcal": {"low": energy["low"], "high": energy["high"]}, "protein": targets.get("protein"),
              "carbs": targets.get("carbs"), "fat": targets.get("fat")}
    weights = {"kcal": 3.0, "protein": 2.0, "carbs": 1.0, "fat": 1.0}

    def totals(ch):
        t = {k: 0.0 for k in weights}
        for i, (ci, por) in enumerate(ch):
            n = options[i][ci][0]["nutrition_per_serving"]
            for k in weights:
                t[k] += (n.get(k) or 0) * por
        return t

    def loss(ch):
        t = totals(ch)
        base = sum(weights[k] * _range_loss(t[k], ranges[k]) for k in weights)
        pref = sum(-0.004 * options[i][ci][1] + 0.01 * abs(por - 1.0) for i, (ci, por) in enumerate(ch))
        return base + pref

    best = loss(choice)
    for _ in range(3):
        improved = False
        for i, opts in enumerate(options):
            portions = PORTIONS if slots[i]["kind"] in ("main", "breakfast", "post") else [0.5, 0.75, 1.0, 1.25, 1.5]
            used_ids = {options[j][cj][0]["id"] for j, (cj, _) in enumerate(choice) if j != i}
            for ci, (r, _, _) in enumerate(opts):
                if r["id"] in used_ids:
                    continue
                for por in portions:
                    trial = list(choice)
                    trial[i] = (ci, por)
                    l = loss(trial)
                    if l < best - 1e-6:
                        best, choice, improved = l, trial, True
        if not improved:
            break
    return choice


def generate_plan(category_key: str, profile: Dict[str, Any], plan_id: Optional[str] = None,
                  variant: int = 0) -> Dict[str, Any]:
    category = get_category(category_key)
    if not category:
        raise PlanError(f"Unknown diet category '{category_key}'")
    if not recipe_store.available:
        raise PlanError("The recipe database has not been built yet. Run: python scripts/build_diet_dataset.py")
    targets = compute_targets(profile, category)
    slots, notes = build_slots(profile)
    energy = (targets.get("energy") or {}).get("target")
    used: List[int] = []
    options: List[List[Tuple[Dict[str, Any], float, float]]] = []
    kept_slots = []
    for i, slot in enumerate(slots):
        target_kcal = energy * slot["share"] if energy else None
        ranked, slot_notes = find_recipes_for_slot(profile, category, slot, target_kcal, used,
                                                   seed=_seed(category_key, slot["slot"], variant, i), limit=6)
        notes += slot_notes
        if not ranked:
            notes.append(f"No recipe in the dataset matched all your requirements for {slot['label'].lower()}; "
                         f"you can add one manually or relax a filter.")
            continue
        if variant:
            ranked = ranked[variant % len(ranked):] + ranked[:variant % len(ranked)]
        used += [r[0]["id"] for r in ranked]
        options.append(ranked)
        kept_slots.append(slot)
    choice = optimise_choices(options, kept_slots, targets)
    meals = [make_meal(options[i][ci][0], kept_slots[i], portion) for i, (ci, portion) in enumerate(choice)]
    plan = {
        "id": plan_id or f"plan_{uuid.uuid4().hex[:12]}", "category_key": category_key,
        "category_name": category["name"], "assistant_name": category["assistant_name"],
        "profile": profile, "meals": meals, "notes": sorted(set(notes), key=notes.index), "variant": variant,
        "created_at": datetime.utcnow().isoformat(),
    }
    return recalculate(plan)


def _find_meal(plan: Dict[str, Any], meal_id: str) -> Dict[str, Any]:
    for m in plan["meals"]:
        if m["id"] == meal_id:
            return m
    raise PlanError("Meal not found in this plan")


def _recipe_or_error(recipe_id: Any) -> Dict[str, Any]:
    try:
        rid = int(recipe_id)
    except (TypeError, ValueError):
        raise PlanError("A valid recipe id is required")
    recipe = recipe_store.get(rid)
    if not recipe:
        raise PlanError("Recipe not found")
    return recipe


def _clean_servings(v: Any) -> float:
    try:
        s = float(v)
    except (TypeError, ValueError):
        raise PlanError("Servings must be a number")
    if s < 0.25 or s > 4:
        raise PlanError("Servings must be between 0.25 and 4")
    return round(s * 4) / 4.0


ALLOWED_PROFILE_KEYS = {"diet_preference", "goal", "activity_level", "sport", "other_sport_name",
                        "training_days_per_week", "session_minutes", "intensity", "training_time", "day_type", "age",
                        "sex", "height_cm", "weight_kg", "allergies", "intolerances", "dislikes", "cuisine",
                        "meals_per_day", "max_prep_minutes"}


def sanitize_profile(profile: Dict[str, Any], base: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (profile or {}).items():
        if k not in ALLOWED_PROFILE_KEYS:
            continue
        if k in ("allergies", "intolerances", "dislikes"):
            if isinstance(v, str):
                v = [x.strip() for x in v.split(",")]
            v = [str(x).strip()[:40] for x in (v or []) if str(x).strip()][:20]
        elif k in ("age", "height_cm", "weight_kg", "session_minutes", "training_days_per_week", "meals_per_day",
                   "max_prep_minutes"):
            if v in (None, ""):
                v = None
            else:
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    raise PlanError(f"{k.replace('_', ' ')} must be a number")
                limits = {"age": (14, 100), "height_cm": (120, 230), "weight_kg": (30, 250), "session_minutes": (10, 480),
                          "training_days_per_week": (0, 7), "meals_per_day": (3, 6), "max_prep_minutes": (10, 240)}[k]
                if not (limits[0] <= v <= limits[1]):
                    raise PlanError(f"{k.replace('_', ' ')} should be between {limits[0]} and {limits[1]}")
                if k in ("meals_per_day", "training_days_per_week", "age"):
                    v = int(v)
        elif k == "training_time":
            if v and not valid_time(v):
                raise PlanError("Training time must look like 17:30")
        elif k == "diet_preference":
            if v not in DIET_LABELS:
                raise PlanError("Unknown dietary preference")
        elif k == "sex":
            v = v if v in ("male", "female") else None
        elif isinstance(v, str):
            v = v.strip()[:60] or None
        out[k] = v
    return out


def apply_operation(plan: Dict[str, Any], op: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """Applies one edit to a copy of the plan and returns (new_plan, human summary)."""
    plan = copy.deepcopy(plan)
    kind = op.get("op")
    category = get_category(plan["category_key"])
    if kind == "replace_meal":
        meal = _find_meal(plan, op.get("meal_id"))
        recipe = _recipe_or_error(op.get("recipe_id"))
        servings = _clean_servings(op.get("servings", meal.get("servings", 1)))
        new = make_meal(recipe, {"slot": meal["slot"], "label": meal["label"], "time": meal["time"],
                                 "kind": meal.get("kind", "main"), "post_training": meal.get("post_training"),
                                 "pre_training": meal.get("pre_training")}, servings)
        new["id"] = meal["id"]
        plan["meals"][plan["meals"].index(meal)] = new
        summary = f"Replaced {meal['label'].lower()} '{meal['name']}' with '{recipe['name']}'"
    elif kind == "add_meal":
        recipe = _recipe_or_error(op.get("recipe_id"))
        slot = op.get("slot") if op.get("slot") in SLOT_LABELS else "custom"
        t = op.get("time") or "15:00"
        if not valid_time(t):
            raise PlanError("Time must look like 15:30")
        label = (op.get("label") or SLOT_LABELS[slot]).strip()[:40]
        meal = make_meal(recipe, {"slot": slot, "label": label, "time": t, "kind": SLOT_KIND[slot],
                                  "post_training": slot == "post_workout"}, _clean_servings(op.get("servings", 1)))
        plan["meals"].append(meal)
        summary = f"Added '{recipe['name']}' as {label.lower()} at {t}"
    elif kind == "remove_meal":
        meal = _find_meal(plan, op.get("meal_id"))
        if len(plan["meals"]) <= 1:
            raise PlanError("A plan needs at least one meal")
        plan["meals"].remove(meal)
        summary = f"Removed {meal['label'].lower()} '{meal['name']}'"
    elif kind == "set_servings":
        meal = _find_meal(plan, op.get("meal_id"))
        old = meal["servings"]
        meal["servings"] = _clean_servings(op.get("servings"))
        summary = f"Changed {meal['label'].lower()} from {old:g} to {meal['servings']:g} serving(s)"
    elif kind == "set_time":
        meal = _find_meal(plan, op.get("meal_id"))
        if not valid_time(op.get("time")):
            raise PlanError("Time must look like 07:30")
        meal["time"] = op["time"]
        summary = f"Moved {meal['label'].lower()} to {op['time']}"
    elif kind == "set_label":
        meal = _find_meal(plan, op.get("meal_id"))
        meal["label"] = (op.get("label") or meal["label"]).strip()[:40]
        summary = f"Renamed meal to {meal['label']}"
    elif kind in ("update_ingredient", "remove_ingredient", "restore_ingredient"):
        meal = _find_meal(plan, op.get("meal_id"))
        try:
            idx = int(op.get("index"))
        except (TypeError, ValueError):
            raise PlanError("Ingredient index is required")
        ing = next((i for i in meal["ingredients"] if i["idx"] == idx), None)
        if not ing:
            raise PlanError("Ingredient not found")
        if kind == "restore_ingredient":
            if ing["status"] == "added":
                meal["ingredients"].remove(ing)
                summary = f"Removed added ingredient '{ing['name']}'"
            else:
                orig = ing.get("original") or {}
                ing.update({k: orig.get(k, ing.get(k)) for k in ("quantity", "unit", "name", "description", "line")})
                ing.pop("fdc_id", None)
                ing["status"] = "original"
                ing.pop("original", None)
                summary = f"Restored '{ing['name']}'"
        elif kind == "remove_ingredient":
            if ing["status"] == "added":
                meal["ingredients"].remove(ing)
            else:
                if ing["status"] == "original":
                    ing["original"] = {k: ing.get(k) for k in ("quantity", "unit", "name", "description", "line")}
                ing["status"] = "removed"
            summary = f"Removed '{ing['name']}' from {meal['name']}"
        else:
            if ing["status"] == "original":
                ing["original"] = {k: ing.get(k) for k in ("quantity", "unit", "name", "description", "line")}
            before = ing.get("line") or ing["name"]
            if "name" in op and op["name"]:
                ing["name"] = str(op["name"]).strip()[:80]
            if "quantity" in op:
                q, _ = parse_quantity(op["quantity"])
                if op["quantity"] not in ("", None) and (q is None or q < 0):
                    raise PlanError("Quantity must be a number such as 150, 1.5 or 1 1/2")
                ing["quantity"] = str(op["quantity"]).strip()
            if "unit" in op:
                ing["unit"] = str(op.get("unit") or "").strip()[:20]
            if op.get("fdc_id"):
                food = usda_db.get(op["fdc_id"])
                if not food:
                    raise PlanError("USDA food not found")
                ing["fdc_id"] = food["fdc_id"]
                if not op.get("name"):
                    ing["name"] = food["description"]
            elif "name" in op:
                ing.pop("fdc_id", None)
            ing["description"] = "" if ("name" in op or op.get("fdc_id")) else ing.get("description", "")
            ing["line"] = " ".join(x for x in [ing["quantity"], ing["unit"], ing["name"]] if x)
            if ing["status"] != "added":
                orig = ing.get("original") or {}
                same = all((orig.get(k) or "") == (ing.get(k) or "") for k in ("quantity", "unit", "name")) and not ing.get("fdc_id")
                ing["status"] = "original" if same else "modified"
                if same:
                    ing.pop("original", None)
            summary = f"Changed '{before}' to '{ing['line']}' in {meal['name']}"
    elif kind == "add_ingredient":
        meal = _find_meal(plan, op.get("meal_id"))
        name = (op.get("name") or "").strip()[:80]
        food = usda_db.get(op["fdc_id"]) if op.get("fdc_id") else None
        if op.get("fdc_id") and not food:
            raise PlanError("USDA food not found")
        if not name and food:
            name = food["description"]
        if not name:
            raise PlanError("Ingredient name is required")
        q, _ = parse_quantity(op.get("quantity"))
        if q is None or q <= 0:
            raise PlanError("Quantity must be a positive number")
        idx = max([i["idx"] for i in meal["ingredients"]] + [-1]) + 1
        unit = str(op.get("unit") or "g").strip()[:20]
        ing = {"idx": idx, "quantity": str(op.get("quantity")).strip(), "unit": unit, "name": name, "description": "",
               "line": " ".join(x for x in [str(op.get('quantity')).strip(), unit, name] if x), "status": "added"}
        if food:
            ing["fdc_id"] = food["fdc_id"]
        meal["ingredients"].append(ing)
        summary = f"Added {ing['line']} to {meal['name']}"
    elif kind == "reset_meal":
        meal = _find_meal(plan, op.get("meal_id"))
        recipe = _recipe_or_error(meal["recipe_id"])
        fresh = make_meal(recipe, {"slot": meal["slot"], "label": meal["label"], "time": meal["time"],
                                   "kind": meal.get("kind"), "post_training": meal.get("post_training"),
                                   "pre_training": meal.get("pre_training")}, meal["servings"])
        fresh["id"] = meal["id"]
        plan["meals"][plan["meals"].index(meal)] = fresh
        summary = f"Reset '{meal['name']}' to the original recipe"
    elif kind == "update_profile":
        plan["profile"] = sanitize_profile(op.get("profile") or {}, plan["profile"])
        summary = "Updated your details"
        if op.get("regenerate"):
            fresh = generate_plan(plan["category_key"], plan["profile"], plan_id=plan["id"], variant=plan.get("variant", 0))
            fresh["created_at"] = plan.get("created_at")
            return fresh, summary + " and rebuilt the meal plan"
    elif kind == "regenerate":
        variant = int(plan.get("variant", 0)) + 1
        fresh = generate_plan(plan["category_key"], plan["profile"], plan_id=plan["id"], variant=variant)
        fresh["created_at"] = plan.get("created_at")
        return fresh, "Generated a different set of meals"
    elif kind == "batch":
        summaries = []
        for sub in op.get("ops") or []:
            if sub.get("op") == "batch":
                raise PlanError("Nested batches are not allowed")
            plan, s = apply_operation(plan, sub)
            summaries.append(s)
        return plan, "; ".join(summaries)
    else:
        raise PlanError(f"Unknown operation '{kind}'")
    return recalculate(plan), summary
