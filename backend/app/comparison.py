"""Contrastive baseline comparison for timestamped acoustic feature windows."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median
from typing import Iterable

from .domain import AnalysisResult, FeatureWindow, ReferenceProfile
from .scoring import analyze_windows

_COMPARABLE_FEATURES = (
    "speech_rate_wpm",
    "pause_seconds",
    "pitch_variation_semitones",
    "mean_f0_hz",
    "energy_db",
    "spectral_centroid_hz",
    "spectral_rolloff_hz",
    "spectral_flatness",
    "zero_crossing_rate",
    "clarity_score",
)


@dataclass(frozen=True, slots=True)
class WindowComparison:
    start_seconds: float
    end_seconds: float
    reference_start_seconds: float
    reference_end_seconds: float
    observed: dict[str, float]
    reference: dict[str, float]
    deltas: dict[str, float]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ContrastiveAnalysis:
    reference_profile: ReferenceProfile
    analysis: AnalysisResult
    comparisons: tuple[WindowComparison, ...]
    data_completeness: dict[str, bool]

    def as_dict(self) -> dict[str, object]:
        return {
            "reference_profile": asdict(self.reference_profile),
            "analysis": self.analysis.as_dict(),
            "comparisons": [item.as_dict() for item in self.comparisons],
            "data_completeness": self.data_completeness,
        }


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def derive_reference_profile(reference_windows: Iterable[FeatureWindow]) -> ReferenceProfile:
    """Build robust thresholds from a measured ideal-delivery recording."""

    windows = tuple(reference_windows)
    if not windows:
        raise ValueError("at least one reference window is required")
    defaults = ReferenceProfile()
    rates = [item.speech_rate_wpm for item in windows if item.speech_rate_wpm is not None]
    pauses = [item.pause_seconds for item in windows if item.pause_seconds is not None]
    pitch = [
        item.pitch_variation_semitones
        for item in windows
        if item.pitch_variation_semitones is not None
    ]
    energy = [item.energy_db for item in windows if item.energy_db is not None]
    clarity = [item.clarity_score for item in windows if item.clarity_score is not None]
    rate_center = median(rates) if rates else None
    return ReferenceProfile(
        target_rate_min_wpm=max(1.0, round(rate_center * 0.85, 2))
        if rate_center is not None
        else defaults.target_rate_min_wpm,
        target_rate_max_wpm=round(rate_center * 1.15, 2)
        if rate_center is not None
        else defaults.target_rate_max_wpm,
        target_pause_max_seconds=round(_percentile(pauses, 0.9) or defaults.target_pause_max_seconds, 2),
        target_pitch_variation_min_semitones=round(
            _percentile(pitch, 0.2) or defaults.target_pitch_variation_min_semitones, 2
        ),
        target_energy_min_db=round(_percentile(energy, 0.2) or defaults.target_energy_min_db, 2),
        target_clarity_min=round(_percentile(clarity, 0.2) or defaults.target_clarity_min, 2),
    )


def _nearest_reference(
    target: FeatureWindow,
    target_duration: float,
    references: tuple[FeatureWindow, ...],
    reference_duration: float,
) -> FeatureWindow:
    target_fraction = ((target.start_seconds + target.end_seconds) / 2) / target_duration
    expected_reference_time = target_fraction * reference_duration
    return min(
        references,
        key=lambda item: abs(((item.start_seconds + item.end_seconds) / 2) - expected_reference_time),
    )


def compare_windows(
    reference_windows: Iterable[FeatureWindow], target_windows: Iterable[FeatureWindow]
) -> ContrastiveAnalysis:
    references = tuple(reference_windows)
    targets = tuple(target_windows)
    if not references or not targets:
        raise ValueError("reference and target windows are required")
    reference_duration = max(item.end_seconds for item in references)
    target_duration = max(item.end_seconds for item in targets)
    comparisons: list[WindowComparison] = []
    for target in targets:
        reference = _nearest_reference(
            target, target_duration, references, reference_duration
        )
        observed: dict[str, float] = {}
        baseline: dict[str, float] = {}
        deltas: dict[str, float] = {}
        for name in _COMPARABLE_FEATURES:
            observed_value = getattr(target, name)
            reference_value = getattr(reference, name)
            if observed_value is None or reference_value is None:
                continue
            observed[name] = round(float(observed_value), 4)
            baseline[name] = round(float(reference_value), 4)
            deltas[name] = round(float(observed_value - reference_value), 4)
        comparisons.append(
            WindowComparison(
                start_seconds=target.start_seconds,
                end_seconds=target.end_seconds,
                reference_start_seconds=reference.start_seconds,
                reference_end_seconds=reference.end_seconds,
                observed=observed,
                reference=baseline,
                deltas=deltas,
            )
        )
    profile = derive_reference_profile(references)
    feature_names = {
        name
        for window in targets
        for name in _COMPARABLE_FEATURES
        if getattr(window, name) is not None
    }
    return ContrastiveAnalysis(
        reference_profile=profile,
        analysis=analyze_windows(targets, profile),
        comparisons=tuple(comparisons),
        data_completeness={name: name in feature_names for name in _COMPARABLE_FEATURES},
    )
