import type { AnalysisResult, FeatureWindow } from "./api";

export const demoTranscript =
  "Clear communication starts with a deliberate pause before the key claim. When delivery races, the listener can lose the argument before it has begun.";

export const demoWindows: FeatureWindow[] = [
  {
    start_seconds: 0,
    end_seconds: 5,
    speech_rate_wpm: 150,
    pause_seconds: 0.3,
    pitch_variation_semitones: 2.1,
    energy_db: -21,
    clarity_score: 0.9,
  },
  {
    start_seconds: 5,
    end_seconds: 10,
    speech_rate_wpm: 202,
    pause_seconds: 0.1,
    pitch_variation_semitones: 0.9,
    energy_db: -33,
    clarity_score: 0.58,
  },
  {
    start_seconds: 10,
    end_seconds: 15,
    speech_rate_wpm: 179,
    pause_seconds: 1.9,
    pitch_variation_semitones: 1.1,
    energy_db: -25,
    clarity_score: 0.74,
  },
];

export const fallbackDemoResult: AnalysisResult = {
  overall_score: 69.2,
  dimension_scores: {
    pace_and_pauses: 71.1,
    prosody: 88.9,
    energy: 79.2,
    clarity: 88.6,
  },
  findings: [
    {
      finding_type: "rushed_delivery",
      start_seconds: 5,
      end_seconds: 10,
      severity: 0.19,
      evidence: "Speech rate measured 202 WPM; the selected profile caps this segment at 170 WPM.",
      practice_action: "Rerecord this sentence more slowly and pause after its key claim.",
    },
    {
      finding_type: "low_energy",
      start_seconds: 5,
      end_seconds: 10,
      severity: 0.18,
      evidence: "Energy measured -33.0 dB; the selected profile targets at least -28.0 dB.",
      practice_action: "Move closer to the microphone and deliver this line with supported breath.",
    },
    {
      finding_type: "excessive_pause",
      start_seconds: 10,
      end_seconds: 15,
      severity: 0.36,
      evidence: "Pause measured 1.90s; the selected profile caps an unplanned pause at 1.40s.",
      practice_action: "Practice linking this phrase to the next thought with a shorter transition.",
    },
  ],
  scoring_profile: {},
};
