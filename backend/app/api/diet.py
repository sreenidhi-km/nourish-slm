"""
diet.py
=======
FastAPI routes for the Diet Planning feature (all under /api/diet, JWT protected like the rest of
the API): categories, recipe search, nutrition lookups, plan generation / editing / saving,
"Check My Diet" assessment and the plan-specific assistants.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.auth import get_current_user
from backend.app.core.database import get_db
from backend.app.models.diet import DietChatMessage, DietPlan
from backend.app.models.user import User
from backend.app.services import diet_assistant
from backend.app.services.diet_catalog import (
    ACTIVITY_LEVELS, CATEGORIES, GOALS, GROUP_TITLES, INTENSITIES, default_profile, get_category,
)
from backend.app.services.diet_planner import (
    EDIT_OPS, PlanError, apply_operation, excluded_allergens, dislike_terms, generate_plan, recalculate,
    sanitize_profile, SLOT_KIND,
)
from backend.app.services.diet_recipe_store import (
    ALLERGEN_KEYS, ALLERGEN_LABELS, DIET_LABELS, recipe_store, verification_conflicts,
)
from backend.app.services.diet_targets import compute_targets
from backend.app.services.nutrition_service import EDITOR_UNITS, ingredient_nutrition, usda_db

router = APIRouter(prefix="/diet", tags=["Diet Planning"])


# ----------------------------------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------------------------------
class CreatePlanRequest(BaseModel):
    category_key: str
    profile: Dict[str, Any] = Field(default_factory=dict)


class UpdatePlanRequest(BaseModel):
    name: Optional[str] = None
    is_saved: Optional[bool] = None


class EditRequest(BaseModel):
    op: Optional[str] = None
    ops: Optional[List[Dict[str, Any]]] = None
    version: Optional[int] = None
    model_config = {"extra": "allow"}


class ChatRequestBody(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ApplyRequest(BaseModel):
    proposal_id: str


class IngredientNutritionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    quantity: Optional[str] = None
    unit: Optional[str] = ""
    fdc_id: Optional[int] = None


class TargetsRequest(BaseModel):
    category_key: str
    profile: Dict[str, Any] = Field(default_factory=dict)


# ----------------------------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------------------------
_CATEGORY_IMAGE_CACHE: Dict[str, Optional[Dict[str, Any]]] = {}


def _require_data():
    if not recipe_store.available:
        raise HTTPException(status_code=503, detail="The diet recipe database has not been built yet. "
                                                    "Run: python scripts/build_diet_dataset.py")


from backend.app.services.category_photos import category_photo  # noqa: E402


def _category_image(cat: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """A real dish photo from the dataset that matches the category (cached)."""
    if cat["key"] in _CATEGORY_IMAGE_CACHE:
        return _CATEGORY_IMAGE_CACHE[cat["key"]]
    img = category_photo(cat["key"])          # hand-picked photo (Unsplash)
    if img is None and recipe_store.available:
        diet = cat["defaults"].get("diet_preference") or "no_preference"
        focus = (cat.get("slot_focus") or {}).get("main") or []
        for kw in cat.get("image_keywords") or [""]:
            res = recipe_store.search(page=1, page_size=1, order="name", diet=diet, meal_type="main", q=kw or None,
                                      focus_any=focus[:1] or None)
            if not res["items"]:
                res = recipe_store.search(page=1, page_size=1, diet=diet, q=kw or None)
            items = [i for i in res["items"] if not verification_conflicts(i, diet)]
            if items:
                r = items[0]
                img = {"url": r["image_url"], "alt": f"{r['name']} - example dish for {cat['name']}",
                       "recipe_name": r["name"], "recipe_id": r["id"], "source_url": r["source_url"]}
                break
    _CATEGORY_IMAGE_CACHE[cat["key"]] = img
    return img


def _card(cat: Dict[str, Any]) -> Dict[str, Any]:
    return {"key": cat["key"], "group": cat["group"], "name": cat["name"], "description": cat["description"],
            "focus": cat["focus"], "goal_text": cat["goal_text"], "assistant_name": cat["assistant_name"],
            "image": _category_image(cat)}


def _get_plan_row(db: Session, user: User, plan_id: str) -> DietPlan:
    row = db.query(DietPlan).filter(DietPlan.id == plan_id, DietPlan.user_id == user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Diet plan not found")
    return row


def _plan_out(row: DietPlan) -> Dict[str, Any]:
    plan = copy.deepcopy(row.plan)
    plan.update({"id": row.id, "name": row.name, "is_saved": row.is_saved, "version": row.version,
                 "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()})
    return plan


def _store(db: Session, row: DietPlan, plan: Dict[str, Any]):
    row.plan = plan
    row.profile = plan["profile"]
    row.version = (row.version or 0) + 1
    db.commit()
    db.refresh(row)


def _msg_out(m: DietChatMessage) -> Dict[str, Any]:
    return {"id": m.id, "role": m.role, "content": m.content, "proposals": m.proposals or [],
            "meta": m.meta or {}, "created_at": m.created_at.isoformat()}


# ----------------------------------------------------------------------------------------------
# Categories & reference data
# ----------------------------------------------------------------------------------------------
@router.get("/categories")
def list_categories(current_user: User = Depends(get_current_user)):
    groups = []
    for g, title in GROUP_TITLES.items():
        groups.append({"key": g, "title": title, "categories": [_card(c) for c in CATEGORIES if c["group"] == g]})
    return {"groups": groups, "data_available": recipe_store.available}


@router.get("/categories/{key}")
def category_detail(key: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cat = get_category(key)
    if not cat:
        raise HTTPException(status_code=404, detail="Unknown diet category")
    latest = (db.query(DietPlan).filter(DietPlan.user_id == current_user.id, DietPlan.category_key == key)
              .order_by(DietPlan.updated_at.desc()).first())
    return {**_card(cat), "notes": cat["notes"], "questions": cat["questions"],
            "default_profile": default_profile(cat, current_user.dietary_preference),
            "latest_plan_id": latest.id if latest else None}


@router.get("/options")
def options(current_user: User = Depends(get_current_user)):
    return {
        "goals": GOALS, "activity_levels": {k: v[0] for k, v in ACTIVITY_LEVELS.items()}, "intensities": INTENSITIES,
        "diet_preferences": DIET_LABELS, "allergens": {k: ALLERGEN_LABELS[k] for k in ALLERGEN_KEYS},
        "intolerances": ["lactose", "gluten", "egg", "soy", "nuts", "peanut"],
        "cuisines": ["any", "indian", "italian", "continental"], "units": EDITOR_UNITS,
        "sports": {c["defaults"].get("sport"): c["name"] for c in CATEGORIES if c["defaults"].get("sport")},
        "slots": {k: v for k, v in SLOT_KIND.items()}, "edit_ops": EDIT_OPS,
    }


@router.get("/meta")
def dataset_meta(current_user: User = Depends(get_current_user)):
    _require_data()
    meta = recipe_store.meta()
    return {"recipes": meta, "usda_foods": len(usda_db.foods) if usda_db.load() else 0,
            "sources": [
                {"name": "Food.com Recipes and Reviews (2020 crawl, parsed)", "use": "ingredient quantities, servings, "
                 "per-serving nutrition incl. fibre, photos", "licence": "CC0 1.0 (original Kaggle release by irkaal); "
                 "photos remain the property of their Food.com authors and are linked, not copied"},
                {"name": "Food.com Recipes and Interactions (Majumder et al., 2019)", "use": "step-by-step instructions, "
                 "tags, %DV nutrition for remaining recipes", "licence": "research dataset (already used by Nourish SLM)"},
                {"name": "USDA FoodData Central SR Legacy (2018) + FNDDS/Branded records", "use": "ingredient-level "
                 "estimates when you edit a meal", "licence": "public domain (CC0)"},
            ]}


@router.post("/targets")
def preview_targets(req: TargetsRequest, current_user: User = Depends(get_current_user)):
    cat = get_category(req.category_key)
    if not cat:
        raise HTTPException(status_code=404, detail="Unknown diet category")
    try:
        profile = sanitize_profile(req.profile, default_profile(cat, current_user.dietary_preference))
    except PlanError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return compute_targets(profile, cat)


# ----------------------------------------------------------------------------------------------
# Recipes & nutrition
# ----------------------------------------------------------------------------------------------
@router.get("/recipes")
def search_recipes(q: Optional[str] = None, diet: Optional[str] = None, meal_type: Optional[str] = None,
                   cuisine: Optional[str] = None, focus: Optional[str] = None, ingredients: Optional[str] = None,
                   exclude_allergens: Optional[str] = None, max_minutes: Optional[int] = None,
                   order: str = "name", page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=48),
                   current_user: User = Depends(get_current_user)):
    _require_data()
    if diet and diet not in DIET_LABELS:
        raise HTTPException(status_code=422, detail="Unknown diet")
    if meal_type and meal_type not in ("breakfast", "main", "snack"):
        raise HTTPException(status_code=422, detail="meal_type must be breakfast, main or snack")
    res = recipe_store.search(
        page=page, page_size=page_size, order=order, q=(q or None), diet=diet, meal_type=meal_type, cuisine=cuisine,
        focus_any=[f for f in (focus or "").split(",") if f], include_ingredients=[i.strip() for i in (ingredients or "").split(",") if i.strip()],
        exclude_allergens=[a for a in (exclude_allergens or "").split(",") if a in ALLERGEN_KEYS],
        max_total_min=max_minutes)
    if diet:
        res["items"] = [dict(i, verify_conflicts=verification_conflicts(i, diet)) for i in res["items"]]
    return res


@router.get("/recipes/{recipe_id}")
def get_recipe(recipe_id: int, current_user: User = Depends(get_current_user)):
    _require_data()
    r = recipe_store.get(recipe_id)
    if not r:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return r


@router.get("/ingredients/search")
def search_ingredients(q: str = Query(..., min_length=2, max_length=60), current_user: User = Depends(get_current_user)):
    return {"items": usda_db.search(q, limit=10)}


@router.post("/nutrition/ingredient")
def nutrition_for_ingredient(req: IngredientNutritionRequest, current_user: User = Depends(get_current_user)):
    return ingredient_nutrition(req.name, req.quantity, req.unit or "", "", req.fdc_id)


# ----------------------------------------------------------------------------------------------
# Plans
# ----------------------------------------------------------------------------------------------
@router.post("/plans")
def create_plan(req: CreatePlanRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_data()
    cat = get_category(req.category_key)
    if not cat:
        raise HTTPException(status_code=404, detail="Unknown diet category")
    try:
        profile = sanitize_profile(req.profile, default_profile(cat, current_user.dietary_preference))
        plan = generate_plan(cat["key"], profile)
    except PlanError as e:
        raise HTTPException(status_code=422, detail=str(e))
    row = DietPlan(id=plan["id"], user_id=current_user.id, category_key=cat["key"], name=f"{cat['name']} plan",
                   is_saved=False, profile=profile, plan=plan, version=1)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _plan_out(row)


@router.get("/plans")
def list_plans(saved_only: bool = False, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = db.query(DietPlan).filter(DietPlan.user_id == current_user.id)
    if saved_only:
        q = q.filter(DietPlan.is_saved.is_(True))
    rows = q.order_by(DietPlan.updated_at.desc()).limit(100).all()
    out = []
    for r in rows:
        cat = get_category(r.category_key) or {}
        t = (r.plan or {}).get("totals", {}).get("values", {})
        out.append({"id": r.id, "name": r.name, "is_saved": r.is_saved, "category_key": r.category_key,
                    "category_name": cat.get("name", r.category_key), "meal_count": len((r.plan or {}).get("meals", [])),
                    "kcal": t.get("kcal"), "assessment_label": (r.plan or {}).get("assessment", {}).get("label"),
                    "updated_at": r.updated_at.isoformat()})
    return out


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _plan_out(_get_plan_row(db, current_user, plan_id))


@router.put("/plans/{plan_id}")
def update_plan(plan_id: str, req: UpdatePlanRequest, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    row = _get_plan_row(db, current_user, plan_id)
    if req.name is not None:
        name = req.name.strip()[:120]
        if not name:
            raise HTTPException(status_code=422, detail="Plan name cannot be empty")
        row.name = name
    if req.is_saved is not None:
        row.is_saved = bool(req.is_saved)
    db.commit()
    db.refresh(row)
    return _plan_out(row)


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = _get_plan_row(db, current_user, plan_id)
    db.delete(row)
    db.commit()
    return {"message": "Diet plan deleted"}


@router.post("/plans/{plan_id}/edit")
def edit_plan(plan_id: str, req: EditRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_data()
    row = _get_plan_row(db, current_user, plan_id)
    if req.version is not None and req.version != row.version:
        raise HTTPException(status_code=409, detail="This plan was changed elsewhere. Reload it and try again.")
    body = req.model_dump(exclude_none=True)
    body.pop("version", None)
    op = {"op": "batch", "ops": body["ops"]} if body.get("ops") else body
    if not op.get("op"):
        raise HTTPException(status_code=422, detail="An edit operation is required")
    try:
        plan, summary = apply_operation(row.plan, op)
    except PlanError as e:
        raise HTTPException(status_code=422, detail=str(e))
    _store(db, row, plan)
    out = _plan_out(row)
    out["last_change"] = summary
    return out


@router.post("/plans/{plan_id}/assess")
def assess(plan_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_data()
    row = _get_plan_row(db, current_user, plan_id)
    plan = recalculate(copy.deepcopy(row.plan))
    _store(db, row, plan)
    return {"assessment": plan["assessment"], "totals": plan["totals"], "targets": plan["targets"],
            "version": row.version}


@router.get("/plans/{plan_id}/alternatives")
def alternatives(plan_id: str, meal_id: Optional[str] = None, slot: Optional[str] = None, q: Optional[str] = None,
                 focus: Optional[str] = None, cuisine: Optional[str] = None, page: int = Query(1, ge=1),
                 page_size: int = Query(9, ge=1, le=30), db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """Recipes that respect this plan's diet, allergies and disliked foods, for replacing or adding a meal."""
    _require_data()
    row = _get_plan_row(db, current_user, plan_id)
    plan = row.plan
    profile = plan["profile"]
    kind = None
    if meal_id:
        meal = next((m for m in plan["meals"] if m["id"] == meal_id), None)
        if not meal:
            raise HTTPException(status_code=404, detail="Meal not found")
        kind = meal.get("kind")
    elif slot:
        kind = SLOT_KIND.get(slot)
    meal_type = {"breakfast": "breakfast", "main": "main", "snack": "snack", "post": None}.get(kind) if kind else None
    pref = profile.get("diet_preference") or "no_preference"
    res = recipe_store.search(page=page, page_size=page_size, order="name" if q else "protein_density",
                              q=q or None, diet=pref, meal_type=meal_type, cuisine=cuisine,
                              focus_any=[f for f in (focus or "").split(",") if f],
                              exclude_allergens=excluded_allergens(profile), dislikes=dislike_terms(profile),
                              exclude_ids=[m["recipe_id"] for m in plan["meals"]])
    res["items"] = [i for i in res["items"] if not verification_conflicts(i, pref)]
    return res


