import type {
  AnalysisResult,
  ContrastiveAnalysis,
  FeatureWindow,
  Finding,
  WindowComparison,
} from "./api";

type ReferenceProfile = {
  target_rate_min_wpm: number;
  target_rate_max_wpm: number;
  target_pause_max_seconds: number;
  target_pitch_variation_min_semitones: number;
  target_energy_min_db: number;
  target_clarity_min: number;
};

const comparableFeatures = [
  "speech_rate_wpm",
  "pause_seconds",
  "pitch_variation_semitones",
  "mean_f0_hz",
  "energy_db",
  "spectral_centroid_hz",
  "spectral_rolloff_hz",
  "spectral_flatness",
  "zero_crossing_rate",
  "clarity_score",
] as const;

const defaults: ReferenceProfile = {
  target_rate_min_wpm: 110,
  target_rate_max_wpm: 170,
  target_pause_max_seconds: 1.2,
  target_pitch_variation_min_semitones: 2.5,
  target_energy_min_db: -28,
  target_clarity_min: 0.7,
};

const round = (value: number, digits = 2) => Number(value.toFixed(digits));
const clamp = (value: number, low = 0, high = 1) => Math.max(low, Math.min(value, high));
const mean = (values: number[]) => values.reduce((sum, value) => sum + value, 0) / values.length;

function percentile(values: number[], fraction: number): number | undefined {
  if (!values.length) return undefined;
  const ordered = values.slice().sort((a, b) => a - b);
  const position = fraction * (ordered.length - 1);
  const lower = Math.floor(position);
  const weight = position - lower;
  return ordered[lower] * (1 - weight) + ordered[Math.min(lower + 1, ordered.length - 1)] * weight;
}

function median(values: number[]): number | undefined {
  return percentile(values, 0.5);
}

function valuesFor(windows: FeatureWindow[], key: keyof FeatureWindow): number[] {
  return windows.map((window) => window[key]).filter((value): value is number => typeof value === "number");
}

function deriveProfile(windows: FeatureWindow[]): ReferenceProfile {
  const rateCenter = median(valuesFor(windows, "speech_rate_wpm"));
  return {
    target_rate_min_wpm: rateCenter === undefined ? defaults.target_rate_min_wpm : round(rateCenter * 0.85),
    target_rate_max_wpm: rateCenter === undefined ? defaults.target_rate_max_wpm : round(rateCenter * 1.15),
    target_pause_max_seconds: round(percentile(valuesFor(windows, "pause_seconds"), 0.9) || defaults.target_pause_max_seconds),
    target_pitch_variation_min_semitones: round(
      percentile(valuesFor(windows, "pitch_variation_semitones"), 0.2) || defaults.target_pitch_variation_min_semitones,
    ),
    target_energy_min_db: round(percentile(valuesFor(windows, "energy_db"), 0.2) || defaults.target_energy_min_db),
    target_clarity_min: round(percentile(valuesFor(windows, "clarity_score"), 0.2) || defaults.target_clarity_min),
  };
}

function decibels(samples: Float32Array): number {
  if (!samples.length) return -96;
  let sum = 0;
  for (const sample of samples) sum += sample * sample;
  const rms = Math.sqrt(sum / samples.length);
  return rms > 0 ? round(20 * Math.log10(rms)) : -96;
}

function pitchFor(samples: Float32Array, sampleRate: number): number | undefined {
  if (samples.length < 2) return undefined;
  let crossings = 0;
  for (let index = 1; index < samples.length; index += 1) {
    if ((samples[index - 1] <= 0 && samples[index] > 0) || (samples[index - 1] >= 0 && samples[index] < 0)) crossings += 1;
  }
  const pitch = crossings / (2 * (samples.length / sampleRate));
  return pitch >= 65 && pitch <= 400 ? pitch : undefined;
}

