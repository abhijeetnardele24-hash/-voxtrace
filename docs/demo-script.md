# VoxTrace Demo Video Script — 6 Minutes

## 0:00–0:30 — Problem

“Public-speaking feedback is often vague. VoxTrace makes it auditable: every issue has an exact time interval, a measured acoustic cause, a baseline comparison, and a specific practice action.”

Show the title and the ideal-versus-target concept.

## 0:30–1:20 — Dataset construction

Show the dataset card, consent/licence fields, same-script reference recording, and generated stress variants. Explain that generated labels remain `pending` until reviewed and that evaluation holds out entire speakers to prevent leakage.

## 1:20–2:05 — Architecture

Show the architecture diagram. Explain ephemeral WAV validation, feature windows, optional WhisperX phoneme alignment, reference-profile derivation, deterministic scoring, and the React dashboard. State clearly that no runtime LLM invents scores.

## 2:05–3:20 — Live comparison

Upload the ideal recording and target recording of the same script. Point out the supported format and privacy statement. Run the comparison and show:

1. overall and dimension scores;
2. feature completeness;
3. paired energy windows;
4. highlighted deviation intervals.

## 3:20–4:20 — Causal explanation

Open one rushed-delivery interval. Read the observed speech rate, reference/threshold, relative deviation, and practice action. Then show one energy or pitch interval and emphasize that missing metrics stay missing.

## 4:20–5:10 — Stress testing and evaluation

Show the contrastive generator, reviewed manifest records, speaker-held-out split, and generated evaluation report. Present only measured macro F1 and mean IoU values from the final report.

## 5:10–5:40 — Reproducibility

Run `python -m pytest -q`, show the production frontend build, and briefly show Docker and the setup instructions.

## 5:40–6:00 — Limitations and close

Explain microphone, accent, culture, alignment, and non-clinical limitations. Close with: “VoxTrace does not replace a coach or judge. It gives both of them evidence they can inspect.”

## Recording checklist

- Use English narration or English subtitles.
- Keep the final video between 3 and 10 minutes.
- Do not show private email, API keys, invite links, or unconsented recordings.
- Verify the GitHub, live-demo, and Devpost links in an incognito window.
