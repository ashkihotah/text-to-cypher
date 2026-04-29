import argparse
import os
from typing import override
import traceback

from neo4j import GraphDatabase
from neo4j.time import DateTime
from neo4j.exceptions import (
    CypherSyntaxError,
    DatabaseError,
    CypherTypeError,
    ClientError
)
import pandas as pd
import dotenv
import pickle
from tqdm import tqdm

import signal

from experiments.utils import read_df, read_yaml_config
from experiments.patterns import (
    DfToDfGenerator,
)

# Recursively clean Neo4j objects from the dict before pickling, 
# or use a custom pickler.
def clean_neo4j_types(data):
    """
    Iteratively traverse and clean Neo4j objects from the nested data structure.
    Mutates lists and dicts in-place for maximum memory efficiency.
    """
    # Handle the case where the root object itself is a primitive/DateTime
    if not isinstance(data, (list, dict)):
        if isinstance(data, DateTime):
            return data.iso_format()
        return data

    # Use a stack to keep track of nested structures to process
    stack = [data]

    while stack:
        current = stack.pop()

        if isinstance(current, list):
            for i in range(len(current)):
                val = current[i]
                if isinstance(val, (list, dict)):
                    stack.append(val)
                elif isinstance(val, DateTime):
                    current[i] = val.iso_format()
                    
        elif isinstance(current, dict):
            for key, val in current.items():
                if isinstance(val, (list, dict)):
                    stack.append(val)
                elif isinstance(val, DateTime):
                    current[key] = val.iso_format()

    return data

class CypherExecutionTimeoutError(Exception):
    """Custom exception to indicate a timeout during Cypher query execution."""
    pass

# Define what happens when the alarm goes off
def timeout_handler(signum, frame):
    raise CypherExecutionTimeoutError("Server took too long to start sending records.")

# Attach the handler to the SIGALRM signal
signal.signal(signal.SIGALRM, timeout_handler)

class Predictor(DfToDfGenerator):

    def init_neo4j(self, neo4j_url: str, database: str, force_drop: bool = False):
        self.db = database
        if database == "eoflix":
            database = "neoflix"

        # Close the existing session and driver if they are already open
        if hasattr(self, 'session') and self.session is not None and not force_drop:
            self.session.close()
        if hasattr(self, 'neo4j') and self.neo4j is not None and not force_drop:
            self.neo4j.close()

        self.neo4j = GraphDatabase.driver(
            neo4j_url,
            auth=(database, database),
            database=database,
            # max_transaction_retry_time=self.timeout
        )
        self.session = self.neo4j.session(database=database)

    @override
    def __init__(
        self,
        in_df: pd.DataFrame,
        join_column: str,
        subfolder: str,
        out_df: pd.DataFrame = None,
        cypher_column: str = "cypher",
        result_set_limit: int = 50000,
        timeout: int = 120
    ):
        super().__init__(
            in_df=in_df,
            join_column=join_column,
            out_df=out_df,
        )
        self.cypher_column = cypher_column
        self.result_set_limit = result_set_limit
        self.subfolder = subfolder
        self.timeout = timeout
        self.init_neo4j(
            neo4j_url=dotenv.get_key(".env", "NEO4J_URL"),
            database="movies",
        )
        os.makedirs(self.subfolder, exist_ok=True)
    
    def save_rows(
        self, 
        record_id: str,
        cypher: str,
    ):
        is_less_than_limit = True
        file_path = f"{self.subfolder}/{record_id}.pkl"
        if not os.path.exists(file_path):
            signal.alarm(self.timeout)
            cursor = self.session.run(cypher)
            cursor.peek()
            signal.alarm(0)
            with tqdm( total=self.result_set_limit,
                desc=f"Sample {record_id}", 
                leave=False, 
                unit=" rows"
            ) as inner_bar:
                # Open file in Write-Binary ('wb') mode
                with open(file_path, 'wb') as f:
                    rows_written = 0
                    while rows_written < self.result_set_limit and cursor.peek():
                        record = next(cursor)
                        cleaned_row = clean_neo4j_types(record.data())
                        # Dump directly to the file stream
                        pickle.dump(cleaned_row, f)
                        rows_written += 1
                        inner_bar.update(1)
                    if cursor.peek():
                        is_less_than_limit = False
                        os.remove(file_path)
                        file_path = None
                        print(
                            f"\033[93mResult set for record {record_id} exceeded "
                            f"the limit of {self.result_set_limit} rows. "
                            "Skipping saving results.\033[0m"
                        )

        return file_path, is_less_than_limit

    @override
    def generate_output_record(self, input_record: dict) -> dict:
        cypher = input_record.get(self.cypher_column, None)
        rows_file = None
        syntax_error = None
        is_less_than_limit = None
        is_timeout_expired = False

        if pd.notna(cypher):
            database = input_record['database_reference_alias'].split("_")[-1]
            if self.db != database:
                # print in blue that we're switching the neo4j connection
                print(f'\033[94mSwitching Neo4j connection to database: {database}\033[0m')
                self.init_neo4j(
                    neo4j_url=dotenv.get_key(".env", "NEO4J_URL"),
                    database=database,
                )
                        
            try:
                rows_file, is_less_than_limit = self.save_rows(
                    record_id=input_record[self.join_column],
                    cypher=cypher,
                )
                syntax_error = False
            except (
                CypherSyntaxError,
                DatabaseError,
                CypherTypeError,
                ClientError,
            ):
                rows_file = None
                syntax_error = True                    
            except (
                CypherExecutionTimeoutError,
            ):
                signal.alarm(0)  # Cancel the alarm if it was triggered
                print(
                    f"\033[91mClientError while executing query for record {input_record[self.join_column]}. "
                    "This may be due to a timeout or other client-side issue.\033[0m"
                )
                is_timeout_expired = True
                self.init_neo4j(
                    neo4j_url=dotenv.get_key(".env", "NEO4J_URL"),
                    database=database,
                    force_drop=True,
                )
            # except Exception as e:
            #     print(f'\033[91m')
            #     traceback.print_exc()
            #     print(f'\033[0m')

        return {
            self.join_column: input_record[self.join_column],
            "rows_file": rows_file,
            "syntax_error": syntax_error,
            f"is_less_than_limit_{self.result_set_limit}": is_less_than_limit,
            "is_timeout_expired": is_timeout_expired,
        }

