# finetune/trainer/train_script.py – Training script using transformers + PEFT
import argparse
import json
import os
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from datasets import Dataset, load_dataset
from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
import bitsandbytes as bnb

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_model", required=True)
    parser.add_argument("--dataset_path", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--job_id", required=True)
    parser.add_argument("--num_epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=4)
    parser.add_argument("--learning_rate", type=float, default=2e-4)
    parser.add_argument("--max_seq_length", type=int, default=512)
    parser.add_argument("--lora_r", type=int, default=8)
    parser.add_argument("--lora_alpha", type=int, default=16)
    parser.add_argument("--lora_dropout", type=float, default=0.1)
    parser.add_argument("--use_4bit", action="store_true", default=True)
    parser.add_argument("--use_lora", action="store_true", default=True)
    return parser.parse_args()

def load_dataset_from_path(path: str):
    """Load dataset from JSONL or CSV"""
    if path.endswith(".jsonl"):
        data = []
        with open(path, "r") as f:
            for line in f:
                item = json.loads(line)
                data.append({"text": item.get("text", item.get("prompt", ""))})
        return Dataset.from_list(data)
    elif path.endswith(".csv"):
        import pandas as pd
        df = pd.read_csv(path)
        if "text" in df.columns:
            return Dataset.from_pandas(df[["text"]])
        else:
            raise ValueError("CSV must have 'text' column")
    else:
        # Assume Hugging Face dataset
        return load_dataset(path, split="train")

def format_instruction(example):
    """Format example for instruction fine‑tuning"""
    # For CrownStar conversations, we might have user/assistant pairs
    # Simplified: just use the text field
    return example

def main():
    args = parse_args()
    
    # Load model with 4‑bit quantization if requested
    if args.use_4bit and torch.cuda.is_available():
        from transformers import BitsAndBytesConfig
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16
        )
        model = AutoModelForCausalLM.from_pretrained(
            args.base_model,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            args.base_model,
            torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
            device_map="auto",
            trust_remote_code=True
        )
    
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    
    # Prepare model for k‑bit training
    if args.use_4bit:
        model = prepare_model_for_kbit_training(model)
    
    # LoRA configuration
    if args.use_lora:
        lora_config = LoraConfig(
            r=args.lora_r,
            lora_alpha=args.lora_alpha,
            lora_dropout=args.lora_dropout,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
        )
        model = get_peft_model(model, lora_config)
        model.print_trainable_parameters()
    
    # Load dataset
    dataset = load_dataset_from_path(args.dataset_path)
    
    # Tokenize
    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=args.max_seq_length,
            padding="max_length"
        )
    
    tokenized_dataset = dataset.map(tokenize_function, batched=True, remove_columns=dataset.column_names)
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.num_epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        warmup_steps=100,
        learning_rate=args.learning_rate,
        fp16=torch.cuda.is_available(),
        logging_steps=10,
        save_steps=500,
        save_total_limit=3,
        report_to="none"
    )
    
    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=data_collator,
    )
    
    # Train
    trainer.train()
    
    # Save adapter and tokenizer
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    
    # Save metadata
    metadata = {
        "base_model": args.base_model,
        "job_id": args.job_id,
        "hyperparams": vars(args),
        "completed_at": str(datetime.datetime.utcnow())
    }
    with open(os.path.join(args.output_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Training completed. Adapter saved to {args.output_dir}")

if __name__ == "__main__":
    import datetime
    main()
