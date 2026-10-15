"""Stage 5 of 6: map an accumulated risk score to a recommended tier.

These thresholds are placeholders to tune on real threads. A tier is only ever a
recommendation: a human moderator makes the final decision.
"""

# Accumulated risk at or above a threshold recommends that tier (highest first).
TIER_THRESHOLDS = [
    ("high_severity_report", 6.0),
    ("flag", 3.0),
    ("warning", 1.0),
]

TIERS = ["none"] + [name for name, _ in sorted(TIER_THRESHOLDS, key=lambda t: t[1])]


def recommended_tier(risk: float) -> str:
    for name, threshold in TIER_THRESHOLDS:
        if risk >= threshold:
            return name
    return "none"


def next_tier(risk: float):
    """The nearest tier above the current risk as (name, threshold), or None."""
    higher = [(n, t) for n, t in TIER_THRESHOLDS if t > risk]
    return min(higher, key=lambda x: x[1]) if higher else None