def init_parser():
    parser = argparse.ArgumentParser(description="Collect rows returned by executing Cypher queries in the given dataframe.")
    parser.add_argument("--databases-df", type=str, required=False,
        help="Path to the databases dataframe file.",
    )
    parser.add_argument("--databases-df-yaml-config", type=str, default=None,
        help="Path to the YAML config file for reading the databases dataframe.",
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
    parser.add_argument("--predictions-subfolder", type=str, required=True,
        help="Subfolder where the pickled query results will be saved.",
    )
    parser.add_argument("--join-column", type=str, default="df.index",
        help="Column name to join input and output dataframes during resumption.",
    )
    parser.add_argument("--cypher-column", type=str, default="cypher",
        help="Column name in the input dataframe that contains the Cypher queries to execute.",
    )
    parser.add_argument("--verbose", type=bool, default=True,
        help="Enable verbose logging.",
    )

    return parser

def get_input_df(args: argparse.Namespace) -> pd.DataFrame:
    input_df = read_df(args.predictions_df, **read_yaml_config(args.predictions_df_yaml_config))

    if args.databases_df is not None:
        databases_df = read_df(args.databases_df, **read_yaml_config(args.databases_df_yaml_config))
        if args.join_column == 'df.index' and 'df.index' not in databases_df.columns:
            databases_df['df.index'] = databases_df.index
        
        input_df = databases_df.merge(
            input_df,
            on=args.join_column,
            how="inner",
        )
    else:
        if args.join_column == 'df.index' and 'df.index' not in input_df.columns:
            input_df['df.index'] = input_df.index

        # filter all rows not having database_reference_alias column
        input_df = input_df[input_df['database_reference_alias'].notna()]

        columns_to_keep = [args.join_column, 'database_reference_alias', args.cypher_column]
        input_df = input_df[columns_to_keep]

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

    # order the input_df by the database_reference_alias column to minimize
    #  the number of times we need to switch the neo4j database connection
    input_df = input_df.sort_values(by='database_reference_alias')

    generator = Predictor(
        in_df=input_df,
        join_column=args.join_column,
        subfolder=args.predictions_subfolder,
        out_df=output_df,
        cypher_column=args.cypher_column,
    )
    generator.generate(
        save_path=args.output_df,
        **read_yaml_config(args.output_df_yaml_config),
    )

if __name__ == "__main__":
    main()