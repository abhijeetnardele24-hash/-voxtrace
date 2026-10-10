import json
from pathlib import Path

import pytest

from backend.cli import main


def _manifest_line(
    recording_id: str, speaker_id: str, reviewer_status: str = "reviewed"
) -> str:
    return json.dumps(
        {
            "recording_id": recording_id,
            "script_id": "script-a",
            "speaker_id": speaker_id,
            "variant_type": "rushed",
            "duration_seconds": 3,
            "licence": "CC0",
            "consent_record": "team-consent-log",
            "transcript": "A short example.",
            "labels": [
                {
                    "finding_type": "rushed_delivery",
                    "start_seconds": 0,
                    "end_seconds": 2,
                    "severity": 0.7,
                    "reviewer_status": reviewer_status,
                }
            ],
        }
    )


def test_cli_writes_dataset_summary(tmp_path: Path, monkeypatch) -> None:
    manifests = tmp_path / "manifests.jsonl"
    manifests.write_text(
        _manifest_line("a", "speaker-a") + "\n" + _manifest_line("b", "speaker-b") + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "summary.json"
    monkeypatch.setattr(
        "sys.argv",
        ["voxtrace", "dataset-summary", "--manifests", str(manifests), "--output", str(output)],
    )
    main()
    assert json.loads(output.read_text(encoding="utf-8"))["held_out_speakers"] == ["speaker-b"]


def test_cli_evaluates_predictions_within_each_recording(tmp_path: Path, monkeypatch) -> None:
    manifests = tmp_path / "manifests.jsonl"
    manifests.write_text(
        _manifest_line("train", "speaker-a")
        + "\n"
        + _manifest_line("held-out-1", "speaker-b")
        + "\n"
        + _manifest_line("held-out-2", "speaker-b")
        + "\n",
        encoding="utf-8",
    )
    predictions = tmp_path / "predictions.json"
    predictions.write_text(
        json.dumps(
            [
                {
                    "recording_id": "held-out-1",
                    "finding_type": "rushed_delivery",
                    "start_seconds": 0,
                    "end_seconds": 2,
                    "severity": 0.7,
                    "evidence": "Measured speech rate exceeded the reference threshold.",
                    "practice_action": "Rehearse once with deliberate phrase boundaries.",
                }
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "evaluation.json"
    markdown = tmp_path / "evaluation.md"
    monkeypatch.setattr(
        "sys.argv",
        [
            "voxtrace",
            "evaluate",
            "--manifests",
            str(manifests),
            "--predictions",
            str(predictions),
            "--json-output",
            str(output),
            "--markdown-output",
            str(markdown),
        ],
    )
    main()
    metric = json.loads(output.read_text(encoding="utf-8"))["metrics"]["by_category"][
        "rushed_delivery"
    ]
    assert metric["true_positives"] == 1
    assert metric["false_negatives"] == 1
    assert metric["false_positives"] == 0


def test_cli_rejects_pending_labels_without_explicit_stress_test_flag(
    tmp_path: Path, monkeypatch
) -> None:
    manifests = tmp_path / "manifests.jsonl"
    manifests.write_text(
        _manifest_line("train", "speaker-a")
        + "\n"
        + _manifest_line("held-out", "speaker-b", reviewer_status="pending")
        + "\n",
        encoding="utf-8",
    )
    predictions = tmp_path / "predictions.json"
    predictions.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "voxtrace",
            "evaluate",
            "--manifests",
            str(manifests),
            "--predictions",
            str(predictions),
            "--json-output",
            str(tmp_path / "evaluation.json"),
            "--markdown-output",
            str(tmp_path / "evaluation.md"),
        ],
    )
    with pytest.raises(ValueError, match="labels are pending"):
        main()
