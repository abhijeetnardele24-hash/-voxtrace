"""Domain models for deterministic, timestamp-grounded speech analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import math
from typing import Any


class FindingType(StrEnum):
    RUSHED_DELIVERY = "rushed_delivery"
    EXCESSIVE_PAUSE = "excessive_pause"
    MONOTONE_DELIVERY = "monotone_delivery"
    LOW_ENERGY = "low_energy"
    LOW_CLARITY = "low_clarity"


@dataclass(frozen=True, slots=True)
class FeatureWindow:
    """Acoustic measurements for a bounded speech interval.

    Values must originate from the extraction pipeline. The scoring engine never
    invents values or treats missing values as evidence.
    """

    start_seconds: float
    end_seconds: float
    speech_rate_wpm: float | None = None
    pause_seconds: float | None = None
    pitch_variation_semitones: float | None = None
    mean_f0_hz: float | None = None
    energy_db: float | None = None
    spectral_centroid_hz: float | None = None
    spectral_rolloff_hz: float | None = None
    spectral_flatness: float | None = None
    zero_crossing_rate: float | None = None
    mfcc_means: tuple[float, ...] | None = None
    clarity_score: float | None = None

    def __post_init__(self) -> None:
        if self.start_seconds < 0:
            raise ValueError("start_seconds cannot be negative")
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds")
        if self.speech_rate_wpm is not None and self.speech_rate_wpm < 0:
            raise ValueError("speech_rate_wpm cannot be negative")
        if self.pause_seconds is not None and self.pause_seconds < 0:
            raise ValueError("pause_seconds cannot be negative")
        if self.pitch_variation_semitones is not None and self.pitch_variation_semitones < 0:
            raise ValueError("pitch_variation_semitones cannot be negative")
        if self.clarity_score is not None and not 0 <= self.clarity_score <= 1:
            raise ValueError("clarity_score must be between 0 and 1")
        numeric_values = (
            self.start_seconds,
            self.end_seconds,
            self.speech_rate_wpm,
            self.pause_seconds,
            self.pitch_variation_semitones,
            self.mean_f0_hz,
            self.energy_db,
            self.spectral_centroid_hz,
            self.spectral_rolloff_hz,
            self.spectral_flatness,
            self.zero_crossing_rate,
            self.clarity_score,
        )
        if any(value is not None and not math.isfinite(value) for value in numeric_values):
            raise ValueError("feature measurements must be finite")
        if self.mean_f0_hz is not None and self.mean_f0_hz <= 0:
            raise ValueError("mean_f0_hz must be positive")
        if self.spectral_centroid_hz is not None and self.spectral_centroid_hz < 0:
            raise ValueError("spectral_centroid_hz cannot be negative")
        if self.spectral_rolloff_hz is not None and self.spectral_rolloff_hz < 0:
            raise ValueError("spectral_rolloff_hz cannot be negative")
        if self.spectral_flatness is not None and not 0 <= self.spectral_flatness <= 1:
            raise ValueError("spectral_flatness must be between 0 and 1")
        if self.zero_crossing_rate is not None and not 0 <= self.zero_crossing_rate <= 1:
            raise ValueError("zero_crossing_rate must be between 0 and 1")
        if self.mfcc_means is not None:
            if not 1 <= len(self.mfcc_means) <= 40:
                raise ValueError("mfcc_means must contain between 1 and 40 coefficients")
            if not all(math.isfinite(value) for value in self.mfcc_means):
                raise ValueError("MFCC measurements must be finite")


@dataclass(frozen=True, slots=True)
class ReferenceProfile:
    """Explicit scoring thresholds for one rubric and speaking context."""

    target_rate_min_wpm: float = 130.0
    target_rate_max_wpm: float = 170.0
    target_pause_max_seconds: float = 1.4
    target_pitch_variation_min_semitones: float = 1.5
    target_energy_min_db: float = -28.0
    target_clarity_min: float = 0.70

    def __post_init__(self) -> None:
        if self.target_rate_min_wpm >= self.target_rate_max_wpm:
            raise ValueError("minimum target rate must be lower than maximum target rate")
        if self.target_pause_max_seconds <= 0:
            raise ValueError("target pause maximum must be positive")
        if self.target_pitch_variation_min_semitones < 0:
            raise ValueError("target pitch variation minimum cannot be negative")
        if not 0 <= self.target_clarity_min <= 1:
            raise ValueError("target clarity minimum must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class Finding:
    """A timestamped issue with its measured causal evidence."""

    finding_type: FindingType
    start_seconds: float
    end_seconds: float
    severity: float
    evidence: str
    practice_action: str

    def __post_init__(self) -> None:
        if self.end_seconds <= self.start_seconds:
            raise ValueError("finding end must be after its start")
        if not 0 <= self.severity <= 1:
            raise ValueError("severity must be between 0 and 1")

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["finding_type"] = self.finding_type.value
        return payload


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """The serializable output returned to the dashboard."""

    overall_score: float
    dimension_scores: dict[str, float]
    findings: tuple[Finding, ...]
    scoring_profile: ReferenceProfile

    def as_dict(self) -> dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "dimension_scores": self.dimension_scores,
            "findings": [finding.as_dict() for finding in self.findings],
            "scoring_profile": asdict(self.scoring_profile),
        }
