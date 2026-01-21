import argparse
import json
import os
from pathlib import Path
import traceback
from typing import override

import dotenv
import pandas as pd
from tqdm import tqdm

from langchain_neo4j import Neo4jGraph
from langgraph.errors import GraphRecursionError

from text2cypher.evaluation.psj_similarity import provenance_subgraph_jaccard_similarity
from text2cypher.evaluation.runtime import jaccard

from text2cypher.architecture.vector_stores import FAISSIndex, Model2VecEmbeddings
from text2cypher.architecture.agents import RetrievalAgent
from text2cypher.architecture.indexes import SchemaIndex

from text2cypher.utils import add_agent_args, get_llm

dotenv.load_dotenv()

def init_parser():
    parser = argparse.ArgumentParser(description="Generate synthetic data analysis.")

    parser.add_argument("--input-df", type=str, required=True,
        help="Path to the input .csv or .parquet dataset file.",
    )
    parser.add_argument("--separator", type=str, default=",",
        help="Separator used in the input .csv dataset file.",
    )
    parser.add_argument("--output-df", type=str, required=True,
        help="Path to the output file where generated data will be saved.",
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

    add_agent_args(parser)
    return parser

def read_df(path: str, separator: str = ",") -> pd.DataFrame:
    if path.endswith('.csv'):
        df = pd.read_csv(path, sep=separator)
    elif path.endswith('.parquet'):
        df = pd.read_parquet(path)
    else:
        raise ValueError("Unsupported file format. Please provide a .csv or .parquet file.")
    return df

def resume(args: argparse.Namespace):
    in_df = read_df(args.input_df, separator=args.separator)
    if args.join_column == 'df.index':
        in_df['df.index'] = in_df.index
    print(in_df.head())

    # if files exists in out_path, load them and return the dataframes
    if Path(args.output_df).exists():
        print(f"Resuming from existing output at {args.output_df}...")
        out_df = read_df(args.output_df, separator=args.separator)
        unprocessed_mask = ~in_df[args.join_column].isin(out_df[args.join_column])
        unprocessed_records = in_df[unprocessed_mask].to_dict(orient="records")
        print(out_df.head())
        processed_records = out_df.to_dict(orient="records")
    else:
        print(f"No existing output found at {args.output_df}. Starting fresh generation...")
        os.makedirs(Path(args.output_df).parent, exist_ok=True)
        processed_records = []
        unprocessed_records = in_df.to_dict(orient="records")
    
    input("Press Enter to continue...")

    return unprocessed_records, processed_records

class GenerateRecordInterface:

    def generate_output_record(self, input_record: dict) -> dict:
        raise NotImplementedError

def generate(generate_record: GenerateRecordInterface, args: argparse.Namespace):
    unprocessed_records, processed_records = resume(args)
    total = len(unprocessed_records) + len(processed_records)

    bar = tqdm(total=total, unit="sample", desc="Generating trajectories")
    bar.update(len(processed_records))

    try:
        for record in unprocessed_records: 
            processed_records.append(
                generate_record.generate_output_record(record)
            )
            bar.update(1)
    except KeyboardInterrupt:
        print("\nGeneration interrupted by user.")
    except Exception as e:
        traceback.print_exc()
    finally:
        print(f"\nSaving progress to {args.output_df}...")
        pd.DataFrame(processed_records).to_csv(args.output_df, sep=args.separator, index=False)
        bar.close()

class TrajectoryGenerator(GenerateRecordInterface):

    def init_toolkit_runtime_configs(self, neo4j_url: str, database: str, toolkit: RetrievalAgent.ToolKit = None):
        self.db = database
        if database == "eoflix":
            database = "neoflix"
        neo4j = Neo4jGraph(
            url=neo4j_url,
            username=database,
            password=database,
            database=database,
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
          
    def __init__(self, args: argparse.Namespace):
        self.embedding_model_str = "minishlab/potion-retrieval-32M" # "minishlab/M2V_base_output"
        self.embedding_model = Model2VecEmbeddings(
            model_path=self.embedding_model_str
        )
        # self.embedding_model = OllamaEmbeddings(
        #     model="snowflake-arctic-embed:22m",
        # )
        
        if args.log_dir_path:
            self.log_dir_path = f"./{args.log_dir_path}/{args.workflow}/{args.model.replace(':','-')}/"
        else:
            self.log_dir_path = None
        
        retriever_llm = get_llm(
            provider=args.provider,
            model=args.model,
        )

        with open("rsc/prompts/schema_retrieval/system_prompt.md", "r", encoding="utf-8") as f:
            retriever_system_prompt = f.read()

            # with open("rsc/prompts/schema_retrieval/tool_call_patterns.md", "r", encoding="utf-8") as f:
            #     tool_call_patterns = f.read()
            #     retriever_system_prompt = retriever_system_prompt.format(
            #         tool_call_patterns="",
            #     )

            if args.workflow == "structured_output":
                with open("rsc/prompts/schema_retrieval/structured_output_constraint.md", "r", encoding="utf-8") as f:
                    retriever_system_prompt += "\n" + f.read()
        
        with open("rsc/prompts/schema_retrieval/user_prompt.md", "r", encoding="utf-8") as f:
            retriever_user_prompt = f.read()
        
        self.init_toolkit_runtime_configs(
            toolkit=None,
            neo4j_url=os.getenv("NEO4J_URI"),
            database="movies",
        )

        self.agent = RetrievalAgent(
            mode=args.workflow,
            toolkit=self.toolkit,
            llm=retriever_llm,
            system_prompt=retriever_system_prompt,
            user_prompt=retriever_user_prompt,
        )

    @override
    def generate_output_record(self, input_record: dict) -> dict:
        record_id = str(input_record[args.join_column])
        if self.log_dir_path:
            log_file_path = f"{self.log_dir_path}/{record_id}.md"
        else:
            log_file_path = None

        if input_record['database_reference_alias']:
            db = input_record['database_reference_alias'].split('_')[-1]
            if db != self.db:
                self.init_toolkit_runtime_configs(
                    toolkit=self.toolkit,
                    neo4j_url=os.getenv("NEO4J_URI"),
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

                trajectory_dict = RetrievalAgent.serialize_messages_state(final_state)
                json_trajectory = json.dumps(trajectory_dict)

                generated_cypher = final_state['result'].get("cypher_query", None)

                # check if the ground truth query results are empty
                if len(self.toolkit.neo4j.query(
                    input_record['cypher'],
                )) == 0:
                    print(f"WARNING: Ground truth query results are empty for record {record_id}")
                    is_empty = True
                else:
                    is_empty = False

                return_dict = {
                    args.join_column: record_id,
                    "json_trajectory": json_trajectory,
                    "generated_cypher": generated_cypher,
                    "is_empty": is_empty,
                    **self.evaluate(input_record, generated_cypher)
                }
                input("finished_sample> ")

            except GraphRecursionError as e:
                print("Skipping further generation due to recursion error.")
                print(f"\nGraphRecursionError: {e}")
                return_dict = {}            
            
        else:
            return_dict = {}

        return return_dict

    def evaluate(self, row: dict, generated_cypher: str):
        if generated_cypher is None:
            return {
                "jaccard_similarity": 0.0,
                "psj_similarity": 0.0,
            }

        similarity = jaccard(
            generated_cypher,
            row['cypher'],
            neo4j=self.toolkit.neo4j
        )    

        print(f"Ground Truth Cypher: {row['cypher']}")
        print(f"Generated Cypher: {generated_cypher}")
        print(f"Jaccard Similarity: {similarity}")

        psj_sim = provenance_subgraph_jaccard_similarity(
            generated_cypher,
            row['cypher'],
            neo4j=self.toolkit.neo4j
        )

        print(f"Provenance Subgraph Jaccard Similarity: {psj_sim}")

        return {
            "jaccard_similarity": similarity,
            "psj_similarity": psj_sim,
        }

if __name__ == "__main__":
    parser = init_parser()
    args = parser.parse_args()

    generate(
        generate_record=TrajectoryGenerator(args),
        args=args
    )
