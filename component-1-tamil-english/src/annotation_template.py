from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent.parent

INPUT_PATH = (
    PROJECT_DIR
    / "reports"
    / "generated"
    / "tamhatex_review_sample.csv"
)

OUTPUT_PATH = (
    PROJECT_DIR
    / "reports"
    / "generated"
    / "tamhatex_annotation_template.csv"
)


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Review sample not found: {INPUT_PATH}"
        )

    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")

    # Add separate columns for human annotation.
    df["human_label"] = ""
    df["human_decision"] = ""
    df["human_notes"] = ""
    df["annotator_id"] = ""
    df["annotation_status"] = "NOT_REVIEWED"

    # Save the annotation template separately.
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print("TAMHATEX ANNOTATION TEMPLATE")
    print("=" * 35)
    print(f"Records prepared: {len(df)}")
    print(f"Human labels: {df['human_label'].isna().sum()} missing values")
    print(f"Annotation status: NOT_REVIEWED")
    print(f"\nSaved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()