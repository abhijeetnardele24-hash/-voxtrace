"""Safe, dependency-free baseline WAV ingestion and energy extraction."""

from __future__ import annotations

import math
import statistics
import struct
import wave
from dataclasses import dataclass
from pathlib import Path

from .domain import FeatureWindow


class AudioValidationError(ValueError):
    """Raised when an uploaded WAV is not supported by the baseline extractor."""


@dataclass(frozen=True, slots=True)
class MonoPcmAudio:
    sample_rate_hz: int
    samples: tuple[int, ...]

    @property
    def duration_seconds(self) -> float:
        return len(self.samples) / self.sample_rate_hz


def load_pcm_wav(path: Path, max_duration_seconds: float = 600.0) -> MonoPcmAudio:
    """Load 16-bit PCM WAV audio and downmix it deterministically to mono."""

    try:
        with wave.open(str(path), "rb") as reader:
            channel_count = reader.getnchannels()
            sample_width = reader.getsampwidth()
            sample_rate_hz = reader.getframerate()
            frame_count = reader.getnframes()
            compression = reader.getcomptype()
            if compression != "NONE":
                raise AudioValidationError("compressed WAV files are not supported")
            if sample_width != 2:
                raise AudioValidationError("only 16-bit PCM WAV files are supported")
            if channel_count not in (1, 2):
                raise AudioValidationError("only mono or stereo WAV files are supported")
            if sample_rate_hz <= 0:
                raise AudioValidationError("WAV sample rate must be positive")
            duration_seconds = frame_count / sample_rate_hz
            if duration_seconds <= 0:
                raise AudioValidationError("audio file is empty")
            if duration_seconds > max_duration_seconds:
                raise AudioValidationError(
                    f"audio exceeds maximum duration of {max_duration_seconds:.0f} seconds"
                )
            raw_frames = reader.readframes(frame_count)
    except (OSError, EOFError, wave.Error) as error:
        raise AudioValidationError(f"invalid WAV audio: {error}") from error

    expected_values = frame_count * channel_count
    try:
        values = struct.unpack(f"<{expected_values}h", raw_frames)
    except struct.error as error:
        raise AudioValidationError("WAV frame data is incomplete") from error

    if channel_count == 1:
        mono_samples = values
    else:
        mono_samples = tuple((left + right) // 2 for left, right in zip(values[::2], values[1::2]))
    return MonoPcmAudio(sample_rate_hz=sample_rate_hz, samples=tuple(mono_samples))


def _decibels_full_scale(samples: tuple[int, ...]) -> float:
    if not samples:
        return -96.0
    mean_square = sum(sample * sample for sample in samples) / len(samples)
    if mean_square == 0:
        return -96.0
    rms = math.sqrt(mean_square)
    return round(20.0 * math.log10(rms / 32768.0), 2)


def extract_energy_windows(
    audio: MonoPcmAudio,
    window_seconds: float = 1.0,
    silence_threshold_dbfs: float = -45.0,
) -> tuple[FeatureWindow, ...]:
    """Create contiguous energy windows with a simple measured pause proxy.

    The pause proxy marks fully quiet windows. It intentionally does not claim
    word-level or rhetorical pause detection; forced alignment owns that later.
    """

    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")
    samples_per_window = max(1, round(audio.sample_rate_hz * window_seconds))
    windows: list[FeatureWindow] = []
    for offset in range(0, len(audio.samples), samples_per_window):
        chunk = audio.samples[offset : offset + samples_per_window]
        start_seconds = offset / audio.sample_rate_hz
        end_seconds = min(len(audio.samples), offset + samples_per_window) / audio.sample_rate_hz
        energy_db = _decibels_full_scale(chunk)
        windows.append(
            FeatureWindow(
                start_seconds=round(start_seconds, 3),
                end_seconds=round(end_seconds, 3),
                energy_db=energy_db,
                pause_seconds=round(end_seconds - start_seconds, 3)
                if energy_db <= silence_threshold_dbfs
                else 0.0,
            )
        )
    return tuple(windows)


def _estimate_zero_crossing_pitch_hz(
    samples: tuple[int, ...], sample_rate_hz: int
) -> float | None:
    """Estimate voiced fundamental frequency from zero crossings.

    This lightweight estimator is deliberately conservative: non-speech, silence,
    and frequencies outside a broad human-voice band return ``None`` rather than
    an invented pitch. The enhanced model-based extractor can replace this
    implementation later without changing the API contract.
    """

    if len(samples) < 2:
        return None
    crossings = sum(
        (previous <= 0 < current) or (previous >= 0 > current)
        for previous, current in zip(samples, samples[1:])
    )
    duration_seconds = len(samples) / sample_rate_hz
    estimated_hz = crossings / (2 * duration_seconds)
    if not 65 <= estimated_hz <= 400:
        return None
    return estimated_hz


def _pitch_variation_semitones(
    samples: tuple[int, ...],
    sample_rate_hz: int,
    microframe_seconds: float,
    silence_threshold_dbfs: float,
) -> float | None:
    microframe_size = max(1, round(sample_rate_hz * microframe_seconds))
    pitches = [
        pitch
        for offset in range(0, len(samples), microframe_size)
        if _decibels_full_scale(samples[offset : offset + microframe_size])
        > silence_threshold_dbfs
        for pitch in (
            _estimate_zero_crossing_pitch_hz(
                samples[offset : offset + microframe_size],
                sample_rate_hz,
            ),
        )
        if pitch is not None
    ]
    if len(pitches) < 2:
        return None
    reference_hz = statistics.median(pitches)
    semitone_offsets = [12 * math.log2(pitch / reference_hz) for pitch in pitches]
    return round(statistics.pstdev(semitone_offsets), 2)


def extract_acoustic_windows(
    audio: MonoPcmAudio,
    window_seconds: float = 1.0,
    microframe_seconds: float = 0.05,
    silence_threshold_dbfs: float = -45.0,
) -> tuple[FeatureWindow, ...]:
    """Extract measured energy, silence, and pitch-variation features.

    The returned windows intentionally omit speech rate and clarity. Those
    require transcript alignment and separately validated methods, which must not
    be approximated silently.
    """

    if window_seconds <= 0 or microframe_seconds <= 0:
        raise ValueError("window_seconds and microframe_seconds must be positive")
    samples_per_window = max(1, round(audio.sample_rate_hz * window_seconds))
    windows: list[FeatureWindow] = []
    for offset in range(0, len(audio.samples), samples_per_window):
        chunk = audio.samples[offset : offset + samples_per_window]
        start_seconds = offset / audio.sample_rate_hz
        end_seconds = min(len(audio.samples), offset + samples_per_window) / audio.sample_rate_hz
        energy_db = _decibels_full_scale(chunk)
        is_silent = energy_db <= silence_threshold_dbfs
        windows.append(
            FeatureWindow(
                start_seconds=round(start_seconds, 3),
                end_seconds=round(end_seconds, 3),
                energy_db=energy_db,
                pause_seconds=round(end_seconds - start_seconds, 3) if is_silent else 0.0,
                pitch_variation_semitones=None
                if is_silent
                else _pitch_variation_semitones(
                    chunk,
                    audio.sample_rate_hz,
                    microframe_seconds,
                    silence_threshold_dbfs,
                ),
            )
        )
    return tuple(windows)
