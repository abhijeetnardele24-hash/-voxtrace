export type FindingType =
  | "rushed_delivery"
  | "excessive_pause"
  | "monotone_delivery"
  | "low_energy"
  | "low_clarity";

export type FeatureWindow = {
  start_seconds: number;
  end_seconds: number;
  speech_rate_wpm?: number;
  pause_seconds?: number;
  pitch_variation_semitones?: number;
  mean_f0_hz?: number;
  energy_db?: number;
  spectral_centroid_hz?: number;
  spectral_rolloff_hz?: number;
  spectral_flatness?: number;
  zero_crossing_rate?: number;
  mfcc_means?: number[];
  clarity_score?: number;
};

export type Finding = {
  finding_type: FindingType;
  start_seconds: number;
  end_seconds: number;
  severity: number;
  evidence: string;
  practice_action: string;
};

export type AnalysisResult = {
  overall_score: number;
  dimension_scores: Record<string, number>;
  findings: Finding[];
  scoring_profile: Record<string, number>;
};

export type WindowComparison = {
  start_seconds: number;
  end_seconds: number;
  reference_start_seconds: number;
  reference_end_seconds: number;
  observed: Record<string, number>;
  reference: Record<string, number>;
  deltas: Record<string, number>;
};

export type ContrastiveAnalysis = {
  reference_profile: Record<string, number>;
  analysis: AnalysisResult;
  comparisons: WindowComparison[];
  data_completeness: Record<string, boolean>;
  reference_duration_seconds?: number;
  target_duration_seconds?: number;
  timing_mode?: string;
};

const apiBase = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

async function responseJson<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `${fallback} (${response.status}).`);
  }
  return (await response.json()) as T;
}

export async function analyzeWindows(windows: FeatureWindow[]): Promise<AnalysisResult> {
  const response = await fetch(`${apiBase}/v1/analyze/windows`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ windows }),
  });
  return responseJson<AnalysisResult>(response, "Analysis failed");
}

export async function compareWindows(
  referenceWindows: FeatureWindow[],
  targetWindows: FeatureWindow[],
): Promise<ContrastiveAnalysis> {
  const response = await fetch(`${apiBase}/v1/compare/windows`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      reference_windows: referenceWindows,
      target_windows: targetWindows,
    }),
  });
  return responseJson<ContrastiveAnalysis>(response, "Comparison failed");
}

export async function extractAcousticWindows(audio: File): Promise<FeatureWindow[]> {
  const body = new FormData();
  body.append("audio", audio);
  const response = await fetch(`${apiBase}/v1/audio/feature-windows`, {
    method: "POST",
    body,
  });
  const payload = await responseJson<{ windows: FeatureWindow[] }>(response, "Audio upload failed");
  return payload.windows;
}

export async function compareAudio(
  referenceAudio: File,
  targetAudio: File,
): Promise<ContrastiveAnalysis> {
  const body = new FormData();
  body.append("reference_audio", referenceAudio);
  body.append("target_audio", targetAudio);
  const response = await fetch(`${apiBase}/v1/audio/compare`, { method: "POST", body });
  return responseJson<ContrastiveAnalysis>(response, "Audio comparison failed");
}
