import json
from pathlib import Path

from backend.cli import main


def _manifest_line(recording_id: str, speaker_id: str) -> str:
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
                    "reviewer_status": "reviewed",
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
