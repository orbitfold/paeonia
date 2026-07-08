import pytest

from paeonia.pitch import Pitch
from paeonia.tonality import MODES, ScalePosition, Tonality, TonalityPlan


SEVEN_NOTE_MODES = [
    mode
    for mode, intervals in MODES.items()
    if len(intervals) == 7
]


@pytest.mark.parametrize("tonic", ["C", "G", "Bb", "F#"])
def test_tonics_analyze_and_realize_across_octave_boundaries(tonic):
    tonality = Tonality(tonic)

    for tonal_octave in range(1, 9):
        for degree in range(tonality.degree_count):
            position = ScalePosition(degree, tonal_octave)
            pitch = tonality.realize_pitch(position)

            assert tonality.analyze_pitch(pitch, chromatic="error") == position


@pytest.mark.parametrize("mode", SEVEN_NOTE_MODES)
def test_all_builtin_seven_note_modes_round_trip(mode):
    tonality = Tonality("F#", mode)

    for tonal_octave in (4, 5):
        for degree in range(tonality.degree_count):
            pitch = tonality.realize_pitch(ScalePosition(degree, tonal_octave))

            assert tonality.realize_pitch(
                tonality.analyze_pitch(pitch, chromatic="error")
            ) == pitch


def test_f_sharp_and_g_flat_analysis_are_distinct_in_c_major():
    tonality = Tonality("C")
    f_sharp = Pitch.parse("F#4")
    g_flat = Pitch.parse("Gb4")

    assert f_sharp.midi == g_flat.midi
    assert tonality.analyze_pitch(f_sharp) == ScalePosition(3, 5, 1)
    assert tonality.analyze_pitch(g_flat) == ScalePosition(4, 5, -1)

    with pytest.raises(ValueError):
        tonality.analyze_pitch(f_sharp, chromatic="error")
    with pytest.raises(ValueError):
        tonality.analyze_pitch(g_flat, chromatic="error")


def test_b_sharp_and_c_flat_octave_spellings_round_trip():
    c_sharp_major = Tonality("C#")
    g_flat_major = Tonality("Gb")

    b_sharp = Pitch.parse("B#4")
    c_flat = Pitch.parse("Cb4")

    assert c_sharp_major.realize_pitch(c_sharp_major.analyze_pitch(b_sharp)) == b_sharp
    assert g_flat_major.realize_pitch(g_flat_major.analyze_pitch(c_flat)) == c_flat


@pytest.mark.parametrize("tonic", ["C", "G", "Bb", "F#"])
@pytest.mark.parametrize("mode", SEVEN_NOTE_MODES)
def test_analyze_then_realize_preserves_written_pitch_for_supported_tonalities(
    tonic,
    mode,
):
    tonality = Tonality(tonic, mode)

    for tonal_octave in (4, 5):
        for degree in range(tonality.degree_count):
            for alteration in (-1, 0, 1):
                pitch = tonality.realize_pitch(
                    ScalePosition(degree, tonal_octave, alteration)
                )

                assert tonality.realize_pitch(tonality.analyze_pitch(pitch)) == pitch


def test_transpose_pitch_preserves_alteration():
    tonality = Tonality("C")

    assert tonality.transpose_pitch(Pitch.parse("F#4"), 1) == Pitch.parse("G#4")
    assert tonality.transpose_pitch(Pitch.parse("Gb4"), -1) == Pitch.parse("Fb4")


def test_quantize_pitch_obeys_direction_and_tie_break():
    tonality = Tonality("C")
    pitch = Pitch.parse("F#4")

    assert tonality.quantize_pitch(pitch, direction="down") == Pitch.parse("F4")
    assert tonality.quantize_pitch(pitch, direction="up") == Pitch.parse("G4")
    assert tonality.quantize_pitch(
        pitch,
        direction="nearest",
        tie_break="lower",
    ) == Pitch.parse("F4")
    assert tonality.quantize_pitch(
        pitch,
        direction="nearest",
        tie_break="upper",
    ) == Pitch.parse("G4")


def test_tonality_plan_at_persists_latest_change_point_and_falls_back():
    fallback = Tonality("C")
    g_major = Tonality("G")
    f_major = Tonality("F")
    plan = TonalityPlan.from_mapping({8: g_major, 16: f_major})

    assert plan.at(0, fallback=fallback) == fallback
    assert plan.at(8, fallback=fallback) == g_major
    assert plan.at(15, fallback=fallback) == g_major
    assert plan.at(16, fallback=fallback) == f_major
    assert plan.at(99, fallback=fallback) == f_major
    assert TonalityPlan().at(4, fallback=fallback) == fallback


def test_custom_scale_analysis_is_explicit():
    tonality = Tonality("C", intervals=(0, 4, 7))

    assert tonality.analyze_pitch(Pitch.parse("E4")) == ScalePosition(1, 5)
    assert tonality.analyze_pitch(
        Pitch.parse("F4"),
        chromatic="nearest",
    ) == ScalePosition(1, 5)

    with pytest.raises(ValueError):
        tonality.analyze_pitch(Pitch.parse("F4"), chromatic="error")


def test_chromatic_scale_analysis_uses_exact_pitch_class_membership():
    tonality = Tonality("C", "chromatic")

    assert tonality.analyze_pitch(Pitch.parse("F#4")) == ScalePosition(6, 5)
    assert tonality.realize_pitch(ScalePosition(6, 5)) == Pitch.parse("F#4")
