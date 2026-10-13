#!/bin/bash
# Downloads what is too large for git: the fine-tuned LoRA adapter weights,
# the cleaned recipe dataset used for retrieval, and the Qwen3-4B base model.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="sreenidhi-km/nourish-slm"
TAG="v1.0.0"
BASE="https://github.com/$REPO/releases/download/$TAG"

ADAPTER="models/qwen3-4b-recipe-lora/adapter_model.safetensors"
if [ ! -s "$ADAPTER" ]; then
  echo "Downloading LoRA adapter (~130 MB)..."
  curl -fL --progress-bar -o "$ADAPTER" "$BASE/adapter_model.safetensors"
fi

DATA="data/processed/foodcom_cleaned.csv"
if [ ! -s "$DATA" ]; then
  echo "Downloading cleaned recipe dataset..."
  mkdir -p data/processed
  curl -fL --progress-bar -o /tmp/foodcom_cleaned.csv.zip "$BASE/foodcom_cleaned.csv.zip"
  unzip -o -q /tmp/foodcom_cleaned.csv.zip -d data/processed && rm -f /tmp/foodcom_cleaned.csv.zip
fi

echo "Downloading Qwen/Qwen3-4B base model (~8 GB, cached in ~/.cache/huggingface)..."
python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-4B')"
echo "All assets ready."
