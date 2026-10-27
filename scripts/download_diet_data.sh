#!/bin/bash
# Downloads the public datasets used by the Diet Planning feature and builds
# data/processed/diet_recipes.db + data/processed/usda_foods.json.
#   1. Food.com "Recipes and Reviews" (parsed CSV, ~680 MB) - quantities, servings, nutrition, photos
#   2. USDA FoodData Central SR Legacy (CSV zip, ~6 MB, public domain) - ingredient nutrition
# data/raw/RAW_recipes.csv (Food.com Recipes and Interactions) must already exist; it is the same
# file the SLM was trained on (see README "Reproducing the model").
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/raw/diet

PARSED="data/raw/diet/parsed_recipes.csv"
if [ ! -s "$PARSED" ]; then
  echo "Downloading Food.com recipes (parsed) from Hugging Face..."
  curl -fL --progress-bar -o "$PARSED" \
    "https://huggingface.co/datasets/Karo8870/food.com-parsed-dataset/resolve/main/parsed_recipes.csv?download=true"
fi

USDA_ZIP="data/raw/diet/FoodData_Central_sr_legacy_food_csv_2018-04.zip"
if [ ! -s "$USDA_ZIP" ]; then
  echo "Downloading USDA FoodData Central SR Legacy..."
  curl -fL --progress-bar -o "$USDA_ZIP" \
    "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip"
fi

if [ ! -s data/raw/RAW_recipes.csv ]; then
  echo "data/raw/RAW_recipes.csv is missing. Download it from"
  echo "https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions and run this again."
  exit 1
fi

PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
[ -x .venv-mac/bin/python ] && [ ! -x .venv/bin/python ] && PY=.venv-mac/bin/python
"$PY" scripts/build_diet_dataset.py
echo "Diet data ready."
