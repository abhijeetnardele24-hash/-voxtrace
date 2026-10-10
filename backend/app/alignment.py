"""Validated word-timestamp contracts and derived delivery measurements.

This module intentionally accepts timestamps produced by a real aligner; it
never synthesizes word timing from a transcript length or audio duration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .domain import FeatureWindow


@dataclass(frozen=True, slots=True)
class WordTimestamp:
    """One spoken word located by an alignment engine or human review."""

    text: str
    start_seconds: float
    end_seconds: float
    confidence: float | None = None
    source: str = "forced_alignment"

    def __post_init__(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError("word text cannot be empty")
        if self.start_seconds < 0 or self.end_seconds <= self.start_seconds:
            raise ValueError("word timestamps must be a positive interval")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("word confidence must be between 0 and 1")
        if self.source not in {"forced_alignment", "human_review"}:
            raise ValueError("word source must be forced_alignment or human_review")


def validate_word_sequence(words: Iterable[WordTimestamp]) -> tuple[WordTimestamp, ...]:
    """Reject overlapping or unordered words instead of silently repairing them."""

    ordered = tuple(words)
    if not ordered:
        raise ValueError("at least one word timestamp is required")
    previous_end = 0.0
    for word in ordered:
        if word.start_seconds < previous_end:
            raise ValueError("word timestamps must be ordered and non-overlapping")
        previous_end = word.end_seconds
    return ordered


def apply_word_timing(
    acoustic_windows: Iterable[FeatureWindow], words: Iterable[WordTimestamp]
) -> tuple[FeatureWindow, ...]:
    """Add measured WPM and preceding pause values to existing acoustic windows.

    WPM is populated only when a word is located within the window.  A pause is
    the gap immediately before the first word in that window, so it is a real
    word-boundary pause rather than a silence-window proxy.
    """

    verified_words = validate_word_sequence(words)
    previous_end_by_start = {
        word.start_seconds: (verified_words[index - 1].end_seconds if index else 0.0)
        for index, word in enumerate(verified_words)
    }
    result: list[FeatureWindow] = []
    for window in acoustic_windows:
        contained = tuple(
            word
            for word in verified_words
            if window.start_seconds <= word.start_seconds < window.end_seconds
        )
        rate = (
            round(len(contained) * 60 / (window.end_seconds - window.start_seconds), 1)
            if contained
            else None
        )
        pause = None
        if contained:
            first = contained[0]
            pause = round(max(0.0, first.start_seconds - previous_end_by_start[first.start_seconds]), 3)
        result.append(
            FeatureWindow(
                start_seconds=window.start_seconds,
                end_seconds=window.end_seconds,
                speech_rate_wpm=rate,
                pause_seconds=pause,
                pitch_variation_semitones=window.pitch_variation_semitones,
                energy_db=window.energy_db,
                clarity_score=window.clarity_score,
            )
        )
    return tuple(result)
