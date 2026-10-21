"""Metric functions named in the proposal (section 3.4). Pure Python, no extra packages."""
from math import sqrt


def _ranks(values: list[float]) -> list[float]:
    """Rank 1 = smallest. Tied values share the average of the ranks they cover."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(a: dict, b: dict) -> float | None:
    """Spearman rank correlation of two user->score dicts. A user missing from one counts as 0.
    Returns None when it is undefined (fewer than 2 users, or one side has no variation)."""
    users = sorted(set(a) | set(b))
    if len(users) < 2:
        return None
    ra = _ranks([a.get(u, 0.0) for u in users])
    rb = _ranks([b.get(u, 0.0) for u in users])
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra)
    vb = sum((y - mb) ** 2 for y in rb)
    if va == 0 or vb == 0:
        return None
    return cov / sqrt(va * vb)


def ranking(scores: dict) -> list[str]:
    """Users from highest to lowest score (ties broken by user id so output is stable)."""
    return sorted(scores, key=lambda u: (-scores[u], u))


def top_k_overlap(a: dict, b: dict, k: int) -> float:
    """Share of the top k users that both rankings agree on (0 to 1)."""
    return len(set(ranking(a)[:k]) & set(ranking(b)[:k])) / k


def tier_report(predicted: dict, expected: dict, tiers: list[str]) -> dict:
    """Compare predicted tiers with expert-labelled ones. Users missing from `predicted` count
    as 'none'. Returns agreement, per-tier precision/recall, and the confusion matrix."""
    users = sorted(expected)
    pred = {u: predicted.get(u, "none") for u in users}
    agree = sum(1 for u in users if pred[u] == expected[u])
    per_tier = {}
    for t in tiers:
        tp = sum(1 for u in users if pred[u] == t and expected[u] == t)
        n_pred = sum(1 for u in users if pred[u] == t)
        n_exp = sum(1 for u in users if expected[u] == t)
        per_tier[t] = {
            "precision": tp / n_pred if n_pred else None,
            "recall": tp / n_exp if n_exp else None,
            "support": n_exp,
        }
    confusion = {e: {p: 0 for p in tiers} for e in tiers}
    for u in users:
        confusion[expected[u]][pred[u]] += 1
    return {"n": len(users), "agreement": agree / len(users) if users else None,
            "per_tier": per_tier, "confusion": confusion}


def is_monotonic(series: list[float], tol: float = 1e-9) -> bool:
    """True if the series never goes down: the 'risk only rises with repeated offences' check."""
    return all(b >= a - tol for a, b in zip(series, series[1:]))
