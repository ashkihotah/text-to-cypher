"""
Training script for Text-to-Cypher converter agent using encoder-decoder architecture.

This script implements the training approach described in the encoder-decoder solution
documentation, using special tokens for structure marking and T5/CodeT5 models.
"""

import argparse
import json
from pathlib import Path
from typing import Optional

import pandas as pd
import torch
# from torch.utils.data import Dataset, DataLoader
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
    DataCollatorForSeq2Seq,
)
from transformers.trainer_callback import TrainerCallback


# Special tokens for structure marking (as per documentation)
SPECIAL_TOKENS = [
    "<cmd:>",      # Marks user command/question
    "<schema:>",   # Marks schema section
    "<node:>",     # Marks node labels
    "<rel:>",      # Marks relationships
    "<prop:>",     # Marks properties
    "<from:>",     # Marks source node in relationship
    "<to:>",       # Marks target node in relationship
    "<label:>",    # Marks relationship label
    "<type:>",     # Marks data type (used in preprocessing)
]

class MetricsCallback(TrainerCallback):
    """Callback to log custom metrics during training."""
    
    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs:
            # You can add custom metrics here
            pass

# reviewed
def setup_model_and_tokenizer(
    model_name: str,
    special_tokens: list[str],
) -> tuple[AutoModelForSeq2SeqLM, AutoTokenizer]:
    """
    Initialize model and tokenizer with special tokens.
    
    According to the documentation (qa.md), we should NOT add Cypher syntax
    tokens (MATCH, WHERE, etc.) as they are already handled well by BPE.
    Instead, we only add structural tokens that help separate logical blocks.
    
    Args:
        model_name: HuggingFace model identifier (e.g., 't5-base', 'Salesforce/codet5-base')
        special_tokens: List of special structure tokens to add
        
    Returns:
        Tuple of (model, tokenizer)
    """
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    
    # Add special tokens for structure marking (not syntax tokens)
    # These tokens already exist in our preprocessed data
    num_added = tokenizer.add_special_tokens({
        'additional_special_tokens': special_tokens
    })
    
    print(f"Added {num_added} special tokens to tokenizer")
    
    # Load model
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    
    # Resize token embeddings to accommodate new special tokens
    if num_added > 0:
        model.resize_token_embeddings(len(tokenizer))
        print(f"Resized model embeddings to {len(tokenizer)} tokens")
    
    return model, tokenizer

# empty
def compute_metrics(eval_pred):
    """
    Compute evaluation metrics.
    
    For now, we rely on the default cross-entropy loss.
    In production, you might want to add:
    - Exact match accuracy
    - Execution success rate (if you have a Neo4j instance)
    - BLEU score (though less meaningful for structured queries)
    """
    predictions, labels = eval_pred
    # Decode predictions and labels if needed
    # For now, return empty dict and rely on loss
    return {}

def init_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train encoder-decoder model for Text-to-Cypher conversion"
    )
    
    # Data arguments
    parser.add_argument("--train-data", type=str, required=True,
        help="Path to training data CSV file",
    )
    parser.add_argument("--eval-data", type=str, default=None,
        help="Path to evaluation data CSV file (optional)",
    )
    
    # Model arguments
    parser.add_argument("--model-name", type=str, default="Salesforce/codet5-base",
        help="HuggingFace model identifier. Recommended: 'Salesforce/codet5-base', "
             "'Salesforce/codet5-large', 't5-base', 't5-large', or 't5-3b'",
    )
    parser.add_argument(
        "--max-source-length",
        type=int,
        default=512,
        help="Maximum length for input sequences (question + schema)",
    )
    parser.add_argument(
        "--max-target-length",
        type=int,
        default=256,
        help="Maximum length for output Cypher queries",
    )
    
    # Training arguments
    parser.add_argument("--output-dir", type=str, default="./models/text2cypher",
        help="Directory to save model checkpoints",
    )
    parser.add_argument(
        "--num-epochs",
        type=int,
        default=10,
        help="Number of training epochs",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Training batch size per device",
    )
    parser.add_argument(
        "--eval-batch-size",
        type=int,
        default=16,
        help="Evaluation batch size per device",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=3e-4,
        help="Learning rate for decoder. Encoder will use learning_rate/10 "
             "(as recommended in documentation for transfer learning)",
    )
    parser.add_argument(
        "--warmup-steps",
        type=int,
        default=500,
        help="Number of warmup steps for learning rate scheduler",
    )
    parser.add_argument(
        "--weight-decay",
        type=float,
        default=0.01,
        help="Weight decay for optimizer",
    )
    parser.add_argument(
        "--gradient-accumulation-steps",
        type=int,
        default=4,
        help="Number of gradient accumulation steps",
    )
    parser.add_argument(
        "--fp16",
        action="store_true",
        help="Use mixed precision training (FP16)",
    )
    parser.add_argument(
        "--bf16",
        action="store_true",
        help="Use bfloat16 precision (recommended for A100 GPUs)",
    )
    parser.add_argument(
        "--logging-steps",
        type=int,
        default=50,
        help="Log metrics every N steps",
    )
    parser.add_argument(
        "--eval-steps",
        type=int,
        default=500,
        help="Run evaluation every N steps",
    )
    parser.add_argument(
        "--save-steps",
        type=int,
        default=500,
        help="Save checkpoint every N steps",
    )
    parser.add_argument(
        "--save-total-limit",
        type=int,
        default=3,
        help="Maximum number of checkpoints to keep",
    )
    return parser

