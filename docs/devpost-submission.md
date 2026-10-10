# Devpost Submission Draft

## Project name

VoxTrace

## Elevator pitch

An evidence-first speech coach that compares ideal and flawed deliveries, grounds every issue to an exact timestamp, and explains the measured acoustic cause.

## About the project

### Inspiration

Public-speaking feedback is often subjective: a speaker is told to “slow down” or “sound more confident” without being shown where the problem occurred or what changed in the signal. VoxTrace was built to make delivery feedback auditable. It compares two recordings of the same script—an ideal baseline and a target delivery—and turns measurable acoustic differences into timestamped practice guidance.

### What it does

VoxTrace accepts 16-bit PCM WAV recordings and extracts bounded acoustic windows. It measures energy, silence, pitch variation, mean F0, spectral centroid, spectral rolloff, spectral flatness, zero-crossing rate, and compact cepstral coefficients. When word timestamps are available, it also measures speech rate and word-boundary pauses.

The comparison engine maps target windows to the ideal same-script recording, derives an explicit reference profile, and reports the observed value, baseline value, and delta. A deterministic scoring layer identifies rushed delivery, excessive pauses, monotone delivery, low energy, and low clarity only when the required measurement exists. Missing measurements remain visibly missing.

### How we built it

The backend uses Python, FastAPI, NumPy, and an optional WhisperX phoneme-alignment worker. Uploads are size- and duration-limited, processed through temporary files, and deleted immediately. A React and TypeScript dashboard presents the overall rubric score, data completeness, baseline-vs-target energy timeline, timestamped findings, causal evidence, and prioritized practice actions.

Dataset tooling validates licences and consent records, creates a deterministic speaker-held-out split, and generates reviewable same-script stress variants from licensed reference recordings. Evaluation tooling reports temporal intersection-over-union, per-category precision/recall/F1, macro F1, and mean matched IoU.

### Challenges

The main challenge was preserving scientific honesty under hackathon time pressure. It is easy to display impressive-looking confidence values or stretch transcript words evenly across an audio file. VoxTrace does neither. Forced alignment has explicit provenance, the resource-heavy model is isolated behind a guarded optional endpoint, and every unsupported metric is omitted.

Another challenge was comparing recordings with different durations. The current deterministic baseline comparison maps windows by normalized same-script time, while the forced-alignment path provides word-level timing for speech-rate and pause analysis.

### Accomplishments

- A working ideal-vs-target audio comparison API and dashboard.
- Exact timestamped causal findings with no invented metrics.
- FFT-derived spectral descriptors, compact cepstral coefficients, F0, energy, silence, pitch variation, and word-timing contracts.
- Optional WhisperX phoneme forced alignment with strict server-side gating.
- Reproducible contrastive-dataset generation and validation tooling.
- Speaker-held-out temporal evaluation utilities.
- 24 passing backend tests and a verified production frontend build.
- Transparent AI-assistance, privacy, licensing, and responsible-use documentation.

### What we learned

Temporal grounding is not the same as attaching a timestamp to generic feedback. The timestamp, feature value, reference value, threshold, and explanation must all share the same provenance. We also learned that data quality and review status matter more than simply collecting many recordings; the pipeline therefore keeps generated labels pending until a human reviews them.

### What's next

Before final submission we will finish the licensed multi-speaker contrastive dataset, review its labels, run the held-out-speaker evaluation, deploy the public demo, and publish the measured results and demo video. Future work includes multilingual alignment profiles, microphone-condition normalization, richer synchronized transcript highlighting, and user-controlled encrypted persistence.

## Built with

`python`, `fastapi`, `numpy`, `whisperx`, `react`, `typescript`, `vite`, `docker`, `pytest`, `html5`, `css3`

## Links

- GitHub: <https://github.com/abhijeetnardele24-hash/-voxtrace>
- Live demo: `<add deployment URL>`
- Video: `<add public or unlisted YouTube URL>`

## Additional information

- Team name: `<provide team name>`
- Track: Track C
- Team leader email: `<provide email>`
