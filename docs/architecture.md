# VoxTrace Architecture

## Design principle

Every displayed score, interval, and recommendation must be traceable to measured input data and an explicit rule or validated model. The system does not fabricate confidence or causal explanations.

## Current implemented path

```text
PCM WAV upload
  -> format, duration, and size validation
  -> deterministic mono downmix
  -> one-second dBFS energy windows
  -> JSON response for dashboard rendering

Pre-extracted timestamped features
  -> deterministic rubric thresholds
  -> timestamped findings
  -> evidence string + practice action
  -> score response
```

## Planned pipeline boundary

```text
Audio + transcript
  -> forced alignment (word timestamps)
  -> acoustic feature extraction
  -> speaker normalization
  -> baseline alignment
  -> temporal deviation detector
  -> deterministic rubric scorer
  -> dashboard
```

## API contracts

### `POST /v1/audio/energy-windows`

- Accepts one small PCM WAV upload.
- Enforces a 20 MB upload limit.
- Rejects compressed, non-16-bit, non-mono/stereo, empty, and overlong files.
- Returns measured duration, energy in dBFS, and a conservative silent-window pause proxy.

### `POST /v1/analyze/windows`

- Accepts pre-extracted windows with timestamp bounds and optional features.
- Does not convert missing data into findings.
- Returns a normalized score, per-dimension scores, timestamped findings, exact evidence, and the profile used.

## Security and privacy

- Raw uploads are decoded only through a temporary file and removed immediately after processing.
- Production deployments must add rate limits, authentication, structured audit logging, encrypted storage, and user-controlled data deletion before retaining uploads.
- Public datasets contain only recordings with consent or a documented redistribution licence.
