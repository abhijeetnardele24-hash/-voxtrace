"""Create a reviewable same-script contrastive recording set from one licensed WAV."""

from __future__ import annotations

import argparse
import json
import shutil
import wave
from pathlib import Path

import numpy as np

from backend.app.audio import load_pcm_wav


def _write_wav(path: Path, samples: np.ndarray, sample_rate_hz: int) -> None:
    clipped = np.clip(np.rint(samples), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate_hz)
        writer.writeframes(clipped.tobytes())


def _speed(samples: np.ndarray, factor: float) -> np.ndarray:
    output_size = max(1, round(samples.size / factor))
    source_positions = np.linspace(0, samples.size - 1, output_size)
    return np.interp(source_positions, np.arange(samples.size), samples)


def _insert_pause(samples: np.ndarray, sample_rate_hz: int, seconds: float) -> np.ndarray:
    split = round(samples.size * 0.55)
    silence = np.zeros(round(sample_rate_hz * seconds), dtype=np.float64)
    return np.concatenate((samples[:split], silence, samples[split:]))


def _label(
    kind: str, start_seconds: float, end_seconds: float, severity: float
) -> dict[str, object]:
    return {
        "finding_type": kind,
        "start_seconds": round(start_seconds, 3),
        "end_seconds": round(end_seconds, 3),
        "severity": severity,
        "reviewer_status": "pending",
    }


def build_dataset(args: argparse.Namespace) -> Path:
    source = Path(args.reference).resolve()
    audio = load_pcm_wav(source)
    output = Path(args.output).resolve()
    audio_dir = output / "audio"
    labels_dir = output / "labels"
    audio_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    samples = np.asarray(audio.samples, dtype=np.float64)

    variants: dict[
        str, tuple[np.ndarray, list[tuple[str, float, float | None, float]]]
    ] = {
        "reference": (samples, []),
        "near_perfect": (samples * 0.9, []),
        "rushed": (_speed(samples, 1.28), [("rushed_delivery", 0.0, None, 0.7)]),
        "excessive_pause": (
            _insert_pause(samples, audio.sample_rate_hz, 1.8),
            [
                (
                    "excessive_pause",
                    audio.duration_seconds * 0.55,
                    audio.duration_seconds * 0.55 + 1.8,
                    0.75,
                )
            ],
        ),
        "low_energy": (samples * 0.32, [("low_energy", 0.0, None, 0.75)]),
    }
    mixed = _insert_pause(_speed(samples, 1.2), audio.sample_rate_hz, 1.6) * 0.42
    variants["mixed_flaws"] = (
        mixed,
        [
            ("rushed_delivery", 0.0, None, 0.55),
            (
                "excessive_pause",
                (audio.duration_seconds / 1.2) * 0.55,
                (audio.duration_seconds / 1.2) * 0.55 + 1.6,
                0.65,
            ),
            ("low_energy", 0.0, None, 0.6),
        ],
    )

    manifests: list[dict[str, object]] = []
    for variant, (variant_samples, labels) in variants.items():
        filename = f"{args.script_id}-{args.speaker_id}-{variant}.wav"
        target = audio_dir / filename
        if variant == "reference":
            shutil.copyfile(source, target)
        else:
            _write_wav(target, variant_samples, audio.sample_rate_hz)
        duration = len(variant_samples) / audio.sample_rate_hz
        manifests.append(
            {
                "recording_id": target.stem,
                "script_id": args.script_id,
                "speaker_id": args.speaker_id,
                "variant_type": variant,
                "audio_path": target.relative_to(output).as_posix(),
                "sample_rate_hz": audio.sample_rate_hz,
                "duration_seconds": round(duration, 3),
                "licence": args.licence,
                "consent_record": args.consent_record,
                "transcript": args.transcript,
                "labels": [
                    _label(kind, start, duration if end is None else end, severity)
                    for kind, start, end, severity in labels
                ],
            }
        )

    manifest_path = labels_dir / "manifests.jsonl"
    mode = "a" if args.append and manifest_path.exists() else "w"
    with manifest_path.open(mode, encoding="utf-8") as stream:
        stream.write("\n".join(json.dumps(item, ensure_ascii=False) for item in manifests) + "\n")
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate reviewable contrastive WAV variants from a licensed ideal delivery."
    )
    parser.add_argument("--reference", required=True, help="16-bit PCM WAV ideal delivery")
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--speaker-id", required=True)
    parser.add_argument("--script-id", required=True)
    parser.add_argument("--licence", required=True)
    parser.add_argument("--consent-record", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--append", action="store_true", help="append to an existing manifest")
    args = parser.parse_args()
    print(build_dataset(args))


if __name__ == "__main__":
    main()
