"""Validation and split utilities for the VoxTrace contrastive dataset."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .domain import FindingType

_ALLOWED_VARIANTS = {
    "reference",
    "near_perfect",
    "rushed",
    "excessive_pause",
    "monotone",
    "low_energy",
    "mixed_flaws",
}


@dataclass(frozen=True, slots=True)
class TemporalLabel:
    """A human-authored, reviewable label for one intentional delivery deviation."""

    finding_type: FindingType
    start_seconds: float
    end_seconds: float
    severity: float
    reviewer_status: str

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "TemporalLabel":
        try:
            label = cls(
                finding_type=FindingType(data["finding_type"]),
                start_seconds=float(data["start_seconds"]),
                end_seconds=float(data["end_seconds"]),
                severity=float(data["severity"]),
                reviewer_status=str(data["reviewer_status"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"invalid temporal label: {error}") from error
        if label.start_seconds < 0 or label.end_seconds <= label.start_seconds:
            raise ValueError("label timestamps must be non-negative and increasing")
        if not 0 <= label.severity <= 1:
            raise ValueError("label severity must be between 0 and 1")
        if label.reviewer_status not in {"pending", "reviewed"}:
            raise ValueError("reviewer_status must be pending or reviewed")
        return label


@dataclass(frozen=True, slots=True)
class RecordingManifest:
    """Metadata required to publish or evaluate one contrastive recording."""

    recording_id: str
    script_id: str
    speaker_id: str
    variant_type: str
    duration_seconds: float
    licence: str
    consent_record: str
    transcript: str
    labels: tuple[TemporalLabel, ...]

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "RecordingManifest":
        required = (
            "recording_id",
            "script_id",
            "speaker_id",
            "variant_type",
            "duration_seconds",
            "licence",
            "consent_record",
            "transcript",
            "labels",
        )
        missing = [field for field in required if field not in data]
        if missing:
            raise ValueError(f"recording is missing required fields: {', '.join(missing)}")

        try:
            manifest = cls(
                recording_id=str(data["recording_id"]).strip(),
                script_id=str(data["script_id"]).strip(),
                speaker_id=str(data["speaker_id"]).strip(),
                variant_type=str(data["variant_type"]).strip(),
                duration_seconds=float(data["duration_seconds"]),
                licence=str(data["licence"]).strip(),
                consent_record=str(data["consent_record"]).strip(),
                transcript=str(data["transcript"]).strip(),
                labels=tuple(TemporalLabel.from_mapping(item) for item in data["labels"]),
            )
        except (TypeError, ValueError) as error:
            raise ValueError(f"invalid recording manifest: {error}") from error

        if not all((manifest.recording_id, manifest.script_id, manifest.speaker_id)):
            raise ValueError("recording_id, script_id, and speaker_id cannot be blank")
        if manifest.variant_type not in _ALLOWED_VARIANTS:
            raise ValueError(f"unsupported variant_type: {manifest.variant_type}")
        if manifest.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if not manifest.licence:
            raise ValueError("licence cannot be blank")
        if not manifest.consent_record:
            raise ValueError("consent_record cannot be blank")
        if not manifest.transcript:
            raise ValueError("transcript cannot be blank")
        if manifest.variant_type == "reference" and manifest.labels:
            raise ValueError("reference recordings must not contain intentional flaw labels")
        if manifest.variant_type != "reference" and not manifest.labels:
            raise ValueError("non-reference recordings require at least one temporal label")
        for label in manifest.labels:
            if label.end_seconds > manifest.duration_seconds:
                raise ValueError(
                    f"label ending at {label.end_seconds}s exceeds recording duration "
                    f"of {manifest.duration_seconds}s"
                )
        return manifest


def load_manifests_jsonl(path: Path) -> tuple[RecordingManifest, ...]:
    """Read manifests while preserving line-specific validation failures."""

    manifests: list[RecordingManifest] = []
    seen_ids: set[str] = set()
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            manifest = RecordingManifest.from_mapping(json.loads(raw_line))
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError(f"{path}:{line_number}: {error}") from error
        if manifest.recording_id in seen_ids:
            raise ValueError(f"{path}:{line_number}: duplicate recording_id {manifest.recording_id}")
        seen_ids.add(manifest.recording_id)
        manifests.append(manifest)
    if not manifests:
        raise ValueError(f"{path}: no recording manifests found")
    return tuple(manifests)


def split_by_speaker(
    manifests: tuple[RecordingManifest, ...], holdout_speaker_count: int = 1
) -> tuple[tuple[RecordingManifest, ...], tuple[RecordingManifest, ...]]:
    """Create a deterministic held-out-speaker split without leakage."""

    speakers = sorted({manifest.speaker_id for manifest in manifests})
    if holdout_speaker_count <= 0 or holdout_speaker_count >= len(speakers):
        raise ValueError("holdout_speaker_count must be between 1 and speaker_count - 1")
    held_out_speakers = set(speakers[-holdout_speaker_count:])
    training = tuple(manifest for manifest in manifests if manifest.speaker_id not in held_out_speakers)
    held_out = tuple(manifest for manifest in manifests if manifest.speaker_id in held_out_speakers)
    return training, held_out
