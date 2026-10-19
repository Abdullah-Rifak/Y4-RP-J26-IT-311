from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = PROJECT_DIR / "data" / "TamHateX_V2_research_candidate.csv"
OUTPUT_PATH = PROJECT_DIR / "reports" / "generated" / "tamhatex_review_sample.csv"


def main():
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATASET_PATH}")

    df = pd.read_csv(DATASET_PATH, encoding="utf-8-sig")

    # Normalize text fields used for filtering.
    df["original_label"] = df["original_label"].fillna("").astype(str).str.strip()
    df["proposed_research_label"] = (
        df["proposed_research_label"].fillna("").astype(str).str.strip()
    )
    df["review_status"] = df["review_status"].fillna("").astype(str).str.strip()

    # 1. Include every original HATE record changed to NON_HATE.
    changed_to_non_hate = df[
        (df["original_label"] == "HATE")
        & (df["proposed_research_label"] == "NON_HATE")
    ]

    # 2. Include every record requiring human review.
    needs_review = df[df["review_status"] == "NEEDS_HUMAN_REVIEW"]

    # 3. Select up to 20 reproducible examples from each proposed category.

# 3. Select up to 20 reproducible examples from each proposed category.
    sample_groups = []

    for category, group in df.groupby("proposed_research_label"):
        sample = group.sample(
            n=min(20, len(group)),
            random_state=42,
        )
        sample_groups.append(sample)

    category_samples = pd.concat(sample_groups, ignore_index=True)




    # Combine groups and remove repeated records by record_id.
    review_sample = pd.concat(
        [changed_to_non_hate, needs_review, category_samples],
        ignore_index=True,
    )

    review_sample = review_sample.drop_duplicates(
        subset=["record_id"],
        keep="first",
    )

    # Put records with missing text first so they are easy to identify.
    review_sample["text_missing"] = (
        review_sample["text"].isna()
        | review_sample["text"].astype(str).str.strip().eq("")
    )

    review_sample = review_sample.sort_values(
        by=["text_missing", "record_id"],
        ascending=[False, True],
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    review_sample.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print("TAMHATEX REVIEW SAMPLE")
    print("=" * 35)
    print(f"Total source records: {len(df)}")
    print(f"Changed from HATE to NON_HATE: {len(changed_to_non_hate)}")
    print(f"Needs human review: {len(needs_review)}")
    print(f"Records in review sample after deduplication: {len(review_sample)}")
    print(f"Records with missing text in sample: {review_sample['text_missing'].sum()}")
    print(f"\nProposed label distribution:")
    print(review_sample["proposed_research_label"].value_counts().to_string())
    print(f"\nSaved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

