import struct
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.audio import (
    AudioValidationError,
    extract_acoustic_windows,
    extract_energy_windows,
    load_pcm_wav,
)
from backend.app.main import app


def _write_pcm_wav(path: Path, samples: list[int], sample_rate: int = 8_000) -> None:
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def test_load_and_extract_energy_from_pcm_wav(tmp_path: Path) -> None:
    path = tmp_path / "speech.wav"
    _write_pcm_wav(path, [1_000] * 8_000 + [0] * 8_000)

    audio = load_pcm_wav(path)
    windows = extract_energy_windows(audio)

    assert audio.duration_seconds == 2.0
    assert len(windows) == 2
    assert windows[0].energy_db is not None and windows[0].energy_db > -45
    assert windows[0].pause_seconds == 0.0
    assert windows[1].energy_db == -96.0
    assert windows[1].pause_seconds == 1.0


def test_rejects_unsupported_sample_width(tmp_path: Path) -> None:
    path = tmp_path / "eight-bit.wav"
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(1)
        writer.setframerate(8_000)
        writer.writeframes(b"\x00" * 8_000)

    with pytest.raises(AudioValidationError, match="16-bit"):
        load_pcm_wav(path)


def test_extracts_stable_pitch_variation_from_sine_wave(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    sample_rate = 8_000
    samples = [
        int(10_000 * __import__("math").sin(2 * __import__("math").pi * 200 * index / sample_rate))
        for index in range(sample_rate)
    ]
    _write_pcm_wav(path, samples, sample_rate)

    window = extract_acoustic_windows(load_pcm_wav(path))[0]

    assert window.energy_db is not None and window.energy_db > -45
    assert window.pitch_variation_semitones is not None
    assert window.pitch_variation_semitones < 0.1


def test_audio_endpoint_returns_measured_windows(tmp_path: Path) -> None:
    path = tmp_path / "speech.wav"
    _write_pcm_wav(path, [1_000] * 8_000)

    with TestClient(app) as client:
        response = client.post(
            "/v1/audio/feature-windows",
            files={"audio": ("speech.wav", path.read_bytes(), "audio/wav")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["duration_seconds"] == 1.0
    assert payload["windows"][0]["energy_db"] > -45
    assert payload["analysis_capability"] == "baseline_dsp_energy_pause_pitch_variation"


def test_uploaded_audio_features_flow_into_scoring(tmp_path: Path) -> None:
    path = tmp_path / "steady-tone.wav"
    sample_rate = 8_000
    samples = [
        int(10_000 * __import__("math").sin(2 * __import__("math").pi * 200 * index / sample_rate))
        for index in range(sample_rate)
    ]
    _write_pcm_wav(path, samples, sample_rate)

    with TestClient(app) as client:
        features_response = client.post(
            "/v1/audio/feature-windows",
            files={"audio": ("steady-tone.wav", path.read_bytes(), "audio/wav")},
        )
        score_response = client.post(
            "/v1/analyze/windows",
            json={"windows": features_response.json()["windows"]},
        )

    assert features_response.status_code == 200
    assert score_response.status_code == 200
    assert score_response.json()["findings"][0]["finding_type"] == "monotone_delivery"


def test_dashboard_origin_is_allowed() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/v1/analyze/windows",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
