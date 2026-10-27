"""
diet_assistant.py
=================
The small assistant inside every diet plan. Each plan has its own conversation (stored per plan
id) and the assistant only ever sees that plan: its category, the user's goal and restrictions,
the current meals, quantities, totals and the latest assessment.

Requests that change the plan are answered with *proposals*: a concrete edit operation plus a
preview computed by applying the edit to a copy of the plan with the same nutrition engine the
rest of the app uses. Nothing is changed until the user presses Apply (see api/diet.py), and the
assistant never quotes nutrition numbers that did not come from the backend calculation.

Free-form questions fall back to the existing Nourish model (base Qwen3-4B with the recipe LoRA
disabled) with the plan summary as context; any sentence in its reply that states calorie or
gram figures is removed so the model cannot invent nutrition values.
"""

from __future__ import annotations

import copy
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from backend.app.services.diet_catalog import get_category
from backend.app.services.diet_planner import (
    PlanError, apply_operation, dislike_terms, excluded_allergens, find_recipes_for_slot, _seed, _to_min,
)
from backend.app.services.diet_recipe_store import ALLERGEN_LABELS, DIET_LABELS
from backend.app.services.food_labels import classify_diet, detect_allergens, extra_animal_flags
from backend.app.services.nutrition_service import ingredient_nutrition, usda_db
from backend.app.services.recipe_validator import validate_recipe_against_preference

SLOT_WORDS = [
    (r"\b(pre[- ]?(workout|training|exercise|match|run|session)|before (my |the )?(workout|training|session|match|run|gym|practice))\b", "pre"),
    (r"\b(post[- ]?(workout|training|exercise|match|run|session)|after (my |the )?(workout|training|session|match|run|gym|practice)|recovery meal)\b", "post"),
    (r"\bbreakfast\b", "breakfast"), (r"\blunch\b", "lunch"), (r"\bdinner|supper\b", "dinner"),
    (r"\b(morning|mid[- ]morning) snack\b", "morning_snack"), (r"\b(evening|afternoon) snack\b", "evening_snack"),
    (r"\bsnack\b", "snack"),
]
NUTRIENT_WORDS = {"protein": "protein", "carb": "carbs", "carbohydrate": "carbs", "calorie": "kcal", "kcal": "kcal",
                  "energy": "kcal", "fibre": "fiber", "fiber": "fiber", "fat": "fat"}
CUISINES = ["indian", "italian", "continental"]

SWAP_GROUPS = {
    "protein": (["paneer", "panir", "tofu", "tempeh", "chicken", "turkey", "egg", "fish", "salmon", "tuna", "cod",
                 "shrimp", "prawn", "beef", "lamb", "mutton", "pork", "lentil", "dal", "chickpea", "chana", "rajma",
                 "kidney bean", "black bean", "soya", "seitan", "cottage cheese", "yogurt", "curd"],
                ["tofu", "paneer", "tempeh", "chickpeas", "lentils", "eggs", "chicken breast", "greek yogurt",
                 "soya chunks", "cod", "kidney beans", "cottage cheese"]),
    "fat": (["butter", "ghee", "cream", "oil", "margarine", "mayonnaise", "coconut milk"],
            ["olive oil", "ghee", "greek yogurt", "coconut milk", "canola oil"]),
    "carb": (["rice", "pasta", "spaghetti", "noodle", "bread", "potato", "flour", "tortilla", "roti", "naan", "couscous"],
             ["brown rice", "quinoa", "millet", "whole wheat flour", "sweet potato", "rolled oats", "basmati rice"]),
    "milk": (["milk"], ["soy milk", "almond milk", "low fat milk", "skim milk"]),
    "sweet": (["sugar", "honey", "syrup", "jaggery"], ["jaggery", "maple syrup", "honey", "dates"]),
}


# ----------------------------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------------------------
def _vals(meal: Dict[str, Any]) -> Dict[str, Optional[float]]:
    return (meal.get("nutrition") or {}).get("values") or {}


def _fmt_n(v: Optional[Dict[str, Any]]) -> str:
    if not v or v.get("kcal") is None:
        return "nutrition not available"
    parts = [f"{round(v['kcal'])} kcal", f"{round(v.get('protein') or 0)} g protein",
             f"{round(v.get('carbs') or 0)} g carbs", f"{round(v.get('fat') or 0)} g fat"]
    if v.get("fiber") is not None:
        parts.append(f"{round(v['fiber'])} g fibre")
    return ", ".join(parts)


def _slot_matches(meal: Dict[str, Any], key: str) -> bool:
    if key == "pre":
        return meal.get("slot") == "pre_workout" or "pre-training" in (meal.get("label") or "").lower()
    if key == "post":
        return bool(meal.get("post_training")) or meal.get("slot") == "post_workout"
    if key == "snack":
        return meal.get("kind") == "snack" or "snack" in (meal.get("slot") or "")
    return meal.get("slot") == key


