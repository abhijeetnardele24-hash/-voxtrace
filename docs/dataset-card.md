# VoxTrace-Contrastive-1 Dataset Card

## Purpose

This dataset supports reproducible analysis of delivery deviations in spoken presentations. It is not a general-purpose measure of communication ability, intelligence, health, or employability.

## Unit of data

One audio recording of one scripted segment, paired with a transcript, a delivery variant, and timestamped labels for intentionally introduced deviations.

## Required metadata

- recording ID and script ID
- pseudonymous speaker ID
- variant type
- recording licence or consent record
- transcript
- label reviewer
- acoustic extraction configuration

## Splits

Split by speaker, never by recording. A held-out speaker must not occur in training or threshold calibration.

## Prohibited content

- private or unconsented recordings
- minors without documented guardian consent
- recordings containing personal contact details
- copyrighted material without a documented right to redistribute

## Labelling policy

Each labelled flaw requires a category, start time, end time, severity, label author, and reviewer status. A second reviewer should inspect a representative subset before results are reported.
