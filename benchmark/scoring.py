"""Transparent per-dimension scoring for benchmark predictions."""

from __future__ import annotations

from typing import Any

from core.metrics import pair_metrics, set_metrics


def score_prediction(
    *,
    structural: list[str],
    minimal: list[str],
    interactions: list[list[str]],
    provenance: list[list[str]],
    ground_truth: Any,
) -> dict[str, Any]:
    structural_score = set_metrics(structural, ground_truth.structural_slice)
    minimal_score = set_metrics(minimal, ground_truth.minimal_slice)
    provenance_score = pair_metrics(provenance, ground_truth.expected_provenance)
    interaction_score = pair_metrics(interactions, ground_truth.expected_interactions)
    return {
        "structural_slice": structural_score,
        "minimal_slice": minimal_score,
        "interaction": interaction_score,
        "provenance": provenance_score,
        "slice_reduction_ratio": 1.0 - (len(minimal) / max(1, len(structural))),
        "pass": all(
            (
                structural_score["exact_match"],
                minimal_score["exact_match"],
                provenance_score["exact_match"],
                interaction_score["exact_match"],
            )
        ),
    }


def aggregate_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"scenario_count": 0}
    dimensions = ("structural_slice", "minimal_slice", "interaction", "provenance")
    return {
        "scenario_count": len(rows),
        "passed": sum(bool(row.get("pass")) for row in rows),
        "dimensions": {
            dimension: {
                "precision": sum(row[dimension]["precision"] for row in rows) / len(rows),
                "recall": sum(row[dimension]["recall"] for row in rows) / len(rows),
                "exact_match_rate": sum(bool(row[dimension]["exact_match"]) for row in rows)
                / len(rows),
            }
            for dimension in dimensions
        },
    }
