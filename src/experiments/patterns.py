from abc import abstractmethod
import traceback

import pandas as pd
from tqdm import tqdm
# from pynput import keyboard
import signal  # Import signal module

from experiments.utils import save_df

class DfToDfGenerator:

    def __init__(
        self,
        in_df: pd.DataFrame,
        join_column: str,
        out_df: pd.DataFrame = None,
        save_every: int = 10, # number of minutes after which to save progress
    ):
        self.join_column = join_column
        self.save_every = save_every
        self.resume(in_df, out_df)
    
    @abstractmethod
    def generate_output_record(self, input_record: dict) -> dict:
        raise NotImplementedError
    
    def resume(self, in_df: pd.DataFrame, out_df: pd.DataFrame = None):
        if self.join_column == 'df.index' and 'df.index' not in in_df.columns:
            in_df['df.index'] = in_df.index
        print(in_df.info())
        print(in_df.head())
        print(in_df.shape)

        if out_df is not None:
            unprocessed_mask = ~in_df[self.join_column].isin(out_df[self.join_column])
            self.unprocessed_records = in_df[unprocessed_mask].to_dict(orient="records")
            print(out_df.head())
            print(out_df.shape)
            self.processed_records = out_df.to_dict(orient="records")
        else:
            self.unprocessed_records = in_df.to_dict(orient="records")
            self.processed_records = []
        
        input("next> ")

    def generate(self, save_path: str, **kwargs):
        total = len(self.unprocessed_records) + len(self.processed_records)
        bar = tqdm(total=total, unit="sample")
        bar.update(len(self.processed_records))

        interrupted = False
        def signal_handler(signum, frame):
            nonlocal interrupted
            interrupted = True
            print("\nSafe exit requested. Finishing current record before saving...")
        signal.signal(signal.SIGINT, signal_handler)
        
        unprocessed_index = 0
        last_save_time = pd.Timestamp.now()
        try:
            while not interrupted and unprocessed_index < len(self.unprocessed_records):
                self.processed_records.append(
                    self.generate_output_record(
                        self.unprocessed_records[unprocessed_index]
                    )
                )
                unprocessed_index += 1
                bar.update(1)

                elapse_min = (pd.Timestamp.now() - last_save_time).total_seconds() / 60
                if elapse_min > self.save_every:
                    df = pd.DataFrame(self.processed_records)
                    print(f"\033[92mSaving progress after {elapse_min:.2f} minutes\033[0m")
                    save_df(df, save_path, **kwargs)
                    last_save_time = pd.Timestamp.now()
        except Exception as e:
            traceback.print_exc()
        finally:
            df = pd.DataFrame(self.processed_records)
            print(f"\033[92mSaving generated data to {save_path}\033[0m")
            save_df(df, save_path, **kwargs)
            bar.close()
