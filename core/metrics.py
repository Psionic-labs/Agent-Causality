"""Transparent set and pair metrics shared by benchmarks and the explorer."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def set_metrics(predicted: Iterable[str], expected: Iterable[str]) -> dict[str, Any]:
    predicted_set, expected_set = set(predicted), set(expected)
    true_positive = len(predicted_set & expected_set)
    false_positive = len(predicted_set - expected_set)
    false_negative = len(expected_set - predicted_set)
    return {
        "precision": true_positive / len(predicted_set)
        if predicted_set
        else (1.0 if not expected_set else 0.0),
        "recall": true_positive / len(expected_set) if expected_set else 1.0,
        "exact_match": predicted_set == expected_set,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "missing": sorted(expected_set - predicted_set),
        "unexpected": sorted(predicted_set - expected_set),
    }


def pair_metrics(
    predicted: Iterable[Iterable[str]], expected: Iterable[Iterable[str]]
) -> dict[str, Any]:
    def canonical(rows: Iterable[Iterable[str]]) -> set[tuple[str, ...]]:
        return {tuple(sorted(map(str, row))) for row in rows}

    result = set_metrics(
        ("|".join(p) for p in canonical(predicted)), ("|".join(p) for p in canonical(expected))
    )
    result["false_interaction_rate"] = result["false_positive"] / max(
        1, result["true_positive"] + result["false_positive"]
    )
    return result
