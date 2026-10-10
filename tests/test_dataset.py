from pathlib import Path

import pytest

from backend.app.dataset import RecordingManifest, load_manifests_jsonl, split_by_speaker


def _manifest(recording_id: str, speaker_id: str, variant_type: str = "rushed") -> dict[str, object]:
    labels: list[dict[str, object]] = []
    if variant_type != "reference":
        labels = [
            {
                "finding_type": "rushed_delivery",
                "start_seconds": 0.5,
                "end_seconds": 1.5,
                "severity": 0.7,
                "reviewer_status": "reviewed",
            }
        ]
    return {
        "recording_id": recording_id,
        "script_id": "script-1",
        "speaker_id": speaker_id,
        "variant_type": variant_type,
        "duration_seconds": 3,
        "licence": "CC0",
        "consent_record": f"consent:{speaker_id}",
        "transcript": "A short test transcript.",
        "labels": labels,
    }


def test_rejects_label_outside_recording_duration() -> None:
    data = _manifest("recording-1", "speaker-a")
    data["labels"] = [
        {
            "finding_type": "rushed_delivery",
            "start_seconds": 1,
            "end_seconds": 4,
            "severity": 0.7,
            "reviewer_status": "reviewed",
        }
    ]

    with pytest.raises(ValueError, match="exceeds recording duration"):
        RecordingManifest.from_mapping(data)


def test_reference_recording_cannot_have_intentional_flaw_labels() -> None:
    data = _manifest("recording-1", "speaker-a", "reference")
    data["labels"] = [
        {
            "finding_type": "low_energy",
            "start_seconds": 0,
            "end_seconds": 1,
            "severity": 0.5,
            "reviewer_status": "pending",
        }
    ]

    with pytest.raises(ValueError, match="reference recordings"):
        RecordingManifest.from_mapping(data)


def test_split_by_speaker_prevents_leakage() -> None:
    manifests = tuple(
        RecordingManifest.from_mapping(data)
        for data in (
            _manifest("recording-a", "speaker-a"),
            _manifest("recording-b", "speaker-b"),
            _manifest("recording-c", "speaker-c"),
        )
    )

    training, held_out = split_by_speaker(manifests)

    assert {item.speaker_id for item in training}.isdisjoint(
        {item.speaker_id for item in held_out}
    )
    assert {item.speaker_id for item in held_out} == {"speaker-c"}


def test_load_manifests_rejects_duplicate_recording_ids(tmp_path: Path) -> None:
    source = tmp_path / "manifests.jsonl"
    line = (
        '{"recording_id":"same","script_id":"s","speaker_id":"speaker-a",'
        '"variant_type":"reference","duration_seconds":2,"licence":"CC0",'
        '"consent_record":"recorded","transcript":"test","labels":[]}'
    )
    source.write_text(f"{line}\n{line}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate recording_id"):
        load_manifests_jsonl(source)
