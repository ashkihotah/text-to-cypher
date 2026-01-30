import argparse
import json
from pathlib import Path
import pandas as pd

from text2cypher.experiments.config import (
    CYPHERBENCH_SCHEMAS_PATH, 
    SAMPLE_FORMAT_FUNCTIONS, 
    SCHEMA_FORMAT_FUNCTIONS
)

def init_parser():
    parser = argparse.ArgumentParser(
        description="Preprocess CypherBench dataset for text-to-Cypher models."
    )
    parser.add_argument("--input-path", type=str, required=True,
        help="Path to the input CypherBench dataset file (JSON format).",
    )
    parser.add_argument("--schema-format-fn", type=str,
        choices=list(SCHEMA_FORMAT_FUNCTIONS.keys()), default="special_tokens",
        help="Format to use for the graph schemas.",
    )
    parser.add_argument("--sample-format-fn", type=str,
        choices=list(SAMPLE_FORMAT_FUNCTIONS.keys()), default="special_tokens",
        help="Format to use for the samples.",
    )
    parser.add_argument("--output-path", type=str, required=True,
        help="Path to save the preprocessed dataset (Parquet format).",
    )
    return parser

def init_schema(graph: str, format_fn: callable) -> str:
    path = CYPHERBENCH_SCHEMAS_PATH / f"{graph}_schema.json"
    with open(path, 'r', encoding='utf-8') as f:
        schema = json.load(f)

    return format_fn(schema)

if __name__ == "__main__":
    parser = init_parser()
    args = parser.parse_args()

    # Load dataset from json file
    df = pd.read_json(args.input_path)

    df['schema'] = df['graph'].apply(
        lambda x: init_schema(x, SCHEMA_FORMAT_FUNCTIONS[args.schema_format_fn])
    )
    sample_format_fn = SAMPLE_FORMAT_FUNCTIONS[args.sample_format_fn]
    df['sample'] = df.apply(
        lambda x:
            f"{sample_format_fn(x['nl_question'])}\n"
            + f"{x['schema']}", axis=1
    )
    path = Path(args.output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)