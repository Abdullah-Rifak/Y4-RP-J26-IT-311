import csv
from pathlib import Path
from collections import Counter

# Locate the dataset relative to this script
project_dir = Path(__file__).resolve().parent.parent
dataset_path = project_dir / "data" / "tamil_offensive_full_dev.csv"

# Read the tab-separated file; it has no header row
with dataset_path.open("r", encoding="utf-8-sig", newline="") as file:
    reader = csv.reader(file, delimiter="\t")

    # Assign our own column names
    rows = []

    for row in reader:
        if len(row) >= 2:
            comment = row[0].strip()
            label = row[1].strip()

            rows.append({
                "comment": comment,
                "label": label
            })

print("COLUMN NAMES:")
print(["comment", "label"])

print("\nTOTAL RECORDS:")
print(len(rows))

print("\nFIRST 5 RECORDS:")
for row in rows[:5]:
    print(row)

print("\nLAST 5 RECORDS:")
for row in rows[-5:]:
    print(row)

print("\nLABEL DISTRIBUTION:")
label_counts = Counter(row["label"] for row in rows)

for label, count in label_counts.most_common():
    percentage = (count / len(rows)) * 100
    print(f"{label}: {count} records ({percentage:.2f}%)")