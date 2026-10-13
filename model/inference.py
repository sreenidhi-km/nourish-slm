"""
inference.py
============
SLM Model Inference Pipeline.
Loads model weights, constructs system & instruction prompts, generates recipe text,
and validates against user dietary constraints.
"""

import sys
import os
import json
import time
import torch
from typing import Dict, Any, List
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from model.config.config import ModelConfig
from backend.app.services.recipe_validator import validate_recipe_against_preference
from backend.app.services.formatting import format_duration, format_servings


TRAIN_SYSTEM_PROMPT = (
    "You are a professional AI food recipe assistant. Generate safe, delicious recipes "
    "respecting user dietary preferences and available ingredients."
)
TRAIN_INSTRUCTION = "Create a detailed recipe using the provided ingredients while adhering strictly to the dietary preference."

# SLM generation can be disabled (e.g. CPU-only demo) with SLM_GENERATE=false
SLM_GENERATE = os.environ.get("SLM_GENERATE", "true").lower() == "true"
SLM_MAX_NEW_TOKENS = int(os.environ.get("SLM_MAX_NEW_TOKENS", "450"))


# Prompt format used in notebooks/qwen3_4b_finetuningFinal.ipynb (the Windows/RTX 4070 training run).
# Inference must use the same system prompt, user message and enable_thinking=False.
NOURISH_SYSTEM_PROMPT = (
    "You are Nourish, a recipe assistant. Create safe, practical recipes from the user's ingredients. "
    "Follow the dietary preference strictly: Vegan = no meat, fish, eggs or dairy; "
    "Vegetarian = no meat, fish or eggs (dairy allowed); Eggitarian = no meat or fish (eggs and dairy allowed); "
    "Non-Vegetarian = no restrictions. Pantry staples (oil, salt, pepper, water, spices) may be added if they fit "
    "the preference. Answer in this format:\n"
    "Recipe Name: ...\nDietary Preference: ...\nCuisine: ...\nTotal Time: ...\n"
    "Ingredients:\n- ...\n\nInstructions:\n1. ..."
)

_PREF_LABELS = {
    "vegan": "Vegan", "vegetarian": "Vegetarian", "eggitarian": "Eggitarian",
    "non_vegetarian": "Non-Vegetarian", "no_preference": "Non-Vegetarian",
}


def build_training_style_messages(ingredients: List[str], preference: str, cuisine: str) -> List[Dict[str, str]]:
    """Builds chat messages in the same format the adapter was fine-tuned on."""
    cuisine_text = cuisine if cuisine and cuisine not in ("General", "All", "") else "General"
    pref_text = _PREF_LABELS.get((preference or "").lower(), preference or "Non-Vegetarian")
    user_msg = (
        f"Ingredients I have: {', '.join(ingredients[:8])}\n"
        f"Dietary preference: {pref_text}\n"
        f"Cuisine: {cuisine_text}\n"
        f"Create a complete recipe that uses these ingredients and strictly follows the dietary preference."
    )
    return [
        {"role": "system", "content": NOURISH_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]


def _parse_text_recipe(text: str):
    """Parses the 'Recipe Name / Ingredients / Instructions' text format produced by the fine-tuned adapter."""
    import re as _re
    text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL).strip()
    m = _re.search(r"Recipe Name:\s*(.+)", text)
    if not m:
        return None
    title = m.group(1).strip()
    total = _re.search(r"Total Time:\s*(.+)", text)
    ing_block = _re.search(r"Ingredients:\s*\n(.*?)(?:\n\s*Instructions:|$)", text, flags=_re.DOTALL)
    ins_block = _re.search(r"Instructions:\s*\n(.*)", text, flags=_re.DOTALL)
    ings = []
    if ing_block:
        for line in ing_block.group(1).splitlines():
            line = line.strip()
            if line.startswith(("-", "*", "•")):
                line = line.lstrip("-*• ").strip()
                if line:
                    ings.append(line)
    steps = []
    if ins_block:
        for line in ins_block.group(1).splitlines():
            mm = _re.match(r"\s*\d+[.)]\s*(.+)", line)
            if mm:
                steps.append(mm.group(1).strip())
    if not title or len(ings) < 2 or len(steps) < 2:
        return None
    data = {"title": title, "ingredients": ings, "instructions": steps}
    if total:
        data["cook_time"] = total.group(1).strip()
        data["prep_time"] = "10 mins"
    return data


