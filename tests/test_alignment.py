import pytest

from backend.app.alignment import WordTimestamp, apply_word_timing, validate_word_sequence
from backend.app.domain import FeatureWindow


def test_word_timing_adds_real_wpm_and_preceding_pause() -> None:
    words = (
        WordTimestamp("hello", 0.2, 0.5),
        WordTimestamp("world", 0.6, 0.9),
        WordTimestamp("again", 2.0, 2.3),
    )
    windows = (
        FeatureWindow(0, 1, energy_db=-20),
        FeatureWindow(1, 3, energy_db=-20),
    )

    enriched = apply_word_timing(windows, words)

    assert enriched[0].speech_rate_wpm == 120.0
    assert enriched[0].pause_seconds == 0.2
    assert enriched[1].speech_rate_wpm == 30.0
    assert enriched[1].pause_seconds == 1.1


def test_word_timing_rejects_overlap() -> None:
    with pytest.raises(ValueError, match="non-overlapping"):
        validate_word_sequence(
            (WordTimestamp("one", 0, 0.7), WordTimestamp("two", 0.6, 1.0))
        )
