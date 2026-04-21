import argparse
import os
from typing import override

import pandas as pd




import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)

import re
import os
from dotenv import load_dotenv

from experiments.utils import add_agent_args, read_df, read_yaml_config
from experiments.patterns import (
    DfToDfGenerator,
)

load_dotenv()

class CypherGenerator(DfToDfGenerator):
    
    @override
    def __init__(
        self,
        in_df: pd.DataFrame,
        join_column: str,
        model_name: str,
        out_df: pd.DataFrame = None,
    ):
        super().__init__(
            in_df=in_df,
            join_column=join_column,
            out_df=out_df,
        )
        # bnb_config = BitsAndBytesConfig(
        #     # 4 bit quantization parameters
        #     load_in_4bit=True,
        #     bnb_4bit_use_double_quant=True,
        #     bnb_4bit_quant_type="nf4",
        #     bnb_4bit_compute_dtype=torch.bfloat16,

        #     # # 8 bit quantization parameters (uncomment if using 8 bit quantization)
        #     # load_in_8bit=True,
        #     # bnb_8bit_use_double_quant=True,
        #     # bnb_8bit_quant_type="nf8",
        #     # bnb_8bit_compute_dtype=torch.bfloat16,
        # )
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            # quantization_config=bnb_config,
            torch_dtype=torch.bfloat16,
            # attn_implementation="eager",
            # low_cpu_mem_usage=True,
            token=os.getenv("HF_TOKEN"),
        )
        self.user_instruction = (
            "Below is a database Neo4j schema and a question related to that database. "
            "Write a Cypher query to answer the question. "
            "Use only the provided relationship types and properties in the schema.\n\n"
            "### Schema:\n{schema}\n\n### Question:\n{question}\n\n### Cypher Query:\n\n"
        )
        self.model_generate_parameters = {
            "top_p": 0.9,
            "temperature": 0.2,
            "max_new_tokens": 512,
            "do_sample": True,
            "pad_token_id": self.tokenizer.eos_token_id,
        }

    def prepare_chat_prompt(self, question, schema) -> list[dict]:
        chat = [
            # {
            #     "role": "system",
            #     "content": self.system_instructions,
            # },
            {
                "role": "user",
                "content": self.user_instruction.format(
                    schema=schema, question=question
                ),
            }
        ]
        return chat

    def _postprocess_output_cypher(self, output_cypher: str) -> str:
        pattern = r"```(?:cypher)?\s*((?:.*|\s)+)\s*```"
        match = re.search(pattern, output_cypher)
        if match:
            return match.group(1).strip()
        else:
            return output_cypher.strip()

    @override
    def generate_output_record(self, input_record: dict) -> dict:
        record_id = str(input_record[self.join_column])

        question = input_record['question']
        schema = input_record['schema']
        new_message = self.prepare_chat_prompt(question=question, schema=schema)
        prompt = self.tokenizer.apply_chat_template(new_message, add_generation_prompt=True, tokenize=False)
        inputs = self.tokenizer(prompt, return_tensors="pt", padding=True)

        inputs.to(self.model.device)
        self.model.eval()
        with torch.no_grad():
            tokens = self.model.generate(**inputs, **self.model_generate_parameters)
            tokens = tokens[:, inputs.input_ids.shape[1] :]
            raw_outputs = self.tokenizer.batch_decode(tokens, skip_special_tokens=True)
            outputs = [self._postprocess_output_cypher(output) for output in raw_outputs]

        return_dict = {
            self.join_column: record_id,
            "json_trajectory": None,
            "generated_cypher": outputs[0],
        }

        return return_dict

def init_parser():
    parser = argparse.ArgumentParser(description="Generate synthetic data analysis.")
    add_agent_args(parser)

    parser.add_argument("--input-df", type=str, required=True,
        help="Path to the input .csv or .parquet data file.",
    )
    parser.add_argument("--input-df-yaml-config", type=str, default=None,
        help="Path to the YAML config file for reading the input dataframe.",
    )
    parser.add_argument("--output-df", type=str, required=True,
        help="Path to the output file where generated data will be saved.",
    )
    parser.add_argument("--output-df-yaml-config", type=str, default=None,
        help="Path to the YAML config file for saving the output dataframe.",
    )
    parser.add_argument("--join-column", type=str, default="df.index",
        help="Column name to join input and output dataframes during resumption.",
    )
    parser.add_argument("--model-name", type=str,
        help="Name of the Hugging Face model to use for generation (e.g., 'Azzedde/llama3.1-8b-text2cypher').",
    )
    parser.add_argument("--verbose", type=bool, default=True,
        help="Enable verbose logging.",
    )

    return parser

def main():
    parser = init_parser()
    args = parser.parse_args()

    if os.path.exists(args.output_df):
        output_df = read_df(args.output_df)
        # output_df = output_df.dropna()
    else:
        output_df = None

    input_df = read_df(args.input_df, **read_yaml_config(args.input_df_yaml_config))
    input_df = input_df[input_df['database_reference_alias'].notna()]#[:100]
    generator = CypherGenerator(
        in_df=input_df,
        join_column=args.join_column,
        model_name=args.model_name,
        out_df=output_df,
    )
    generator.generate(
        save_path=args.output_df,
        **read_yaml_config(args.output_df_yaml_config),
    )

if __name__ == "__main__":
    main()