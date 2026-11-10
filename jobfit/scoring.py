from __future__ import annotations

from .config import WEIGHTS

BANDS = [
    (90, "Exceptional fit"),
    (80, "Strong fit"),
    (70, "Good fit"),
    (60, "Moderate fit"),
    (50, "Weak fit"),
    (0, "Poor fit"),
]


def weighted_score(scores: dict) -> float:
    total = 0.0
    for key, weight in WEIGHTS.items():
        s = max(0, min(100, int(scores.get(key, {}).get("score", 0))))
        total += s * weight / 100
    return round(total, 1)


def band(score: float) -> str:
    for floor, label in BANDS:
        if score >= floor:
            return label
    return BANDS[-1][1]
