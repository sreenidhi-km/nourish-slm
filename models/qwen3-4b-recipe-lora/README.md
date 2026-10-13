# Nourish SLM LoRA adapter

LoRA adapter for [Qwen/Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B) fine-tuned to write structured JSON recipes that respect a dietary preference.

- Method: QLoRA (4-bit base), r = 16, alpha = 32, dropout 0.05, on q, k, v, o, gate, up and down projections
- Data: 6,000 balanced Food.com instruction examples, 1 epoch, 375 steps, learning rate 2e-4, max length 640
- Results on held-out recipes: test loss 2.895 to 1.106, perplexity 18.1 to 3.0, complete recipes 66.7% to 97.0%

`adapter_model.safetensors` is not stored in git; run `scripts/download_assets.sh` to fetch it.
