"""Transparent scoring rules for timestamp-grounded delivery feedback."""

from __future__ import annotations

from collections.abc import Iterable

from .domain import AnalysisResult, FeatureWindow, Finding, FindingType, ReferenceProfile

_DIMENSION_WEIGHTS = {
    "pace_and_pauses": 0.30,
    "prosody": 0.25,
    "energy": 0.25,
    "clarity": 0.20,
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(value, high))


def _mean(values: Iterable[float]) -> float | None:
    items = tuple(values)
    return sum(items) / len(items) if items else None


def _score_against_floor(value: float | None, floor: float) -> float | None:
    if value is None:
        return None
    if floor == 0:
        return 100.0
    return round(100.0 * _clamp(value / floor), 1)


def _score_minimum_with_margin(
    value: float | None, minimum: float, degradation_margin: float
) -> float | None:
    """Score a measurement that must remain at or above a threshold.

    This form is used for decibels because a direct ratio is invalid when the
    threshold is negative. The margin expresses where the score reaches zero;
    it is a transparent UI scoring rule, not a probability estimate.
    """

    if value is None:
        return None
    if value >= minimum:
        return 100.0
    return round(100.0 * (1.0 - _clamp((minimum - value) / degradation_margin)), 1)


def _score_rate(value: float | None, profile: ReferenceProfile) -> float | None:
    if value is None:
        return None
    if profile.target_rate_min_wpm <= value <= profile.target_rate_max_wpm:
        return 100.0
    deviation = (
        profile.target_rate_min_wpm - value
        if value < profile.target_rate_min_wpm
        else value - profile.target_rate_max_wpm
    )
    tolerance = profile.target_rate_max_wpm - profile.target_rate_min_wpm
    return round(100.0 * (1.0 - _clamp(deviation / tolerance)), 1)


def _score_pause(value: float | None, profile: ReferenceProfile) -> float | None:
    if value is None:
        return None
    if value <= profile.target_pause_max_seconds:
        return 100.0
    return round(
        100.0 * (1.0 - _clamp((value - profile.target_pause_max_seconds) / profile.target_pause_max_seconds)),
        1,
    )


def _available_average(scores: Iterable[float | None]) -> float | None:
    return _mean(score for score in scores if score is not None)


def _severity(actual: float, expected: float) -> float:
    """Return a bounded relative deviation without pretending it is probability."""

    denominator = max(abs(expected), 1.0)
    return round(_clamp(abs(actual - expected) / denominator), 2)


def _make_finding(
    window: FeatureWindow,
    finding_type: FindingType,
    severity: float,
    evidence: str,
    practice_action: str,
) -> Finding:
    return Finding(
        finding_type=finding_type,
        start_seconds=window.start_seconds,
        end_seconds=window.end_seconds,
        severity=severity,
        evidence=evidence,
        practice_action=practice_action,
    )


