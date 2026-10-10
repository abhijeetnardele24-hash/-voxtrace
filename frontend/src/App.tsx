import { useMemo, useState } from "react";

import {
  analyzeWindows,
  extractAcousticWindows,
  type AnalysisResult,
  type Finding,
} from "./api";
import { demoTranscript, demoWindows, fallbackDemoResult } from "./demo";

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

function formatTime(seconds: number): string {
  const wholeSeconds = Math.floor(seconds);
  return `${String(Math.floor(wholeSeconds / 60)).padStart(2, "0")}:${String(
    wholeSeconds % 60,
  ).padStart(2, "0")}`;
}

function scoreTone(score: number): string {
  if (score >= 85) return "good";
  if (score >= 65) return "watch";
  return "risk";
}

function App() {
  const [analysis, setAnalysis] = useState<AnalysisResult>(fallbackDemoResult);
  const [transcript, setTranscript] = useState(demoTranscript);
  const [selectedAudio, setSelectedAudio] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState("Showing a seeded demo. Run the analysis to call the local API.");

  const strongestPracticeAction = analysis.findings
    .slice()
    .sort((a, b) => b.severity - a.severity)[0]?.practice_action;

  const timelineFindings = useMemo(
    () => analysis.findings.slice().sort((a, b) => a.start_seconds - b.start_seconds),
    [analysis.findings],
  );

  async function runDemoAnalysis() {
    setIsLoading(true);
    setStatus(
      selectedAudio
        ? `Uploading ${selectedAudio.name} for measured baseline analysis…`
        : "Analyzing seeded feature windows through the VoxTrace API…",
    );
    try {
      const windows = selectedAudio
        ? await extractAcousticWindows(selectedAudio)
        : demoWindows;
      const result = await analyzeWindows(windows);
      setAnalysis(result);
      setStatus(
        selectedAudio
          ? "Live baseline result received. This WAV workflow measures energy, silence, and pitch variation; transcript alignment and speech-rate analysis will be added separately."
          : "Live API result received. Every displayed issue is tied to a measured feature window.",
      );
    } catch (error) {
      setAnalysis(fallbackDemoResult);
      setStatus(
        `The local API could not be reached, so this dashboard is showing the bundled evidence-preserving demo. ${
          error instanceof Error ? error.message : ""
        }`,
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#" aria-label="VoxTrace home">
          <span className="brand-mark" aria-hidden="true">V</span>
          <span>VoxTrace</span>
        </a>
        <div className="topbar-meta">
          <span className="live-dot" aria-hidden="true" />
          <span>Evidence-first analysis</span>
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">CONTRASTIVE SPEECH ANALYTICS</p>
          <h1>Know exactly where your delivery loses the room.</h1>
          <p className="hero-copy">
            VoxTrace turns acoustic evidence into timestamped coaching—not vague AI feedback.
          </p>
        </div>
        <div className="hero-proof">
          <span>DEMO PROFILE</span>
          <strong>Speaker A · Script 01</strong>
          <small>All findings are reproducible from measured windows.</small>
        </div>
      </section>

      <section className="score-grid" aria-label="Speech scoring overview">
        <article className="overall-card">
          <p>Overall delivery score</p>
          <div className={`overall-score ${scoreTone(analysis.overall_score)}`}>
            {analysis.overall_score.toFixed(1)}
            <span>/100</span>
          </div>
          <small>Transparent profile-based scoring</small>
        </article>
        {Object.entries(analysis.dimension_scores).map(([dimension, score]) => (
          <article className="metric-card" key={dimension}>
            <div className="metric-card-header">
              <span>{dimensionNames[dimension] ?? dimension}</span>
              <strong className={scoreTone(score)}>{score.toFixed(1)}</strong>
            </div>
            <div className="progress-track" aria-label={`${dimension} score ${score}`}>
              <span className={`progress-fill ${scoreTone(score)}`} style={{ width: `${score}%` }} />
            </div>
          </article>
        ))}
      </section>

      <section className="workspace-grid">
        <article className="panel input-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">INPUT</p>
              <h2>Speech workspace</h2>
            </div>
            <span className="status-chip">PCM WAV ready</span>
          </div>
          <label className="upload-zone">
            <input
              type="file"
              accept="audio/wav,.wav"
              onChange={(event) => setSelectedAudio(event.target.files?.[0] ?? null)}
            />
            <span className="upload-icon" aria-hidden="true">↑</span>
            <strong>{selectedAudio ? selectedAudio.name : "Upload a WAV recording"}</strong>
            <small>
              {selectedAudio
                ? "Ready for measured baseline analysis"
                : "16-bit PCM WAV · up to 20 MB"}
            </small>
          </label>
          <label className="transcript-label" htmlFor="transcript">
            Transcript
          </label>
          <textarea
            id="transcript"
            value={transcript}
            onChange={(event) => setTranscript(event.target.value)}
            rows={5}
          />
          <button className="primary-button" type="button" onClick={runDemoAnalysis} disabled={isLoading}>
            {isLoading
              ? "Analyzing…"
              : selectedAudio
                ? "Analyze uploaded recording"
                : "Run evidence-backed demo"}
          </button>
          <p className="api-status" role="status">{status}</p>
        </article>

        <article className="panel timeline-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">TEMPORAL GROUNDING</p>
              <h2>Delivery timeline</h2>
            </div>
            <span className="status-chip">{timelineFindings.length} findings</span>
          </div>
          <div className="timeline-legend">
            <span><i className="legend-good" /> within profile</span>
            <span><i className="legend-risk" /> evidence-backed issue</span>
          </div>
          <div className="timeline" aria-label="15 second speech timeline">
            <div className="timeline-axis"><span>00:00</span><span>00:05</span><span>00:10</span><span>00:15</span></div>
            <div className="waveform" aria-hidden="true">
              {Array.from({ length: 52 }, (_, index) => (
                <i key={index} style={{ height: `${20 + ((index * 23) % 72)}%` }} />
              ))}
            </div>
            <div className="finding-lanes">
              {timelineFindings.map((finding) => (
                <span
                  className="timeline-finding"
                  key={`${finding.finding_type}-${finding.start_seconds}`}
                  style={{
                    left: `${(finding.start_seconds / 15) * 100}%`,
                    width: `${Math.max(((finding.end_seconds - finding.start_seconds) / 15) * 100, 7)}%`,
                  }}
                  title={`${findingNames[finding.finding_type]}: ${finding.evidence}`}
                >
                  {findingNames[finding.finding_type]}
                </span>
              ))}
            </div>
          </div>
          <aside className="practice-box">
            <span>PRIORITY PRACTICE</span>
            <p>{strongestPracticeAction ?? "No issue detected in the currently measured windows."}</p>
          </aside>
        </article>
      </section>

      <section className="panel findings-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">CAUSAL EXPLANATIONS</p>
            <h2>What the system measured</h2>
          </div>
          <span className="evidence-badge">No inferred metrics</span>
        </div>
        <div className="findings-list">
          {timelineFindings.map((finding) => (
            <article className="finding-card" key={`${finding.finding_type}-${finding.start_seconds}`}>
              <div className="finding-time">
                {formatTime(finding.start_seconds)}–{formatTime(finding.end_seconds)}
              </div>
              <div>
                <h3>{findingNames[finding.finding_type]}</h3>
                <p>{finding.evidence}</p>
              </div>
              <div className="severity">
                <span>severity</span>
                <strong>{Math.round(finding.severity * 100)}%</strong>
              </div>
            </article>
          ))}
        </div>
      </section>

      <footer>
        <span>VoxTrace is an educational coaching prototype.</span>
        <span>Scores are evidence-backed, not a universal judgement of speaking ability.</span>
      </footer>
    </main>
  );
}

export default App;
