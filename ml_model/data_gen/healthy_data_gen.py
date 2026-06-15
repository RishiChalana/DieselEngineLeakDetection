"""
Generate time-sequential healthy engine data using EngineSimulator.
Each row is the next time step - no independent random draws per row.
"""
import os
import pandas as pd
import numpy as np
from .engine_simulator_core import EngineSimulator


NUM_SAMPLES = 20_000
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data_store", "healthy_dataset.csv")


def generate_healthy_dataset(
    n_samples: int = NUM_SAMPLES,
    output_path: str = OUTPUT_PATH,
    seed: int | None = 42,
) -> pd.DataFrame:
    """Generate sequential healthy engine data. No writing inside loop."""
    engine = EngineSimulator(seed=seed)
    data: list[dict] = []
    for _ in range(n_samples):
        sample = engine.step()
        data.append(sample)
    df = pd.DataFrame(data)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    return df


if __name__ == "__main__":
    df = generate_healthy_dataset()
    print("Healthy dataset generated:", df.shape)
    print(df.describe())