function pitchSummary(samples: Float32Array, sampleRate: number): [number | undefined, number | undefined] {
  const frameSize = Math.max(1, Math.round(sampleRate * 0.05));
  const pitches: number[] = [];
  for (let offset = 0; offset < samples.length; offset += frameSize) {
    const frame = samples.subarray(offset, Math.min(offset + frameSize, samples.length));
    if (decibels(frame) <= -45) continue;
    const pitch = pitchFor(frame, sampleRate);
    if (pitch !== undefined) pitches.push(pitch);
  }
  const center = median(pitches);
  if (center === undefined) return [undefined, undefined];
  const offsets = pitches.map((pitch) => 12 * Math.log2(pitch / center));
  const variance = offsets.reduce((sum, value) => sum + (value - mean(offsets)) ** 2, 0) / offsets.length;
  return [round(mean(pitches)), round(Math.sqrt(variance))];
}

function fft(real: Float64Array, imaginary: Float64Array) {
  const count = real.length;
  for (let index = 1, reversed = 0; index < count; index += 1) {
    let bit = count >> 1;
    while (reversed & bit) {
      reversed ^= bit;
      bit >>= 1;
    }
    reversed ^= bit;
    if (index < reversed) {
      [real[index], real[reversed]] = [real[reversed], real[index]];
      [imaginary[index], imaginary[reversed]] = [imaginary[reversed], imaginary[index]];
    }
  }
  for (let length = 2; length <= count; length <<= 1) {
    const angle = (-2 * Math.PI) / length;
    for (let start = 0; start < count; start += length) {
      for (let offset = 0; offset < length / 2; offset += 1) {
        const cosine = Math.cos(angle * offset);
        const sine = Math.sin(angle * offset);
        const even = start + offset;
        const odd = even + length / 2;
        const realOdd = real[odd] * cosine - imaginary[odd] * sine;
        const imaginaryOdd = real[odd] * sine + imaginary[odd] * cosine;
        real[odd] = real[even] - realOdd;
        imaginary[odd] = imaginary[even] - imaginaryOdd;
        real[even] += realOdd;
        imaginary[even] += imaginaryOdd;
      }
    }
  }
}

function spectralFeatures(samples: Float32Array, sampleRate: number) {
  let size = 1;
  while (size * 2 <= Math.min(samples.length, 4096)) size *= 2;
  if (size < 2) return { centroid: 0, rolloff: 0, flatness: 0, zcr: 0, mfcc: Array(13).fill(0) as number[] };
  const real = new Float64Array(size);
  const imaginary = new Float64Array(size);
  for (let index = 0; index < size; index += 1) real[index] = samples[index] * (0.5 - 0.5 * Math.cos((2 * Math.PI * index) / (size - 1)));
  fft(real, imaginary);
  const bins = size / 2 + 1;
  const power = new Float64Array(bins);
  const logPower = new Float64Array(bins);
  let total = 0;
  let weighted = 0;
  let logMagnitude = 0;
  let magnitudeTotal = 0;
  for (let index = 0; index < bins; index += 1) {
    const magnitude = Math.hypot(real[index], imaginary[index]) + 1e-12;
    power[index] = magnitude * magnitude;
    logPower[index] = Math.log(power[index]);
    const frequency = (index * sampleRate) / size;
    total += power[index];
    weighted += frequency * power[index];
    logMagnitude += Math.log(magnitude);
    magnitudeTotal += magnitude;
  }
  let cumulative = 0;
  let rolloffIndex = 0;
  for (; rolloffIndex < bins; rolloffIndex += 1) {
    cumulative += power[rolloffIndex];
    if (cumulative >= total * 0.85) break;
  }
  let crossings = 0;
  for (let index = 1; index < samples.length; index += 1) if ((samples[index - 1] < 0) !== (samples[index] < 0)) crossings += 1;
  const mfcc = Array.from({ length: 13 }, (_, coefficient) => {
    let value = 0;
    for (let index = 0; index < bins; index += 1) value += logPower[index] * Math.cos((Math.PI * coefficient * (index + 0.5)) / bins);
    return round(value / bins, 4);
  });
  return {
    centroid: round(total ? weighted / total : 0),
    rolloff: round((Math.min(rolloffIndex, bins - 1) * sampleRate) / size),
    flatness: round(clamp(Math.exp(logMagnitude / bins) / (magnitudeTotal / bins)), 4),
    zcr: round(clamp(crossings / Math.max(1, samples.length - 1)), 4),
    mfcc,
  };
}

