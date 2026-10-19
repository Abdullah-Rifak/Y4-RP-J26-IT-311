from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = PROJECT_DIR / "data" / "TamHateX_V2_research_candidate.csv"

REPORT_DIR = PROJECT_DIR / "reports" / "generated"
REPORT_PATH = REPORT_DIR / "tamhatex_audit.txt"

REQUIRED_COLUMNS = [
    "record_id",
    "text",
    "original_label",
    "original_target",
    "proposed_research_label",
    "script_type",
    "confidence",
    "review_status",
]


def load_dataset():
    """Load the candidate dataset without modifying the source file."""

    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_PATH}"
        )

    df = pd.read_csv(
        DATASET_PATH,
        encoding="utf-8-sig",
        keep_default_na=False,
    )

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    return df


def build_audit_report(df):
    """Create a text report containing dataset quality checks."""

    lines = []

    lines.append("TAMHATEX V2 DATASET AUDIT")
    lines.append("=" * 40)

    lines.append(f"Total records: {len(df)}")
    lines.append(f"Total columns: {len(df.columns)}")

    # Missing text
    missing_text = df["text"].astype(str).str.strip().eq("")

    lines.append("\n1. MISSING TEXT")
    lines.append(f"Records with missing text: {missing_text.sum()}")

    missing_ids = df.loc[missing_text, "record_id"].tolist()
    lines.append(f"Record IDs: {missing_ids}")

    # Duplicate IDs
    duplicate_ids = df["record_id"].duplicated(keep=False)

    lines.append("\n2. DUPLICATE RECORD IDs")
    lines.append(
        f"Records with repeated IDs: {duplicate_ids.sum()}"
    )

    lines.append(
        f"Repeated IDs: "
        f"{df.loc[duplicate_ids, 'record_id'].drop_duplicates().tolist()}"
    )

    # Duplicate comments
    normalized_text = (
        df["text"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    nonempty_text = normalized_text.ne("")
    duplicate_text = normalized_text.duplicated(keep=False) & nonempty_text

    lines.append("\n3. DUPLICATE COMMENT TEXT")
    lines.append(
        f"Records sharing duplicate non-empty text: "
        f"{duplicate_text.sum()}"
    )

    # Original versus proposed labels
    lines.append("\n4. ORIGINAL LABEL DISTRIBUTION")
    lines.append(
        df["original_label"].value_counts(dropna=False).to_string()
    )

    lines.append("\n5. PROPOSED RESEARCH LABEL DISTRIBUTION")
    lines.append(
        df["proposed_research_label"]
        .value_counts(dropna=False)
        .to_string()
    )

    lines.append("\n6. ORIGINAL LABEL VS PROPOSED LABEL")
    lines.append(
        pd.crosstab(
            df["original_label"],
            df["proposed_research_label"],
            dropna=False,
        ).to_string()
    )

    # Original HATE changed to NON_HATE
    changed_to_non_hate = (
        df["original_label"].str.strip().str.upper().eq("HATE")
        & df["proposed_research_label"]
        .str.strip()
        .str.upper()
        .eq("NON_HATE")
    )

    lines.append("\n7. ORIGINAL HATE -> PROPOSED NON_HATE")
    lines.append(
        f"Records requiring targeted review: "
        f"{changed_to_non_hate.sum()}"
    )

    lines.append(
        "Record IDs: "
        f"{df.loc[changed_to_non_hate, 'record_id'].tolist()}"
    )

    # Script types
    lines.append("\n8. SCRIPT TYPE DISTRIBUTION")
    lines.append(
        df["script_type"].value_counts(dropna=False).to_string()
    )

    # Confidence and review status
    lines.append("\n9. CONFIDENCE DISTRIBUTION")
    lines.append(
        df["confidence"].value_counts(dropna=False).to_string()
    )

    lines.append("\n10. REVIEW STATUS DISTRIBUTION")
    lines.append(
        df["review_status"].value_counts(dropna=False).to_string()
    )

    # Empty proposed labels
    empty_labels = (
        df["proposed_research_label"]
        .astype(str)
        .str.strip()
        .eq("")
    )

    lines.append("\n11. EMPTY PROPOSED LABELS")
    lines.append(f"Records with empty proposed labels: {empty_labels.sum()}")

    return "\n".join(lines)


def main():
    df = load_dataset()

    report = build_audit_report(df)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(report)
    print(f"\nAudit report saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()