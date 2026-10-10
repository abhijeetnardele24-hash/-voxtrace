import { useMemo, useState } from "react";

import {
  analyzeWindows,
  compareAudio,
  compareWindows,
  extractAcousticWindows,
  type AnalysisResult,
  type ContrastiveAnalysis,
  type Finding,
  type WindowComparison,
} from "./api";
import {
  demoReferenceWindows,
  demoTranscript,
  demoWindows,
  fallbackDemoResult,
} from "./demo";
import {
  analyzeWindowsInBrowser,
  compareWindowsInBrowser,
  extractWindowsInBrowser,
} from "./browserAnalysis";

const findingNames: Record<Finding["finding_type"], string> = {
  rushed_delivery: "Rushed delivery",
  excessive_pause: "Excessive pause",
  monotone_delivery: "Monotone delivery",
  low_energy: "Low energy",
  low_clarity: "Low clarity",
};

const dimensionNames: Record<string, string> = {
  pace_and_pauses: "Pace & pauses",
  prosody: "Prosody",
  energy: "Energy",
  clarity: "Clarity",
};

const featureNames: Record<string, string> = {
  energy_db: "Energy",
  pitch_variation_semitones: "Pitch variation",
  mean_f0_hz: "Mean F0",
  spectral_centroid_hz: "Spectral centroid",
  spectral_rolloff_hz: "Spectral rolloff",
  spectral_flatness: "Spectral flatness",
  zero_crossing_rate: "Zero-crossing rate",
  speech_rate_wpm: "Speech rate",
  pause_seconds: "Pause",
  clarity_score: "Clarity proxy",
};

function formatTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds - minutes * 60;
  return `${String(minutes).padStart(2, "0")}:${remainder.toFixed(1).padStart(4, "0")}`;
}

function scoreTone(score: number): string {
  if (score >= 85) return "good";
  if (score >= 65) return "watch";
  return "risk";
}

function energyHeight(value: number | undefined): number {
  if (value === undefined) return 8;
  return Math.max(8, Math.min(100, (value + 60) * 2.15));
}

function displayValue(name: string, value: number | undefined): string {
  if (value === undefined) return "—";
  const units: Record<string, string> = {
    energy_db: " dBFS",
    pitch_variation_semitones: " st",
    mean_f0_hz: " Hz",
    spectral_centroid_hz: " Hz",
    spectral_rolloff_hz: " Hz",
    speech_rate_wpm: " WPM",
    pause_seconds: " s",
  };
  return `${Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(2)}${units[name] ?? ""}`;
}

function localDemoComparison(): WindowComparison[] {
  return demoWindows.map((window, index) => {
    const reference = demoReferenceWindows[index];
    const observed = Object.fromEntries(
      Object.entries(window).filter((entry): entry is [string, number] => typeof entry[1] === "number"),
    );
    const baseline = Object.fromEntries(
      Object.entries(reference).filter((entry): entry is [string, number] => typeof entry[1] === "number"),
    );
    const deltas = Object.fromEntries(
      Object.keys(observed)
        .filter((key) => baseline[key] !== undefined && !key.endsWith("seconds"))
        .map((key) => [key, observed[key] - baseline[key]]),
    );
    return {
      start_seconds: window.start_seconds,
      end_seconds: window.end_seconds,
      reference_start_seconds: reference.start_seconds,
      reference_end_seconds: reference.end_seconds,
      observed,
      reference: baseline,
      deltas,
    };
  });
}

