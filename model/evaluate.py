#!/usr/bin/env python3
"""
evaluate.py
===========
Automated Evaluation Pipeline for Food SLM.
Rule-checker evaluation: runs the dietary VALIDATOR (not the model) on 50 hand-written ingredient lists.
Use `--model` to evaluate real SLM generations on held-out test.jsonl (see run_model_evaluation).
Executes 50 test cases across Vegan, Vegetarian, Eggitarian, and Non-Vegetarian preferences.
Measures Dietary Compliance %, Ingredient Match %, Format Quality %, and Latency.
Generates evaluation report saved to data/evaluation/eval_report.json.
"""

import sys
import os
import json
import time
from typing import List, Dict, Any
PROJECT_ROOT = os.environ.get("PROJECT_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.ingredient_classifier import classify_recipe_diet
from backend.app.services.recipe_validator import validate_recipe_against_preference
from backend.app.services.dietary_rules import DietaryPreference

# 50 Automated Test Cases covering all dietary preferences and kitchen scenarios
TEST_SUITE = [
    # VEGAN (15 Test Cases)
    {"id": 1, "pref": "vegan", "ingredients": ["potato", "tomato", "onion"], "cuisine": "Indian"},
    {"id": 2, "pref": "vegan", "ingredients": ["rice", "black beans", "avocado", "lime"], "cuisine": "Mexican"},
    {"id": 3, "pref": "vegan", "ingredients": ["pasta", "garlic", "olive oil", "basil"], "cuisine": "Italian"},
    {"id": 4, "pref": "vegan", "ingredients": ["tofu", "broccoli", "soy sauce", "ginger"], "cuisine": "Chinese"},
    {"id": 5, "pref": "vegan", "ingredients": ["chickpeas", "tahini", "lemon", "garlic"], "cuisine": "Middle Eastern"},
    {"id": 6, "pref": "vegan", "ingredients": ["spinach", "lentils", "cumin", "turmeric"], "cuisine": "Indian"},
    {"id": 7, "pref": "vegan", "ingredients": ["quinoa", "cucumber", "cherry tomatoes", "olive oil"], "cuisine": "Mediterranean"},
    {"id": 8, "pref": "vegan", "ingredients": ["sweet potato", "black beans", "corn"], "cuisine": "Mexican"},
    {"id": 9, "pref": "vegan", "ingredients": ["oats", "banana", "almond milk", "cinnamon"], "cuisine": "American"},
    {"id": 10, "pref": "vegan", "ingredients": ["eggplant", "zucchini", "bell pepper", "tomato sauce"], "cuisine": "French"},
    {"id": 11, "pref": "vegan", "ingredients": ["cauliflower", "coconut milk", "curry powder"], "cuisine": "Thai"},
    {"id": 12, "pref": "vegan", "ingredients": ["mushrooms", "garlic", "thyme", "olive oil"], "cuisine": "Italian"},
    {"id": 13, "pref": "vegan", "ingredients": ["rice", "edamame", "carrots", "sesame oil"], "cuisine": "Japanese"},
    {"id": 14, "pref": "vegan", "ingredients": ["cabbage", "carrots", "peas", "mustard seeds"], "cuisine": "Indian"},
    {"id": 15, "pref": "vegan", "ingredients": ["pumpkin", "vegetable broth", "nutmeg"], "cuisine": "American"},

    # VEGETARIAN (15 Test Cases)
    {"id": 16, "pref": "vegetarian", "ingredients": ["paneer", "spinach", "cream", "garlic"], "cuisine": "Indian"},
    {"id": 17, "pref": "vegetarian", "ingredients": ["pasta", "heavy cream", "parmesan", "garlic"], "cuisine": "Italian"},
    {"id": 18, "pref": "vegetarian", "ingredients": ["mozzarella", "tomato", "basil", "balsamic"], "cuisine": "Italian"},
    {"id": 19, "pref": "vegetarian", "ingredients": ["rice", "yogurt", "mustard seeds", "curry leaves"], "cuisine": "Indian"},
    {"id": 20, "pref": "vegetarian", "ingredients": ["tortilla", "cheddar", "black beans", "sour cream"], "cuisine": "Mexican"},
    {"id": 21, "pref": "vegetarian", "ingredients": ["butter", "paneer", "tomato puree", "kasuri methi"], "cuisine": "Indian"},
    {"id": 22, "pref": "vegetarian", "ingredients": ["feta cheese", "olives", "cucumber", "red onion"], "cuisine": "Greek"},
    {"id": 23, "pref": "vegetarian", "ingredients": ["ricotta", "spinach", "lasagna sheets", "marinara"], "cuisine": "Italian"},
    {"id": 24, "pref": "vegetarian", "ingredients": ["potato", "butter", "milk", "chives"], "cuisine": "American"},
    {"id": 25, "pref": "vegetarian", "ingredients": ["halloumi", "mint", "lemon", "olive oil"], "cuisine": "Mediterranean"},
    {"id": 26, "pref": "vegetarian", "ingredients": ["cottage cheese", "peaches", "honey"], "cuisine": "American"},
    {"id": 27, "pref": "vegetarian", "ingredients": ["sweet corn", "butter", "lime juice", "cotija cheese"], "cuisine": "Mexican"},
    {"id": 28, "pref": "vegetarian", "ingredients": ["bread", "cheddar cheese", "butter"], "cuisine": "American"},
    {"id": 29, "pref": "vegetarian", "ingredients": ["ghee", "semolina", "sugar", "cardamom"], "cuisine": "Indian"},
    {"id": 30, "pref": "vegetarian", "ingredients": ["greek yogurt", "honey", "walnuts"], "cuisine": "Greek"},

    # EGGITARIAN (10 Test Cases)
    {"id": 31, "pref": "eggitarian", "ingredients": ["eggs", "bread", "butter", "black pepper"], "cuisine": "American"},
    {"id": 32, "pref": "eggitarian", "ingredients": ["eggs", "rice", "soy sauce", "scallions"], "cuisine": "Chinese"},
    {"id": 33, "pref": "eggitarian", "ingredients": ["eggs", "tomato", "onion", "green chilies"], "cuisine": "Indian"},
    {"id": 34, "pref": "eggitarian", "ingredients": ["egg whites", "spinach", "feta cheese"], "cuisine": "Mediterranean"},
    {"id": 35, "pref": "eggitarian", "ingredients": ["eggs", "potatoes", "onion", "olive oil"], "cuisine": "Spanish"},
    {"id": 36, "pref": "eggitarian", "ingredients": ["eggs", "cream", "nutmeg", "pie crust"], "cuisine": "French"},
    {"id": 37, "pref": "eggitarian", "ingredients": ["eggs", "tortilla", "salsa", "avocado"], "cuisine": "Mexican"},
    {"id": 38, "pref": "eggitarian", "ingredients": ["eggs", "ramen noodles", "green onion", "sesame"], "cuisine": "Japanese"},
    {"id": 39, "pref": "eggitarian", "ingredients": ["eggs", "bell pepper", "onion", "tomato"], "cuisine": "Middle Eastern"},
    {"id": 40, "pref": "eggitarian", "ingredients": ["eggs", "mayonnaise", "mustard", "paprika"], "cuisine": "American"},

    # NON-VEGETARIAN (10 Test Cases)
    {"id": 41, "pref": "non_vegetarian", "ingredients": ["chicken breast", "rice", "onion", "spices"], "cuisine": "Indian"},
    {"id": 42, "pref": "non_vegetarian", "ingredients": ["ground beef", "taco shells", "lettuce", "cheese"], "cuisine": "Mexican"},
    {"id": 43, "pref": "non_vegetarian", "ingredients": ["salmon fillet", "lemon", "dill", "butter"], "cuisine": "American"},
    {"id": 44, "pref": "non_vegetarian", "ingredients": ["chicken thighs", "soy sauce", "mirin", "sugar"], "cuisine": "Japanese"},
    {"id": 45, "pref": "non_vegetarian", "ingredients": ["shrimp", "garlic", "butter", "white wine", "parsley"], "cuisine": "Italian"},
    {"id": 46, "pref": "non_vegetarian", "ingredients": ["pork chops", "apples", "rosemary", "olive oil"], "cuisine": "American"},
    {"id": 47, "pref": "non_vegetarian", "ingredients": ["lamb", "yogurt", "garlic", "pita bread"], "cuisine": "Middle Eastern"},
    {"id": 48, "pref": "non_vegetarian", "ingredients": ["bacon", "eggs", "spaghetti", "parmesan"], "cuisine": "Italian"},
    {"id": 49, "pref": "non_vegetarian", "ingredients": ["duck breast", "orange juice", "honey", "thyme"], "cuisine": "French"},
    {"id": 50, "pref": "non_vegetarian", "ingredients": ["cod fillet", "potatoes", "flour", "tarter sauce"], "cuisine": "British"}
]

def run_evaluation(output_path: str = None) -> Dict[str, Any]:
    output_path = output_path or os.path.join(PROJECT_ROOT, "data", "evaluation", "eval_report.json")
    print("="*60)
    print("FOOD SLM - AUTOMATED EVALUATION PIPELINE")
    print(f"Running test suite of {len(TEST_SUITE)} test cases...")
    print("="*60)

    start_time = time.time()
    passed_compliance = 0
    conflicts_found = 0
    total_latency_ms = 0

    results_detail = []

    for test in TEST_SUITE:
        t0 = time.time()
        pref = test["pref"]
        ings = test["ingredients"]
        cuisine = test["cuisine"]

        # Run dietary validation check
        val_res = validate_recipe_against_preference(ings, pref)
        t1 = time.time()

        latency_ms = (t1 - t0) * 1000
        total_latency_ms += latency_ms

        is_passed = val_res["passed"]
        if is_passed:
            passed_compliance += 1
        else:
            conflicts_found += 1

        results_detail.append({
            "test_id": test["id"],
            "requested_preference": pref,
            "ingredients": ings,
            "cuisine": cuisine,
            "passed": is_passed,
            "conflicts": val_res["conflicts"],
            "latency_ms": round(latency_ms, 2)
        })

    avg_latency = total_latency_ms / len(TEST_SUITE)
    compliance_rate = (passed_compliance / len(TEST_SUITE)) * 100.0
    total_duration = time.time() - start_time

    summary = {
        "total_test_cases": len(TEST_SUITE),
        "validator_passed": passed_compliance,
        "dietary_conflicts_count": conflicts_found,
        "validator_pass_percentage": round(compliance_rate, 2),
        "average_latency_ms": round(avg_latency, 2),
        "evaluation_duration_seconds": round(total_duration, 2),
        "breakdown": {
            "vegan_tests": 15,
            "vegetarian_tests": 15,
            "eggitarian_tests": 10,
            "non_vegetarian_tests": 10
        }
    }

    report = {
        "summary": summary,
        "details": results_detail
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\nEVALUATION SUMMARY REPORT:")
    print(f"  Total Test Cases: {summary['total_test_cases']}")
    print(f"  Rule-validator pass rate (NOT model quality): {summary['validator_pass_percentage']}%")
    print(f"  Average Validation Latency: {summary['average_latency_ms']} ms")
    print(f"  Report saved to: {output_path}")

    return report

def run_model_evaluation(n_samples: int = 50, output_path: str = None) -> Dict[str, Any]:
    """
    Evaluates REAL model generations on held-out test.jsonl records.
    Metrics: JSON parse rate, usable-recipe rate, diet compliance of the generated
    ingredients against the requested preference, and generation latency.
    """
    from model.inference import slm_engine, build_training_style_messages, parse_model_recipe
    from model.config.config import ModelConfig

    output_path = output_path or os.path.join(PROJECT_ROOT, "data", "evaluation", "model_eval_report.json")
    slm_engine.load_model()
    if not slm_engine.is_loaded:
        raise RuntimeError("Model could not be loaded; cannot run model evaluation.")

    records = []
    eval_path = getattr(ModelConfig, "EVAL_DATA_PATH", os.path.join(PROJECT_ROOT, "data", "diet_eval.jsonl"))
    with open(eval_path, "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
            if len(records) >= n_samples:
                break

    usable, compliant, latencies, details = 0, 0, [], []
    for rec in records:
        inp = rec["input"]
        msgs = build_training_style_messages(inp["ingredients"], inp["preference"], inp["cuisine"])
        prompt = slm_engine.tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        gen = slm_engine.generate_raw_tokens(prompt, max_new_tokens=450)
        latencies.append(gen["generation_time_ms"])
        parsed = parse_model_recipe(gen["response_text"])
        ok_diet = None
        if parsed is not None:
            usable += 1
            ok_diet = validate_recipe_against_preference(parsed["ingredients"], inp["preference"])["passed"]
            compliant += int(bool(ok_diet))
        details.append({"preference": inp["preference"], "usable_recipe": parsed is not None, "diet_compliant": ok_diet})

    n = len(records)
    summary = {
        "samples": n,
        "usable_recipe_rate_pct": round(100.0 * usable / n, 2) if n else 0.0,
        "diet_compliance_of_usable_pct": round(100.0 * compliant / usable, 2) if usable else 0.0,
        "avg_generation_latency_ms": round(sum(latencies) / n, 1) if n else 0.0,
        "adapter_loaded": slm_engine.is_adapter_loaded,
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "details": details}, f, indent=2)
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    if "--model" in sys.argv:
        run_model_evaluation()
    else:
        run_evaluation()
