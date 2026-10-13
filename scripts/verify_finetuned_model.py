import os
import sys
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

BASE_MODEL_NAME = "Qwen/Qwen3-4B"
ADAPTER_PATH = os.path.abspath("models/qwen3-4b-recipe-lora")

def verify_finetuned_model():
    print("==================================================")
    print("VERIFY FINE-TUNED MODEL & ADAPTER LOADING")
    print("==================================================")
    
    print(f"BASE MODEL:\n{BASE_MODEL_NAME}\n")
    print(f"ADAPTER:\n{ADAPTER_PATH}\n")
    
    # 1. Check if adapter files exist
    config_file = os.path.join(ADAPTER_PATH, "adapter_config.json")
    model_file = os.path.join(ADAPTER_PATH, "adapter_model.safetensors")
    if not (os.path.exists(config_file) and os.path.exists(model_file)):
        print("ADAPTER STATUS:\nFAILED (Adapter files missing)")
        print("MODEL STATUS:\nBASE")
        sys.exit(1)
        
    try:
        # Determine compute device
        if torch.cuda.is_available():
            device = "cuda"
        elif torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
            
        print(f"Loading Base Model on {device}...")
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME)
        base_model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL_NAME,
            torch_dtype=torch.float16 if device != "cpu" else torch.float32,
            device_map=device
        )
        
        print("Loading LoRA Adapter via PEFT...")
        model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
        model.eval()
        
        # Calculate parameters
        trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        total_params = sum(p.numel() for p in model.parameters())
        
        print("\nPEFT Model Active: True")
        print(f"Total parameters: {total_params:,}")
        print(f"Trainable parameters: {trainable_params:,}")
        
        # Test generation
        print("\nGenerating Test Response...")
        messages = [
            {"role": "system", "content": "You are a professional chef and dietary assistant."},
            {"role": "user", "content": "Suggest a simple vegan pasta recipe using tomatoes and garlic."}
        ]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=150,
                temperature=0.3,
                do_sample=True
            )
            
        response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        print("--------------------------------------------------")
        print("Sample Generated Response:\n", response.strip())
        print("--------------------------------------------------")
        
        print("\nADAPTER STATUS:\nLOADED")
        print("\nMODEL STATUS:\nFINE-TUNED")
        return True
    except Exception as e:
        print(f"\nADAPTER STATUS:\nFAILED ({e})")
        print("MODEL STATUS:\nBASE")
        sys.exit(1)

if __name__ == "__main__":
    verify_finetuned_model()
