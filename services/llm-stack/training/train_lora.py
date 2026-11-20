"""
Real QLoRA / LoRA Supervised Fine-Tuning (SFT) script for B2B domain adaptation.
Trains a LoRA adapter on Qwen2.5-7B-Instruct or Llama-3.1-8B-Instruct using Hugging Face PEFT + TRL.

Requirements (on AWS GPU instance):
    pip install torch transformers datasets peft trl bitsandbytes accelerate

Usage:
    python training/train_lora.py \
        --base-model Qwen/Qwen2.5-7B-Instruct \
        --dataset training/sample_dataset.jsonl \
        --output-dir models/lora/b2b-analyst-v1 \
        --epochs 3
"""
from __future__ import annotations

import argparse
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Fine-tune an open-weight LLM with QLoRA for B2B document Q&A")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-7B-Instruct", help="Hugging Face base model ID")
    parser.add_argument("--dataset", default="training/sample_dataset.jsonl", help="Path to JSONL training dataset")
    parser.add_argument("--output-dir", default="models/lora/b2b-analyst-v1", help="Directory to save LoRA adapter")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=2, help="Per-device train batch size")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate")
    parser.add_argument("--lora-r", type=int, default=16, help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=32, help="LoRA alpha")
    parser.add_argument("--max-seq-len", type=int, default=2048, help="Maximum sequence length")
    parser.add_argument("--use-4bit", action="store_true", default=True, help="Enable 4-bit QLoRA quantization")
    return parser.parse_args()


def main():
    args = parse_args()
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Training dataset not found: {dataset_path}")

    import torch
    from datasets import load_dataset
    from peft import LoraConfig, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
    from trl import SFTTrainer

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required for QLoRA fine-tuning. Run this on an AWS GPU instance (e.g. g5.xlarge).")

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quant_config = None
    if args.use_4bit:
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=quant_config,
        device_map="auto",
        trust_remote_code=True,
    )
    if args.use_4bit:
        model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )

    dataset = load_dataset("json", data_files=str(dataset_path), split="train")

    def format_example(example):
        messages = example["messages"]
        return {"text": tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)}

    dataset = dataset.map(format_example)

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=4,
        learning_rate=args.lr,
        bf16=True,
        logging_steps=5,
        save_strategy="epoch",
        optim="paged_adamw_8bit",
        warmup_ratio=0.05,
        lr_scheduler_type="cosine",
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        peft_config=lora_config,
        max_seq_length=args.max_seq_len,
        args=training_args,
    )

    trainer.train()
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"LoRA adapter saved to {args.output_dir}")


if __name__ == "__main__":
    main()
