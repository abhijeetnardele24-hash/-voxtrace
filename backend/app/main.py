"""HTTP API for the VoxTrace deterministic scoring engine."""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from .alignment import WordTimestamp, apply_word_timing
from .audio import AudioValidationError, extract_acoustic_windows, load_pcm_wav
from .comparison import compare_windows
from .domain import FeatureWindow, ReferenceProfile
from .forced_alignment import ForcedAlignmentUnavailable, force_align_transcript
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
    mean_f0_hz: float | None = Field(default=None, gt=0)
    energy_db: float | None = None
    spectral_centroid_hz: float | None = Field(default=None, ge=0)
    spectral_rolloff_hz: float | None = Field(default=None, ge=0)
    spectral_flatness: float | None = Field(default=None, ge=0, le=1)
    zero_crossing_rate: float | None = Field(default=None, ge=0, le=1)
    mfcc_means: tuple[float, ...] | None = Field(default=None, min_length=1, max_length=40)
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
    windows: list[FeatureWindowRequest] = Field(min_length=1, max_length=1200)
    profile: ProfileRequest | None = None


class ComparisonRequest(BaseModel):
    reference_windows: list[FeatureWindowRequest] = Field(min_length=1, max_length=1200)
    target_windows: list[FeatureWindowRequest] = Field(min_length=1, max_length=1200)


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
    windows: list[FeatureWindowRequest] = Field(min_length=1, max_length=1200)
    words: list[WordTimestampRequest] = Field(min_length=1, max_length=5000)


def _window_payload(window: FeatureWindow) -> dict[str, object]:
    return asdict(window)


async def _decode_upload(audio: UploadFile) -> object:
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
        return load_pcm_wav(temporary_path)
    except AudioValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


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


@app.post("/v1/compare/windows")
def compare_feature_windows(request: ComparisonRequest) -> dict[str, object]:
    """Compare measured target windows with an ideal-delivery reference."""

    try:
        result = compare_windows(
            (window.to_domain() for window in request.reference_windows),
            (window.to_domain() for window in request.target_windows),
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
        "windows": [_window_payload(window) for window in windows],
    }


@app.post("/v1/alignment/forced-align")
async def forced_align_uploaded_audio(
    request: Request,
    audio: UploadFile = File(...),
    transcript: str = Form(..., min_length=1, max_length=10_000),
    language_code: str = Form(default="en", pattern="^[A-Za-z]{2,3}$"),
) -> dict[str, object]:
    """Run optional phoneme forced alignment on one validated WAV and transcript."""

    client_key = request.client.host if request.client else "unknown-client"
    allowed, retry_after = UPLOAD_RATE_LIMITER.check(f"align:{client_key}")
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="alignment limit reached; retry shortly",
            headers={"Retry-After": str(retry_after)},
        )
    content = await audio.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="audio upload exceeds the 20 MB limit")
    if not content:
        raise HTTPException(status_code=422, detail="audio upload is empty")
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(suffix=".wav", delete=False) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)
        decoded = load_pcm_wav(temporary_path)
        words = force_align_transcript(
            temporary_path,
            transcript,
            decoded.duration_seconds,
            language_code.lower(),
        )
        return {
            "timing_provenance": "whisperx_phoneme_forced_alignment",
            "language_code": language_code.lower(),
            "duration_seconds": round(decoded.duration_seconds, 3),
            "words": [asdict(word) for word in words],
        }
    except AudioValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ForcedAlignmentUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


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
    decoded = await _decode_upload(audio)
    windows = extract_acoustic_windows(decoded)
    return {
        "duration_seconds": round(decoded.duration_seconds, 3),
        "analysis_capability": "fft_mfcc_energy_pause_f0_pitch_variation",
        "windows": [_window_payload(window) for window in windows],
    }


@app.post("/v1/audio/compare")
async def compare_uploaded_audio(
    request: Request,
    reference_audio: UploadFile = File(...),
    target_audio: UploadFile = File(...),
) -> dict[str, object]:
    """Extract and compare two same-script WAV recordings without persistence."""

    client_key = request.client.host if request.client else "unknown-client"
    allowed, retry_after = UPLOAD_RATE_LIMITER.check(f"compare:{client_key}")
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="comparison upload limit reached; retry shortly",
            headers={"Retry-After": str(retry_after)},
        )
    reference = await _decode_upload(reference_audio)
    target = await _decode_upload(target_audio)
    reference_windows = extract_acoustic_windows(reference)
    target_windows = extract_acoustic_windows(target)
    result = compare_windows(reference_windows, target_windows)
    payload = result.as_dict()
    payload.update(
        {
            "reference_duration_seconds": round(reference.duration_seconds, 3),
            "target_duration_seconds": round(target.duration_seconds, 3),
            "timing_mode": "normalized_same_script_comparison",
        }
    )
    return payload