# ----------------------------------------------------------------------------------------------
# Plan-specific assistant
# ----------------------------------------------------------------------------------------------
@router.get("/plans/{plan_id}/chat")
def chat_history(plan_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = _get_plan_row(db, current_user, plan_id)
    msgs = db.query(DietChatMessage).filter(DietChatMessage.plan_id == row.id).order_by(DietChatMessage.id.asc()).all()
    return {"plan_id": row.id, "assistant_name": row.plan.get("assistant_name"), "messages": [_msg_out(m) for m in msgs]}


@router.post("/plans/{plan_id}/chat")
def chat(plan_id: str, req: ChatRequestBody, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_data()
    row = _get_plan_row(db, current_user, plan_id)
    history = [{"role": m.role, "content": m.content} for m in
               db.query(DietChatMessage).filter(DietChatMessage.plan_id == row.id).order_by(DietChatMessage.id.asc()).all()]
    user_msg = DietChatMessage(plan_id=row.id, role="user", content=req.message.strip())
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)
    try:
        out = diet_assistant.respond(copy.deepcopy(row.plan), req.message, history)
    except PlanError as e:
        out = {"content": f"I couldn't work that out: {e}", "proposals": [], "meta": {"intent": "error"}}
    meta = dict(out.get("meta") or {}, plan_version=row.version)
    reply = DietChatMessage(plan_id=row.id, role="assistant", content=out["content"], proposals=out.get("proposals") or [],
                            meta=meta)
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return {"user_message": _msg_out(user_msg), "reply": _msg_out(reply)}


@router.post("/plans/{plan_id}/chat/{message_id}/apply")
def apply_proposal(plan_id: str, message_id: int, req: ApplyRequest, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    _require_data()
    row = _get_plan_row(db, current_user, plan_id)
    msg = db.query(DietChatMessage).filter(DietChatMessage.id == message_id, DietChatMessage.plan_id == row.id,
                                           DietChatMessage.role == "assistant").first()
    if not msg:
        raise HTTPException(status_code=404, detail="Assistant message not found")
    proposals = copy.deepcopy(msg.proposals or [])
    prop = next((p for p in proposals if p.get("id") == req.proposal_id), None)
    if not prop:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if prop.get("status") == "applied":
        raise HTTPException(status_code=409, detail="This suggestion has already been applied")
    try:
        plan, summary = apply_operation(row.plan, prop["op"])
    except PlanError as e:
        raise HTTPException(status_code=409, detail=f"This suggestion no longer fits the current plan: {e}")
    _store(db, row, plan)  # committed before we tell the user anything was saved
    prop["status"] = "applied"
    msg.proposals = proposals
    t = plan["totals"]["values"]
    confirm = DietChatMessage(
        plan_id=row.id, role="assistant",
        content=(f"Done - {summary}. Your plan has been saved: the day now totals "
                 + (f"{t['kcal']} kcal, {t['protein']} g protein, {t['carbs']} g carbohydrate and {t['fat']} g fat. "
                    if t.get("kcal") is not None else "")
                 + f"Check My Diet: {plan['assessment']['label']}."),
        proposals=[], meta={"intent": "applied", "plan_version": row.version})
    db.add(confirm)
    db.commit()
    db.refresh(confirm)
    return {"plan": _plan_out(row), "message": _msg_out(msg), "confirmation": _msg_out(confirm)}
