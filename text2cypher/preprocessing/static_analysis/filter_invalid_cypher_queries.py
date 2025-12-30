import argparse

import pandas as pd

from text2cypher.evaluation.static_analysis import CypherExtractor

def init_parser():
    parser = argparse.ArgumentParser(description="Try out the evaluation script on a demo dataset.")
    parser.add_argument("--dataset_path", type=str, required=True,
        help="Path to the dataset for evaluation."
    )
    parser.add_argument("--query-col", type=str, required=True,
        help="Column name for the queries in the dataset."
    )
    return parser

'''
python ./text2cypher/prove/eval_demo.py 
--dataset_path ./data/processed/text-to-cypher/CypherBench/train.csv 
--query-col gold_cypher

python ./text2cypher/prove/eval_demo.py 
--dataset_path ./data/raw/text-to-cypher/neo4j-2024v1/train-00000-of-00001.parquet 
--query-col cypher
'''

if __name__ == "__main__":
    parser = init_parser()
    args = parser.parse_args()

    extractor = CypherExtractor()
    
    if args.dataset_path.endswith('.parquet'):
        df = pd.read_parquet(args.dataset_path)
    elif args.dataset_path.endswith('.csv'):
        df = pd.read_csv(args.dataset_path)
    else:
        raise ValueError("Unsupported file format. Please provide a .csv or .parquet file.")
    # print(df.info())

    total_count = len(df)

    import traceback

    def get_exceptions(query: str) -> str:
        try:
            extractor.extract_query(query)
            return None
        except Exception as e:
            # if 'multi_part_query' in str(e):
            #     print(query)
                # traceback.print_exc()
                # input()
            return str(e)
    
    df['exception'] = df[args.query_col].apply(get_exceptions)

    exception_counts = df['exception'].value_counts(dropna=False)
    for exception, count in exception_counts.items():
        print(f"Exception: {exception}\n  Count: {count} / {total_count} ({count / total_count * 100:.2f}%)")

    def get_n_nodes(query: str) -> tuple[int, int]:
        try:
            query = extractor.extract_query(query)
            n_nodes = 0
            n_edges = 0
            n_nodes += len(query.union_queries[0].match_pattern.nodes)
            n_edges += len(query.union_queries[0].match_pattern.edges)
            # for query in query.union_queries:
            #     n_nodes += len(query.match_pattern.nodes)
            #     n_edges += len(query.match_pattern.edges)
            return n_nodes, n_edges
        except:
            return None
        
    df['n_nodes_edges'] = df[args.query_col].apply(get_n_nodes)
    df['n_nodes'] = df['n_nodes_edges'].apply(lambda x: x[0] if x is not None else None)
    df['n_edges'] = df['n_nodes_edges'].apply(lambda x: x[1] if x is not None else None)
    print("Node counts statistics (successful extractions):")
    print(df['n_nodes'].value_counts())
    print("Edge counts statistics (successful extractions):")
    print(df['n_edges'].value_counts())