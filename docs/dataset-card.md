# VoxTrace-Contrastive-1 Dataset Card

## Purpose

This dataset supports reproducible analysis of delivery deviations in spoken presentations. It is not a general-purpose measure of communication ability, intelligence, health, or employability.

## Unit of data

One audio recording of one scripted segment, paired with a transcript, a delivery variant, and timestamped labels for intentionally introduced deviations.

## Checked-in preview (11 October 2026)

The repository contains an 18-recording preview derived from three LibriSpeech utterances representing three pseudonymous speakers and three scripts. LibriSpeech is distributed under CC BY 4.0. Each licensed reference has near-perfect, rushed, excessive-pause, low-energy, and mixed-flaw variants generated deterministically by the checked-in CLI.

The preview's transformation labels remain `pending`. They document exact generated intervals and support pipeline stress testing, but they are not human-reviewed ground truth and are not used to claim final real-world accuracy.

## Required metadata

- recording ID and script ID
- pseudonymous speaker ID
- variant type
- recording licence or consent record
- transcript
- label reviewer
- acoustic extraction configuration
- upstream dataset, utterance identifier, and derivative licence obligations

## Splits

Split by speaker, never by recording. A held-out speaker must not occur in training or threshold calibration.

## Prohibited content

- private or unconsented recordings
- minors without documented guardian consent
- recordings containing personal contact details
- copyrighted material without a documented right to redistribute

## Labelling policy

Each labelled flaw requires a category, start time, end time, severity, label author, and reviewer status. A second reviewer should inspect a representative subset before results are reported.