def detect_findings(
    windows: Iterable[FeatureWindow], profile: ReferenceProfile
) -> tuple[Finding, ...]:
    """Detect only rule-supported issues for windows with measured features."""

    findings: list[Finding] = []
    for window in windows:
        if (
            window.speech_rate_wpm is not None
            and window.speech_rate_wpm > profile.target_rate_max_wpm
        ):
            findings.append(
                _make_finding(
                    window,
                    FindingType.RUSHED_DELIVERY,
                    _severity(window.speech_rate_wpm, profile.target_rate_max_wpm),
                    (
                        f"Speech rate measured {window.speech_rate_wpm:.0f} WPM; "
                        f"the selected profile caps this segment at "
                        f"{profile.target_rate_max_wpm:.0f} WPM."
                    ),
                    "Rerecord this sentence more slowly and pause after its key claim.",
                )
            )
        if (
            window.pause_seconds is not None
            and window.pause_seconds > profile.target_pause_max_seconds
        ):
            findings.append(
                _make_finding(
                    window,
                    FindingType.EXCESSIVE_PAUSE,
                    _severity(window.pause_seconds, profile.target_pause_max_seconds),
                    (
                        f"Pause measured {window.pause_seconds:.2f}s; "
                        f"the selected profile caps an unplanned pause at "
                        f"{profile.target_pause_max_seconds:.2f}s."
                    ),
                    "Practice linking this phrase to the next thought with a shorter transition.",
                )
            )
        if (
            window.pitch_variation_semitones is not None
            and window.pitch_variation_semitones < profile.target_pitch_variation_min_semitones
        ):
            findings.append(
                _make_finding(
                    window,
                    FindingType.MONOTONE_DELIVERY,
                    _severity(
                        window.pitch_variation_semitones,
                        profile.target_pitch_variation_min_semitones,
                    ),
                    (
                        f"Pitch variation measured {window.pitch_variation_semitones:.2f} semitones; "
                        f"the selected profile targets at least "
                        f"{profile.target_pitch_variation_min_semitones:.2f}."
                    ),
                    "Stress one content word and vary pitch across the sentence.",
                )
            )
        if window.energy_db is not None and window.energy_db < profile.target_energy_min_db:
            findings.append(
                _make_finding(
                    window,
                    FindingType.LOW_ENERGY,
                    _severity(window.energy_db, profile.target_energy_min_db),
                    (
                        f"Energy measured {window.energy_db:.1f} dB; "
                        f"the selected profile targets at least {profile.target_energy_min_db:.1f} dB."
                    ),
                    "Move closer to the microphone and deliver this line with supported breath.",
                )
            )
        if window.clarity_score is not None and window.clarity_score < profile.target_clarity_min:
            findings.append(
                _make_finding(
                    window,
                    FindingType.LOW_CLARITY,
                    _severity(window.clarity_score, profile.target_clarity_min),
                    (
                        f"Clarity proxy measured {window.clarity_score:.2f}; "
                        f"the selected profile targets at least {profile.target_clarity_min:.2f}."
                    ),
                    "Slow down slightly and articulate consonant endings in this phrase.",
                )
            )
    return tuple(sorted(findings, key=lambda item: (item.start_seconds, item.finding_type.value)))


def analyze_windows(
    windows: Iterable[FeatureWindow], profile: ReferenceProfile | None = None
) -> AnalysisResult:
    """Calculate evidence-backed scores from pre-extracted feature windows."""

    profile = profile or ReferenceProfile()
    window_list = tuple(windows)
    if not window_list:
        raise ValueError("at least one feature window is required")

    pace_scores = [
        score
        for window in window_list
        for score in (
            _score_rate(window.speech_rate_wpm, profile),
            _score_pause(window.pause_seconds, profile),
        )
        if score is not None
    ]
    dimension_scores: dict[str, float] = {}
    pace_score = _mean(pace_scores)
    if pace_score is not None:
        dimension_scores["pace_and_pauses"] = round(pace_score, 1)

    prosody_score = _available_average(
        _score_against_floor(window.pitch_variation_semitones, profile.target_pitch_variation_min_semitones)
        for window in window_list
    )
    if prosody_score is not None:
        dimension_scores["prosody"] = round(prosody_score, 1)

    energy_score = _available_average(
        _score_minimum_with_margin(
            window.energy_db,
            profile.target_energy_min_db,
            degradation_margin=12.0,
        )
        for window in window_list
    )
    if energy_score is not None:
        dimension_scores["energy"] = round(energy_score, 1)

    clarity_score = _available_average(
        _score_against_floor(window.clarity_score, profile.target_clarity_min)
        for window in window_list
    )
    if clarity_score is not None:
        dimension_scores["clarity"] = round(clarity_score, 1)

    weighted_scores = [
        (score * _DIMENSION_WEIGHTS[name], _DIMENSION_WEIGHTS[name])
        for name, score in dimension_scores.items()
    ]
    if not weighted_scores:
        raise ValueError("feature windows do not contain scoreable measurements")
    weighted_total = sum(score for score, _ in weighted_scores)
    present_weight = sum(weight for _, weight in weighted_scores)
    overall_score = round(weighted_total / present_weight, 1)

    return AnalysisResult(
        overall_score=overall_score,
        dimension_scores=dimension_scores,
        findings=detect_findings(window_list, profile),
        scoring_profile=profile,
    )
