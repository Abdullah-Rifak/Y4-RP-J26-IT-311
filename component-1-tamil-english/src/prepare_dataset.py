from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent.parent

DEFAULT_DATASET_PATH = Path(
    r"C:\Users\Almeda\Desktop\Y4\RP\Test Data\New folder"
    r"\DravidianCodeMix\tamil_offensive_full_train.csv"
)


def load_dataset(dataset_path=DEFAULT_DATASET_PATH):
    """Load and validate a DravidianCodeMix dataset."""

    dataset_path = Path(dataset_path)

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {dataset_path}"
        )

    df = pd.read_csv(
        dataset_path,
        sep="\t",
        encoding="utf-8-sig",
        header=None,
        usecols=[0, 1],
        names=["comment", "label"],
    )

    df = df.dropna(subset=["comment", "label"]).copy()

    df["comment"] = df["comment"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip()

    df = df[
        (df["comment"] != "")
        & (df["label"] != "")
    ].reset_index(drop=True)

    return df


if __name__ == "__main__":
    dataset = load_dataset()

    print(f"Total records: {len(dataset)}")
    print("\nLabel distribution:")
    print(dataset["label"].value_counts().to_string())

