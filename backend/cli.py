"""Reproducible command-line tooling for the VoxTrace dataset and reports."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .app.dataset import load_manifests_jsonl, split_by_speaker
from .app.domain import Finding, FindingType
from .app.evaluation import evaluate_temporal_grounding


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _manifest_summary(manifests_path: Path, holdout_speakers: int) -> dict[str, Any]:
    manifests = load_manifests_jsonl(manifests_path)
    training, held_out = split_by_speaker(manifests, holdout_speakers)
    return {
        "dataset_manifest": str(manifests_path),
        "recordings": len(manifests),
        "speakers": sorted({item.speaker_id for item in manifests}),
        "scripts": sorted({item.script_id for item in manifests}),
        "labelled_intervals": sum(len(item.labels) for item in manifests),
        "training_recording_ids": [item.recording_id for item in training],
        "held_out_recording_ids": [item.recording_id for item in held_out],
        "held_out_speakers": sorted({item.speaker_id for item in held_out}),
    }


def _load_predictions(path: Path) -> tuple[Finding, ...]:
    """Read a deliberately small, reviewable JSON finding interchange format."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("prediction file must contain a JSON list")
    findings: list[Finding] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"prediction {index} must be an object")
        try:
            findings.append(
                Finding(
                    finding_type=FindingType(item["finding_type"]),
                    start_seconds=float(item["start_seconds"]),
                    end_seconds=float(item["end_seconds"]),
                    severity=float(item["severity"]),
                    evidence=str(item.get("evidence", "recorded prediction")),
                    practice_action=str(item.get("practice_action", "review recording")),
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"invalid prediction {index}: {error}") from error
    return tuple(findings)


def _report_markdown(summary: dict[str, Any], metrics: dict[str, Any]) -> str:
    categories = metrics["by_category"]
    rows = "\n".join(
        f"| {name} | {item['precision']:.4f} | {item['recall']:.4f} | {item['f1']:.4f} |"
        for name, item in sorted(categories.items())
    )
    return (
        "# VoxTrace evaluation report\n\n"
        "This report is generated from reviewed labels and explicit prediction JSON. "
        "It does not infer or fill in unmeasured metrics.\n\n"
        f"- Held-out speakers: {', '.join(summary['held_out_speakers'])}\n"
        f"- Held-out recordings: {len(summary['held_out_recording_ids'])}\n"
        f"- IoU match threshold: {metrics['minimum_iou']:.2f}\n"
        f"- Macro F1: {metrics['macro_f1']:.4f}\n"
        f"- Mean matched IoU: {metrics['mean_matched_iou']:.4f}\n\n"
        "| Category | Precision | Recall | F1 |\n"
        "| --- | ---: | ---: | ---: |\n"
        f"{rows or '| No evaluated categories | — | — | — |'}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="VoxTrace reproducibility utilities")
    commands = parser.add_subparsers(dest="command", required=True)
    dataset = commands.add_parser("dataset-summary", help="validate data and produce leakage-safe split")
    dataset.add_argument("--manifests", type=Path, required=True)
    dataset.add_argument("--holdout-speakers", type=int, default=1)
    dataset.add_argument("--output", type=Path, required=True)
    report = commands.add_parser("evaluate", help="generate metrics from labels and prediction JSON")
    report.add_argument("--manifests", type=Path, required=True)
    report.add_argument("--predictions", type=Path, required=True)
    report.add_argument("--holdout-speakers", type=int, default=1)
    report.add_argument("--minimum-iou", type=float, default=0.5)
    report.add_argument("--json-output", type=Path, required=True)
    report.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()

    summary = _manifest_summary(args.manifests, args.holdout_speakers)
    if args.command == "dataset-summary":
        _write_json(args.output, summary)
        return

    manifests = load_manifests_jsonl(args.manifests)
    _, held_out = split_by_speaker(manifests, args.holdout_speakers)
    result = evaluate_temporal_grounding(
        _load_predictions(args.predictions),
        tuple(label for item in held_out for label in item.labels),
        args.minimum_iou,
    )
    metrics = {
        "minimum_iou": args.minimum_iou,
        "macro_f1": result.macro_f1,
        "mean_matched_iou": result.mean_matched_iou,
        "by_category": {name: asdict(value) for name, value in result.by_category.items()},
    }
    _write_json(args.json_output, {"dataset": summary, "metrics": metrics})
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(_report_markdown(summary, metrics), encoding="utf-8")


if __name__ == "__main__":
    main()
