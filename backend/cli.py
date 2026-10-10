"""Reproducible command-line tooling for the VoxTrace dataset and reports."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .app.dataset import load_manifests_jsonl, split_by_speaker
from .app.domain import Finding, FindingType
from .app.evaluation import CategoryMetrics, evaluate_temporal_grounding


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


def _load_predictions(path: Path) -> dict[str, tuple[Finding, ...]]:
    """Read a deliberately small, reviewable JSON finding interchange format."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("prediction file must contain a JSON list")
    findings: dict[str, list[Finding]] = {}
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"prediction {index} must be an object")
        try:
            recording_id = str(item["recording_id"]).strip()
            if not recording_id:
                raise ValueError("recording_id cannot be blank")
            findings.setdefault(recording_id, []).append(
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
    return {recording_id: tuple(items) for recording_id, items in findings.items()}


def _aggregate_recording_metrics(
    predictions: dict[str, tuple[Finding, ...]], manifests: tuple[Any, ...], minimum_iou: float
) -> dict[str, Any]:
    counts: dict[str, list[int]] = {}
    matched_iou_total = 0.0
    matched_count = 0
    for manifest in manifests:
        report = evaluate_temporal_grounding(
            predictions.get(manifest.recording_id, ()), manifest.labels, minimum_iou
        )
        recording_matches = sum(metric.true_positives for metric in report.by_category.values())
        matched_iou_total += report.mean_matched_iou * recording_matches
        matched_count += recording_matches
        for name, metric in report.by_category.items():
            values = counts.setdefault(name, [0, 0, 0])
            values[0] += metric.true_positives
            values[1] += metric.false_positives
            values[2] += metric.false_negatives

    categories: dict[str, CategoryMetrics] = {}
    for name, (tp, fp, fn) in counts.items():
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        categories[name] = CategoryMetrics(
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
        )
    return {
        "minimum_iou": minimum_iou,
        "macro_f1": round(
            sum(metric.f1 for metric in categories.values()) / len(categories), 4
        )
        if categories
        else 0.0,
        "mean_matched_iou": round(matched_iou_total / matched_count, 4)
        if matched_count
        else 0.0,
        "by_category": {name: asdict(value) for name, value in categories.items()},
    }


def _report_markdown(summary: dict[str, Any], metrics: dict[str, Any]) -> str:
    categories = metrics["by_category"]
    rows = "\n".join(
        f"| {name} | {item['precision']:.4f} | {item['recall']:.4f} | {item['f1']:.4f} |"
        for name, item in sorted(categories.items())
    )
    return (
        f"# VoxTrace {metrics['report_kind']} report\n\n"
        f"{metrics['label_note']}\n\n"
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
    report.add_argument(
        "--allow-pending-labels",
        action="store_true",
        help="explicitly run a synthetic stress test against pending generated labels",
    )
    args = parser.parse_args()

    summary = _manifest_summary(args.manifests, args.holdout_speakers)
    if args.command == "dataset-summary":
        _write_json(args.output, summary)
        return

    manifests = load_manifests_jsonl(args.manifests)
    _, held_out = split_by_speaker(manifests, args.holdout_speakers)
    has_pending = any(label.reviewer_status != "reviewed" for item in held_out for label in item.labels)
    if has_pending and not args.allow_pending_labels:
        raise ValueError(
            "held-out labels are pending; review them or pass --allow-pending-labels "
            "to create a clearly marked synthetic stress-test report"
        )
    metrics = _aggregate_recording_metrics(
        _load_predictions(args.predictions), held_out, args.minimum_iou
    )
    metrics["report_kind"] = "synthetic stress-test" if has_pending else "evaluation"
    metrics["label_note"] = (
        "These metrics use deterministic transformation labels that remain pending, not "
        "human-reviewed ground truth. They measure pipeline behavior only and must not be "
        "presented as real-world accuracy."
        if has_pending
        else "This report uses reviewed labels and explicit, recording-scoped prediction JSON."
    )
    _write_json(args.json_output, {"dataset": summary, "metrics": metrics})
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(_report_markdown(summary, metrics), encoding="utf-8")


if __name__ == "__main__":
    main()
