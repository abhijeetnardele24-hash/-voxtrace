# VoxTrace — Multimodal AI Hackathon 2026 Submission Plan

## 1. Mission

Build **VoxTrace**, a reproducible speech-delivery analysis platform for Track C:

> Given a recording and transcript, identify *where* delivery breaks down, *what* acoustic pattern caused it, and *how* the speaker can improve.

VoxTrace must not be a generic chatbot that gives vague feedback. Its proof of value is:

1. a custom, documented contrastive dataset;
2. exact timestamp-level flaw detection;
3. explainable acoustic evidence;
4. repeatable, speaker-normalized scoring;
5. a polished dashboard and clear demo.

## 2. Competition Facts

- Event: Multimodal AI Hackathon 2026
- Selected track: **Track C — Contrastive Speech Analytics & Temporal Flaw Grounding**
- Submission deadline: **15 October 2026, 12:15 AM IST**
- Team size: 1–4 members
- Every individual may be on only one submitting team, and a team may enter only one track.
- Final submission needs:
  - Devpost project description
  - public GitHub repository with source code and README
  - public or unlisted YouTube video (3–10 minutes, English audio/subtitles)
  - all real team members added through Devpost
- AI coding assistants are allowed, but every AI tool used must be disclosed in `README.md`.

Official event links:

- Rules: <https://multimodal-ai-hackathon-2026-7.devpost.com/rules>
- Problem statements: <https://drive.google.com/file/d/1sPrF1CWyJMGk8c3JOwu08_sboeaAE5xc/view>
- Event page: <https://multimodal-ai-hackathon-2026-7.devpost.com/>

## 3. What Judges Score

| Criterion | Weight | Our evidence |
|---|---:|---|
| Data engineering and stress testing | 30% | Public contrastive dataset, paired recordings, temporal labels, documented quality gradient, held-out split |
| Causal explainability and temporal grounding | 25% | Exact intervals, baseline-versus-submission comparison, interpretable feature deltas, timestamp metrics |
| Feature extraction | 20% | Forced alignment, F0, energy, pause, speech-rate, MFCC, spectral features and normalization |
| Visualization and dashboard | 15% | Upload workflow, synchronized waveform/transcript/features, clear scorecard and action plan |
| Reproducibility and code quality | 10% | One-command setup, deterministic runs, tests, fixed configuration, transparent limits |

## 4. Product Definition

### User journey

1. User selects a speech rubric and uploads a WAV/MP3 file plus transcript.
2. System validates duration, audio quality and transcript availability.
3. Forced alignment maps each word to an audio timestamp.
4. Feature pipeline extracts speaker-normalized acoustic features in short windows.
5. Detection engine identifies anomalous regions and assigns one or more categories:
   - rushed delivery
   - unnatural pause
   - monotone delivery
   - low energy
   - unstable loudness
   - unclear articulation
6. Dashboard renders:
   - an overall rubric score;
   - waveform and time-series feature overlays;
   - highlighted intervals;
   - plain-English causal explanations;
   - prioritized practice drills.
7. User can open each flaw and see the exact signal evidence behind the result.

### Non-goals

- We do not claim to diagnose speech, health, or neurological conditions.
- We do not claim universal “good speaking” standards.
- We do not generate ungrounded feedback.
- We do not train on, upload, or publish recordings without permission or a valid public licence.

## 5. Dataset Strategy — The Winning Evidence

### Dataset name

`VoxTrace-Contrastive-1`

### Minimum viable quality target

- 8–12 scripts
- 3–5 speakers
- 5–7 versions per script
- Each script has a controlled quality ladder:
  1. reference/ideal delivery
  2. near-perfect delivery
  3. rushed delivery
  4. excessive or misplaced pauses
  5. monotone/low prosody
  6. low-energy delivery
  7. mixed-flaw delivery

### Required data fields per recording

- `recording_id`
- `script_id`
- `speaker_id` (pseudonymous)
- `variant_type`
- source/licence/consent record
- transcript
- sampling rate and duration
- flaw labels: category, start seconds, end seconds, severity
- annotator and review status

