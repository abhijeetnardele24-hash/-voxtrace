import argparse
import struct
import wave
from pathlib import Path

from backend.app.dataset import load_manifests_jsonl
from backend.contrastive_cli import build_dataset


def _write_pcm_wav(path: Path) -> None:
    samples = [2_000] * 8_000
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(8_000)
        writer.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def test_generator_creates_same_script_reviewable_spectrum(tmp_path: Path) -> None:
    source = tmp_path / "reference.wav"
    _write_pcm_wav(source)
    output = tmp_path / "dataset"
    manifest_path = build_dataset(
        argparse.Namespace(
            reference=str(source),
            transcript="A licensed test transcript.",
            speaker_id="speaker-test",
            script_id="script-test",
            licence="CC0",
            consent_record="test-consent",
            output=str(output),
        )
    )

    manifests = load_manifests_jsonl(manifest_path)

    assert len(manifests) == 6
    assert {item.variant_type for item in manifests} == {
        "reference",
        "near_perfect",
        "rushed",
        "excessive_pause",
        "low_energy",
        "mixed_flaws",
    }
    assert all(item.audio_path and (output / item.audio_path).exists() for item in manifests)
    assert all(
        label.reviewer_status == "pending"
        for item in manifests
        for label in item.labels
    )
