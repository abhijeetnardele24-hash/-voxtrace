"""Optional WhisperX phoneme alignment with strict, explicit provenance."""

from __future__ import annotations

import os
from pathlib import Path
from threading import Lock

from .alignment import WordTimestamp, validate_word_sequence


class ForcedAlignmentUnavailable(RuntimeError):
    """Raised when the optional alignment runtime is disabled or unavailable."""


_ALIGNMENT_LOCK = Lock()


def _enabled() -> bool:
    return os.getenv("VOXTRACE_ENABLE_ALIGNMENT", "false").lower() in {"1", "true", "yes"}


def force_align_transcript(
    audio_path: Path,
    transcript: str,
    duration_seconds: float,
    language_code: str = "en",
) -> tuple[WordTimestamp, ...]:
    """Align a fixed transcript to validated audio using WhisperX's phoneme model.

    The optional model is deliberately gated because loading it is resource-heavy.
    Calls are serialized so anonymous requests cannot load multiple model copies.
    """

    if not _enabled():
        raise ForcedAlignmentUnavailable(
            "forced alignment is disabled; set VOXTRACE_ENABLE_ALIGNMENT=true after installing the alignment extras"
        )
    normalized_transcript = " ".join(transcript.split())
    if not normalized_transcript:
        raise ValueError("transcript cannot be blank")
    if len(normalized_transcript) > 10_000:
        raise ValueError("transcript exceeds the 10,000 character limit")
    if not language_code.isalpha() or not 2 <= len(language_code) <= 3:
        raise ValueError("language_code must contain two or three letters")

    try:
        import whisperx
    except ImportError as error:
        raise ForcedAlignmentUnavailable(
            "WhisperX is not installed; install backend/requirements-alignment.txt"
        ) from error

    device = os.getenv("VOXTRACE_ALIGNMENT_DEVICE", "cpu")
    cache_only = os.getenv("VOXTRACE_ALIGNMENT_CACHE_ONLY", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    segments = [{"start": 0.0, "end": duration_seconds, "text": normalized_transcript}]
    with _ALIGNMENT_LOCK:
        audio = whisperx.load_audio(str(audio_path))
        model, metadata = whisperx.load_align_model(
            language_code=language_code,
            device=device,
            model_cache_only=cache_only,
        )
        result = whisperx.align(
            segments,
            model,
            metadata,
            audio,
            device,
            return_char_alignments=False,
            print_progress=False,
        )

    words: list[WordTimestamp] = []
    for item in result.get("word_segments", []):
        if item.get("start") is None or item.get("end") is None:
            continue
        text = str(item.get("word", "")).strip()
        if not text:
            continue
        score = item.get("score")
        words.append(
            WordTimestamp(
                text=text,
                start_seconds=round(float(item["start"]), 3),
                end_seconds=round(float(item["end"]), 3),
                confidence=round(float(score), 4) if score is not None else None,
                source="forced_alignment",
            )
        )
    if not words:
        raise ValueError("the alignment model returned no word timestamps")
    return validate_word_sequence(words)
