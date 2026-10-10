"""Reproducible temporal-grounding evaluation for VoxTrace findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .dataset import TemporalLabel
from .domain import Finding, FindingType


class TimestampedFinding(Protocol):
    finding_type: FindingType
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True, slots=True)
class CategoryMetrics:
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    mean_matched_iou: float
    macro_f1: float
    by_category: dict[str, CategoryMetrics]


def interval_iou(left: TimestampedFinding, right: TimestampedFinding) -> float:
    """Return intersection-over-union of two time intervals."""

    overlap = max(
        0.0,
        min(left.end_seconds, right.end_seconds) - max(left.start_seconds, right.start_seconds),
    )
    union = max(left.end_seconds, right.end_seconds) - min(left.start_seconds, right.start_seconds)
    return overlap / union if union > 0 else 0.0


def _metric(tp: int, fp: int, fn: int) -> CategoryMetrics:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return CategoryMetrics(
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
    )


def evaluate_temporal_grounding(
    predictions: tuple[Finding, ...],
    labels: tuple[TemporalLabel, ...],
    minimum_iou: float = 0.5,
) -> EvaluationReport:
    """Evaluate predictions with one-to-one, same-category interval matching."""

    if not 0 < minimum_iou <= 1:
        raise ValueError("minimum_iou must be in (0, 1]")

    categories = sorted(
        {item.finding_type for item in predictions} | {item.finding_type for item in labels},
        key=lambda item: item.value,
    )
    per_category: dict[str, CategoryMetrics] = {}
    matched_ious: list[float] = []

    for category in categories:
        category_predictions = [
            item for item in predictions if item.finding_type == category
        ]
        remaining_labels = [item for item in labels if item.finding_type == category]
        matches = 0

        for prediction in category_predictions:
            candidate_index, candidate_iou = max(
                (
                    (index, interval_iou(prediction, label))
                    for index, label in enumerate(remaining_labels)
                ),
                default=(-1, 0.0),
                key=lambda item: item[1],
            )
            if candidate_index >= 0 and candidate_iou >= minimum_iou:
                remaining_labels.pop(candidate_index)
                matched_ious.append(candidate_iou)
                matches += 1

        per_category[category.value] = _metric(
            tp=matches,
            fp=len(category_predictions) - matches,
            fn=len(remaining_labels),
        )

    macro_f1 = (
        sum(metric.f1 for metric in per_category.values()) / len(per_category)
        if per_category
        else 0.0
    )
    return EvaluationReport(
        mean_matched_iou=round(sum(matched_ious) / len(matched_ious), 4)
        if matched_ious
        else 0.0,
        macro_f1=round(macro_f1, 4),
        by_category=per_category,
    )
