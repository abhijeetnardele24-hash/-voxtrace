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
  energy_db?: number;
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

const apiBase = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export async function analyzeWindows(windows: FeatureWindow[]): Promise<AnalysisResult> {
  const response = await fetch(`${apiBase}/v1/analyze/windows`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ windows }),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Analysis failed (${response.status}).`);
  }
  return (await response.json()) as AnalysisResult;
}

export async function extractAcousticWindows(audio: File): Promise<FeatureWindow[]> {
  const body = new FormData();
  body.append("audio", audio);
  const response = await fetch(`${apiBase}/v1/audio/feature-windows`, {
    method: "POST",
    body,
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Audio upload failed (${response.status}).`);
  }
  const payload = (await response.json()) as { windows: FeatureWindow[] };
  return payload.windows;
}