### Quality controls

- Never split the same speaker between train and test sets.
- Keep a held-out-speaker test set.
- Have a second person review a sample of labels.
- Preserve raw audio separately from processed features.
- Use original scripts, public-domain material, or material with documented reuse rights.
- Do not publish personal names, contact details, or unconsented recordings.

## 6. Technical Architecture

```text
Audio + Transcript
        |
        v
Upload/API validation
        |
        v
Forced alignment ------------> word timestamps
        |
        v
Acoustic feature extraction -> F0, energy, pauses, rate, MFCCs, clarity proxies
        |
        v
Speaker normalization + baseline alignment
        |
        v
Temporal anomaly detector ---> flaw intervals + confidence + feature deltas
        |
        +---------------------> deterministic rubric scorer
        |
        v
Dashboard API
        |
        v
Interactive dashboard: waveform, transcript, overlays, explanations, drills
```

### Proposed stack

| Layer | Technology | Purpose |
|---|---|---|
| Dashboard | React + Vite + TypeScript | Fast, polished judge-facing interface |
| API | FastAPI + Python | Audio-processing and evaluation endpoints |
| Alignment | WhisperX or equivalent forced-alignment tool | Word-level timestamps |
| Audio analysis | NumPy + standard-library WAV processing | Deterministic acoustic features |
| Storage | Versioned JSON/JSONL and browser-local state | Dataset metadata and results |
| Charts | React + SVG/CSS | Synchronized feature views |
| Testing | pytest + frontend component tests | Repeatability and input validation |

Final technology choices must be documented honestly in the README and Devpost “Built With” tags.

## 7. Scoring Method

Scores must be deterministic and explainable. Start with a transparent, feature-based system before adding any learned classifier.

### Rubric dimensions

- Pace and pause quality
- Prosody and pitch variation
- Energy and loudness control
- Articulation/clarity proxy

### Example causal explanation

```text
00:42.1–00:46.8 — Rushed delivery (high confidence)
Observed rate: 205 words/minute
Speaker-normalized reference range: 135–165 words/minute
Evidence: sustained rate z-score of +2.3, with no compensating pause after a key claim.
Practice action: rerecord this sentence at 150 words/minute and insert a 0.5–0.8 second pause after “therefore”.
```

No metric or percentage may be invented. Every displayed number must be computed from recorded inputs.

## 8. Evaluation Plan

### Dataset evaluation

- Temporal intersection-over-union (IoU) for flaw intervals
- Precision, recall and F1 by flaw category
- Macro F1 across categories
- Severity-score correlation with human labels
- Performance by held-out speaker
- Run-to-run reproducibility: same input/configuration yields the same result

### Product evaluation

- End-to-end processing success rate
- Median processing time per minute of audio
- User-facing explanation completeness: every displayed issue links to measured features
- Dashboard usability test with at least two users

### Honest limitations to report

- Results depend on microphone quality and background noise.
- Acoustic delivery does not fully measure rhetorical content or cultural communication norms.
- Forced alignment can be less reliable for code-switching, accents, and noisy audio.
- The prototype is educational feedback, not an authoritative competition-judging system.

## 9. Repository Structure

```text
devpost project/
├── HACKATHON_MASTER_PLAN.md
├── README.md
├── LICENSE
├── AI_ASSISTANCE.md
├── docs/
│   ├── architecture.md
│   ├── dataset-card.md
│   ├── evaluation.md
│   └── demo-script.md
├── data/
│   ├── raw/                 # not committed if consent/licensing prohibits it
│   ├── processed/
│   └── labels/
├── backend/
├── frontend/
├── tests/
└── assets/
```

## 10. Delivery Plan

### Phase 1 — Foundation

- [x] Create public GitHub repository.
- [x] Add license and `.gitignore`.
- [x] Add dataset card and consent/licence log.
- [x] Lock a small, high-quality stress-preview scope.
- [x] Source licensed references and generate the first paired examples.
- [x] Create Devpost draft now; do not wait until the last day.

