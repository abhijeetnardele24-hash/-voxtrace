from backend.app.comparison import compare_windows, derive_reference_profile
from backend.app.domain import FeatureWindow


def test_reference_profile_is_derived_from_measured_baseline() -> None:
    reference = (
        FeatureWindow(0, 1, speech_rate_wpm=140, pause_seconds=0.2, energy_db=-20),
        FeatureWindow(1, 2, speech_rate_wpm=160, pause_seconds=0.4, energy_db=-22),
    )

    profile = derive_reference_profile(reference)

    assert profile.target_rate_min_wpm == 127.5
    assert profile.target_rate_max_wpm == 172.5
    assert -22 <= profile.target_energy_min_db <= -20


def test_comparison_aligns_by_normalized_time_and_reports_completeness() -> None:
    reference = (
        FeatureWindow(0, 1, energy_db=-20, spectral_centroid_hz=1_000),
        FeatureWindow(1, 2, energy_db=-22, spectral_centroid_hz=900),
    )
    target = (
        FeatureWindow(0, 2, energy_db=-30, spectral_centroid_hz=700),
        FeatureWindow(2, 4, energy_db=-25, spectral_centroid_hz=800),
    )

    result = compare_windows(reference, target)

    assert result.comparisons[0].deltas["energy_db"] == -10
    assert result.comparisons[1].deltas["energy_db"] == -3
    assert result.data_completeness["spectral_centroid_hz"] is True
    assert result.data_completeness["speech_rate_wpm"] is False
