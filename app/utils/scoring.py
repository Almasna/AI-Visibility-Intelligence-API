from __future__ import annotations

import math


INTENT_SCORES = {
    "commercial": 1.0,
    "comparison": 1.0,
    "transactional": 0.9,
    "informational": 0.6,
}


def calculate_opportunity_score(
    search_volume: int,
    competitive_difficulty: float,
    domain_visible: bool | None,
    intent: str,
    max_volume: int,
) -> float:
    """Return a deterministic opportunity score in the inclusive range 0..1."""
    safe_volume = max(0, int(search_volume))
    safe_max_volume = max(0, int(max_volume))
    if safe_max_volume == 0:
        volume_score = 0.0
    else:
        volume_score = math.log1p(min(safe_volume, safe_max_volume)) / math.log1p(
            safe_max_volume
        )

    difficulty = min(100.0, max(0.0, float(competitive_difficulty)))
    difficulty_score = 1.0 - difficulty / 100.0
    visibility_gap_score = (
        1.0 if domain_visible is False else 0.0 if domain_visible is True else 0.5
    )
    intent_score = INTENT_SCORES.get(intent, INTENT_SCORES["informational"])

    score = (
        0.35 * volume_score
        + 0.25 * difficulty_score
        + 0.25 * visibility_gap_score
        + 0.15 * intent_score
    )
    return round(min(1.0, max(0.0, score)), 4)
