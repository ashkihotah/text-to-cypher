import argparse
import os
from typing import override
import pandas as pd
import pickle
import nltk
from nltk.translate.gleu_score import sentence_gleu
from rouge_score import rouge_scorer

# Append the custom local directory to NLTK's search path
# nltk_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "rsc", "nltk_data")
# nltk.data.path.append(nltk_data_dir)
nltk.data.path.append('./rsc/nltk_data')
# Alternatively, if running relative to project root: nltk.data.path.append('./rsc/nltk_data')

from text2cypher.evaluation.jaccard import (
    exact_match_jaccard,
    fast_jaccard,
    greedy_jaccard,
)
from text2cypher.evaluation.psj_similarity import provenance_subgraph_jaccard_similarity

from experiments.utils import read_df, read_yaml_config
from experiments.patterns import (
    DfToDfGenerator,
)

class Evaluator(DfToDfGenerator):

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
    
    def retrieve_preds_gts(self, input_file: str):
        rows = []
        with open(input_file, "rb") as f:
            eof = False
            while not eof:
                try:
                    rows.append(pickle.load(f))
                except EOFError:
                    eof = True
        return rows

    @override
    def generate_output_record(self, input_record: dict) -> dict:
        similarity = None
        gleu_score = None
        rouge_l_f1 = None
        # psj_sim = None

        preds_file = input_record["preds_file"]
        gts_file = input_record["gts_file"]

        if pd.notna(preds_file):
            preds = self.retrieve_preds_gts(preds_file)
        if pd.notna(gts_file):
            gts = self.retrieve_preds_gts(gts_file)

        # if len(preds) > 10000 or len(gts) > 10000:
        #     print(f"\033[93mResult too large (preds: {len(preds)}, gts: {len(gts)}). Skipping this record.\033[0m")

        if pd.notna(preds_file) and pd.notna(gts_file):
            similarity = exact_match_jaccard(preds, gts, 
                "order by" in f"{input_record['generated_cypher']} {input_record['cypher']}".lower()
            )
            # psj_sim = provenance_subgraph_jaccard_similarity(
            #     input_record['generated_cypher'],
            #     input_record['cypher'],
            #     neo4j=self.neo4j
            # )
            
        if pd.notna(input_record.get('generated_cypher')) and pd.notna(input_record.get('cypher')):
            ref = [nltk.tokenize.word_tokenize(input_record['cypher'])]
            hyp = nltk.tokenize.word_tokenize(input_record['generated_cypher'])
            gleu_score = sentence_gleu(ref, hyp)

            scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
            scores = scorer.score(input_record['cypher'], input_record['generated_cypher'])
            rouge_l_f1 = scores['rougeL'].fmeasure

        return {
            self.join_column: input_record[self.join_column],
            "jaccard_similarity": similarity,
            "google_bleu": gleu_score,
            "rouge_l_f1": rouge_l_f1,
            # "psj_similarity": psj_sim,
        }

def init_parser():
    parser = argparse.ArgumentParser(description="Generate synthetic data analysis.")
    parser.add_argument("--dataset-df", type=str, required=True,
        help="Path to the dataset dataframe file.",
    )
    parser.add_argument("--dataset-df-yaml-config", type=str, default=None,
        help="Path to the YAML config file for reading the dataset dataframe.",
    )
    
    parser.add_argument("--generations-df", type=str, required=True,
        help="Path to the generations dataframe file.",
    )
    parser.add_argument("--generations-df-yaml-config", type=str, default=None,
        help="Path to the YAML config file for reading the generations dataframe.",
    )

    parser.add_argument("--predictions-df", type=str, required=True,
        help="Path to the predictions dataframe file.",
    )
    parser.add_argument("--predictions-df-yaml-config", type=str, default=None,
        help="Path to the YAML config file for reading the predictions dataframe.",
    )
    parser.add_argument("--ground-truths-df", type=str, required=True,
        help="Path to the ground truths dataframe file.",
    )
    parser.add_argument("--ground-truths-df-yaml-config", type=str, default=None,
        help="Path to the YAML config file for reading the ground truths dataframe.",
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
    if args.join_column == 'df.index' and 'df.index' not in dataset_df.columns:
        dataset_df['df.index'] = dataset_df.index
    ground_truths_df = read_df(args.ground_truths_df, **read_yaml_config(args.ground_truths_df_yaml_config))
    ground_truths_df = ground_truths_df.rename(columns={"rows_file": "gts_file", 'syntax_error': "gts_syntax_error"})
    is_less_than_limit_col = [col for col in ground_truths_df.columns if col.startswith("is_less_than_limit_")][0]
    # filter all ground truths that have True in columns "syntax_error", "is_less_than_limit_", "is_timeout_expired"
    ground_truths_df = ground_truths_df[
        (ground_truths_df['gts_syntax_error'] == False) &
        (ground_truths_df[is_less_than_limit_col] == True) &
        (ground_truths_df['is_timeout_expired'] == False)
    ]
    ground_truths_df = ground_truths_df[[args.join_column, 'gts_file']].merge(
        dataset_df[[args.join_column, 'cypher']],
        on=args.join_column,
        how='inner',
    )
    
    predictions_df = read_df(args.predictions_df, **read_yaml_config(args.predictions_df_yaml_config))
    predictions_df = predictions_df.rename(columns={"rows_file": "preds_file", 'syntax_error': "preds_syntax_error"})
    generations_df = read_df(args.generations_df, **read_yaml_config(args.generations_df_yaml_config))
    # predictions_df = predictions_df[
    #     (predictions_df['preds_syntax_error'] == False) &
    #     (predictions_df[is_less_than_limit_col] == True) &
    #     (predictions_df['is_timeout_expired'] == False)
    # ]
    predictions_df = predictions_df[[args.join_column, 'preds_file']].merge(
        generations_df[[args.join_column, 'generated_cypher']],
        on=args.join_column,
        how='inner',
    )

    # Join ground truths and predictions on the join column, keeping all ground truths (left join)
    input_df = ground_truths_df.merge(
        predictions_df,
        on=args.join_column,
        how='left',
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