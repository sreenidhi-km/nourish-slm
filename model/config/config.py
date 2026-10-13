"""
config.py
=========
Configuration options for Small Language Model (SLM) fine-tuning, evaluation, and inference.
"""

import os

PROJECT_ROOT = os.environ.get("PROJECT_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

class ModelConfig:
    # Model Selection (Default: Qwen/Qwen3-4B for high quality recipe fine-tuning & inference)
    BASE_MODEL_NAME = os.environ.get("BASE_MODEL_NAME", "Qwen/Qwen3-4B")
    OUTPUT_DIR = os.environ.get("MODEL_OUTPUT_DIR", os.path.join(PROJECT_ROOT, "models"))
    FINAL_ADAPTER_DIR = os.environ.get("FINAL_ADAPTER_DIR", os.path.join(PROJECT_ROOT, "models", "qwen3-4b-recipe-lora"))
    
    # Dataset paths
    CLEANED_DATA_PATH = os.environ.get("CLEANED_DATA_PATH", os.path.join(PROJECT_ROOT, "data/processed/foodcom_cleaned.csv"))
    RAW_DATA_PATH = os.environ.get("RAW_DATA_PATH", os.path.join(PROJECT_ROOT, "data/raw/RAW_recipes.csv"))
    EVAL_DATA_PATH = os.environ.get("EVAL_DATA_PATH", os.path.join(PROJECT_ROOT, "data/diet_eval.jsonl"))

    # LoRA PEFT Parameters
    LORA_R = 16
    LORA_ALPHA = 32
    LORA_DROPOUT = 0.05
    TARGET_MODULES = ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]

    # Training Parameters
    NUM_EPOCHS = int(os.environ.get("NUM_EPOCHS", "1"))
    BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "2"))
    GRADIENT_ACCUMULATION_STEPS = int(os.environ.get("GRAD_ACC", "4"))
    LEARNING_RATE = float(os.environ.get("LEARNING_RATE", "2e-4"))
    MAX_SEQ_LENGTH = 512
    WARMUP_RATIO = 0.05
    LOGGING_STEPS = 10
    SAVE_STEPS = 50
