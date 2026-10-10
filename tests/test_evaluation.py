from backend.app.dataset import TemporalLabel
from backend.app.domain import Finding, FindingType
from backend.app.evaluation import evaluate_temporal_grounding, interval_iou


def _finding(start: float, end: float, finding_type: FindingType) -> Finding:
    return Finding(
        finding_type=finding_type,
        start_seconds=start,
        end_seconds=end,
        severity=0.5,
        evidence="measured",
        practice_action="practice",
    )


def _label(start: float, end: float, finding_type: FindingType) -> TemporalLabel:
    return TemporalLabel(
        finding_type=finding_type,
        start_seconds=start,
        end_seconds=end,
        severity=0.5,
        reviewer_status="reviewed",
    )


def test_interval_iou_is_exact_for_overlapping_intervals() -> None:
    assert interval_iou(
        _finding(0, 4, FindingType.RUSHED_DELIVERY),
        _label(2, 6, FindingType.RUSHED_DELIVERY),
    ) == 1 / 3


def test_temporal_evaluation_matches_each_label_once() -> None:
    report = evaluate_temporal_grounding(
        predictions=(
            _finding(0, 4, FindingType.RUSHED_DELIVERY),
            _finding(0.5, 4.5, FindingType.RUSHED_DELIVERY),
            _finding(7, 8, FindingType.LOW_ENERGY),
        ),
        labels=(
            _label(0, 4, FindingType.RUSHED_DELIVERY),
            _label(7, 8, FindingType.LOW_ENERGY),
        ),
    )

    rushed = report.by_category["rushed_delivery"]
    assert rushed.true_positives == 1
    assert rushed.false_positives == 1
    assert rushed.false_negatives == 0
    assert report.by_category["low_energy"].f1 == 1.0
    assert report.mean_matched_iou == 1.0
    assert report.macro_f1 == 0.8334
