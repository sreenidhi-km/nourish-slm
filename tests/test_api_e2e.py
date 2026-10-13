#!/usr/bin/env python3
"""
End-to-end API tests for Nourish SLM
"""
import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000"

def req(method, path, data=None, token=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "detail": e.read().decode()}

# Login
print("Logging in...")
resp = req("POST", "/api/auth/login", {"email": "sreenidhi@foodslm.ai", "password": "password123"})
token = resp.get("access_token", "")
if not token:
    print("LOGIN FAILED:", resp)
    exit(1)
print(f"✓ Login OK, token: {token[:30]}...")

print()
print("=== TEST 1: Vegan + Indian + potatoes/onions/tomatoes ===")
r = req("POST", "/api/chat", {"message": "I have potatoes, onions and tomatoes", "preference": "vegan", "cuisine": "Indian"}, token)
recipe = r.get("recipe", {})
print(f"Title: {recipe.get('title')}")
print(f"Cuisine: {recipe.get('cuisine')}")
print(f"Diet: {recipe.get('diet_type')}")
print(f"Validation passed: {r.get('validation', {}).get('passed')}")
assert recipe.get("cuisine") == "Indian", f"FAIL: expected Indian, got {recipe.get('cuisine')}"
assert recipe.get("diet_type") == "vegan", f"FAIL: expected vegan, got {recipe.get('diet_type')}"
assert r.get("validation", {}).get("passed"), "FAIL: validation not passed"
print("✓ PASS")

print()
print("=== TEST 2: Vegetarian + Italian + pasta/tomatoes ===")
r = req("POST", "/api/chat", {"message": "pasta and tomatoes", "preference": "vegetarian", "cuisine": "Italian"}, token)
recipe = r.get("recipe", {})
print(f"Title: {recipe.get('title')}")
print(f"Cuisine: {recipe.get('cuisine')}")
print(f"Diet: {recipe.get('diet_type')}")
print(f"Validation passed: {r.get('validation', {}).get('passed')}")
assert recipe.get("cuisine") == "Italian", f"FAIL: expected Italian, got {recipe.get('cuisine')}"
assert recipe.get("diet_type") in ("vegetarian", "vegan"), f"FAIL: diet was {recipe.get('diet_type')}"
assert r.get("validation", {}).get("passed"), "FAIL: validation not passed"
print("✓ PASS")

print()
print("=== TEST 3: Non-Vegetarian + Indian + chicken/rice ===")
r = req("POST", "/api/chat", {"message": "I have chicken and rice", "preference": "non_vegetarian", "cuisine": "Indian"}, token)
recipe = r.get("recipe", {})
print(f"Title: {recipe.get('title')}")
print(f"Cuisine: {recipe.get('cuisine')}")
print(f"Diet: {recipe.get('diet_type')}")
assert recipe.get("cuisine") == "Indian", f"FAIL: expected Indian, got {recipe.get('cuisine')}"
assert recipe.get("diet_type") == "non_vegetarian", f"FAIL: diet was {recipe.get('diet_type')}"
print("✓ PASS")

print()
print("=== TEST 4: Vegan + Italian + pasta ===")
r = req("POST", "/api/chat", {"message": "pasta", "preference": "vegan", "cuisine": "Italian"}, token)
recipe = r.get("recipe", {})
print(f"Title: {recipe.get('title')}")
print(f"Cuisine: {recipe.get('cuisine')}")
print(f"Diet: {recipe.get('diet_type')}")
assert recipe.get("cuisine") == "Italian", f"FAIL: expected Italian, got {recipe.get('cuisine')}"
assert recipe.get("diet_type") in ("vegan",), f"FAIL: diet was {recipe.get('diet_type')}"
print("✓ PASS")

print()
print("=== TEST 5: Eggitarian + Continental + eggs/vegetables ===")
r = req("POST", "/api/chat", {"message": "I have eggs and vegetables", "preference": "eggitarian", "cuisine": "Continental"}, token)
recipe = r.get("recipe", {})
print(f"Title: {recipe.get('title')}")
print(f"Cuisine: {recipe.get('cuisine')}")
print(f"Diet: {recipe.get('diet_type')}")
assert recipe.get("cuisine") == "Continental", f"FAIL: expected Continental, got {recipe.get('cuisine')}"
assert recipe.get("diet_type") in ("vegan", "vegetarian", "eggitarian"), f"FAIL: diet was {recipe.get('diet_type')}"
print("✓ PASS")

print()
print("=== TEST 6: Preference change Vegan -> Non-Vegetarian ===")
r = req("POST", "/api/chat", {"message": "chicken tikka", "preference": "non_vegetarian", "cuisine": "Indian"}, token)
recipe = r.get("recipe", {})
print(f"Diet returned: {recipe.get('diet_type')}")
profile = req("GET", "/api/user/profile", token=token)
print(f"User DB preference: {profile.get('dietary_preference')}")
assert recipe.get("diet_type") == "non_vegetarian", f"FAIL: diet was {recipe.get('diet_type')}"
print("✓ PASS")

print()
print("=== TEST 7: Cuisine change Indian -> Italian ===")
r = req("POST", "/api/chat", {"message": "pasta and garlic", "preference": "vegetarian", "cuisine": "Italian"}, token)
recipe = r.get("recipe", {})
print(f"Cuisine returned: {recipe.get('cuisine')}")
assert recipe.get("cuisine") == "Italian", f"FAIL: expected Italian, got {recipe.get('cuisine')}"
print("✓ PASS")

print()
print("=== TEST 9: Chat history ===")
history = req("GET", "/api/chat/history", token=token)
print(f"Chat sessions count: {len(history)}")
if history:
    print(f"Most recent chat title: {history[0].get('title')}")
    assert history[0].get("title"), "FAIL: chat has no title"
    print("✓ PASS")

print()
print("=== TEST 10: Open old chat session ===")
if history:
    chat_id = history[0]["id"]
    session = req("GET", f"/api/chat/{chat_id}", token=token)
    msgs = session.get("messages", [])
    print(f"Chat ID: {chat_id}")
    print(f"Messages loaded: {len(msgs)}")
    assert len(msgs) > 0, "FAIL: no messages in chat"
    print(f"First message role: {msgs[0].get('role')}")
    print("✓ PASS")

print()
print("=== Cuisine validation: Chinese/Mexican should be rejected ===")
r = req("POST", "/api/chat", {"message": "pasta", "preference": "vegan", "cuisine": "Chinese"}, token)
recipe = r.get("recipe", {})
print(f"Chinese cuisine input -> recipe cuisine: {recipe.get('cuisine')}")
assert recipe.get("cuisine") != "Chinese", f"FAIL: Chinese cuisine should not pass through"
print("✓ PASS (Chinese not allowed)")

print()
print("✅ ALL TESTS PASSED")