### Phase 2 — Credible analysis

- [x] Implement transcript validation and optional forced alignment.
- [x] Extract features and store them in a reproducible format.
- [x] Implement deterministic normalization and scoring.
- [x] Implement temporal flaw detection.
- [x] Validate outputs using known injected flaws.

### Phase 3 — Judge-facing experience

- [x] Build upload flow.
- [x] Build synchronized waveform, transcript and feature charts.
- [x] Build issue cards with timestamps, evidence and practice actions.
- [x] Add a transparent limitations panel.
- [x] Add seeded demo examples so judges can test without uploading audio.

### Phase 4 — Evidence and submission

- [x] Run a clearly labelled synthetic held-out-speaker stress test.
- [x] Generate tables and evidence for the README and five-page report.
- [x] Run backend and production frontend verification.
- [x] Record and publish the 7:37 narrated demo video.
- [x] Add screenshots, GitHub URL, video URL and all real teammates to Devpost.
- [x] Preview the public Devpost project page.
- [x] Submit before the deadline and verify Devpost shows “Project submitted.”

## 11. Demo Video Script (6–8 Minutes)

1. **0:00–0:35** — Problem and one-sentence pitch.
2. **0:35–1:30** — Dataset: paired quality spectrum, labels, and licences.
3. **1:30–2:30** — Architecture and reproducibility.
4. **2:30–4:45** — Live workflow: upload audio/transcript, process, inspect exact timestamps.
5. **4:45–5:45** — Explain one detected flaw using the feature graph and causal explanation.
6. **5:45–6:45** — Evaluation results and held-out-speaker performance.
7. **6:45–7:30** — Limits, responsible use, and future work.

## 12. Serious Compliance Notes

1. **No fake results.** Do not claim accuracy, F1, correlation, user testing, or “AI detection” without measured evidence.
2. **No unlicensed data.** Record original material, use public-domain material, or document the licence for every external asset.
3. **No deceptive AI disclosure.** List all AI tools used to build the project in `AI_ASSISTANCE.md` and the README.
4. **No secrets in Git.** Use `.env.example`; never commit API keys, access tokens, recordings with identifying metadata, or private transcripts.
5. **No generic chatbot substitution.** The rubric rewards custom contrastive data, temporal labels, acoustic rigor, and causal explanations.
6. **No last-minute submission.** A Devpost draft is not a final submission. Complete the final Submit step and capture confirmation.
7. **No guarantee of winning.** We can maximize rubric coverage, quality, evidence, and clarity; the organizer’s judges make the final decision.

## 13. Devpost Content Draft

### Project name

VoxTrace

### Tagline

An explainable speech coach that locates delivery flaws to the exact second.

### One-sentence pitch

VoxTrace turns speech recordings into timestamped, evidence-backed coaching by comparing acoustic delivery against a custom contrastive quality dataset.

### Built-with tags (update to match the final implementation)

`Python`, `FastAPI`, `NumPy`, `WhisperX`, `React`, `TypeScript`, `Vite`, `Docker`, `pytest`

## 14. Team Roles

For a four-person team:

| Role | Main responsibility |
|---|---|
| ML/audio lead | Dataset, alignment, features, scoring, evaluation |
| Backend lead | API, job processing, data model, tests |
| Frontend lead | Dashboard, waveform/charts, upload flow, screenshots |
| Product/documentation lead | Labels review, report, demo video, Devpost submission |

For a solo or two-person team, build the analysis pipeline and evidence first; reduce feature breadth before compromising reproducibility.

## 15. Definition of Done

The project is ready only when a judge can:

1. clone the public repository;
2. follow the README successfully;
3. run a seeded example;
4. upload audio and transcript;
5. see exact timestamped issues with measured evidence;
6. inspect the dataset card and evaluation results;
7. watch the video and understand the system in under 10 minutes;
8. find AI-tool disclosure and data licences.
