import re
import collections
import pandas as pd

dataset_path = "data/tamil_offensive_full_dev.csv"

df = pd.read_csv(
    dataset_path,
    sep="\t",
    encoding="utf-8-sig",
    header=None,
    usecols=[0, 1],
    names=["comment", "label"],
)

pattern = re.compile(r"([A-Za-z])\1{2,}", re.IGNORECASE)

counts = collections.Counter()
examples = collections.defaultdict(list)

for comment in df["comment"].dropna().astype(str):
    for match in pattern.finditer(comment):
        word = match.group().lower()
        counts[word] += 1

        if len(examples[word]) < 2:
            examples[word].append(comment)

print("Unique repeated-letter forms:", len(counts))
print("\nTop 20 forms:")

for word, count in counts.most_common(20):
    print(f"{word}: {count} occurrence(s)")
    print(f"  Example: {examples[word][0][:120]}")
    