from backend.app.domain import FeatureWindow, FindingType, ReferenceProfile
from backend.app.scoring import analyze_windows, detect_findings


def test_detects_timestamped_and_explained_findings() -> None:
    profile = ReferenceProfile()
    window = FeatureWindow(
        start_seconds=42.0,
        end_seconds=47.0,
        speech_rate_wpm=205.0,
        pause_seconds=1.8,
        pitch_variation_semitones=0.8,
        energy_db=-34.0,
        clarity_score=0.52,
    )

    findings = detect_findings([window], profile)

    assert {item.finding_type for item in findings} == {
        FindingType.RUSHED_DELIVERY,
        FindingType.EXCESSIVE_PAUSE,
        FindingType.MONOTONE_DELIVERY,
        FindingType.LOW_ENERGY,
        FindingType.LOW_CLARITY,
    }
    assert all(item.start_seconds == 42.0 and item.end_seconds == 47.0 for item in findings)
    assert all(item.evidence and item.practice_action for item in findings)
    energy_finding = next(item for item in findings if item.finding_type == FindingType.LOW_ENERGY)
    assert energy_finding.severity == 0.21


def test_good_measured_window_has_high_score_and_no_findings() -> None:
    result = analyze_windows(
        [
            FeatureWindow(
                start_seconds=0.0,
                end_seconds=5.0,
                speech_rate_wpm=150.0,
                pause_seconds=0.6,
                pitch_variation_semitones=2.0,
                energy_db=-20.0,
                clarity_score=0.9,
            )
        ]
    )

    assert result.overall_score == 100.0
    assert result.findings == ()


def test_missing_measurements_do_not_create_fake_findings() -> None:
    result = analyze_windows(
        [FeatureWindow(start_seconds=0.0, end_seconds=2.0, speech_rate_wpm=150.0)]
    )

    assert result.findings == ()
    assert result.dimension_scores == {"pace_and_pauses": 100.0}
    assert result.overall_score == 100.0
