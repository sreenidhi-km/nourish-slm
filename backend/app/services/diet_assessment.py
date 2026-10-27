"""
diet_assessment.py
==================
"Check My Diet": compares the current plan (after every edit) with the user's own targets.

The result separates three kinds of findings so they are never confused:
  * restriction  - a detected conflict with the user's diet, allergies or disliked foods
  * nutrient_gap - a calculated difference between the plan totals and the estimated targets
  * data         - missing or estimated nutrition data that limits the assessment
plus general recommendations (timing, distribution). No single unexplained score is used.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.app.services.diet_recipe_store import ALLERGEN_LABELS, DIET_LABELS, verification_conflicts
from backend.app.services.food_labels import classify_diet, detect_allergens, extra_animal_flags
from backend.app.services.recipe_validator import validate_recipe_against_preference

LABELS = {
    "aligned": "Well Aligned With Your Goals",
    "minor": "Minor Adjustments Recommended",
    "significant": "Significant Gaps Identified",
    "info": "More Information Needed",
}


def _active_ingredient_names(meal: Dict[str, Any]) -> List[str]:
    return [i.get("name", "") for i in meal.get("ingredients", []) if i.get("status") != "removed"]


def meal_restriction_conflicts(meal: Dict[str, Any], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    from backend.app.services.diet_planner import dislike_terms, excluded_allergens
    names = _active_ingredient_names(meal)
    out = []
    pref = profile.get("diet_preference") or "no_preference"
    val = validate_recipe_against_preference(names, pref)
    for c in val.get("conflicts", []):
        out.append({"type": "diet", "meal_id": meal["id"], "meal": meal["label"], "ingredient": c["ingredient"],
                    "message": f"'{c['ingredient']}' in {meal['name']} is {c['reason'].split(' (')[0]}, which conflicts "
                               f"with your {DIET_LABELS.get(pref, pref).lower()} preference.",
                    "suggested_alternative": c.get("suggested_alternative")})
    seen = {c["ingredient"] for c in out}
    forbidden = {"vegan": ("meat", "egg", "dairy"), "vegetarian": ("meat", "egg"), "eggitarian": ("meat",)}.get(pref, ())
    for n in names:
        if n in seen or not forbidden:
            continue
        x = extra_animal_flags(n)
        hit = next((k for k in forbidden if x[k]), None)
        if hit:
            word = {"meat": "meat or fish", "egg": "egg", "dairy": "dairy"}[hit]
            out.append({"type": "diet", "meal_id": meal["id"], "meal": meal["label"], "ingredient": n,
                        "message": f"'{n}' in {meal['name']} looks like {word}, which conflicts with your "
                                   f"{DIET_LABELS.get(pref, pref).lower()} preference.", "suggested_alternative": None})
    flags = classify_diet(names)[1]
    found = set(detect_allergens(names, flags))
    for a in excluded_allergens(profile):
        if a in found:
            out.append({"type": "allergen", "meal_id": meal["id"], "meal": meal["label"], "allergen": a,
                        "message": f"{meal['name']} appears to contain {ALLERGEN_LABELS.get(a, a).lower()} "
                                   f"(detected from its ingredient names), which you asked to avoid."})
    lowered = [n.lower() for n in names]
    for term in dislike_terms(profile):
        hit = next((n for n in lowered if term in n), None)
        if hit:
            out.append({"type": "dislike", "meal_id": meal["id"], "meal": meal["label"], "ingredient": hit,
                        "message": f"{meal['name']} contains '{hit}', which you listed as a food to avoid."})
    for v in verification_conflicts(meal, pref):
        if any(v["ingredient"].lower() == n for n in lowered):
            out.append({"type": "verify", "meal_id": meal["id"], "meal": meal["label"], "ingredient": v["ingredient"],
                        "message": f"Check '{v['ingredient']}' in {meal['name']}: {v['reason']}."})
    return out


def _range_status(value: Optional[float], low: Optional[float], high: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    if low is not None and value < low:
        gap = (low - value) / low if low else 0
        return "low_minor" if gap <= 0.15 else "low_significant"
    if high is not None and value > high:
        gap = (value - high) / high if high else 0
        return "high_minor" if gap <= 0.15 else "high_significant"
    return "ok"


def _fmt(v, unit=""):
    if v is None:
        return "not set"
    return f"{round(v)}{(' ' + unit) if unit else ''}"


def assess_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    profile = plan.get("profile") or {}
    targets = plan.get("targets") or {}
    totals = plan.get("totals") or {}
    vals = totals.get("values") or {}
    complete = totals.get("complete") or {}
    meals = plan.get("meals") or []
    checks: List[Dict[str, Any]] = []
    suggestions: List[Dict[str, Any]] = []
    severity = {"significant": 0, "minor": 0}

    # ---------------- restrictions ----------------
    conflicts = []
    for m in meals:
        conflicts += meal_restriction_conflicts(m, profile)
    hard = [c for c in conflicts if c["type"] in ("diet", "allergen", "dislike")]
    verify = [c for c in conflicts if c["type"] == "verify"]
    if hard:
        severity["significant"] += 1
        checks.append({"key": "restrictions", "kind": "restriction", "status": "conflict",
                       "title": "Dietary restrictions",
                       "message": f"{len(hard)} conflict(s) with your diet, allergies or disliked foods were detected."})
        for c in hard[:4]:
            alt = f" Try {c['suggested_alternative']} instead." if c.get("suggested_alternative") else ""
            suggestions.append({"kind": "restriction", "text": c["message"] + alt, "meal_id": c["meal_id"]})
    else:
        checks.append({"key": "restrictions", "kind": "restriction", "status": "ok", "title": "Dietary restrictions",
                       "message": "No conflicts detected in the available ingredient data."})
    if verify:
        checks.append({"key": "verify", "kind": "data", "status": "warning", "title": "Ingredients to verify",
                       "message": f"{len(verify)} ingredient(s) may or may not suit your diet depending on the product: "
                                  + "; ".join(v["message"] for v in verify[:2])})

    # ---------------- data completeness ----------------
    unavailable = totals.get("meals_unavailable") or []
    estimated = totals.get("meals_estimated") or []
    if unavailable:
        checks.append({"key": "data", "kind": "data", "status": "incomplete", "title": "Nutrition data",
                       "message": f"{len(unavailable)} meal(s) have no reliable nutrition after edits "
                                  f"({', '.join(unavailable[:3])}). Totals below exclude them."})
        suggestions.append({"kind": "data", "text": "Give missing ingredient quantities in grams, pick the matching USDA "
                                                    "food, or reset the edited meal for a reliable calculation."})
    elif estimated:
        checks.append({"key": "data", "kind": "data", "status": "estimate", "title": "Nutrition data",
                       "message": f"{len(estimated)} edited meal(s) use USDA ingredient estimates; the rest use the "
                                  "recipes' published values."})
    else:
        checks.append({"key": "data", "kind": "data", "status": "ok", "title": "Nutrition data",
                       "message": "All values come from the recipes' published per-serving nutrition."})
    if not complete.get("fiber", True) and not unavailable:
        checks.append({"key": "fiber_data", "kind": "data", "status": "incomplete", "title": "Fibre data",
                       "message": "Fibre is not available for every meal, so the fibre total is a minimum."})

    # ---------------- nutrients ----------------
    kcal = vals.get("kcal")
    energy = targets.get("energy")
    if energy and kcal is not None and not unavailable:
        st = _range_status(kcal, energy["low"], energy["high"])
        diff = kcal - energy["target"]
        msg = (f"Estimated intake {_fmt(kcal, 'kcal')} vs target {_fmt(energy['target'], 'kcal')} "
               f"(range {_fmt(energy['low'])}-{_fmt(energy['high'], 'kcal')}).")
        if st == "ok":
            checks.append({"key": "energy", "kind": "nutrient_gap", "status": "ok", "title": "Calories", "message":
                           msg + " Within your estimated range."})
        else:
            sev = "significant" if st.endswith("significant") else "minor"
            severity[sev] += 1
            word = "below" if st.startswith("low") else "above"
            checks.append({"key": "energy", "kind": "nutrient_gap", "status": f"{word}_{sev}", "title": "Calories",
                           "message": msg + f" About {abs(round(diff))} kcal {word} the target."})
            suggestions.append({"kind": "nutrient_gap",
                                "text": ("Increase a portion (for example a main meal by a quarter serving) or add a snack."
                                         if word == "below" else
                                         "Reduce a portion or swap a meal for a lighter recipe.")})
    elif not energy:
        checks.append({"key": "energy", "kind": "data", "status": "unknown", "title": "Calories",
                       "message": f"Plan provides {_fmt(kcal, 'kcal')}. A personal calorie target needs your "
                                  f"{', '.join(targets.get('missing') or ['details'])}."})

    def gram_check(key, title, unit_word):
        t = targets.get(key)
        v = vals.get(key)
        if v is None or unavailable:
            return
        share_t = (targets.get("shares") or {}).get(key)
        if t and (t.get("low") is not None or t.get("high") is not None):
            st = _range_status(v, t.get("low"), t.get("high"))
            rng = (f"{_fmt(t.get('low'))}-{_fmt(t.get('high'), 'g')}" if t.get("low") is not None and t.get("high") is not None
                   else (f"at least {_fmt(t.get('low'), 'g')}" if t.get("low") is not None else f"at most {_fmt(t.get('high'), 'g')}"))
            msg = f"{_fmt(v, 'g')} {unit_word} vs estimated target {rng} ({t.get('basis')})."
        elif share_t and kcal:
            pct = v * (9 if key == "fat" else 4) / kcal * 100 if kcal else 0
            st = _range_status(pct, share_t["low"], share_t["high"])
            msg = (f"{_fmt(v, 'g')} {unit_word} = {round(pct)} % of energy vs a {share_t['low']}-{share_t['high']} % range "
                   f"(add your weight for gram targets).")
        else:
            return
        if st == "ok":
            checks.append({"key": key, "kind": "nutrient_gap", "status": "ok", "title": title, "message": msg + " Within range."})
            return
        sev = "significant" if st.endswith("significant") else "minor"
        # Going over a protein or fibre range is rarely a problem; keep it informational.
        if st.startswith("high") and key in ("protein", "fiber"):
            sev = "minor"
        severity[sev] += 1
        word = "below" if st.startswith("low") else "above"
        checks.append({"key": key, "kind": "nutrient_gap", "status": f"{word}_{sev}", "title": title,
                       "message": msg + f" Currently {word} the range."})
        return word

    pw = gram_check("protein", "Protein", "protein")
    cw = gram_check("carbs", "Carbohydrates", "carbohydrate")
    fw = gram_check("fat", "Fat", "fat")
    fib = targets.get("fiber")
    if fib and vals.get("fiber") is not None and not unavailable:
        v = vals["fiber"]
        if v < fib["low"]:
            sev = "minor" if v >= fib["low"] * 0.7 else "significant"
            severity[sev] += 1
            checks.append({"key": "fiber", "kind": "nutrient_gap", "status": f"below_{sev}", "title": "Fibre",
                           "message": f"{_fmt(v, 'g')} fibre vs at least {_fmt(fib['low'], 'g')} ({fib['basis']})."
                                      + (" (Some meals lack fibre data.)" if not complete.get("fiber", True) else "")})
            suggestions.append({"kind": "nutrient_gap", "text": "Add vegetables, legumes, fruit or whole grains, or swap a "
                                                                "snack for a higher-fibre option."})
        else:
            checks.append({"key": "fiber", "kind": "nutrient_gap", "status": "ok", "title": "Fibre",
                           "message": f"{_fmt(v, 'g')} fibre meets the {_fmt(fib['low'], 'g')} guide."})
    if pw == "below":
        suggestions.append({"kind": "nutrient_gap", "text": "Add a protein-rich food (dal, paneer, tofu, eggs, yoghurt, "
                                                            "chicken or fish to suit your diet) or ask the assistant "
                                                            "to swap a snack for a higher-protein option."})
    if cw == "below" and targets.get("is_training_day"):
        suggestions.append({"kind": "nutrient_gap", "text": "Carbohydrate is below the range for your training load: "
                                                            "increase the portion of a carbohydrate-rich meal "
                                                            "(rice, roti, pasta, oats, potatoes)."})
    if cw == "above" and (targets.get("macro_style") == "low_carb"):
        suggestions.append({"kind": "nutrient_gap", "text": "Swap a starchy meal for a low-carbohydrate recipe to stay "
                                                            "under about a quarter of energy from carbohydrate."})
    if fw == "above":
        suggestions.append({"kind": "nutrient_gap", "text": "Fat is above range: choose a leaner recipe or a smaller portion "
                                                            "of the richest meal."})

    # ---------------- distribution & timing ----------------
    pmp = targets.get("per_meal_protein")
    if pmp and not unavailable:
        mains = [m for m in meals if m.get("kind") in ("main", "breakfast", "post")]
        good = [m for m in mains if ((m.get("nutrition") or {}).get("values") or {}).get("protein", 0) >= pmp["low"]]
        if mains and len(good) < min(3, len(mains)):
            checks.append({"key": "distribution", "kind": "timing", "status": "minor", "title": "Protein distribution",
                           "message": f"{len(good)} of {len(mains)} main meals reach about {pmp['low']} g protein "
                                      f"({pmp['basis']}). Spreading protein across meals is generally recommended."})
            severity["minor"] += 1
        elif mains:
            checks.append({"key": "distribution", "kind": "timing", "status": "ok", "title": "Protein distribution",
                           "message": f"Protein is spread across {len(good)} meals with at least {pmp['low']} g each."})
    if targets.get("is_training_day"):
        pre = [m for m in meals if m.get("slot") == "pre_workout" or m.get("pre_training")]
        post = [m for m in meals if m.get("post_training") or m.get("slot") == "post_workout"]
        if not pre:
            checks.append({"key": "pre", "kind": "timing", "status": "minor", "title": "Before training",
                           "message": "No pre-training snack: a small carbohydrate-based snack 1-3 hours before can help."})
            severity["minor"] += 1
        else:
            pv = (pre[0].get("nutrition") or {}).get("values") or {}
            heavy = (pv.get("fat") or 0) > 15 or (pv.get("fiber") or 0) > 8
            checks.append({"key": "pre", "kind": "timing", "status": "minor" if heavy else "ok", "title": "Before training",
                           "message": (f"{pre[0]['name']} at {pre[0]['time']}: {_fmt(pv.get('carbs'), 'g')} carbohydrate, "
                                       f"{_fmt(pv.get('fat'), 'g')} fat"
                                       + (f", {_fmt(pv.get('fiber'), 'g')} fibre" if pv.get("fiber") is not None else "")
                                       + (". Quite high in fat/fibre for just before exercise." if heavy else
                                          ". Light and carbohydrate-based."))})
            if heavy:
                severity["minor"] += 1
        if not post:
            checks.append({"key": "post", "kind": "timing", "status": "minor", "title": "After training",
                           "message": "No meal is marked for recovery after training."})
            severity["minor"] += 1
        else:
            pv = (post[0].get("nutrition") or {}).get("values") or {}
            need = (pmp or {}).get("low", 20)
            ok = (pv.get("protein") or 0) >= min(need, 20) and (pv.get("carbs") or 0) >= 20
            checks.append({"key": "post", "kind": "timing", "status": "ok" if ok else "minor", "title": "After training",
                           "message": f"{post[0]['name']} at {post[0]['time']}: {_fmt(pv.get('protein'), 'g')} protein and "
                                      f"{_fmt(pv.get('carbs'), 'g')} carbohydrate"
                                      + ("." if ok else " - consider more protein and carbohydrate for recovery.")})
            if not ok:
                severity["minor"] += 1
    elif profile.get("sport"):
        if any(m.get("slot") in ("pre_workout", "post_workout") for m in meals):
            checks.append({"key": "rest_day", "kind": "timing", "status": "info", "title": "Rest day",
                           "message": "This is set as a rest day, so the training snacks are optional."})

    # ---------------- overall label ----------------
    info_needed = (not energy and not targets.get("protein")) or (len(unavailable) > max(1, len(meals) // 3))
    if severity["significant"]:
        label = "significant"
    elif info_needed:
        label = "info"
    elif severity["minor"]:
        label = "minor"
    else:
        label = "aligned"
    reasons = [c["title"] + ": " + c["message"] for c in checks if c["status"] not in ("ok", "info", "estimate")][:4]
    summary = {
        "aligned": "Your plan is within your estimated ranges and no restriction conflicts were found.",
        "minor": "Mostly suitable, with a few small differences from your estimated targets.",
        "significant": "There are important differences from your targets or a restriction conflict.",
        "info": "Some details are missing, so only a partial assessment is possible.",
    }[label]
    return {
        "label_key": label, "label": LABELS[label], "summary": summary, "reasons": reasons, "checks": checks,
        "suggestions": suggestions[:6], "restriction_conflicts": hard, "verification_notes": verify,
        "assessed_at": datetime.utcnow().isoformat(),
        "disclaimer": "This assessment compares estimates with general guidance; it does not guarantee performance, "
                      "weight change or any health outcome.",
    }