export async function extractWindowsInBrowser(file: File): Promise<FeatureWindow[]> {
  if (file.size > 20 * 1024 * 1024) throw new Error("Each audio file must be 20 MB or smaller.");
  const context = new AudioContext();
  try {
    const decoded = await context.decodeAudioData(await file.arrayBuffer());
    if (!decoded.length || decoded.duration > 600) throw new Error("Audio must be between 0 and 10 minutes.");
    const mono = new Float32Array(decoded.length);
    for (let channel = 0; channel < decoded.numberOfChannels; channel += 1) {
      const data = decoded.getChannelData(channel);
      for (let index = 0; index < data.length; index += 1) mono[index] += data[index] / decoded.numberOfChannels;
    }
    const windowSize = Math.max(1, Math.round(decoded.sampleRate));
    const windows: FeatureWindow[] = [];
    for (let offset = 0; offset < mono.length; offset += windowSize) {
      const chunk = mono.subarray(offset, Math.min(offset + windowSize, mono.length));
      const energy = decibels(chunk);
      const [meanF0, pitchVariation] = energy > -45 ? pitchSummary(chunk, decoded.sampleRate) : [undefined, undefined];
      const spectral = spectralFeatures(chunk, decoded.sampleRate);
      windows.push({
        start_seconds: round(offset / decoded.sampleRate, 3),
        end_seconds: round(Math.min(offset + windowSize, mono.length) / decoded.sampleRate, 3),
        energy_db: energy,
        pause_seconds: energy <= -45 ? round(chunk.length / decoded.sampleRate, 3) : 0,
        mean_f0_hz: meanF0,
        pitch_variation_semitones: pitchVariation,
        spectral_centroid_hz: spectral.centroid,
        spectral_rolloff_hz: spectral.rolloff,
        spectral_flatness: spectral.flatness,
        zero_crossing_rate: spectral.zcr,
        mfcc_means: spectral.mfcc,
      });
    }
    return windows;
  } finally {
    await context.close();
  }
}

