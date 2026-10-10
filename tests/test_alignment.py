import pytest
from fastapi.testclient import TestClient

from backend.app.alignment import WordTimestamp, apply_word_timing, validate_word_sequence
from backend.app.domain import FeatureWindow
from backend.app.main import app


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


def test_forced_alignment_is_explicitly_gated(tmp_path, monkeypatch) -> None:
    import struct
    import wave

    monkeypatch.setenv("VOXTRACE_ENABLE_ALIGNMENT", "false")
    path = tmp_path / "speech.wav"
    samples = [1_000] * 8_000
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(8_000)
        writer.writeframes(struct.pack(f"<{len(samples)}h", *samples))

    with TestClient(app) as client:
        response = client.post(
            "/v1/alignment/forced-align",
            data={"transcript": "A fixed transcript.", "language_code": "en"},
            files={"audio": ("speech.wav", path.read_bytes(), "audio/wav")},
        )

    assert response.status_code == 503
    assert "forced alignment is disabled" in response.json()["detail"]
