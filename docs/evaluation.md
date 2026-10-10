# Evaluation Protocol

## Question

Can VoxTrace identify intentionally introduced delivery deviations at useful timestamps for speakers it did not see during threshold calibration?

## Evaluation split

Use a held-out-speaker split:

- All recordings from a speaker must be in either training/calibration or test, never both.
- Report the number of speakers, scripts, recordings, and labelled intervals in each split.
- Do not tune thresholds after viewing held-out results.

## Required metrics

| Metric | Why it matters |
|---|---|
| Interval IoU | Whether predicted flaw spans overlap the labelled time range |
| Precision / recall / macro F1 | Whether each flaw category is detected without excessive false alarms |
| Severity correlation | Whether ranked feedback tracks human labels |
| Run-to-run agreement | Whether the same input/configuration produces the same output |
| Processing time | Whether feedback is usable in a live coaching workflow |

## Implemented temporal-grounding evaluator

`backend/app/evaluation.py` now evaluates predictions against human labels with:

- exact interval IoU;
- one-to-one, same-category matching at a documented IoU threshold;
- per-category true positives, false positives, false negatives, precision, recall, and F1;
- macro F1 and mean IoU across matched intervals.

Use this evaluator against recordings from held-out speakers. Do not report results until the actual contrastive dataset and reviewed labels exist.

## Reporting template

```text
Dataset version:
Test speakers:
Test recordings:
Labelled intervals:
Window size:
Alignment model/version:
Threshold profile/version:

Metric                         Result
Macro F1                       <measured value>
Mean interval IoU              <measured value>
Severity Spearman correlation  <measured value>
Median processing sec/min      <measured value>
Run-to-run agreement           <measured value>
```

## Integrity rule

Never replace unmeasured fields with estimates in the final report. If a metric cannot be calculated, state why and present it as a limitation rather than a result.
