import argparse
import json
import os
from pathlib import Path
import traceback
from typing import Callable, override

import dotenv
import pandas as pd
from tqdm import tqdm

from langchain_neo4j import Neo4jGraph
from langgraph.errors import GraphRecursionError
import yaml

from text2cypher.architecture.vector_stores import FAISSIndex, Model2VecEmbeddings
from text2cypher.architecture.agents import RetrievalAgent
from text2cypher.architecture.indexes import SchemaIndex

from text2cypher.experiments.utils import add_agent_args, get_llm, read_df, read_yaml_config
from text2cypher.experiments.datasets.patterns import (
    DfToDfGenerator,
)

dotenv.load_dotenv()

class TrajectoryGenerator(DfToDfGenerator):

    def init_toolkit_runtime_configs(self, neo4j_url: str, database: str, toolkit: RetrievalAgent.ToolKit = None):
        self.db = database
        if database == "eoflix":
            database = "neoflix"
        neo4j = Neo4jGraph(
            url=neo4j_url,
            username=database,
            password=database,
            database=database,
            # sanitize=True,
        )
        schema_vector_store = FAISSIndex(
            neo4j=neo4j,
            embedding_model=self.embedding_model,
            indexes_dir=f"./indexes/{self.embedding_model_str}/{self.db}/",
        )
        schema_index = SchemaIndex(
            neo4j=neo4j,
            embedding_model=self.embedding_model,
        )
        if toolkit is None:
            self.toolkit = RetrievalAgent.ToolKit(
                neo4j=neo4j,
                schema_index=schema_index,
                schema_vector_store=schema_vector_store
            )
        else:
            self.toolkit.init_runtime(
                neo4j=neo4j,
                schema_index=schema_index,
                schema_vector_store=schema_vector_store
            )
    
    @override
    def __init__(
        self,
        in_df: pd.DataFrame,
        join_column: str,
        provider: str,
        model: str,
        workflow: str,
        log_dir_path: str = None,
        out_df: pd.DataFrame = None,
    ):
        super().__init__(
            in_df=in_df,
            join_column=join_column,
            out_df=out_df,
        )
        self.workflow = workflow
        self.embedding_model_str = "minishlab/potion-retrieval-32M" # "minishlab/M2V_base_output"
        self.embedding_model = Model2VecEmbeddings(
            model_path=self.embedding_model_str
        )
        # self.embedding_model = OllamaEmbeddings(
        #     model="snowflake-arctic-embed:22m",
        # )
        
        if log_dir_path:
            self.log_dir_path = f"./{log_dir_path}/{self.workflow}/{model.replace(':','-')}/"
        else:
            self.log_dir_path = None
        
        retriever_llm = get_llm(
            provider=provider,
            model=model,
        )

        with open("rsc/prompts/schema_retrieval/system_prompt.md", "r", encoding="utf-8") as f:
            retriever_system_prompt = f.read()

            # with open("rsc/prompts/schema_retrieval/tool_call_patterns.md", "r", encoding="utf-8") as f:
            #     tool_call_patterns = f.read()
            #     retriever_system_prompt = retriever_system_prompt.format(
            #         tool_call_patterns="",
            #     )

            if self.workflow == "structured_output":
                with open("rsc/prompts/schema_retrieval/structured_output_constraint.md", "r", encoding="utf-8") as f:
                    retriever_system_prompt += "\n" + f.read()
        
        with open("rsc/prompts/schema_retrieval/user_prompt.md", "r", encoding="utf-8") as f:
            retriever_user_prompt = f.read()
        
        self.init_toolkit_runtime_configs(
            toolkit=None,
            neo4j_url=os.getenv("NEO4J_URL"),
            database="movies",
        )

        self.agent = RetrievalAgent(
            mode=self.workflow,
            toolkit=self.toolkit,
            llm=retriever_llm,
            system_prompt=retriever_system_prompt,
            user_prompt=retriever_user_prompt,
        )

    @override
    def generate_output_record(self, input_record: dict) -> dict:
        record_id = str(input_record[self.join_column])
        if self.log_dir_path:
            log_file_path = f"{self.log_dir_path}/{record_id}.md"
        else:
            log_file_path = None

        db = input_record['database_reference_alias'].split('_')[-1]
        if db != self.db:
            self.init_toolkit_runtime_configs(
                toolkit=self.toolkit,
                neo4j_url=os.getenv("NEO4J_URL"),
                database=db,
            )

        try:
            final_state = self.agent.logged_stream(
                init_state=RetrievalAgent.WorkflowInitialState(
                    user_query=input_record['question'],
                    # kg_schema=input_record['schema'],
                    # cypher_query=input_record['cypher'],
                ),
                thread_id=record_id,
                verbose=True,
                log_file_path=log_file_path,
            )

        except GraphRecursionError as e:
            print("Skipping further generation due to recursion error.")
            print(f"\nGraphRecursionError: {e}")
        
        final_state = self.agent.workflow.get_state(
            config={"configurable": {"thread_id": record_id}}
        ).values
        
        trajectory_dict = RetrievalAgent.serialize_messages_state(final_state)
        json_trajectory = json.dumps(trajectory_dict)

        result = final_state['result']
        if result is None:
            generated_cypher = None
        else:
            generated_cypher = result.get("cypher_query", None)

        return_dict = {
            self.join_column: record_id,
            "json_trajectory": json_trajectory,
            "generated_cypher": generated_cypher,
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
    parser.add_argument("--workflow", type=str, choices=["structured_output", "native_tool_call"], default="native_tool_call",
        help="The workflow to use for data generation.",
    )
    parser.add_argument("--log-dir-path", type=str, default=None,
        help="Directory path to save logs.",
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
    generator = TrajectoryGenerator(
        in_df=input_df,
        join_column=args.join_column,
        provider=args.provider,
        model=args.model,
        workflow=args.workflow,
        log_dir_path=args.log_dir_path,
        out_df=output_df,
    )
    generator.generate(
        save_path=args.output_df,
        **read_yaml_config(args.output_df_yaml_config),
    )

if __name__ == "__main__":
    main()