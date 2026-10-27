"""
test_diet.py
============
API and logic tests for the Diet Planning feature. Runs against the real recipe database
(data/processed/diet_recipes.db) and USDA table; uses a temporary SQLite file for users/plans so the
app's own database is not touched. Skips automatically if the diet data has not been built.
"""

import os
import sys
import tempfile
import uuid

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend.app.core.database import Base, get_db  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.services.diet_recipe_store import recipe_store  # noqa: E402
from backend.app.services.food_labels import classify_diet, extra_animal_flags  # noqa: E402
from backend.app.services.nutrition_service import compute_meal_nutrition, ingredient_nutrition  # noqa: E402

pytestmark = pytest.mark.skipif(not recipe_store.available, reason="diet_recipes.db not built")

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_engine = create_engine(f"sqlite:///{_tmp.name}", connect_args={"check_same_thread": False})
_Session = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=_engine)


def _override_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[get_db] = _override_db
    c = TestClient(app)
    yield c
    app.dependency_overrides.pop(get_db, None)


def _user(client, pref="vegetarian"):
    email = f"diet_{uuid.uuid4().hex[:8]}@foodslm.ai"
    r = client.post("/api/auth/register", json={"name": "Diet Tester", "email": email, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    client.put("/api/user/preferences", json={"dietary_preference": pref}, headers=h)
    return h


PROFILE = {"age": 22, "sex": "male", "height_cm": 175, "weight_kg": 68}
FORBIDDEN = {
    "vegan": ("meat", "egg", "dairy"), "vegetarian": ("meat", "egg"), "eggitarian": ("meat",), "non_vegetarian": (),
}


def _assert_diet(plan, pref):
    allowed = {"vegan": {"vegan"}, "vegetarian": {"vegan", "vegetarian"},
               "eggitarian": {"vegan", "vegetarian", "eggitarian"}}.get(pref)
    for m in plan["meals"]:
        names = [i["name"] for i in m["ingredients"] if i["status"] != "removed"]
        if allowed:
            assert m["diet"] in allowed, (m["name"], m["diet"])
            assert classify_diet(names)[0] in allowed, (m["name"], names)
        for n in names:
            flags = extra_animal_flags(n)
            for k in FORBIDDEN[pref]:
                assert not flags[k], (pref, m["name"], n, k)


# --------------------------------------------------------------------------------------------- 1 sidebar data
def test_categories_listed(client):
    h = _user(client)
    r = client.get("/api/diet/categories", headers=h)
    assert r.status_code == 200
    groups = {g["key"]: g for g in r.json()["groups"]}
    assert set(groups) == {"preferences", "goals", "sports"}
    keys = {c["key"] for g in groups.values() for c in g["categories"]}
    for k in ("vegetarian", "vegan", "non_vegetarian", "eggetarian", "balanced", "weight_loss", "weight_gain",
              "muscle_building", "high_protein", "low_carb", "endurance", "recovery", "cricket", "football",
              "basketball", "tennis", "badminton", "swimming", "running", "cycling", "gym", "bodybuilding", "yoga",
              "other_sport"):
        assert k in keys
    for g in groups.values():
        for c in g["categories"]:
            assert c["image"] and c["image"]["url"].startswith("https://"), c["key"]


def test_requires_auth(client):
    assert client.get("/api/diet/categories").status_code in (401, 200)  # 200 only when ALLOW_DEMO_USER=true


# --------------------------------------------------------------------------------------------- 2 sports plans
@pytest.mark.parametrize("key", ["cricket", "football", "swimming", "running"])
def test_sports_plans(client, key):
    h = _user(client, "non_vegetarian")
    r = client.post("/api/diet/plans", json={"category_key": key, "profile": PROFILE}, headers=h)
    assert r.status_code == 200, r.text
    plan = r.json()
    assert len(plan["meals"]) >= 4
    slots = [m["slot"] for m in plan["meals"]]
    assert "pre_workout" in slots or any("pre-training" in m["label"].lower() for m in plan["meals"])
    assert any(m["post_training"] for m in plan["meals"])
    times = [m["time"] for m in plan["meals"]]
    assert times == sorted(times)
    for m in plan["meals"]:
        assert m["image_url"].startswith("https://")
        assert m["nutrition"]["status"] == "source"
        assert m["nutrition"]["values"]["kcal"] > 0
        assert len(m["steps"]) >= 2 and len(m["ingredients"]) >= 2
    assert plan["targets"]["energy"]["target"] > 1500
    assert plan["targets"]["carbs"]["basis"].endswith("training day")
    assert plan["assessment"]["label"]


def test_sport_plan_does_not_assume_weight_loss(client):
    h = _user(client, "non_vegetarian")
    plan = client.post("/api/diet/plans", json={"category_key": "football", "profile": PROFILE}, headers=h).json()
    assert plan["profile"]["goal"] == "performance"
    assert "deficit" not in plan["targets"]["energy"]["basis"]


# --------------------------------------------------------------------------------------------- 3 dietary prefs
@pytest.mark.parametrize("key,pref", [("vegan", "vegan"), ("vegetarian", "vegetarian"), ("eggetarian", "eggitarian"),
                                      ("non_vegetarian", "non_vegetarian"), ("high_protein", "vegan"),
                                      ("muscle_building", "vegetarian")])
def test_dietary_restrictions_respected(client, key, pref):
    h = _user(client, pref)
    plan = client.post("/api/diet/plans", json={"category_key": key, "profile": {**PROFILE, "diet_preference": pref}},
                       headers=h).json()
    assert plan["profile"]["diet_preference"] == pref
    _assert_diet(plan, pref)
    assert not plan["assessment"]["restriction_conflicts"]


def test_allergies_and_dislikes_respected(client):
    h = _user(client, "vegetarian")
    plan = client.post("/api/diet/plans", json={"category_key": "vegetarian", "profile": {
        **PROFILE, "allergies": ["peanut", "tree_nuts"], "intolerances": ["lactose"], "dislikes": ["mushroom"]}},
                       headers=h).json()
    for m in plan["meals"]:
        assert not {"peanut", "tree_nuts", "dairy"} & set(m["allergens"]), (m["name"], m["allergens"])
        assert not any("mushroom" in i["name"].lower() for i in m["ingredients"])


# --------------------------------------------------------------------------------------------- 4 editing
def _plan_with_paneer(client, h):
    plan = client.post("/api/diet/plans", json={"category_key": "high_protein", "profile": {**PROFILE,
                       "diet_preference": "vegetarian"}}, headers=h).json()
    res = client.get(f"/api/diet/plans/{plan['id']}/alternatives", params={"meal_id": plan["meals"][-1]["id"],
                     "q": "paneer"}, headers=h).json()
    cand = next(i for i in res["items"] if i["servings"])
    plan = client.post(f"/api/diet/plans/{plan['id']}/edit", json={"op": "replace_meal",
                       "meal_id": plan["meals"][-1]["id"], "recipe_id": cand["id"]}, headers=h).json()
    return plan, plan["meals"][[m["recipe_id"] for m in plan["meals"]].index(cand["id"])]


def test_edit_ingredient_recalculates(client):
    h = _user(client, "vegetarian")
    plan, meal = _plan_with_paneer(client, h)
    before_total = plan["totals"]["values"]["kcal"]
    ing = next(i for i in meal["ingredients"] if "paneer" in i["name"].lower() or "panir" in i["name"].lower())
    r = client.post(f"/api/diet/plans/{plan['id']}/edit", json={"op": "update_ingredient", "meal_id": meal["id"],
                    "index": ing["idx"], "name": "tofu", "quantity": "200", "unit": "g", "version": plan["version"]},
                    headers=h)
    assert r.status_code == 200, r.text
    new = r.json()
    m2 = next(m for m in new["meals"] if m["id"] == meal["id"])
    changed = next(i for i in m2["ingredients"] if i["idx"] == ing["idx"])
    assert changed["status"] == "modified" and changed["name"] == "tofu"
    assert m2["nutrition"]["status"] in ("estimate", "unavailable")
    if m2["nutrition"]["status"] == "estimate":
        assert m2["nutrition"]["values"] != meal["nutrition"]["values"]
        assert new["totals"]["values"]["kcal"] != before_total
    # the daily total always equals the sum of the meals
    s = sum(m["nutrition"]["values"]["kcal"] for m in new["meals"] if m["nutrition"]["status"] != "unavailable")
    assert abs(s - new["totals"]["values"]["kcal"]) <= len(new["meals"])
    # restoring brings back the source values exactly
    back = client.post(f"/api/diet/plans/{plan['id']}/edit", json={"op": "restore_ingredient", "meal_id": meal["id"],
                       "index": ing["idx"]}, headers=h).json()
    m3 = next(m for m in back["meals"] if m["id"] == meal["id"])
    assert m3["nutrition"]["status"] == "source"
    assert m3["nutrition"]["values"] == meal["nutrition"]["values"]


def test_servings_scale_linearly(client):
    h = _user(client, "non_vegetarian")
    plan = client.post("/api/diet/plans", json={"category_key": "balanced", "profile": PROFILE}, headers=h).json()
    m = plan["meals"][0]
    r = client.post(f"/api/diet/plans/{plan['id']}/edit", json={"op": "set_servings", "meal_id": m["id"],
                    "servings": m["servings"] * 2 if m["servings"] <= 2 else 1}, headers=h).json()
    m2 = r["meals"][[x["id"] for x in r["meals"]].index(m["id"])]
    src = m2["source_per_serving"]
    assert m2["nutrition"]["values"]["kcal"] == round(src["kcal"] * m2["servings"])
    assert abs(m2["nutrition"]["values"]["protein"] - round(src["protein"] * m2["servings"], 1)) < 0.11


def test_add_remove_meal_and_time(client):
    h = _user(client, "vegan")
    plan = client.post("/api/diet/plans", json={"category_key": "vegan", "profile": PROFILE}, headers=h).json()
    n = len(plan["meals"])
    alt = client.get(f"/api/diet/plans/{plan['id']}/alternatives", params={"slot": "evening_snack"}, headers=h).json()
    rid = alt["items"][0]["id"]
    p2 = client.post(f"/api/diet/plans/{plan['id']}/edit", json={"op": "add_meal", "recipe_id": rid,
                     "slot": "evening_snack", "time": "17:15"}, headers=h).json()
    assert len(p2["meals"]) == n + 1
    new_id = next(m["id"] for m in p2["meals"] if m["recipe_id"] == rid)
    p3 = client.post(f"/api/diet/plans/{plan['id']}/edit", json={"op": "set_time", "meal_id": new_id, "time": "18:00"},
                     headers=h).json()
    assert next(m for m in p3["meals"] if m["id"] == new_id)["time"] == "18:00"
    p4 = client.post(f"/api/diet/plans/{plan['id']}/edit", json={"op": "remove_meal", "meal_id": new_id}, headers=h).json()
    assert len(p4["meals"]) == n


# --------------------------------------------------------------------------------------------- 5 check my diet
def test_check_my_diet_uses_updated_data(client):
    h = _user(client, "vegetarian")
    plan = client.post("/api/diet/plans", json={"category_key": "muscle_building", "profile": {**PROFILE,
                       "diet_preference": "vegetarian"}}, headers=h).json()
    first = client.post(f"/api/diet/plans/{plan['id']}/assess", headers=h).json()["assessment"]
    assert first["label"] in ("Well Aligned With Your Goals", "Minor Adjustments Recommended",
                              "Significant Gaps Identified", "More Information Needed")
    assert any(c["key"] == "protein" for c in first["checks"])
    # Remove all but one meal: the assessment must now report a significant energy gap
    p = plan
    for m in plan["meals"][1:]:
        p = client.post(f"/api/diet/plans/{plan['id']}/edit", json={"op": "remove_meal", "meal_id": m["id"]},
                        headers=h).json()
    a = client.post(f"/api/diet/plans/{plan['id']}/assess", headers=h).json()["assessment"]
    energy = next(c for c in a["checks"] if c["key"] == "energy")
    assert energy["status"].startswith("below")
    assert a["label"] == "Significant Gaps Identified"
    assert "kcal" in energy["message"]


def test_assessment_flags_restriction_conflict(client):
    h = _user(client, "vegetarian")
    plan = client.post("/api/diet/plans", json={"category_key": "vegetarian", "profile": PROFILE}, headers=h).json()
    m = plan["meals"][0]
    p = client.post(f"/api/diet/plans/{plan['id']}/edit", json={"op": "add_ingredient", "meal_id": m["id"],
                    "name": "chicken breast", "quantity": "100", "unit": "g"}, headers=h).json()
    a = p["assessment"]
    assert a["restriction_conflicts"], a
    assert a["label"] == "Significant Gaps Identified"
    kinds = {c["kind"] for c in a["checks"]}
    assert "restriction" in kinds and "nutrient_gap" in kinds


def test_more_information_needed_without_body_data(client):
    h = _user(client, "no_preference")
    plan = client.post("/api/diet/plans", json={"category_key": "balanced", "profile": {}}, headers=h).json()
    assert plan["targets"]["energy"] is None
    assert plan["assessment"]["label"] == "More Information Needed"


# --------------------------------------------------------------------------------------------- 6/7 assistants
def test_cricket_assistant_proposes_and_applies(client):
    h = _user(client, "vegetarian")
    plan = client.post("/api/diet/plans", json={"category_key": "cricket", "profile": {**PROFILE,
                       "diet_preference": "vegetarian"}}, headers=h).json()
    assert plan["assistant_name"] == "Cricket Diet Assistant"
    r = client.post(f"/api/diet/plans/{plan['id']}/chat",
                    json={"message": "Replace my lunch with a higher-protein vegetarian meal"}, headers=h).json()
    reply = r["reply"]
    assert reply["meta"]["intent"] == "replace_meal"
    assert reply["proposals"], reply["content"]
    prop = reply["proposals"][0]
    lunch = next(m for m in plan["meals"] if m["slot"] == "lunch")
    assert prop["op"]["meal_id"] == lunch["id"]
    rec = recipe_store.get(prop["op"]["recipe_id"])
    assert rec["diet"] in ("vegan", "vegetarian")
    # not applied until confirmed
    assert client.get(f"/api/diet/plans/{plan['id']}", headers=h).json()["meals"] == plan["meals"]
    ap = client.post(f"/api/diet/plans/{plan['id']}/chat/{reply['id']}/apply", json={"proposal_id": prop["id"]},
                     headers=h)
    assert ap.status_code == 200, ap.text
    saved = client.get(f"/api/diet/plans/{plan['id']}", headers=h).json()
    assert next(m for m in saved["meals"] if m["id"] == lunch["id"])["recipe_id"] == rec["id"]
    assert "saved" in ap.json()["confirmation"]["content"]
    again = client.post(f"/api/diet/plans/{plan['id']}/chat/{reply['id']}/apply", json={"proposal_id": prop["id"]},
                        headers=h)
    assert again.status_code == 409


def test_assistant_ingredient_alternative_respects_diet(client):
    h = _user(client, "vegetarian")
    plan, meal = _plan_with_paneer(client, h)
    r = client.post(f"/api/diet/plans/{plan['id']}/chat", json={"message": "Can you suggest an alternative to paneer?"},
                    headers=h).json()["reply"]
    assert r["meta"]["intent"] == "ingredient_swap"
    for p in r["proposals"]:
        assert not extra_animal_flags(p["op"]["name"])["meat"]
        assert p["op"]["name"] not in ("eggs", "chicken breast", "cod")


def test_separate_contexts(client):
    h = _user(client, "non_vegetarian")
    a = client.post("/api/diet/plans", json={"category_key": "cricket", "profile": PROFILE}, headers=h).json()
    b = client.post("/api/diet/plans", json={"category_key": "weight_loss", "profile": PROFILE}, headers=h).json()
    client.post(f"/api/diet/plans/{a['id']}/chat", json={"message": "Why is my breakfast included?"}, headers=h)
    client.post(f"/api/diet/plans/{b['id']}/chat", json={"message": "Does this plan meet my requirements?"}, headers=h)
    ha = client.get(f"/api/diet/plans/{a['id']}/chat", headers=h).json()
    hb = client.get(f"/api/diet/plans/{b['id']}/chat", headers=h).json()
    assert ha["assistant_name"] == "Cricket Diet Assistant" and hb["assistant_name"] == "Weight Loss Diet Assistant"
    assert [m["content"] for m in ha["messages"] if m["role"] == "user"] == ["Why is my breakfast included?"]
    assert [m["content"] for m in hb["messages"] if m["role"] == "user"] == ["Does this plan meet my requirements?"]
    assert a["meals"][0]["name"] in ha["messages"][1]["content"] or "breakfast" in ha["messages"][1]["content"].lower()
    # another user cannot read this plan's chat
    other = _user(client)
    assert client.get(f"/api/diet/plans/{a['id']}/chat", headers=other).status_code == 404


def test_rest_day_and_pre_training(client):
    h = _user(client, "non_vegetarian")
    plan = client.post("/api/diet/plans", json={"category_key": "running", "profile": PROFILE}, headers=h).json()
    r = client.post(f"/api/diet/plans/{plan['id']}/chat", json={"message": "Is my pre-workout snack suitable before training?"},
                    headers=h).json()["reply"]
    assert r["meta"]["intent"] == "pre_check"
    r2 = client.post(f"/api/diet/plans/{plan['id']}/chat", json={"message": "How can I modify this plan for a rest day?"},
                     headers=h).json()["reply"]
    assert r2["meta"]["intent"] == "rest_day" and r2["proposals"]
    ap = client.post(f"/api/diet/plans/{plan['id']}/chat/{r2['id']}/apply", json={"proposal_id": r2["proposals"][0]["id"]},
                     headers=h).json()
    assert ap["plan"]["profile"]["day_type"] == "rest"
    assert not any(m["slot"] == "pre_workout" for m in ap["plan"]["meals"])


# --------------------------------------------------------------------------------------------- 8 general chatbot
def test_general_chatbot_returns_nutrition(client):
    h = _user(client, "vegetarian")
    r = client.post("/api/chat", json={"message": "Suggest a healthy vegetarian dinner using paneer and tomatoes",
                                       "preference": "vegetarian", "cuisine": "Indian"}, headers=h)
    assert r.status_code == 200, r.text
    rec = r.json()["recipe"]
    assert rec["ingredients"] and rec["instructions"]
    n = rec["nutrition"]
    assert n["status"] in ("source", "estimate", "unavailable")
    if n["status"] == "unavailable":
        assert n["reason"]
        rel = rec.get("related_recipe")
        assert rel and rel["nutrition"]["values"]["kcal"] > 0 and rel["image_url"].startswith("https://")
    else:
        assert n["values"]["kcal"] > 0
    assert rec["labels"]["diet"] in ("vegan", "vegetarian")


def test_general_chatbot_small_talk(client):
    h = _user(client)
    r = client.post("/api/chat", json={"message": "hello", "preference": "vegetarian"}, headers=h).json()
    assert r["response_type"] == "text" and r["recipe"] is None


# --------------------------------------------------------------------------------------------- 9 accuracy
def test_source_values_match_database(client):
    h = _user(client, "non_vegetarian")
    plan = client.post("/api/diet/plans", json={"category_key": "gym", "profile": PROFILE}, headers=h).json()
    for m in plan["meals"]:
        rec = recipe_store.get(m["recipe_id"])
        for k in ("kcal", "protein", "carbs", "fat"):
            expected = rec["nutrition_per_serving"][k] * m["servings"]
            got = m["nutrition"]["values"][k]
            assert abs(got - expected) <= (0.5 if k == "kcal" else 0.051), (k, got, expected)
    tot = plan["totals"]["values"]
    assert tot["kcal"] == round(sum(m["nutrition"]["values"]["kcal"] for m in plan["meals"]))


def test_missing_data_not_invented():
    r = ingredient_nutrition("unobtainium dust", "2", "cups")
    assert r["status"] == "unavailable"
    r2 = ingredient_nutrition("butter", "", "")
    assert r2["status"] == "unavailable"
    meal = {"servings": 1, "recipe_servings": None, "source_per_serving": {"kcal": 300, "protein": 10, "carbs": 30,
            "fat": 10, "fiber": None},
            "ingredients": [{"idx": 0, "name": "tofu", "quantity": "100", "unit": "g", "status": "added"}]}
    n = compute_meal_nutrition(meal)
    assert n["status"] == "unavailable" and all(v is None for v in n["values"].values())
    meal["ingredients"] = []
    n2 = compute_meal_nutrition(meal)
    assert n2["values"]["fiber"] is None and "fiber" in n2["missing"]


def test_usda_values_are_copied_not_guessed():
    r = ingredient_nutrition("tofu", "100", "g")
    assert r["status"] == "ok" and r["match"]["fdc_id"] == 172475
    assert r["nutrients"]["protein"] == pytest.approx(17.27, abs=0.01)  # USDA SR Legacy 172475


# --------------------------------------------------------------------------------------------- 10 saving
def test_save_and_reload(client):
    h = _user(client, "vegetarian")
    plan = client.post("/api/diet/plans", json={"category_key": "tennis", "profile": PROFILE}, headers=h).json()
    m = plan["meals"][0]
    client.post(f"/api/diet/plans/{plan['id']}/edit", json={"op": "set_servings", "meal_id": m["id"], "servings": 1.5},
                headers=h)
    r = client.put(f"/api/diet/plans/{plan['id']}", json={"name": "My tennis week", "is_saved": True}, headers=h)
    assert r.status_code == 200
    lst = client.get("/api/diet/plans", params={"saved_only": True}, headers=h).json()
    assert [p["name"] for p in lst] == ["My tennis week"]
    again = client.get(f"/api/diet/plans/{plan['id']}", headers=h).json()
    assert again["is_saved"] and next(x for x in again["meals"] if x["id"] == m["id"])["servings"] == 1.5
    detail = client.get("/api/diet/categories/tennis", headers=h).json()
    assert detail["latest_plan_id"] == plan["id"]


# --------------------------------------------------------------------------------------------- 11 failures
def test_invalid_requests(client):
    h = _user(client)
    assert client.post("/api/diet/plans", json={"category_key": "chess"}, headers=h).status_code == 404
    assert client.post("/api/diet/plans", json={"category_key": "cricket", "profile": {"age": 3}},
                       headers=h).status_code == 422
    assert client.get("/api/diet/plans/plan_missing", headers=h).status_code == 404
    plan = client.post("/api/diet/plans", json={"category_key": "yoga", "profile": PROFILE}, headers=h).json()
    pid = plan["id"]
    assert client.post(f"/api/diet/plans/{pid}/edit", json={"op": "explode"}, headers=h).status_code == 422
    assert client.post(f"/api/diet/plans/{pid}/edit", json={"op": "set_servings", "meal_id": plan["meals"][0]["id"],
                       "servings": 40}, headers=h).status_code == 422
    assert client.post(f"/api/diet/plans/{pid}/edit", json={"op": "set_time", "meal_id": plan["meals"][0]["id"],
                       "time": "25:99"}, headers=h).status_code == 422
    assert client.post(f"/api/diet/plans/{pid}/edit", json={"op": "replace_meal", "meal_id": plan["meals"][0]["id"],
                       "recipe_id": 999999999}, headers=h).status_code == 422
    assert client.post(f"/api/diet/plans/{pid}/edit", json={"op": "set_servings", "meal_id": plan["meals"][0]["id"],
                       "servings": 1, "version": 1_000}, headers=h).status_code == 409
    assert client.post(f"/api/diet/plans/{pid}/chat", json={"message": ""}, headers=h).status_code == 422
    assert client.get("/api/diet/recipes", params={"meal_type": "brunch"}, headers=h).status_code == 422
    assert client.get("/api/diet/recipes", params={"q": "dal", "page_size": 5}, headers=h).json()["page_size"] == 5


# ---- Assistant answers common questions from the plan's own data -----------------------------------------
def _ask(client, h, plan, q):
    return client.post(f"/api/diet/plans/{plan['id']}/chat", json={"message": q}, headers=h).json()["reply"]


def test_assistant_common_questions(client):
    h = _user(client, "vegetarian")
    plan = client.post("/api/diet/plans", json={"category_key": "cricket", "profile": {**PROFILE,
                       "diet_preference": "vegetarian"}}, headers=h).json()
    r = _ask(client, h, plan, "How much protein am I getting today?")
    assert r["meta"]["intent"] == "nutrient_question"
    assert str(round(plan["totals"]["values"]["protein"])) in r["content"]
    assert _ask(client, h, plan, "Is this safe if I have diabetes?")["meta"]["intent"] == "medical"
    assert _ask(client, h, plan, "Can I have coffee before training?")["meta"]["intent"] == "can_i_have"
    assert _ask(client, h, plan, "Make my plan vegan")["meta"]["intent"] == "change_diet"
    assert _ask(client, h, plan, "I'm allergic to peanuts, does anything have peanuts?")["meta"]["intent"] == "allergen_check"
    r = _ask(client, h, plan, "swap rice for something else")
    assert "can't suggest something else" not in r["content"]


def test_lighter_replacement_is_lighter(client):
    h = _user(client, "vegetarian")
    plan = client.post("/api/diet/plans", json={"category_key": "balanced", "profile": {**PROFILE,
                       "diet_preference": "vegetarian"}}, headers=h).json()
    dinner = next(m for m in plan["meals"] if m["slot"] == "dinner")
    r = _ask(client, h, plan, "Can I replace my dinner with something lighter?")
    for p in r["proposals"]:
        assert p["preview"]["meal_after"]["nutrition"]["values"]["kcal"] < dinner["nutrition"]["values"]["kcal"]


def test_plain_cheese_names_are_dairy():
    # "100 g feta" used to be classified as vegan because only "feta cheese" was listed
    assert classify_diet(["100 g feta, crumbled"])[0] == "vegetarian"
    assert classify_diet(["1/2 cup grated parmigiano"])[0] == "vegetarian"
