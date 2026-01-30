import argparse
import json
import os

import pandas as pd
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
    DataCollatorForSeq2Seq,
)
from transformers.trainer_callback import TrainerCallback

import yaml

from text2cypher.experiments.config import HF_ENC_DEC_MODELS

# class MetricsCallback(TrainerCallback):
#     """Callback to log custom metrics during training."""
    
#     def on_log(self, args, state, control, logs=None, **kwargs):
#         if logs:
#             pass

def compute_metrics(eval_pred):
    return {}

def init_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train encoder-decoder model for Text-to-Cypher conversion"
    )
    parser.add_argument("--train-data", type=str, required=True,
        help="Path to training data CSV file",
    )
    parser.add_argument("--eval-data", type=str, default=None,
        help="Path to evaluation data CSV file (optional)",
    )
    parser.add_argument("--model-name", type=str, choices=HF_ENC_DEC_MODELS, required=True,
        help="HuggingFace model identifier."
    )  
    parser.add_argument("--hyperparameters", type=str, required=True,
        help="Path to YAML file with training hyperparameters",
    )
    parser.add_argument("--output-dir", type=str, required=True,
        help="Directory to save model checkpoints",
    )
    
    return parser

def prepare_dataset(tokenizer: AutoTokenizer, path: str) -> Dataset:
    df = pd.read_csv(path)
    # limit to first 100 samples for testing
    df = df.head(100)
    train_dataset: Dataset = Dataset.from_pandas(df)

    def preprocess(examples):
        model_inputs = tokenizer(
            examples["sample"],
            max_length=512,
            truncation=True,
            text_target=examples["gold_cypher"],
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

    # load hyperparameters from YAML file
    with open(args.hyperparameters, "r") as f:
        hyperparams = yaml.safe_load(f)
    
    print(f"Loading model and tokenizer: {args.model_name}")
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model_name)
    
    train_dataset = prepare_dataset(
        tokenizer=tokenizer,
        path=args.train_data,
    )
    print(f"Training samples: {len(train_dataset)}")
    
    eval_dataset = None
    if args.eval_data:
        eval_dataset = prepare_dataset(
            tokenizer=tokenizer,
            path=args.eval_data,
        )
        print(f"Evaluation samples: {len(eval_dataset)}")   
    
    training_args = Seq2SeqTrainingArguments(
        output_dir=args.output_dir,
        **hyperparams,
    )
    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        model=model,
        padding=True,
    )
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        # tokenizer=tokenizer,
        data_collator=data_collator,
        # compute_metrics=compute_metrics,
        # callbacks=[
        #     MetricsCallback(),
        #     EarlyStoppingCallback(
        #         early_stopping_patience=EARLY_STOPPING_PATIENCE,
        #         early_stopping_threshold=EARLY_STOPPING_THRESHOLD
        #     )
        # ]
    )

    print("Starting training...")
    trainer.train()

    # print(f"\nSaving final model to: {args.output_dir}/final")
    # os.makedirs(f"{args.output_dir}/final", exist_ok=True)
    # trainer.save_model(f"{args.output_dir}/final")
    tokenizer.save_pretrained(f"{args.output_dir}/tokenizer")
    
    # Save training stats
    with open(f"{args.output_dir}/training_stats.json", "w") as f:
        json.dump(trainer.state.log_history, f, indent=2)
    
    print("\nTraining completed successfully!")


if __name__ == "__main__":
    main()
