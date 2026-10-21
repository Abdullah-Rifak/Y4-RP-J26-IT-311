"""Small exact statistics for the reviewer study. Pure Python."""
from evaluation.metrics import _ranks


def wilcoxon_exact(diffs: list[float]) -> dict:
    """Two-sided exact Wilcoxon signed-rank test on paired differences.
    Zero differences are dropped. Tied |differences| share average ranks; the exact null
    distribution is built by counting every sign pattern (ranks doubled so they stay whole)."""
    d = [x for x in diffs if x != 0]
    n = len(d)
    if n == 0:
        return {"n": 0, "w_plus": None, "p": None}
    ranks = _ranks([abs(x) for x in d])
    w_plus = sum(r for r, x in zip(ranks, d) if x > 0)
    scaled = [int(round(r * 2)) for r in ranks]
    total = sum(scaled)
    ways = [0] * (total + 1)  # ways[s] = sign patterns whose positive ranks add to s/2
    ways[0] = 1
    for s in scaled:
        for t in range(total, s - 1, -1):
            ways[t] += ways[t - s]
    w = int(round(w_plus * 2))
    lower = sum(ways[: w + 1]) / 2 ** n
    upper = sum(ways[w:]) / 2 ** n
    return {"n": n, "w_plus": w_plus, "p": min(1.0, 2 * min(lower, upper))}


def min_possible_p(n: int) -> float:
    """Smallest two-sided exact p-value n non-zero paired differences can ever give."""
    return min(1.0, 2 / 2 ** n) if n > 0 else 1.0


def holm(pvalues: list[float | None]) -> list[float | None]:
    """Holm step-down adjustment for several tests. None stays None."""
    idx = sorted((i for i, p in enumerate(pvalues) if p is not None), key=lambda i: pvalues[i])
    m = len(idx)
    out: list[float | None] = [None] * len(pvalues)
    running = 0.0
    for rank, i in enumerate(idx):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        out[i] = running
    return out