function scoreWindows(windows: FeatureWindow[], profile: ReferenceProfile): AnalysisResult {
  const findings: Finding[] = [];
  const severity = (actual: number, expected: number) => round(clamp(Math.abs(actual - expected) / Math.max(Math.abs(expected), 1)), 2);
  for (const window of windows) {
    if (window.speech_rate_wpm !== undefined && window.speech_rate_wpm > profile.target_rate_max_wpm) findings.push({ finding_type: "rushed_delivery", start_seconds: window.start_seconds, end_seconds: window.end_seconds, severity: severity(window.speech_rate_wpm, profile.target_rate_max_wpm), evidence: `Speech rate measured ${window.speech_rate_wpm.toFixed(0)} WPM; the selected profile caps this segment at ${profile.target_rate_max_wpm.toFixed(0)} WPM.`, practice_action: "Rerecord this sentence more slowly and pause after its key claim." });
    if (window.pause_seconds !== undefined && window.pause_seconds > profile.target_pause_max_seconds) findings.push({ finding_type: "excessive_pause", start_seconds: window.start_seconds, end_seconds: window.end_seconds, severity: severity(window.pause_seconds, profile.target_pause_max_seconds), evidence: `Pause measured ${window.pause_seconds.toFixed(2)}s; the selected profile caps an unplanned pause at ${profile.target_pause_max_seconds.toFixed(2)}s.`, practice_action: "Practice linking this phrase to the next thought with a shorter transition." });
    if (window.pitch_variation_semitones !== undefined && window.pitch_variation_semitones < profile.target_pitch_variation_min_semitones) findings.push({ finding_type: "monotone_delivery", start_seconds: window.start_seconds, end_seconds: window.end_seconds, severity: severity(window.pitch_variation_semitones, profile.target_pitch_variation_min_semitones), evidence: `Pitch variation measured ${window.pitch_variation_semitones.toFixed(2)} semitones; the selected profile targets at least ${profile.target_pitch_variation_min_semitones.toFixed(2)}.`, practice_action: "Stress one content word and vary pitch across the sentence." });
    if (window.energy_db !== undefined && window.energy_db < profile.target_energy_min_db) findings.push({ finding_type: "low_energy", start_seconds: window.start_seconds, end_seconds: window.end_seconds, severity: severity(window.energy_db, profile.target_energy_min_db), evidence: `Energy measured ${window.energy_db.toFixed(1)} dB; the selected profile targets at least ${profile.target_energy_min_db.toFixed(1)} dB.`, practice_action: "Move closer to the microphone and deliver this line with supported breath." });
  }
  const dimensionScores: Record<string, number> = {};
  const pitchScores = windows.flatMap((window) => window.pitch_variation_semitones === undefined ? [] : [100 * clamp(window.pitch_variation_semitones / profile.target_pitch_variation_min_semitones)]);
  const energyScores = windows.flatMap((window) => window.energy_db === undefined ? [] : [window.energy_db >= profile.target_energy_min_db ? 100 : 100 * (1 - clamp((profile.target_energy_min_db - window.energy_db) / 12))]);
  if (pitchScores.length) dimensionScores.prosody = round(mean(pitchScores), 1);
  if (energyScores.length) dimensionScores.energy = round(mean(energyScores), 1);
  const weights: Record<string, number> = { pace_and_pauses: 0.3, prosody: 0.25, energy: 0.25, clarity: 0.2 };
  const present = Object.entries(dimensionScores);
  const totalWeight = present.reduce((sum, [name]) => sum + weights[name], 0);
  return {
    overall_score: round(present.reduce((sum, [name, score]) => sum + score * weights[name], 0) / totalWeight, 1),
    dimension_scores: dimensionScores,
    findings: findings.sort((a, b) => a.start_seconds - b.start_seconds),
    scoring_profile: profile,
  };
}

export function analyzeWindowsInBrowser(windows: FeatureWindow[]): AnalysisResult {
  return scoreWindows(windows, defaults);
}

export function compareWindowsInBrowser(referenceWindows: FeatureWindow[], targetWindows: FeatureWindow[]): ContrastiveAnalysis {
  const profile = deriveProfile(referenceWindows);
  const referenceDuration = Math.max(...referenceWindows.map((window) => window.end_seconds));
  const targetDuration = Math.max(...targetWindows.map((window) => window.end_seconds));
  const comparisons: WindowComparison[] = targetWindows.map((target) => {
    const expectedTime = (((target.start_seconds + target.end_seconds) / 2) / targetDuration) * referenceDuration;
    const reference = referenceWindows.reduce((closest, candidate) => Math.abs((candidate.start_seconds + candidate.end_seconds) / 2 - expectedTime) < Math.abs((closest.start_seconds + closest.end_seconds) / 2 - expectedTime) ? candidate : closest);
    const observed: Record<string, number> = {};
    const baseline: Record<string, number> = {};
    const deltas: Record<string, number> = {};
    for (const name of comparableFeatures) {
      const actual = target[name];
      const expected = reference[name];
      if (typeof actual === "number" && typeof expected === "number") {
        observed[name] = round(actual, 4);
        baseline[name] = round(expected, 4);
        deltas[name] = round(actual - expected, 4);
      }
    }
    return { start_seconds: target.start_seconds, end_seconds: target.end_seconds, reference_start_seconds: reference.start_seconds, reference_end_seconds: reference.end_seconds, observed, reference: baseline, deltas };
  });
  return {
    reference_profile: profile,
    analysis: scoreWindows(targetWindows, profile),
    comparisons,
    data_completeness: Object.fromEntries(comparableFeatures.map((name) => [name, targetWindows.some((window) => typeof window[name] === "number")])),
    reference_duration_seconds: referenceDuration,
    target_duration_seconds: targetDuration,
    timing_mode: "normalized_same_script_browser",
  };
}
