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
    ):
        self.join_column = join_column
        self.resume(in_df, out_df)
    
    @abstractmethod
    def generate_output_record(self, input_record: dict) -> dict:
        raise NotImplementedError
    
    def resume(self, in_df: pd.DataFrame, out_df: pd.DataFrame = None):
        if self.join_column == 'df.index':
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
        bar = tqdm(total=total, unit="sample", desc="Evaluating trajectories")
        bar.update(len(self.processed_records))

        interrupted = False
        # def on_press(key):
        #     nonlocal interrupted
        #     try:
        #         if key.char == 'ì':
        #             interrupted = True
        #             print("\nGeneration interrupted by the user!")
        #             print(
        #                 "I'm now safely interrupting the process",
        #                 f"and saving generated data to {save_path}..."
        #             )
        #             return False  # Stop listener
        #     except AttributeError:
        #         pass  # Ignore special keys
        # listener = keyboard.Listener(on_press=on_press)
        # listener.start()
        original_sigint_handler = signal.getsignal(signal.SIGINT)
        def signal_handler(signum, frame):
            nonlocal interrupted
            interrupted = True
            print("\nSafe exit requested. Finishing current record before saving...")
        signal.signal(signal.SIGINT, signal_handler)
        
        try:
            while not interrupted and bar.n < total:
                self.processed_records.append(
                    self.generate_output_record(
                        self.unprocessed_records[bar.n - len(self.processed_records)]
                    )
                )
                bar.update(1)
                # input("finished_sample> ")
        except Exception as e:
            traceback.print_exc()
        finally:
            df = pd.DataFrame(self.processed_records)
            print("Saving generated data to", save_path)
            save_df(df, save_path, **kwargs)
            bar.close()
