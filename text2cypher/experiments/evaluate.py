import argparse
import os
from typing import override

from langchain_neo4j import Neo4jGraph
import pandas as pd
import dotenv

from text2cypher.experiments.datasets.patterns import (
    DfToDfGenerator,
)
from text2cypher.evaluation.psj_similarity import provenance_subgraph_jaccard_similarity
from text2cypher.evaluation.runtime import check_validity, jaccard
from text2cypher.experiments.utils import read_df, read_yaml_config

class Evaluator(DfToDfGenerator):

    def init_neo4j(self, neo4j_url: str, database: str):
        self.db = database
        if database == "eoflix":
            database = "neoflix"
        self.neo4j = Neo4jGraph(
            url=neo4j_url,
            username=database,
            password=database,
            database=database,
            # sanitize=True,
        )

    @override
    def __init__(
        self,
        in_df: pd.DataFrame,
        join_column: str,
        out_df: pd.DataFrame = None,
    ):
        super().__init__(
            in_df=in_df,
            join_column=join_column,
            out_df=out_df,
        )
        self.neo4j = Neo4jGraph(
            url=dotenv.get_key(".env", "NEO4J_URL"),
            username="movies",
            password="movies",
            database="movies",
        )
        self.init_neo4j(
            neo4j_url=dotenv.get_key(".env", "NEO4J_URL"),
            database="movies",
        )
    
    @override
    def generate_output_record(self, input_record: dict) -> dict:
        generated_cypher = input_record.get("generated_cypher", None)
        if generated_cypher is not None:
            database = input_record['database_reference_alias'].split("_")[-1]
            if self.db != database:
                self.init_neo4j(
                    neo4j_url=dotenv.get_key(".env", "NEO4J_URL"),
                    database=database,
                )
            
            is_executable, is_empty = check_validity(
                generated_cypher,
                neo4j_driver=self.neo4j._driver,
                database=database,
                timeout=120,
            )

            if is_executable:
                similarity = jaccard(
                    generated_cypher,
                    input_record['cypher'],
                    neo4j=self.neo4j
                )
                psj_sim = provenance_subgraph_jaccard_similarity(
                    generated_cypher,
                    input_record['cypher'],
                    neo4j=self.neo4j
                )
            else:
                similarity = 0.0
                psj_sim = 0.0
        else:
            similarity = None
            psj_sim = None
            is_empty = None
            is_executable = None

        return {
            self.join_column: input_record[self.join_column],
            "jaccard_similarity": similarity,
            "psj_similarity": psj_sim,
            "is_empty": is_empty,
            "is_executable": is_executable,
        }

def init_parser():
    parser = argparse.ArgumentParser(description="Generate synthetic data analysis.")
    parser.add_argument("--dataset-df", type=str, required=True,
        help="Path to the dataset dataframe file.",
    )
    parser.add_argument("--dataset-df-yaml-config", type=str, default=None,
        help="Path to the YAML config file for reading the dataset dataframe.",
    )
    parser.add_argument("--predictions-df", type=str, required=True,
        help="Path to the predictions dataframe file.",
    )
    parser.add_argument("--predictions-df-yaml-config", type=str, default=None,
        help="Path to the YAML config file for reading the predictions dataframe.",
    )
    parser.add_argument("--output-df", type=str, required=True,
        help="Path to the output file where generated evaluations will be saved.",
    )
    parser.add_argument("--output-df-yaml-config", type=str, default=None,
        help="Path to the YAML config file for saving the output dataframe.",
    )
    parser.add_argument("--join-column", type=str, default="df.index",
        help="Column name to join input and output dataframes during resumption.",
    )
    parser.add_argument("--separator", type=str, default=",",
        help="Separator used in the input .csv dataset file.",
    )
    parser.add_argument("--verbose", type=bool, default=True,
        help="Enable verbose logging.",
    )

    return parser

def get_input_df(args: argparse.Namespace) -> pd.DataFrame:
    dataset_df = read_df(args.dataset_df, **read_yaml_config(args.dataset_df_yaml_config))
    if args.join_column == 'df.index':
        dataset_df['df.index'] = dataset_df.index
    
    predictions_df = read_df(args.predictions_df, **read_yaml_config(args.predictions_df_yaml_config))
    input_df = dataset_df.merge(
        predictions_df,
        on=args.join_column,
        how="inner",
    )
    return input_df

def main():
    parser = init_parser()
    args = parser.parse_args()
    
    if os.path.exists(args.output_df):
        output_df = read_df(args.output_df)
        # output_df = output_df.dropna()
    else:
        output_df = None

    input_df = get_input_df(args)
    generator = Evaluator(
        in_df=input_df,
        join_column=args.join_column,
        out_df=output_df,
    )
    generator.generate(
        save_path=args.output_df,
        **read_yaml_config(args.output_df_yaml_config),
    )

if __name__ == "__main__":
    main()