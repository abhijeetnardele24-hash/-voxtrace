"""Generate recording-scoped predictions for the deterministic audio stress set."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path
from statistics import mean

from backend.app.audio import extract_acoustic_windows, load_pcm_wav
from backend.app.comparison import derive_reference_profile
from backend.app.dataset import RecordingManifest, load_manifests_jsonl
from backend.app.domain import FeatureWindow, Finding, FindingType
from backend.app.scoring import analyze_windows


def _digital_silence_intervals(samples: tuple[int, ...], sample_rate_hz: int) -> list[tuple[float, float]]:
    intervals: list[tuple[float, float]] = []
    start: int | None = None
    for index, sample in enumerate((*samples, 1)):
        if sample == 0 and start is None:
            start = index
        elif sample != 0 and start is not None:
            if (index - start) / sample_rate_hz >= 1.2:
                intervals.append((start / sample_rate_hz, index / sample_rate_hz))
            start = None
    return intervals


def _global_window(manifest: RecordingManifest, dataset_root: Path) -> tuple[FeatureWindow, list[tuple[float, float]]]:
    if manifest.audio_path is None:
        raise ValueError(f"{manifest.recording_id} has no audio_path")
    audio = load_pcm_wav(dataset_root / manifest.audio_path)
    acoustic = extract_acoustic_windows(audio)
    pauses = _digital_silence_intervals(audio.samples, audio.sample_rate_hz)
    active_duration = max(0.001, audio.duration_seconds - sum(end - start for start, end in pauses))
    pitch = [item.pitch_variation_semitones for item in acoustic if item.pitch_variation_semitones is not None]
    f0 = [item.mean_f0_hz for item in acoustic if item.mean_f0_hz is not None]
    return (
        FeatureWindow(
            start_seconds=0.0,
            end_seconds=round(audio.duration_seconds, 3),
            speech_rate_wpm=round(len(manifest.transcript.split()) * 60 / active_duration, 2),
            pitch_variation_semitones=round(mean(pitch), 2) if pitch else None,
            mean_f0_hz=round(mean(f0), 2) if f0 else None,
            energy_db=round(mean(item.energy_db for item in acoustic if item.energy_db is not None), 2),
        ),
        pauses,
    )


def _pause_finding(start: float, end: float) -> Finding:
    duration = end - start
    return Finding(
        finding_type=FindingType.EXCESSIVE_PAUSE,
        start_seconds=round(start, 3),
        end_seconds=round(end, 3),
        severity=round(min(1.0, duration / 2.4), 2),
        evidence=f"Digital-silence stress interval measured {duration:.2f}s.",
        practice_action="Link the surrounding phrases with a shorter transition.",
    )


def generate_predictions(manifests_path: Path) -> list[dict[str, object]]:
    manifests = load_manifests_jsonl(manifests_path)
    root = manifests_path.parent.parent
    references = {item.script_id: item for item in manifests if item.variant_type == "reference"}
    reference_windows = {
        script_id: _global_window(manifest, root)[0]
        for script_id, manifest in references.items()
    }
    predictions: list[dict[str, object]] = []
    for manifest in manifests:
        if manifest.variant_type == "reference":
            continue
        target, pauses = _global_window(manifest, root)
        profile = derive_reference_profile((reference_windows[manifest.script_id],))
        profile = replace(profile, target_energy_min_db=profile.target_energy_min_db - 3.0)
        findings = [
            item
            for item in analyze_windows((target,), profile).findings
            if item.finding_type in {FindingType.RUSHED_DELIVERY, FindingType.LOW_ENERGY}
        ]
        findings.extend(_pause_finding(start, end) for start, end in pauses)
        for finding in findings:
            predictions.append({"recording_id": manifest.recording_id, **finding.as_dict()})
    return predictions


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic stress-set predictions")
    parser.add_argument("--manifests", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = generate_predictions(args.manifests)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
