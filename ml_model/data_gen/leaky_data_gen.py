import os
import pandas as pd
import numpy as np
from .engine_simulator_core import EngineSimulator


NUM_SAMPLES = 20_000
HEALTHY_STEPS_BEFORE_LEAK = 0
OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data_store", "leaky_dataset.csv"
)

LEAK_TYPES = ["precompressor", "charge_air", "exhaust"]


def generate_leaky_dataset(
    n_samples: int = NUM_SAMPLES,
    healthy_steps: int = HEALTHY_STEPS_BEFORE_LEAK,
    output_path: str = OUTPUT_PATH,
    seed: int | None = 42,
    leak_type: str | None = None,
) -> pd.DataFrame:

    engine = EngineSimulator(seed=seed)
    data: list[dict] = []

    for t in range(n_samples):

        if t == healthy_steps:
            engine.introduce_leak(
                leak_type=leak_type or np.random.choice(LEAK_TYPES)
            )

        sample = engine.step()

        data.append(sample)

    df = pd.DataFrame(data)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)

    return df


if __name__ == "__main__":
    df = generate_leaky_dataset()
    print("Leaky dataset generated:", df.shape)
    print(df.describe())