function App() {
  const [analysis, setAnalysis] = useState<AnalysisResult>(fallbackDemoResult);
  const [comparison, setComparison] = useState<WindowComparison[]>(localDemoComparison);
  const [completeness, setCompleteness] = useState<Record<string, boolean>>({
    speech_rate_wpm: true,
    pause_seconds: true,
    pitch_variation_semitones: true,
    energy_db: true,
    clarity_score: true,
    spectral_centroid_hz: false,
    spectral_rolloff_hz: false,
    spectral_flatness: false,
    zero_crossing_rate: false,
    mean_f0_hz: false,
  });
  const [transcript, setTranscript] = useState(demoTranscript);
  const [referenceAudio, setReferenceAudio] = useState<File | null>(null);
  const [targetAudio, setTargetAudio] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState(
    "Seeded contrastive demo. Run analysis to verify the values through the local API.",
  );

  const findings = useMemo(
    () => analysis.findings.slice().sort((a, b) => a.start_seconds - b.start_seconds),
    [analysis.findings],
  );
  const duration = Math.max(15, ...comparison.map((item) => item.end_seconds));
  const availableFeatures = Object.values(completeness).filter(Boolean).length;
  const priorityAction = findings.slice().sort((a, b) => b.severity - a.severity)[0]?.practice_action;

  async function runAnalysis() {
    setIsLoading(true);
    try {
      if (referenceAudio && targetAudio) {
        setStatus("Extracting both recordings and computing measured baseline deltas…");
        const result = await compareAudio(referenceAudio, targetAudio);
        applyContrastiveResult(result);
        setStatus(
          "Measured comparison complete. Windows are mapped by normalized same-script time; transcript forced alignment is a separate optional pipeline.",
        );
      } else if (targetAudio) {
        setStatus("Extracting target recording features without a reference baseline…");
        const windows = await extractAcousticWindows(targetAudio);
        const result = await analyzeWindows(windows);
        setAnalysis(result);
        setComparison([]);
        setCompleteness({
          energy_db: true,
          pause_seconds: true,
          pitch_variation_semitones: true,
          mean_f0_hz: true,
          spectral_centroid_hz: true,
          spectral_rolloff_hz: true,
          spectral_flatness: true,
          zero_crossing_rate: true,
          speech_rate_wpm: false,
          clarity_score: false,
        });
        setStatus("Target-only analysis complete. Add the ideal same-script recording for contrastive deltas.");
      } else {
        setStatus("Running the seeded ideal-vs-flawed windows through the API…");
        const result = await compareWindows(demoReferenceWindows, demoWindows);
        applyContrastiveResult(result);
        setStatus("Seeded API comparison verified. All visible values come from the checked-in demo windows.");
      }
    } catch (error) {
      try {
        if (referenceAudio && targetAudio) {
          setStatus("The API is unavailable; measuring both recordings locally in your browser…");
          const [referenceWindows, targetWindows] = await Promise.all([
            extractWindowsInBrowser(referenceAudio),
            extractWindowsInBrowser(targetAudio),
          ]);
          applyContrastiveResult(compareWindowsInBrowser(referenceWindows, targetWindows));
          setStatus("On-device comparison complete. Audio stayed in this browser; transcript-dependent speech rate and clarity remain unavailable without forced alignment.");
        } else if (targetAudio) {
          setStatus("The API is unavailable; measuring the target recording locally in your browser…");
          const windows = await extractWindowsInBrowser(targetAudio);
          setAnalysis(analyzeWindowsInBrowser(windows));
          setComparison([]);
          setCompleteness({ energy_db: true, pause_seconds: true, pitch_variation_semitones: true, mean_f0_hz: true, spectral_centroid_hz: true, spectral_rolloff_hz: true, spectral_flatness: true, zero_crossing_rate: true, speech_rate_wpm: false, clarity_score: false });
          setStatus("On-device target analysis complete. Add an ideal recording for contrastive deltas.");
        } else {
          setAnalysis(fallbackDemoResult);
          setComparison(localDemoComparison());
          setStatus(`Checked-in deterministic demo loaded locally. ${error instanceof Error ? error.message : ""}`);
        }
      } catch (localError) {
        setStatus(`Analysis could not be completed. ${localError instanceof Error ? localError.message : "Please use a valid audio file."}`);
      }
    } finally {
      setIsLoading(false);
    }
  }

  function applyContrastiveResult(result: ContrastiveAnalysis) {
    setAnalysis(result.analysis);
    setComparison(result.comparisons);
    setCompleteness(result.data_completeness);
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="VoxTrace home">
          <span className="brand-mark" aria-hidden="true">V</span>
          <span>VoxTrace</span>
        </a>
        <nav className="topbar-links" aria-label="Project links">
          <span className="topbar-meta"><i className="live-dot" />Evidence-first engine</span>
          <a href="#method">Method</a>
          <a href="https://github.com/abhijeetnardele24-hash/-voxtrace">Source</a>
        </nav>
      </header>

      <section className="hero" id="top">
        <div>
          <p className="eyebrow">MULTIMODAL AI HACKATHON 2026 · TRACK C</p>
          <h1>Audit every delivery flaw against acoustic evidence.</h1>
          <p className="hero-copy">
            Compare the same script's ideal and target recordings, isolate exact deviation windows,
            and turn the measured delta into practice—not vague AI judgement.
          </p>
          <div className="proof-row">
            <span><b>Input</b> 16-bit PCM WAV</span>
            <span><b>Privacy</b> ephemeral processing</span>
            <span><b>Scoring</b> deterministic</span>
          </div>
        </div>
        <article className="overall-card hero-score">
          <p>Current delivery score</p>
          <div className={`overall-score ${scoreTone(analysis.overall_score)}`}>
            {analysis.overall_score.toFixed(1)}<span>/100</span>
          </div>
          <small>{availableFeatures}/10 feature families available in this run</small>
        </article>
      </section>

      <section className="score-grid" aria-label="Speech scoring overview">
        {Object.entries(analysis.dimension_scores).map(([dimension, score]) => (
          <article className="metric-card" key={dimension}>
            <div className="metric-card-header">
              <span>{dimensionNames[dimension] ?? dimension}</span>
              <strong className={scoreTone(score)}>{score.toFixed(1)}</strong>
            </div>
            <div className="progress-track"><span className={`progress-fill ${scoreTone(score)}`} style={{ width: `${score}%` }} /></div>
            <small>{completeness[dimension === "pace_and_pauses" ? "speech_rate_wpm" : dimension === "prosody" ? "pitch_variation_semitones" : dimension === "energy" ? "energy_db" : "clarity_score"] ? "measured" : "not available"}</small>
          </article>
        ))}
      </section>

      <section className="workspace-grid">
        <article className="panel input-panel">
          <div className="panel-heading">
            <div><p className="eyebrow">CONTRASTIVE INPUT</p><h2>Same script, two deliveries</h2></div>
            <span className="status-chip">No cloud upload</span>
          </div>
          <div className="dual-upload">
            <label className="upload-zone">
              <input type="file" accept="audio/wav,.wav" onChange={(event) => setReferenceAudio(event.target.files?.[0] ?? null)} />
              <span className="upload-role">IDEAL BASELINE</span>
              <strong>{referenceAudio?.name ?? "Choose reference WAV"}</strong>
              <small>Same transcript · effective delivery</small>
            </label>
            <label className="upload-zone">
              <input type="file" accept="audio/wav,.wav" onChange={(event) => setTargetAudio(event.target.files?.[0] ?? null)} />
              <span className="upload-role">TARGET DELIVERY</span>
              <strong>{targetAudio?.name ?? "Choose target WAV"}</strong>
              <small>Recording to evaluate</small>
            </label>
          </div>
          <label className="transcript-label" htmlFor="transcript">Shared transcript</label>
          <textarea id="transcript" value={transcript} onChange={(event) => setTranscript(event.target.value)} rows={5} maxLength={10_000} />
          <button className="primary-button" type="button" onClick={runAnalysis} disabled={isLoading}>
            {isLoading ? "Measuring…" : referenceAudio && targetAudio ? "Compare recordings" : targetAudio ? "Analyze target only" : "Run seeded contrastive demo"}
          </button>
          <p className="api-status" role="status">{status}</p>
        </article>

        <article className="panel timeline-panel">
          <div className="panel-heading">
            <div><p className="eyebrow">TEMPORAL PROOF</p><h2>Baseline vs target energy</h2></div>
            <span className="status-chip">{findings.length} grounded findings</span>
          </div>
          <div className="timeline-legend">
            <span><i className="legend-good" /> ideal baseline</span>
            <span><i className="legend-target" /> target recording</span>
            <span><i className="legend-risk" /> flaw interval</span>
          </div>
          <div className="timeline">
            <div className="timeline-axis"><span>00:00</span><span>{formatTime(duration / 2)}</span><span>{formatTime(duration)}</span></div>
            <div className="comparison-waveform" aria-label="Measured baseline and target energy windows">
              {(comparison.length ? comparison : localDemoComparison()).map((item, index) => (
                <div className="wave-pair" key={`${item.start_seconds}-${index}`}>
                  <i className="wave-reference" style={{ height: `${energyHeight(item.reference.energy_db)}%` }} title={`Baseline ${displayValue("energy_db", item.reference.energy_db)}`} />
                  <i className="wave-target" style={{ height: `${energyHeight(item.observed.energy_db)}%` }} title={`Target ${displayValue("energy_db", item.observed.energy_db)}`} />
                </div>
              ))}
            </div>
            <div className="finding-lanes">
              {findings.map((finding, index) => (
                <span className="timeline-finding" key={`${finding.finding_type}-${finding.start_seconds}-${index}`} style={{ left: `${(finding.start_seconds / duration) * 100}%`, width: `${Math.max(((finding.end_seconds - finding.start_seconds) / duration) * 100, 6)}%` }} title={finding.evidence}>
                  {findingNames[finding.finding_type]}
                </span>
              ))}
            </div>
          </div>
          <aside className="practice-box"><span>PRIORITY PRACTICE</span><p>{priorityAction ?? "No threshold-supported issue was found in the available features."}</p></aside>
        </article>
      </section>

      <section className="panel findings-panel">
        <div className="panel-heading">
          <div><p className="eyebrow">CAUSAL AUDIT TRAIL</p><h2>Measured findings</h2></div>
          <span className="evidence-badge">Missing metrics stay missing</span>
        </div>
        <div className="findings-list">
          {findings.length ? findings.map((finding, index) => (
            <article className="finding-card" key={`${finding.finding_type}-${finding.start_seconds}-${index}`}>
              <div className="finding-time">{formatTime(finding.start_seconds)}–{formatTime(finding.end_seconds)}</div>
              <div><h3>{findingNames[finding.finding_type]}</h3><p>{finding.evidence}</p><small>{finding.practice_action}</small></div>
              <div className="severity"><span>relative deviation</span><strong>{Math.round(finding.severity * 100)}%</strong></div>
            </article>
          )) : <div className="empty-state">No issue was supported by the currently available measurements.</div>}
        </div>
      </section>

      <section className="evidence-grid" id="method">
        <article className="panel">
          <p className="eyebrow">FEATURE EXTRACTION</p><h2>What this run can prove</h2>
          <div className="feature-matrix">
            {Object.entries(featureNames).map(([key, label]) => <span className={completeness[key] ? "available" : "missing"} key={key}><i />{label}<b>{completeness[key] ? "available" : "missing"}</b></span>)}
          </div>
        </article>
        <article className="panel">
          <p className="eyebrow">REPRODUCIBILITY</p><h2>Submission evidence</h2>
          <ul className="evidence-list">
            <li><b>26 automated tests</b><span>API, DSP, alignment contracts, comparison, evaluation</span></li>
            <li><b>Speaker-held-out evaluation</b><span>Synthetic stress report complete; natural benchmark remains future work</span></li>
            <li><b>Forced alignment</b><span>Optional WhisperX phoneme alignment, explicitly gated on the server</span></li>
            <li><b>Transparent limits</b><span>No invented confidence, model accuracy, or dataset claims</span></li>
          </ul>
        </article>
      </section>

      <footer>
        <span>VoxTrace is an educational coaching prototype—not a medical or universal judging system.</span>
        <span>Source, dataset schema, evaluation protocol, and AI disclosure are documented in the repository.</span>
      </footer>
    </main>
  );
}

export default App;
