import os
import tqdm 
import signal
import traceback

import pandas as pd

from experiments.utils import save_df, read_df

DEFAULT_JOIN_COLUMN = "df.index"

def resume(in_df: pd.DataFrame, save_path: str, join_column: str = DEFAULT_JOIN_COLUMN):

    save_dir = os.path.dirname(save_path)
    file_name = os.path.basename(save_path)
    checkpoint_file = os.path.join(save_dir, f"checkpoint_{file_name}")

    if join_column == DEFAULT_JOIN_COLUMN and DEFAULT_JOIN_COLUMN not in in_df.columns:
        in_df[DEFAULT_JOIN_COLUMN] = in_df.index

    if os.path.exists(save_path):
        print(
            f"\033[92mOutput file {save_path} already exists. "
            "Resuming processed records from output file.\033[0m"
        )
        out_df = read_df(save_path)
        processed_records = out_df.to_dict(orient="records")

        if os.path.exists(checkpoint_file):
            print(
                f"\033[93mCheckpoint found at {checkpoint_file}. "
                "Resuming execution from checkpoint.\033[0m"
            )
            unprocessed_records = read_df(checkpoint_file).to_dict(orient="records")
        else:
            print(
                f"\033[93mNo checkpoint found. "
                "Assuming only records in output file are processed.\033[0m"
            )
            unprocessed_mask = ~in_df[join_column].isin(out_df[join_column])
            unprocessed_records = in_df[unprocessed_mask].to_dict(orient="records")
            print(out_df.head())
            print(out_df.shape)
    else:
        print(
            f"\033[92mNo output file found at {save_path}. "
            "Starting fresh execution.\033[0m"
        )
        unprocessed_records = in_df.to_dict(orient="records")
        processed_records = []

    print(in_df.info())
    print(in_df.head())
    print(in_df.shape)    
    input("next> ")
    return unprocessed_records, processed_records

def save(processed_records: list, unprocessed_records: list, save_path: str, **kwargs):
    df = pd.DataFrame(processed_records)
    save_df(df, save_path, **kwargs)
    df = pd.DataFrame(unprocessed_records)
    checkpoint_file = os.path.join(os.path.dirname(save_path), f"checkpoint_{os.path.basename(save_path)}")
    save_df(df, checkpoint_file, **kwargs)

def transform(in_df: pd.DataFrame, save_path: str, update_transformed_records: callable, save_every: int = 10, **kwargs):
    unprocessed_records, processed_records = resume(in_df, save_path)

    total = len(unprocessed_records) + len(processed_records)
    bar = tqdm(total=total, unit="sample")
    bar.update(len(processed_records))

    interrupted = False
    def signal_handler(signum, frame):
        nonlocal interrupted
        interrupted = True
        print("\nSafe exit requested. Finishing current record before saving...")
    signal.signal(signal.SIGINT, signal_handler)
    
    unprocessed_index = 0
    last_save_time = pd.Timestamp.now()
    try:
        while not interrupted and unprocessed_index < len(unprocessed_records):
            update_transformed_records(
                processed_records,
                unprocessed_records[unprocessed_index]
            )
            unprocessed_index += 1
            bar.update(1)

            elapse_min = (pd.Timestamp.now() - last_save_time).total_seconds() / 60
            if elapse_min > save_every:
                print(f"\033[92mSaving progress after {elapse_min:.2f} minutes\033[0m")
                save(processed_records, unprocessed_records[unprocessed_index:], save_path, **kwargs)
                last_save_time = pd.Timestamp.now()
    except Exception as e:
        print(f'\033[91m', end="")
        traceback.print_exc()
        print(f'\033[0m', end="")
    finally:
        print(f"\033[92mSaving generated data to {save_path}\033[0m")
        save(processed_records, unprocessed_records[unprocessed_index:], save_path, **kwargs)
        bar.close()