def find_meal_ref(plan: Dict[str, Any], text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    t = text.lower()
    for pat, key in SLOT_WORDS:
        if re.search(pat, t):
            m = next((m for m in plan["meals"] if _slot_matches(m, key)), None)
            return m, key
    for m in plan["meals"]:
        name = (m.get("name") or "").lower()
        if name and (name in t or (len(name.split()) > 1 and " ".join(name.split()[:2]) in t)):
            return m, "name"
    return None, None


_STOP = {"can", "you", "for", "the", "and", "with", "your", "this", "that", "what", "how", "why", "use", "make", "into",
         "two", "one", "some", "more", "less", "meal", "plan", "lunch", "dinner", "breakfast", "snack", "salt", "water",
         "pepper", "sugar", "oil", "alternative", "replace", "instead", "suggest", "about", "have", "need", "want"}


def find_ingredient_ref(plan: Dict[str, Any], text: str, meal: Optional[Dict[str, Any]] = None):
    """Finds an ingredient of the plan named in the message (matching on its normalised food name)."""
    from backend.app.services.nutrition_service import normalize_ingredient_text
    t = text.lower()
    meals = [meal] if meal else plan["meals"]
    best = None
    for m in meals:
        for ing in m.get("ingredients", []):
            if ing.get("status") == "removed":
                continue
            core = normalize_ingredient_text(ing.get("name") or "") or (ing.get("name") or "").lower()
            raw = re.sub(r"\(.*?\)", "", (ing.get("name") or "").lower())
            for source in (core, raw):
                words = [w for w in re.findall(r"[a-z]+", source) if len(w) > 2]
                for size in (3, 2, 1):
                    for i in range(0, max(0, len(words) - size + 1)):
                        phrase = " ".join(words[i:i + size])
                        if size == 1 and (phrase in _STOP or len(phrase) < 4):
                            continue
                        if re.search(r"\b" + re.escape(phrase) + r"(e?s)?\b", t):
                            if not best or len(phrase) > len(best[2]):
                                best = (m, ing, phrase)
    return best


def named_food(text: str) -> Optional[str]:
    m = re.search(r"(?:alternative to|alternatives to|substitute for|instead of|replace|swap|without)\s+(?:the\s+|my\s+)?"
                  r"([a-z][a-z\s\-]{2,30}?)(?:\s+(?:with|for|in)\b|[?.!,]|$)", text.lower())
    return m.group(1).strip() if m else None


def _preview(plan: Dict[str, Any], op: Dict[str, Any], meal_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        new_plan, summary = apply_operation(plan, op)
    except PlanError as e:
        return {"error": str(e)}
    before_m = next((m for m in plan["meals"] if m["id"] == meal_id), None) if meal_id else None
    after_m = next((m for m in new_plan["meals"] if m["id"] == meal_id), None) if meal_id else None
    return {
        "summary": summary,
        "meal_before": {"name": before_m["name"], "servings": before_m["servings"], "nutrition": before_m.get("nutrition")} if before_m else None,
        "meal_after": ({"name": after_m["name"], "servings": after_m["servings"], "nutrition": after_m.get("nutrition"),
                        "image_url": after_m.get("image_url"), "ingredients": [i["line"] for i in after_m["ingredients"]
                                                                               if i.get("status") != "removed"][:12]}
                       if after_m else None),
        "totals_before": plan.get("totals"), "totals_after": new_plan.get("totals"),
        "assessment_after": {"label": new_plan["assessment"]["label"], "label_key": new_plan["assessment"]["label_key"]},
    }


def _proposal(plan, title: str, description: str, op: Dict[str, Any], meal_id: Optional[str] = None):
    prev = _preview(plan, op, meal_id)
    if not prev or prev.get("error"):
        return None
    return {"id": f"p_{uuid.uuid4().hex[:8]}", "title": title, "description": description, "op": op,
            "preview": prev, "status": "pending"}


def _ok_for_profile(name: str, profile: Dict[str, Any]) -> bool:
    pref = profile.get("diet_preference") or "no_preference"
    if not validate_recipe_against_preference([name], pref)["passed"]:
        return False
    forbidden = {"vegan": ("meat", "egg", "dairy"), "vegetarian": ("meat", "egg"), "eggitarian": ("meat",)}.get(pref, ())
    x = extra_animal_flags(name)
    if any(x[k] for k in forbidden):
        return False
    flags = classify_diet([name])[1]
    if set(detect_allergens([name], flags)) & set(excluded_allergens(profile)):
        return False
    if any(t in name.lower() for t in dislike_terms(profile)):
        return False
    return True


# ----------------------------------------------------------------------------------------------
# Intent handlers
# ----------------------------------------------------------------------------------------------
def handle_ingredient_swap(plan, text, meal, ing, phrase) -> Dict[str, Any]:
    profile = plan["profile"]
    target = None
    m = re.search(r"(?:with|for|to|use|using)\s+([a-z][a-z\s\-]{2,40}?)(?:\s+instead|\s+in\b|[?.!,]|$)", text.lower())
    if m and phrase not in m.group(1):
        target = m.group(1).strip()
        target = re.sub(r"^(some|a|an|the)\s+", "", target)
        if re.fullmatch(r"(something|anything|another|other|something else|anything else|another one|a different one|"
                        r"different|else|better|healthier|something healthier|something different)", target):
            target = None
    old = ingredient_nutrition(ing["name"], ing.get("quantity"), ing.get("unit"), ing.get("description", ""), ing.get("fdc_id"))
    grams = old.get("grams") if old.get("status") == "ok" else None
    if target:
        candidates = [target]
    else:
        group = next((g for g, (keys, _) in SWAP_GROUPS.items() if any(k in phrase or k in ing["name"].lower() for k in keys)),
                     None)
        candidates = SWAP_GROUPS[group][1] if group else []
    proposals, rejected = [], []
    for cand in candidates:
        if cand in ing["name"].lower() or phrase in cand:
            continue
        if not _ok_for_profile(cand, profile):
            rejected.append(cand)
            continue
        match = usda_db.match(cand)
        if not match:
            rejected.append(cand)
            continue
        food = match["food"]
        if grams:
            op = {"op": "update_ingredient", "meal_id": meal["id"], "index": ing["idx"], "name": cand,
                  "quantity": str(round(grams)), "unit": "g", "fdc_id": food["fdc_id"]}
            desc = (f"Replace {ing.get('line') or ing['name']} with {round(grams)} g {cand} (same weight; USDA: "
                    f"{food['description']}).")
        else:
            op = {"op": "update_ingredient", "meal_id": meal["id"], "index": ing["idx"], "name": cand,
                  "fdc_id": food["fdc_id"]}
            desc = (f"Replace '{ing['name']}' with {cand}, keeping the recipe's quantity "
                    f"'{ing.get('quantity', '')} {ing.get('unit', '')}'.").replace("  ", " ")
        p = _proposal(plan, f"Use {cand} in {meal['name']}", desc, op, meal["id"])
        if p:
            proposals.append(p)
        if len(proposals) >= 3:
            break
    if not proposals:
        if target and target in rejected:
            content = (f"I can't suggest {target} for this plan: it conflicts with your "
                       f"{DIET_LABELS.get(profile.get('diet_preference'), 'diet').lower()} preference, allergies or "
                       f"foods you avoid, or it has no reliable USDA nutrition record.")
        else:
            content = (f"I couldn't find a suitable, well-documented replacement for '{ing['name']}'. Try naming the food "
                       f"you'd like to use, e.g. \"replace {phrase} with tofu\".")
        return {"content": content, "proposals": []}
    lines = [f"Here are alternatives to **{ing['name']}** in your {meal['label'].lower()} ({meal['name']}). "
             f"Each option keeps your restrictions, and the numbers below are recalculated by the nutrition engine:"]
    for p in proposals:
        after = (p["preview"]["meal_after"] or {}).get("nutrition") or {}
        status = after.get("status")
        lines.append(f"• {p['title']}: meal becomes {_fmt_n(after.get('values'))}"
                     + (" (not calculable: " + after.get("reason", "") + ")" if status == "unavailable" else ""))
    if old.get("status") != "ok":
        lines.append(f"Note: the original amount could not be converted to grams ({old.get('reason')}), so changes "
                     f"to this ingredient may show nutrition as unavailable.")
    lines.append("Nothing changes until you press Apply.")
    return {"content": "\n".join(lines), "proposals": proposals}


def handle_replace_meal(plan, text, meal, focus: Optional[str] = None, cuisine: Optional[str] = None) -> Dict[str, Any]:
    profile = plan["profile"]
    category = get_category(plan["category_key"])
    if not meal:
        meal = max(plan["meals"], key=lambda m: _vals(m).get("kcal") or 0)
    current = _vals(meal)
    slot = {"slot": meal["slot"], "label": meal["label"], "time": meal["time"], "kind": meal.get("kind", "main"),
            "post_training": meal.get("post_training"), "pre_training": "pre-training" in meal["label"].lower()}
    extra: Dict[str, Any] = {}
    if focus == "protein":
        extra["must_focus"] = ["high_protein"]
    elif focus == "fiber":
        extra["must_focus"] = ["high_fiber"]
    elif focus == "low_carb":
        extra["must_focus"] = ["low_carb"]
    elif focus == "lighter":
        extra["kcal_max"] = max(150, (current.get("kcal") or 400) * 0.85)
    if cuisine:
        extra["cuisine"] = cuisine
    target = current.get("kcal") or None
    if focus == "lighter" and target:
        target = target * 0.7          # portions are sized to this target, so it must be lower than the current meal
    used = [m["recipe_id"] for m in plan["meals"]]
    ranked, notes = find_recipes_for_slot(profile, category, slot, target, used,
                                          seed=_seed(plan["id"], meal["id"], text), extra=extra, limit=8)
    if focus == "protein":
        ranked = [r for r in ranked if (r[0]["nutrition_per_serving"]["protein"] or 0) * r[2] > (current.get("protein") or 0)]
    if focus == "lighter" and current.get("kcal"):
        ranked = [r for r in ranked if (r[0]["nutrition_per_serving"]["kcal"] or 0) * r[2] < current["kcal"] * 0.9]
    if cuisine:
        ranked = [r for r in ranked if cuisine in r[0].get("cuisines", [])] or ranked
    proposals = []
    for recipe, _, portion in ranked[:2]:
        op = {"op": "replace_meal", "meal_id": meal["id"], "recipe_id": recipe["id"], "servings": portion}
        desc = f"Replace {meal['name']} with {recipe['name']} ({portion:g} serving{'s' if portion != 1 else ''})."
        p = _proposal(plan, f"{recipe['name']}", desc, op, meal["id"])
        if p and focus == "lighter" and current.get("kcal"):
            after_kcal = (((p["preview"]["meal_after"] or {}).get("nutrition") or {}).get("values") or {}).get("kcal")
            if after_kcal is None or after_kcal >= current["kcal"] * 0.95:
                continue
        if p:
            proposals.append(p)
    if not proposals:
        return {"content": "I couldn't find another recipe in the dataset that meets all your requirements for "
                           f"{meal['label'].lower()}. You could relax a filter (cuisine or preparation time).",
                "proposals": []}
    what = {"protein": "higher-protein ", "fiber": "higher-fibre ", "lighter": "lighter ", "low_carb": "lower-carb "}.get(focus, "")
    cz = f"{cuisine.title()} " if cuisine else ""
    lines = [f"Here are {what}{cz}options for your {meal['label'].lower()} (currently {meal['name']}: {_fmt_n(current)}):"]
    for p in proposals:
        after = (p["preview"]["meal_after"] or {}).get("nutrition") or {}
        lines.append(f"• {p['title']}: {_fmt_n(after.get('values'))}")
    lines += [n for n in notes][:1]
    lines.append("Both respect your diet and exclusions. Press Apply on the one you like.")
    return {"content": "\n".join(lines), "proposals": proposals}


def handle_increase(plan, text, meal, nutrient) -> Dict[str, Any]:
    if not meal:
        meal = min([m for m in plan["meals"] if m.get("kind") in ("main", "breakfast", "post")] or plan["meals"],
                   key=lambda m: _vals(m).get(nutrient) or 0)
    proposals = []
    if (meal.get("servings") or 1) < 2:
        new_s = min(2.0, (meal.get("servings") or 1) + 0.5)
        p = _proposal(plan, f"Have {new_s:g} serving{'s' if new_s != 1 else ''} of {meal['name']}",
                      f"Increase the portion from {meal['servings']:g} to {new_s:g} servings.",
                      {"op": "set_servings", "meal_id": meal["id"], "servings": new_s}, meal["id"])
        if p:
            proposals.append(p)
    focus = {"protein": "protein", "fiber": "fiber"}.get(nutrient)
    swap = handle_replace_meal(plan, text, meal, focus=focus)
    proposals += swap.get("proposals", [])[:1]
    label = {"protein": "protein", "carbs": "carbohydrate", "kcal": "energy", "fiber": "fibre", "fat": "fat"}[nutrient]
    lines = [f"To increase {label} in your {meal['label'].lower()} ({meal['name']}, {_fmt_n(_vals(meal))}) you could:"]
    for p in proposals:
        after = (p["preview"]["meal_after"] or {}).get("nutrition") or {}
        lines.append(f"• {p['title']}: {_fmt_n(after.get('values'))}")
    if not proposals:
        lines.append("• I couldn't find a suitable option within your restrictions.")
    return {"content": "\n".join(lines), "proposals": proposals}


def handle_pre_training(plan, meal) -> Dict[str, Any]:
    profile = plan["profile"]
    if not profile.get("sport"):
        return {"content": "This plan isn't linked to a training schedule. Add your sport and training time in "
                           "'Personalise' to get pre- and post-training checks.", "proposals": []}
    if not meal:
        meal = next((m for m in plan["meals"] if m.get("slot") == "pre_workout"), None) or \
               next((m for m in plan["meals"] if "pre-training" in m["label"].lower()), None)
    if not meal:
        return {"content": "There is no pre-training snack in this plan. A small, carbohydrate-based snack 1-3 hours "
                           "before training is a common approach - ask me to add one.", "proposals": []}
    v = _vals(meal)
    t_train = _to_min(profile.get("training_time"), 17 * 60)
    gap = t_train - _to_min(meal.get("time"), t_train)
    issues = []
    if v.get("fat") is not None and v["fat"] > 15:
        issues.append(f"it has {round(v['fat'])} g fat, which slows digestion")
    if v.get("fiber") is not None and v["fiber"] > 8:
        issues.append(f"it has {round(v['fiber'])} g fibre, which some people find uncomfortable before exercise")
    if v.get("carbs") is not None and v.get("kcal") and v["carbs"] * 4 / v["kcal"] < 0.45:
        issues.append("less than half its energy comes from carbohydrate")
    if gap < 30:
        issues.append(f"it is only {max(gap, 0)} minutes before your session")
    elif gap > 240:
        issues.append(f"it is {gap // 60} hours before your session, so it may not count as a pre-training meal")
    verdict = ("Generally suitable" if not issues else "Could be improved")
    content = (f"{verdict}: {meal['name']} at {meal['time']} provides {_fmt_n(v)}"
               + (f", about {gap} minutes before training at {profile.get('training_time')}." if gap > 0 else ".")
               + ("" if not issues else "\nThings to consider: " + "; ".join(issues) + ".")
               + "\nEveryone tolerates food before exercise differently, so adjust to what feels comfortable.")
    proposals = []
    if issues:
        alt = handle_replace_meal(plan, "pre training", meal, focus="lighter")
        proposals = alt.get("proposals", [])[:2]
        if proposals:
            content += "\nLighter, carbohydrate-based options are below."
    return {"content": content, "proposals": proposals}


def handle_post_training(plan) -> Dict[str, Any]:
    meal = next((m for m in plan["meals"] if m.get("post_training") or m.get("slot") == "post_workout"), None)
    targets = plan.get("targets") or {}
    pmp = targets.get("per_meal_protein")
    if meal:
        v = _vals(meal)
        need = f" (your per-meal protein guide is {pmp['low']}-{pmp['high']} g)" if pmp else ""
        content = (f"Your recovery meal is {meal['name']} at {meal['time']}: {_fmt_n(v)}{need}. After training, a meal "
                   f"with both protein and carbohydrate within a couple of hours supports recovery.")
        if pmp and (v.get("protein") or 0) < pmp["low"]:
            alt = handle_replace_meal(plan, "post workout protein", meal, focus="protein")
            return {"content": content + "\nIt is below your protein guide; higher-protein options are below.",
                    "proposals": alt.get("proposals", [])}
        return {"content": content, "proposals": []}
    category = get_category(plan["category_key"])
    t = plan["profile"].get("training_time") or "17:00"
    end = _to_min(t, 17 * 60) + int(float(plan["profile"].get("session_minutes") or 60)) + 30
    slot = {"slot": "post_workout", "label": "Post-training meal", "time": f"{min(end, 23*60)//60:02d}:{min(end, 23*60)%60:02d}",
            "kind": "post", "post_training": True}
    ranked, _ = find_recipes_for_slot(plan["profile"], category, slot, None, [m["recipe_id"] for m in plan["meals"]],
                                      seed=_seed(plan["id"], "post"), limit=3)
    proposals = []
    for r, _, por in ranked[:2]:
        p = _proposal(plan, f"Add {r['name']}", f"Add {r['name']} as a post-training meal at {slot['time']}.",
                      {"op": "add_meal", "recipe_id": r["id"], "slot": "post_workout", "time": slot["time"],
                       "servings": 1}, None)
        if p:
            proposals.append(p)
    return {"content": "There is no post-training meal in this plan. Here are options with protein and carbohydrate "
                       "for recovery:", "proposals": proposals}


def handle_why(plan, meal) -> Dict[str, Any]:
    if not meal:
        return {"content": "Which meal do you mean? You can say breakfast, lunch, dinner, a snack, or the recipe name.",
                "proposals": []}
    n = meal.get("nutrition") or {}
    src = "the recipe's published per-serving values" if n.get("status") == "source" else "USDA estimates for your edits"
    content = (f"{meal['name']} ({meal['label'].lower()}, {meal['time']}): {meal.get('reason', '')}\n"
               f"Its numbers ({_fmt_n(n.get('values'))}) come from {src}.")
    return {"content": content, "proposals": []}


def handle_check(plan) -> Dict[str, Any]:
    a = plan.get("assessment") or {}
    lines = [f"**{a.get('label')}** - {a.get('summary')}"]
    for r in a.get("reasons", [])[:4]:
        lines.append(f"• {r}")
    proposals = []
    checks = {c["key"]: c for c in a.get("checks", [])}
    meals = plan["meals"]
    mains = [m for m in meals if m.get("kind") in ("main", "breakfast", "post")] or meals
    if a.get("restriction_conflicts"):
        c = a["restriction_conflicts"][0]
        meal = next((m for m in meals if m["id"] == c["meal_id"]), None)
        if meal:
            proposals += handle_replace_meal(plan, "conflict", meal).get("proposals", [])[:1]
    pc = checks.get("protein", {}).get("status", "")
    ec = checks.get("energy", {}).get("status", "")
    fc = checks.get("fiber", {}).get("status", "")
    cc = checks.get("carbs", {}).get("status", "")
    if pc.startswith("below"):
        low = min(meals, key=lambda m: _vals(m).get("protein") or 0)
        proposals += handle_replace_meal(plan, "protein", low, focus="protein").get("proposals", [])[:1]
    if ec.startswith("below") or cc.startswith("below"):
        big = max(mains, key=lambda m: _vals(m).get("carbs" if cc.startswith("below") else "kcal") or 0)
        if big["servings"] < 2:
            p = _proposal(plan, f"Have {big['servings'] + 0.25:g} servings of {big['name']}",
                          "A slightly larger portion of this meal raises energy and carbohydrate.",
                          {"op": "set_servings", "meal_id": big["id"], "servings": big["servings"] + 0.25}, big["id"])
            if p:
                proposals.append(p)
    elif ec.startswith("above"):
        big = max(mains, key=lambda m: _vals(m).get("kcal") or 0)
        if big["servings"] > 0.5:
            p = _proposal(plan, f"Have {big['servings'] - 0.25:g} servings of {big['name']}",
                          "A slightly smaller portion of your largest meal lowers energy intake.",
                          {"op": "set_servings", "meal_id": big["id"], "servings": big["servings"] - 0.25}, big["id"])
            if p:
                proposals.append(p)
    if fc.startswith("below") and len(proposals) < 3:
        low = min(meals, key=lambda m: _vals(m).get("fiber") if _vals(m).get("fiber") is not None else 99)
        proposals += handle_replace_meal(plan, "fibre", low, focus="fiber").get("proposals", [])[:1]
    if proposals:
        lines.append("Suggested changes (with recalculated numbers) are below.")
    elif a.get("label_key") == "info":
        lines.append("Add your age, height and weight under 'Personalise' for a complete check.")
    return {"content": "\n".join(lines), "proposals": proposals[:3]}


def handle_rest_day(plan) -> Dict[str, Any]:
    if not plan["profile"].get("sport"):
        return {"content": "This plan doesn't include training, so it already works as a rest-day plan.", "proposals": []}
    ops = [{"op": "update_profile", "profile": {"day_type": "rest"}}]
    removed = []
    for m in plan["meals"]:
        if m.get("slot") in ("pre_workout", "post_workout"):
            ops.append({"op": "remove_meal", "meal_id": m["id"]})
            removed.append(m["name"])
    p = _proposal(plan, "Switch to a rest-day plan",
                  "Recalculate targets for a rest day" + (f" and remove the training snacks ({', '.join(removed)})" if removed else "")
                  + ".", {"op": "batch", "ops": ops})
    content = ("On rest days energy and carbohydrate needs are usually lower, while protein needs stay similar. "
               "I can recalculate your targets for a rest day"
               + (" and remove the pre/post-training snacks." if removed else "."))
    return {"content": content, "proposals": [p] if p else []}


def _sanitize_model_text(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    keep = [s for s in sentences if not re.search(
        r"\d[\d.,]*\s*(k?cal|calories|kilocalories|g\b|grams?|mg|milligrams?|%|percent)", s, re.I)]
    out = " ".join(keep).strip()
    return out[:1200]


def plan_context_text(plan: Dict[str, Any]) -> str:
    p = plan["profile"]
    t = plan.get("totals", {}).get("values", {})
    tg = plan.get("targets") or {}
    lines = [f"Plan: {plan.get('category_name')}. Goal: {p.get('goal')}. Diet: {DIET_LABELS.get(p.get('diet_preference'), 'any')}.",
             f"Sport: {p.get('sport') or 'none'}; training {p.get('session_minutes') or '-'} min at {p.get('training_time') or '-'}; "
             f"day type: {p.get('day_type')}.",
             f"Avoid: {', '.join((p.get('allergies') or []) + (p.get('intolerances') or []) + (p.get('dislikes') or [])) or 'nothing listed'}.",
             "Meals: " + "; ".join(f"{m['time']} {m['label']}: {m['name']}" for m in plan["meals"]),
             f"Assessment: {plan.get('assessment', {}).get('label')}."]
    return "\n".join(lines)


def handle_general(plan, text, history) -> Dict[str, Any]:
    fallback = ("I can help with this plan. Try asking:\n• Why is my lunch included?\n• Can you suggest an alternative to "
                "paneer?\n• Replace my dinner with a higher-protein meal\n• Is my pre-training snack suitable?\n• What "
                "should I eat after my workout?\n• Does this plan meet my requirements?\n• Suggest an Indian alternative "
                "for dinner\n• Modify this plan for a rest day")
    try:
        from model.inference import slm_engine, SLM_GENERATE
    except Exception:
        return {"content": fallback, "proposals": []}
    if not SLM_GENERATE or not hasattr(slm_engine, "generate_chat"):
        return {"content": fallback, "proposals": []}
    msgs = [{"role": "system", "content":
             f"You are the {plan.get('assistant_name')}, a friendly nutrition assistant inside the Nourish app. Answer "
             "briefly (under 120 words) and only about this user's plan, which is described below. Never state "
             "calorie, gram or percentage numbers - the app shows those. Never give medical advice; suggest a "
             "registered dietitian or doctor for medical conditions. Respect the user's diet and restrictions.\n\n"
             + plan_context_text(plan)}]
    for h in history[-6:]:
        msgs.append({"role": h["role"], "content": h["content"][:600]})
    msgs.append({"role": "user", "content": text})
    try:
        reply = slm_engine.generate_chat(msgs, max_new_tokens=220)
    except Exception as e:  # model unavailable or failed: keep the assistant usable
        print(f"Diet assistant model error: {e}")
        reply = None
    clean = _sanitize_model_text(reply or "")
    if len(clean) < 20:
        return {"content": fallback, "proposals": [], "meta": {"source": "fallback"}}
    return {"content": clean, "proposals": [], "meta": {"source": "slm"}}


# ----------------------------------------------------------------------------------------------
# Common questions answered from the plan's own data (no model involved)
# ----------------------------------------------------------------------------------------------
MEDICAL_RE = re.compile(r"\b(diabet\w*|blood sugar|insulin|pregnan\w*|breastfeed\w*|kidney|renal|blood pressure|hypertension|"
                        r"cholesterol|heart (disease|condition)|thyroid|pcos|pcod|celiac|coeliac|ibs|crohn\w*|gout|"
                        r"eating disorder|anemi\w*|anaemi\w*|medication|medicine|surgery)\b", re.I)
_LABEL = {"kcal": ("energy", "kcal"), "protein": ("protein", "g"), "carbs": ("carbohydrate", "g"),
          "fat": ("fat", "g"), "fiber": ("fibre", "g")}


def _target_text(plan, nutrient) -> str:
    tg = plan.get("targets") or {}
    t = tg.get({"kcal": "energy", "fiber": "fiber"}.get(nutrient, nutrient)) or {}
    if not t:
        return ""
    if t.get("target") is not None:
        return f"your estimated target is {round(t['target'])} {t.get('unit', '')} (range {round(t['low'])}-{round(t['high'])})"
    if t.get("low") is not None and t.get("high") is not None:
        return f"your estimated target range is {round(t['low'])}-{round(t['high'])} {t.get('unit', '')}"
    if t.get("min") is not None:
        return f"your estimated target is at least {round(t['min'])} {t.get('unit', '')}"
    return ""


def handle_nutrient_question(plan, meal, nutrient) -> Dict[str, Any]:
    label, unit = _LABEL[nutrient]
    if meal:
        v = _vals(meal).get(nutrient)
        if v is None:
            return {"content": f"The {label} of {meal['name']} is not available.", "proposals": []}
        return {"content": f"Your {meal['label'].lower()} ({meal['name']}, {meal['servings']:g} serving"
                           f"{'s' if meal['servings'] != 1 else ''}) has {round(v)} {unit} of {label}.\n"
                           f"Full values: {_fmt_n(_vals(meal))}.", "proposals": []}
    tot = (plan.get("totals") or {}).get("values") or {}
    v = tot.get(nutrient)
    lines = [f"Across the whole day this plan gives {round(v)} {unit} of {label}." if v is not None
             else f"The day's total {label} is not available because some meals have no nutrition data."]
    tt = _target_text(plan, nutrient)
    if tt:
        lines[0] = lines[0][:-1] + f"; {tt}."
    per = [f"• {m['label']}: {round(_vals(m)[nutrient])} {unit}" for m in plan["meals"] if _vals(m).get(nutrient) is not None]
    return {"content": "\n".join(lines + per), "proposals": []}


def handle_medical(plan, text) -> Dict[str, Any]:
    cond = MEDICAL_RE.search(text).group(0)
    tot = (plan.get("totals") or {}).get("values") or {}
    facts = (f"For reference, this plan gives {_fmt_n(tot)} per day, and each meal's carbohydrate is shown on its card."
             if tot.get("kcal") else "")
    return {"content": f"I can't tell you whether this plan is safe with {cond}. Plans here are built for healthy adults "
                       f"and don't account for medical conditions or medicines. Please show the plan to your doctor or "
                       f"a registered dietitian. They can adjust portions, carbohydrate timing or specific foods for "
                       f"you. {facts}".strip(), "proposals": [], "meta": {"safety": "medical_referral"}}


def _meals_with(plan, allergen: str):
    out = []
    for m in plan["meals"]:
        names = [i["name"] for i in m.get("ingredients", []) if i.get("status") != "removed"]
        _, flags = classify_diet(names)
        hits = [n for n in names if allergen in detect_allergens([n], classify_diet([n])[1])]
        if allergen in detect_allergens(names, flags):
            out.append((m, hits))
    return out


def handle_allergen_question(plan, allergen: str) -> Dict[str, Any]:
    label = ALLERGEN_LABELS.get(allergen, allergen)
    found = _meals_with(plan, allergen)
    listed = allergen in (excluded_allergens(plan["profile"]) or [])
    if not found:
        msg = f"None of the meals in this plan list an ingredient containing {label.lower()}."
        if not listed:
            msg += (f" If you are allergic, add {label} under Allergies in 'Personalise' so every future change and "
                    f"suggestion avoids it too.")
        return {"content": msg + " Detection uses ingredient names, so always check labels on packaged foods.",
                "proposals": []}
    lines = [f"These meals contain {label.lower()}:"]
    lines += [f"• {m['label']} - {m['name']}: {', '.join(h) if h else 'see ingredients'}" for m, h in found]
    proposals = []
    for m, _ in found[:2]:
        proposals += handle_replace_meal(plan, "allergen", m).get("proposals", [])[:1]
    lines.append(f"Add {label} under Allergies in 'Personalise' to rebuild the plan without it, or apply a "
                 f"replacement below." if not listed else "Replacements that avoid it are below.")
    return {"content": "\n".join(lines), "proposals": proposals}


def handle_dislike(plan, text, food: str) -> Dict[str, Any]:
    ref = find_ingredient_ref(plan, food)
    if ref:
        out = handle_ingredient_swap(plan, f"alternative to {food}", ref[0], ref[1], ref[2])
        if out.get("proposals"):
            return out
        # the food is central to the dish (e.g. mushrooms in Mixed Mushroom Rice): offer a different meal instead
        alt = handle_replace_meal(plan, text, ref[0])
        alt["content"] = (f"{ref[0]['name']} is built around {food}, so swapping one ingredient won't work well. "
                          f"Here are other options for your {ref[0]['label'].lower()}:\n" + "\n".join(alt["content"].split("\n")[1:])
                          + f"\nTip: add {food} under 'Foods you avoid' in 'Personalise' so new plans leave it out.")
        return alt
    return {"content": f"None of your current meals contain {food}. Add it under 'Foods you avoid' in 'Personalise' "
                       f"so I leave it out of future suggestions.", "proposals": []}


def handle_can_i_have(plan, food: str) -> Dict[str, Any]:
    profile = plan["profile"]
    pref = profile.get("diet_preference") or "no_preference"
    if re.search(r"\b(coffee|espresso|caffeine|tea|energy drink)\b", food):
        extra = (" Some athletes have caffeine 30-60 minutes before training. If it upsets your stomach or sleep, skip "
                 "it, and keep energy drinks occasional because of their sugar." if profile.get("sport") else
                 " Keep it moderate and avoid it late in the day if it affects your sleep.")
        return {"content": f"Yes, {food} fits this plan." + extra + " Milk or sugar add to the day's totals.",
                "proposals": []}
    diet, flags = classify_diet([food])
    allowed = {"vegan": ["vegan"], "vegetarian": ["vegan", "vegetarian"],
               "eggitarian": ["vegan", "vegetarian", "eggitarian"]}.get(pref)
    if allowed and diet not in allowed:
        return {"content": f"{food.capitalize()} doesn't fit your {DIET_LABELS.get(pref, pref).lower()} preference. "
                           f"Ask me for an alternative.", "proposals": []}
    bad = [ALLERGEN_LABELS.get(a, a) for a in detect_allergens([food], flags) if a in (excluded_allergens(profile) or [])]
    if bad:
        return {"content": f"{food.capitalize()} usually contains {', '.join(bad).lower()}, which is on your allergy "
                           f"list, so I'd avoid it.", "proposals": []}
    return {"content": f"{food.capitalize()} fits your diet and restrictions. It isn't part of this plan, so it isn't "
                       f"counted in the totals. Treat it as an occasional extra, or add it to a meal as an ingredient so "
                       f"the nutrition is recalculated.", "proposals": []}


def handle_change_diet(plan, diet_word: str) -> Dict[str, Any]:
    return {"content": f"To make the whole plan {diet_word}, open 'Personalise', set the dietary preference to "
                       f"{diet_word.capitalize()} and rebuild. Every meal is then chosen again to fit. To change only "
                       f"one meal, ask e.g. \"replace my dinner with a {diet_word} meal\".", "proposals": []}


def handle_night_before(plan, text) -> Dict[str, Any]:
    dinner = next((m for m in plan["meals"] if m["slot"] == "dinner"), None) or plan["meals"][-1]
    out = handle_replace_meal(plan, text, dinner)
    intro = ("The evening before a match or a long session, a familiar meal based on carbohydrate (rice, roti, pasta, "
             "potatoes) with some protein and not too much fat or fibre is a good choice. Avoid trying new foods. "
             f"Your current dinner is {dinner['name']} ({_fmt_n(_vals(dinner))}).")
    if out.get("proposals"):
        out["content"] = intro + "\nOther options:\n" + "\n".join(out["content"].split("\n")[1:])
    else:
        out["content"] = intro
    return out


# ----------------------------------------------------------------------------------------------
# Router
# ----------------------------------------------------------------------------------------------
def respond(plan: Dict[str, Any], message: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    text = (message or "").strip()
    t = text.lower()
    meal, slot_key = find_meal_ref(plan, t)
    nutrient = next((v for k, v in NUTRIENT_WORDS.items() if re.search(r"\b" + k, t)), None)
    cuisine = next((c for c in CUISINES if c in t), None)
    intent = "general"
    meal_level = bool(slot_key) and bool(re.search(r"\b(meal|recipe|dish|something|option|it|one)\b", t))
    ref = None if meal_level else find_ingredient_ref(plan, t, meal if slot_key else None)
    allergen_words = {"peanut": "peanut", "peanuts": "peanut", "nut": "tree_nuts", "nuts": "tree_nuts", "dairy": "dairy",
                      "lactose": "dairy", "milk": "dairy", "egg": "egg", "eggs": "egg", "gluten": "gluten", "wheat": "gluten",
                      "soy": "soy", "soya": "soy", "fish": "fish", "shellfish": "shellfish", "prawn": "shellfish",
                      "shrimp": "shellfish", "sesame": "sesame", "mustard": "mustard"}
    allergen = next((v for k, v in allergen_words.items() if re.search(r"\b" + k + r"\b", t)), None)
    dislike = re.search(r"\b(?:i )?(?:don'?t|do not|dont) (?:like|want|eat)\s+([a-z][a-z \-]{2,30}?)(?:\s+(?:in|at|for)\b|[?.!,]|$)"
                        r"|\b(?:i )?(?:dislike|hate|can'?t stand)\s+([a-z][a-z \-]{2,30}?)(?:[?.!,]|$)", t)
    can_have = re.search(r"\b(?:can|could|may|should) i (?:eat|have|drink|add|include)\s+(?:some\s+|a\s+|an\s+)?"
                         r"([a-z][a-z \-]{2,30}?)(?:\s+(?:on|in|with|before|after|during|while|at)\b|[?.!,]|$)", t)
    change_diet = re.search(r"\bmake (?:my|this|the) (?:whole )?plan (vegan|vegetarian|eggitarian|eggetarian|non[- ]vegetarian)\b", t)
    if MEDICAL_RE.search(t):
        intent, out = "medical", handle_medical(plan, t)
    elif allergen and re.search(r"\b(allerg\w*|intoleran\w*|contain\w*|any|have)\b", t) and \
            not re.search(r"\b(more|increase|add|replace|swap|alternative)\b", t):
        intent, out = "allergen_check", handle_allergen_question(plan, allergen)
    elif nutrient and re.search(r"\b(how (much|many)|what(?:'s| is| are) (my|the)|total|count)\b", t) and \
            not re.search(r"\b(increase|more|boost|raise|replace|swap)\b", t):
        intent, out = "nutrient_question", handle_nutrient_question(plan, meal if slot_key else None, nutrient)
    elif change_diet:
        intent, out = "change_diet", handle_change_diet(plan, change_diet.group(1).replace("eggetarian", "eggitarian"))
    elif dislike and not slot_key:
        intent, out = "dislike", handle_dislike(plan, text, (dislike.group(1) or dislike.group(2)).strip())
    elif re.search(r"\b(tonight|night before|evening before|day before)\b", t) and \
            re.search(r"\b(match|game|race|tournament|competition|session|training)\b", t):
        intent, out = "night_before", handle_night_before(plan, text)
    elif can_have and not re.search(r"\b(more|less|meal|recipe|dish|breakfast|lunch|dinner|snack)\b", can_have.group(1)):
        intent, out = "can_i_have", handle_can_i_have(plan, can_have.group(1).strip())
    elif re.search(r"\brest[- ]day\b", t):
        intent, out = "rest_day", handle_rest_day(plan)
    elif re.search(r"\b(meet|requirements?|on track|what should i change|check|improve|enough|suitable for my goal|"
                   r"is (this|my) plan (ok|good|suitable|balanced))\b", t) and not re.search(r"\b(before|pre)\b", t):
        intent, out = "check", handle_check(plan)
    elif re.search(r"\b(alternative|substitute|replace|swap|instead of|without|switch)\b", t) and ref:
        intent, out = "ingredient_swap", handle_ingredient_swap(plan, text, ref[0], ref[1], ref[2])
    elif re.search(r"\b(alternative to|substitute for|instead of|swap|replace)\b", t) and named_food(t) and not meal_level \
            and not slot_key and not re.search(r"\b(meal|recipe|dish|plan|breakfast|lunch|dinner|snack)\b", named_food(t) or ""):
        food = named_food(t)
        where = f"your {meal['label'].lower()} ({meal['name']})" if (slot_key and meal) else "this plan's current meals"
        intent, out = "ingredient_missing", {
            "content": f"I don't see {food} in {where}, so there is nothing to replace. You can ask me "
                       f"to replace a whole meal (e.g. \"replace my dinner with something higher in protein\"), or "
                       f"edit any ingredient directly in a meal card.", "proposals": []}
    elif re.search(r"\b(water|hydrat\w*|fluids?|drink)\b", t) and not re.search(r"\b(replace|swap)\b", t):
        hyd = (plan.get("targets") or {}).get("hydration") or []
        intent, out = "hydration", {"content": "Hydration guidance for this plan:\n" + "\n".join("• " + x for x in hyd)
                                    + "\nNeeds vary with heat, sweat rate and body size.", "proposals": []}
    elif re.search(r"\b(increase|more|boost|higher|raise|add)\b", t) and nutrient and \
            not re.search(r"\b(replace|swap)\b", t):
        intent, out = "increase", handle_increase(plan, text, meal, nutrient)
    elif slot_key == "pre" and re.search(r"\b(suitable|ok|okay|good|fine|right|enough|eat)\b", t) and \
            not re.search(r"\b(replace|swap|change)\b", t):
        intent, out = "pre_check", handle_pre_training(plan, meal)
    elif slot_key == "post" and re.search(r"\b(what|eat|should|suggest)\b", t) and not re.search(r"\b(replace|swap)\b", t):
        intent, out = "post_training", handle_post_training(plan)
    elif re.search(r"\b(replace|swap|change|different|another|alternative|instead|other option)\b", t) or cuisine:
        focus = {"protein": "protein", "fiber": "fiber"}.get(nutrient)
        if re.search(r"\b(lighter|less calories|fewer calories|lower calorie)\b", t):
            focus = "lighter"
        if re.search(r"\b(low[- ]carb|less carb|fewer carbs)\b", t):
            focus = "low_carb"
        intent, out = "replace_meal", handle_replace_meal(plan, text, meal, focus=focus, cuisine=cuisine)
    elif re.search(r"\bwhy\b", t):
        intent, out = "why", handle_why(plan, meal)
    else:
        out = handle_general(plan, text, history)
    out.setdefault("meta", {})
    out["meta"]["intent"] = intent
    return out