def parse_model_recipe(text: str):
    """Extracts a recipe dict from model output. Returns None unless it is a usable recipe."""
    if not text:
        return None
    if "Recipe Name:" in text:
        return _parse_text_recipe(text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    ings = data.get("ingredients")
    steps = data.get("instructions")
    title = data.get("title")
    if not (isinstance(title, str) and title.strip()):
        return None
    if not (isinstance(ings, list) and len(ings) >= 2 and all(isinstance(i, str) for i in ings)):
        return None
    if not (isinstance(steps, list) and len(steps) >= 2 and all(isinstance(i, str) for i in steps)):
        return None
    return data


class SLMInferenceEngine:
    def __init__(self, base_model_name: str = ModelConfig.BASE_MODEL_NAME, adapter_dir: str = ModelConfig.FINAL_ADAPTER_DIR):
        self.base_model_name = base_model_name
        self.adapter_dir = adapter_dir
        self.tokenizer = None
        self.model = None
        self.is_loaded = False
        self.is_adapter_loaded = False
        self.model_mode = "base"
        self.model_label = "Qwen3-4B · Base"

    def load_model(self):
        """Loads tokenizer and base model + LoRA adapter if present."""
        if self.is_loaded:
            return

        print(f"Loading SLM Tokenizer ({self.base_model_name})...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.base_model_name, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
        print(f"Loading SLM Base Model on device: {device.upper()}...")
        
        try:
            self.model = AutoModelForCausalLM.from_pretrained(
                self.base_model_name,
                torch_dtype=(torch.bfloat16 if device == "mps" else torch.float16) if device in ["cuda", "mps"] else torch.float32,
                trust_remote_code=True,
                device_map="auto" if device == "cuda" else None
            )

            # Check if LoRA adapter files exist
            adapter_config = os.path.join(self.adapter_dir, "adapter_config.json")
            adapter_weights = os.path.join(self.adapter_dir, "adapter_model.safetensors")
            
            if os.path.exists(adapter_config) and os.path.exists(adapter_weights):
                print(f"Loading LoRA adapter weights from {self.adapter_dir}...")
                self.model = PeftModel.from_pretrained(self.model, self.adapter_dir)
                self.is_adapter_loaded = True
                self.model_mode = "finetuned"
                self.model_label = "Qwen3-4B · LoRA"
            else:
                self.is_adapter_loaded = False
                self.model_mode = "base"
                self.model_label = "Qwen3-4B · Base"

            self.model = self.model.to(device)

            print(f"\n==================================================")
            print(f"MODEL: {self.base_model_name}")
            print(f"ADAPTER: {self.adapter_dir}")
            print(f"ADAPTER LOADED: {self.is_adapter_loaded}")
            print(f"MODEL MODE: {self.model_mode.upper()}")
            print(f"MODEL LABEL: {self.model_label}")
            print(f"MODEL DEVICE: {device.upper()}")
            print(f"==================================================\n")

            self.model.eval()
            self.is_loaded = True
            print("SLM Inference Engine loaded successfully.")
        except Exception as e:
            print(f"Warning: Could not load full HF transformer model ({e}). Using fallback execution mode.")
            self.is_loaded = True
            self.model = None

    def generate_raw_tokens(self, prompt: str, max_new_tokens: int = 150) -> Dict[str, Any]:
        """Runs actual model.generate() with MPS synchronization for exact timing & output."""
        if not self.is_loaded or self.model is None:
            self.load_model()
            
        device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
        inputs = self.tokenizer(prompt, return_tensors="pt").to(device)
        input_token_count = inputs.input_ids.shape[1]
        
        if device == "mps" and hasattr(torch.mps, "synchronize"):
            torch.mps.synchronize()
        elif device == "cuda":
            torch.cuda.synchronize()
            
        t0 = time.perf_counter()
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.3,
                do_sample=True,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id
            )
            
        if device == "mps" and hasattr(torch.mps, "synchronize"):
            torch.mps.synchronize()
        elif device == "cuda":
            torch.cuda.synchronize()
        t1 = time.perf_counter()
        
        gen_time_ms = (t1 - t0) * 1000.0
        generated_ids = outputs[0][input_token_count:]
        output_token_count = len(generated_ids)
        response_text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        tokens_per_sec = (output_token_count / (gen_time_ms / 1000.0)) if gen_time_ms > 0 else 0.0
        
        return {
            "response_text": response_text,
            "input_tokens": input_token_count,
            "output_tokens": output_token_count,
            "generation_time_ms": gen_time_ms,
            "tokens_per_sec": tokens_per_sec
        }

    def generate_recipe(
        self,
        ingredients: List[str],
        preference: str = "vegan",
        cuisine: str = "General",
        retrieved_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generates a recipe adhering to user ingredients, preference, and cuisine.
        Executes actual neural model.generate() when loaded.
        """
        pref_clean = preference.lower().strip() if preference else "no_preference"
        cuisine_clean = cuisine.capitalize() if cuisine and cuisine not in ["All", ""] else "General"
        
        gen_time_ms = 0.0
        output_tokens = 0
        
        slm_recipe = None
        source = "template"

        if SLM_GENERATE:
            if not self.is_loaded:
                self.load_model()
            if self.is_loaded and self.model is not None:
                prompt_messages = build_training_style_messages(ingredients, pref_clean, cuisine_clean)
                try:
                    prompt_str = self.tokenizer.apply_chat_template(prompt_messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
                except TypeError:
                    prompt_str = self.tokenizer.apply_chat_template(prompt_messages, tokenize=False, add_generation_prompt=True)
                print(f"SLM generating (max {SLM_MAX_NEW_TOKENS} tokens)...")
                gen_res = self.generate_raw_tokens(prompt_str, max_new_tokens=SLM_MAX_NEW_TOKENS)
                gen_time_ms = gen_res["generation_time_ms"]
                output_tokens = gen_res["output_tokens"]
                print(f"SLM generated {output_tokens} tokens in {gen_time_ms/1000:.1f}s ({gen_res['tokens_per_sec']:.1f} tok/s)")
                slm_recipe = parse_model_recipe(gen_res["response_text"])
                print("SLM output parsed as recipe:", slm_recipe is not None)

        if slm_recipe is not None:
            # 1) Use the model's own recipe (validated + substituted below)
            source = "slm"
            title = slm_recipe["title"].strip()
            recipe_ingredients = list(slm_recipe["ingredients"])
            instructions = list(slm_recipe["instructions"])
            prep_time = format_duration(str(slm_recipe.get("prep_time", "15 mins")))
            cook_time = format_duration(str(slm_recipe.get("cook_time", "20 mins")))
            servings = format_servings(slm_recipe.get("servings", "4"))
        elif retrieved_context and "name" in retrieved_context and retrieved_context.get("match_score", 0) > 0:
            # 2) Fall back to a retrieved dataset recipe
            source = "retrieval"
            title = retrieved_context["name"]
            recipe_ingredients = list(retrieved_context.get("ingredients", ingredients))
            instructions = list(retrieved_context.get("instructions", []))
            prep_time = format_duration(str(retrieved_context.get("prep_time", "15 mins")))
            cook_time = format_duration(str(retrieved_context.get("cook_time", "20 mins")))
            servings = format_servings(retrieved_context.get("servings", "4"))
            if retrieved_context.get("cuisine") and retrieved_context["cuisine"] != "General":
                cuisine_clean = retrieved_context["cuisine"]
        else:
            # 3) Last resort: generic template built from the user's ingredients
            # Dynamic SLM Recipe Construction matching user input
            ing_names = [i.capitalize() for i in ingredients[:3]] if ingredients else ["Seasonal Vegetable"]
            ing_phrase = " & ".join(ing_names)
            
            pref_prefix = f"{pref_clean.replace('_', ' ').capitalize()}" if pref_clean != "no_preference" else ""
            cuisine_prefix = f"{cuisine_clean}" if cuisine_clean != "General" else ""
            
            title = f"{cuisine_prefix} {pref_prefix} {ing_phrase}".strip()
            title = " ".join(title.split()) # clean multi-spaces

            recipe_ingredients = ingredients.copy() if ingredients else ["mixed vegetables"]
            
            # Add staple seasonings
            staples = ["olive oil", "garlic", "salt", "black pepper"]
            for s in staples:
                if s not in recipe_ingredients:
                    recipe_ingredients.append(s)

            instructions = [
                f"Wash and chop all ingredients ({', '.join(ingredients)}).",
                "Heat cooking oil in a pan over medium heat.",
                "Sauté garlic, onions, and aromatics until golden brown.",
                "Add main ingredients and seasonings. Mix well to combine flavors.",
                "Cover and simmer on medium-low heat until tender and fully cooked.",
                "Garnish with fresh herbs and serve hot."
            ]
            prep_time = "15 mins"
            cook_time = "20 mins"
            servings = "4"

        # Check backend dietary validation
        val_res = validate_recipe_against_preference(recipe_ingredients, pref_clean)

        # If conflict detected, perform plant-based alternative substitution
        if not val_res["passed"]:
            import re as _re
            replaced = {}
            clean_ingredients = []
            for ing in recipe_ingredients:
                alt = None
                for conf in val_res["conflicts"]:
                    if conf["ingredient"] == ing and conf.get("suggested_alternative"):
                        alt = conf["suggested_alternative"]
                        break
                if alt:
                    replaced[ing] = alt
                    clean_ingredients.append(alt)
                else:
                    clean_ingredients.append(ing)
            recipe_ingredients = clean_ingredients
            # Keep the steps consistent with the substituted ingredient names
            for orig, alt in replaced.items():
                pat = _re.compile(r"\b" + _re.escape(orig) + r"\b", _re.IGNORECASE)
                instructions = [pat.sub(alt, step) for step in instructions]
            val_res = validate_recipe_against_preference(recipe_ingredients, pref_clean)

        return {
            "title": title,
            "diet_type": pref_clean,
            "cuisine": cuisine_clean,
            "ingredients": recipe_ingredients,
            "instructions": instructions,
            "prep_time": prep_time,
            "cook_time": cook_time,
            "servings": servings,
            "validation": val_res,
            "source": source,
            "generation_time_ms": gen_time_ms,
            "output_tokens": output_tokens
        }

slm_engine = SLMInferenceEngine()

if SLM_GENERATE and os.environ.get("SLM_PRELOAD", "false").lower() == "true":
    import threading as _threading
    _threading.Thread(target=slm_engine.load_model, daemon=True).start()

