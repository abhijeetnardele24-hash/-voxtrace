# VoxTrace

> An explainable speech coach that locates delivery flaws to the exact second.

VoxTrace is a Track C submission for the Multimodal AI Hackathon 2026. It analyzes an audio recording and transcript, finds timestamped delivery deviations, explains the measured acoustic evidence, and suggests a focused practice action.

## Status

Project foundation created. See [HACKATHON_MASTER_PLAN.md](HACKATHON_MASTER_PLAN.md) for the official rubric mapping, data policy, implementation plan, and submission checklist.

## Planned stack

- Frontend: Next.js, TypeScript
- API: FastAPI, Python
- Audio analysis: forced alignment, librosa, Parselmouth/openSMILE
- Storage: SQLite or PostgreSQL

## Quick start

```bash
python -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/uvicorn backend.app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` to inspect and test the API.

Current verified endpoints:

- `GET /health`
- `POST /v1/analyze/windows` — scores pre-extracted, timestamped acoustic features
- `POST /v1/audio/feature-windows` — validates a PCM WAV and returns measured energy, silence, and pitch-variation windows
- `POST /v1/alignment/apply-word-timing` — validates externally aligned words, then derives WPM and word-boundary pauses without inventing timestamps

The audio-upload endpoint is intentionally limited to measured baseline extraction. Word-level analysis requires a real alignment result (or human-reviewed timestamps); VoxTrace never estimates word timestamps by spreading transcript words evenly over an audio duration.

## Dashboard

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. The dashboard uses the local API by default. It includes a seeded demo for judges and can upload a 16-bit PCM WAV for measured energy, silence, and pitch-variation analysis.

## Tests

```bash
.venv/bin/python -m pytest -q
```

## Reproducible dataset automation

Validate a real manifest and create a deterministic held-out-speaker split:

```bash
.venv/bin/python -m backend.cli dataset-summary \
  --manifests data/labels/manifests.jsonl \
  --output data/processed/dataset-summary.json
```

After generating real model predictions as a JSON list, create the measured
JSON and Markdown evaluation reports:

```bash
.venv/bin/python -m backend.cli evaluate \
  --manifests data/labels/manifests.jsonl \
  --predictions data/processed/predictions.json \
  --json-output data/processed/evaluation.json \
  --markdown-output docs/evaluation-results.md
```

## Container run

```bash
docker build -t voxtrace .
docker run --rm -p 8000:8000 voxtrace
```

## Data and responsible use

The project will use original, public-domain, or otherwise licensed recordings only. It is an educational feedback tool, not an authoritative judging or diagnostic system.

## Hackathon submission

- Track: Contrastive Speech Analytics & Temporal Flaw Grounding
- Demo video: to be added
- Live demo: to be added
- Technical report: to be added

## Documentation

- [Master project plan](HACKATHON_MASTER_PLAN.md)
- [AI assistance disclosure](AI_ASSISTANCE.md)
- [Architecture](docs/architecture.md)
- [Dataset card](docs/dataset-card.md)
- [Evaluation protocol](docs/evaluation.md)