def prepare_dataset(tokenizer: AutoTokenizer, df: pd.DataFrame) -> Dataset:
    train_dataset: Dataset = Dataset.from_pandas(df)

    def preprocess(examples):
        model_inputs = tokenizer(
            examples["sample"],
            # max_length=args.max_source_length,
            # truncation=True,
            text_target=examples["cypher_query"],
        )
        return model_inputs

    tokenized_dataset = train_dataset.map(
        preprocess,
        batched=True,
        # batch_size=1000,
        # remove_columns=dataset.column_names
    )
    return tokenized_dataset

def main():
    parser = init_parser()
    args = parser.parse_args()
    
    # Setup model and tokenizer
    print(f"Loading model: {args.model_name}")
    model, tokenizer = setup_model_and_tokenizer(
        model_name=args.model_name,
        special_tokens=SPECIAL_TOKENS,
    )
    
    # Create datasets
    print(f"Loading training data from: {args.train_data}")
    df = pd.read_csv(args.train_data)
    train_dataset = prepare_dataset(tokenizer, df)
    print(f"Training samples: {len(train_dataset)}")
    
    eval_dataset = None
    if args.eval_data:
        print(f"Loading evaluation data from: {args.eval_data}")
        eval_dataset = CypherDataset(
            data_path=args.eval_data,
            tokenizer=tokenizer,
            max_source_length=args.max_source_length,
            max_target_length=args.max_target_length,
        )
        print(f"Evaluation samples: {len(eval_dataset)}")
    
    # Setup training arguments
    # As per documentation: use smaller LR for encoder to preserve language understanding
    # and larger LR for decoder to learn new syntax
    training_args = Seq2SeqTrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.num_epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.eval_batch_size,
        learning_rate=args.learning_rate,
        warmup_steps=args.warmup_steps,
        weight_decay=args.weight_decay,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        fp16=args.fp16,
        bf16=args.bf16,
        logging_steps=args.logging_steps,
        eval_steps=args.eval_steps if eval_dataset else None,
        evaluation_strategy="steps" if eval_dataset else "no",
        save_steps=args.save_steps,
        save_total_limit=args.save_total_limit,
        predict_with_generate=True,  # Use generation for evaluation
        generation_max_length=args.max_target_length,
        load_best_model_at_end=True if eval_dataset else False,
        metric_for_best_model="loss" if eval_dataset else None,
        greater_is_better=False,
        report_to=["tensorboard"],  # Can add "wandb" if configured
        push_to_hub=False,
        dataloader_num_workers=2,
        remove_unused_columns=False,  # Keep all columns in dataset
    )
    
    # Data collator for dynamic padding
    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        model=model,
        padding=True,
    )
    
    # Initialize trainer
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
        callbacks=[MetricsCallback()],
    )
    
    # Train model
    print("Starting training...")
    trainer.train()
    
    # Save final model
    print(f"\nSaving final model to: {args.output_dir}/final")
    trainer.save_model(f"{args.output_dir}/final")
    tokenizer.save_pretrained(f"{args.output_dir}/final")
    
    # Save training stats
    with open(f"{args.output_dir}/training_stats.json", "w") as f:
        json.dump(trainer.state.log_history, f, indent=2)
    
    print("\nTraining completed successfully!")
    print(f"Model saved to: {args.output_dir}/final")


if __name__ == "__main__":
    main()
