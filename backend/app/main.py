"""HTTP API for the VoxTrace deterministic scoring engine."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from .alignment import WordTimestamp, apply_word_timing
from .audio import AudioValidationError, extract_acoustic_windows, load_pcm_wav
from .domain import FeatureWindow, ReferenceProfile
from .rate_limit import FixedWindowRateLimiter
from .scoring import analyze_windows

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
UPLOAD_RATE_LIMITER = FixedWindowRateLimiter(max_requests=20, window_seconds=60)

app = FastAPI(
    title="VoxTrace API",
    version="0.1.0",
    description="Timestamp-grounded, deterministic speech delivery analysis.",
)

_configured_origins = os.getenv(
    "VOXTRACE_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in _configured_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class FeatureWindowRequest(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    speech_rate_wpm: float | None = Field(default=None, ge=0)
    pause_seconds: float | None = Field(default=None, ge=0)
    pitch_variation_semitones: float | None = Field(default=None, ge=0)
    energy_db: float | None = None
    clarity_score: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def end_must_follow_start(self) -> "FeatureWindowRequest":
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds")
        return self

    def to_domain(self) -> FeatureWindow:
        return FeatureWindow(**self.model_dump())


class ProfileRequest(BaseModel):
    target_rate_min_wpm: float = Field(default=130, ge=1)
    target_rate_max_wpm: float = Field(default=170, ge=1)
    target_pause_max_seconds: float = Field(default=1.4, gt=0)
    target_pitch_variation_min_semitones: float = Field(default=1.5, ge=0)
    target_energy_min_db: float = -28
    target_clarity_min: float = Field(default=0.70, ge=0, le=1)

    @model_validator(mode="after")
    def valid_rate_range(self) -> "ProfileRequest":
        if self.target_rate_min_wpm >= self.target_rate_max_wpm:
            raise ValueError("target_rate_min_wpm must be lower than target_rate_max_wpm")
        return self

    def to_domain(self) -> ReferenceProfile:
        return ReferenceProfile(**self.model_dump())


class AnalysisRequest(BaseModel):
    windows: list[FeatureWindowRequest] = Field(min_length=1)
    profile: ProfileRequest | None = None


class WordTimestampRequest(BaseModel):
    text: str = Field(min_length=1, max_length=128)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    source: str = Field(default="forced_alignment", pattern="^(forced_alignment|human_review)$")

    @model_validator(mode="after")
    def end_must_follow_start(self) -> "WordTimestampRequest":
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds")
        return self

    def to_domain(self) -> WordTimestamp:
        return WordTimestamp(**self.model_dump())


class WordTimedFeatureRequest(BaseModel):
    windows: list[FeatureWindowRequest] = Field(min_length=1)
    words: list[WordTimestampRequest] = Field(min_length=1)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "voxtrace-api"}


@app.post("/v1/analyze/windows")
def analyze_feature_windows(request: AnalysisRequest) -> dict[str, object]:
    """Analyze already-extracted windows; audio extraction is intentionally separate."""

    try:
        result = analyze_windows(
            (window.to_domain() for window in request.windows),
            request.profile.to_domain() if request.profile else None,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return result.as_dict()


@app.post("/v1/alignment/apply-word-timing")
def apply_aligned_word_timing(request: WordTimedFeatureRequest) -> dict[str, object]:
    """Enrich acoustic windows with WPM/pause measurements from verified word timing."""

    try:
        windows = apply_word_timing(
            (window.to_domain() for window in request.windows),
            (word.to_domain() for word in request.words),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {
        "analysis_capability": "acoustic_features_plus_word_timestamps",
        "timing_provenance": "provided_alignment",
        "windows": [
            {
                "start_seconds": window.start_seconds,
                "end_seconds": window.end_seconds,
                "speech_rate_wpm": window.speech_rate_wpm,
                "pause_seconds": window.pause_seconds,
                "pitch_variation_semitones": window.pitch_variation_semitones,
                "energy_db": window.energy_db,
                "clarity_score": window.clarity_score,
            }
            for window in windows
        ],
    }


@app.post("/v1/audio/feature-windows")
async def extract_uploaded_audio_features(
    request: Request, audio: UploadFile = File(...)
) -> dict[str, object]:
    """Return measured acoustic windows for a small PCM WAV upload.

    This endpoint deliberately does not claim transcript alignment, speech rate,
    or clarity. Those are supplied only after their own validated pipelines run.
    """

    client_key = request.client.host if request.client else "unknown-client"
    allowed, retry_after = UPLOAD_RATE_LIMITER.check(client_key)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="upload limit reached; retry shortly",
            headers={"Retry-After": str(retry_after)},
        )
    content = await audio.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"audio upload exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
        )
    if not content:
        raise HTTPException(status_code=422, detail="audio upload is empty")

    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(suffix=".wav", delete=False) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)
        decoded = load_pcm_wav(temporary_path)
        windows = extract_acoustic_windows(decoded)
        return {
            "duration_seconds": round(decoded.duration_seconds, 3),
            "analysis_capability": "baseline_dsp_energy_pause_pitch_variation",
            "windows": [
                {
                    "start_seconds": window.start_seconds,
                    "end_seconds": window.end_seconds,
                    "energy_db": window.energy_db,
                    "pause_seconds": window.pause_seconds,
                    "pitch_variation_semitones": window.pitch_variation_semitones,
                }
                for window in windows
            ],
        }
    except AudioValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
