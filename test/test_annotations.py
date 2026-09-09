"""Tests for renderer-independent score-analysis annotations."""

from fractions import Fraction

import pytest

from paeonia import (
    Bar,
    Note,
    Pitch,
    Score,
    Tonality,
    Voice,
)
from paeonia.annotations import (
    AnalysisRenderOptions,
    normalize_analysis_render_options,
)


def _note(name: str, duration: Fraction = Fraction(1)) -> Note:
    return Note((Pitch.parse(name),), duration=duration)


def _passing_tone_score() -> Score:
    quarter = Fraction(1, 4)
    score = Score(default_tonality=Tonality("C"))
    score["soprano"] = Voice([Bar([
        _note("C5", quarter),
        _note("D5", quarter),
        _note("E5", Fraction(1, 2)),
    ])])
    score["alto"] = Voice([Bar([_note("G4")])])
    score["tenor"] = Voice([Bar([_note("E4")])])
    score["bass"] = Voice([Bar([_note("C3")])])
    return score


def test_default_annotations_show_harmony_and_exact_non_chord_source():
    score = _passing_tone_score()

    annotations = score.analysis_annotations()

    harmony = next(item for item in annotations if item.lane == "harmony")
    assert harmony.text == "Harmony: C · I"
    assert harmony.offset == 0
    assert harmony.duration == 1

    non_chord = next(
        item for item in annotations if item.lane == "non_chord_tone"
    )
    assert non_chord.text == "NCT: D5 (passing)"
    assert non_chord.staff_name == "soprano"
    assert non_chord.source is not None
    assert (
        non_chord.source.staff,
        non_chord.source.bar_index,
        non_chord.source.event_index,
        non_chord.source.pitch_index,
    ) == ("soprano", 0, 1, 0)
    assert "set_theory" not in {item.lane for item in annotations}


def test_verticalities_keep_event_and_chord_pitch_references():
    chord = Note(tuple(Pitch.parse(name) for name in ("C4", "Eb4", "G4")))
    score = Score()
    score["keyboard"] = Voice([Bar([chord])])

    frame = score.verticalities(0)[0]

    assert tuple(
        (source.staff, source.bar_index, source.event_index, source.pitch_index)
        for source in frame.sources
    ) == (
        ("keyboard", 0, 0, 0),
        ("keyboard", 0, 0, 1),
        ("keyboard", 0, 0, 2),
    )


def test_chord_symbols_remain_available_without_tonality():
    score = Score()
    score["keyboard"] = Voice([Bar([
        Note(tuple(Pitch.parse(name) for name in ("C4", "E4", "G4")))
    ])])

    harmony = next(
        item
        for item in score.analysis_annotations()
        if item.lane == "harmony"
    )

    assert harmony.text == "Harmony: C"


def test_source_staves_limit_analysis_but_not_rendered_staves():
    score = Score(default_tonality=Tonality("C"))
    score["marimba_right"] = Voice([Bar([
        Note(
            tuple(Pitch.parse(name) for name in ("C4", "E4", "G4")),
            duration=1,
        )
    ])])
    score["marimba_left"] = Voice([Bar([_note("C3")])])
    score["strings"] = Voice([Bar([
        Note(
            tuple(Pitch.parse(name) for name in ("F#4", "A4", "C#5")),
            duration=1,
        )
    ])])
    options = AnalysisRenderOptions(
        source_staves=("marimba_right", "marimba_left"),
        non_chord_tones=False,
        voice_leading=False,
        register_warnings=False,
    )

    rendered = score.to_lilypond(analysis=options)

    assert "Harmony: C · I" in rendered
    assert rendered.count("\\new Staff") == 3
    assert 'instrumentName = "strings"' in rendered


def test_diagnostic_preset_exposes_dense_analysis_lanes():
    half = Fraction(1, 2)
    score = Score(default_tonality=Tonality("C"))
    score["upper"] = Voice([
        Bar([_note("E4", half), _note("F#4", half)]),
        Bar([_note("F4")]),
    ])
    score["lower"] = Voice([
        Bar([_note("F4", half), _note("G4", half)]),
        Bar([_note("G4")]),
    ])
    score["bass"] = Voice([
        Bar([_note("E3", half), _note("F3", half)]),
        Bar([_note("F3")]),
    ])

    lanes = {
        item.lane
        for item in score.analysis_annotations(
            AnalysisRenderOptions.diagnostic()
        )
    }

    assert {
        "harmony",
        "voice_leading",
        "register",
        "dissonance",
        "scale_degree",
        "bass_motion",
        "doubling",
        "density",
        "set_theory",
        "interval",
    } <= lanes


def test_annotation_results_are_recomputed_after_voice_edit():
    score = Score(default_tonality=Tonality("C"))
    score["keyboard"] = Voice([Bar([
        Note(tuple(Pitch.parse(name) for name in ("C4", "E4", "G4")))
    ])])
    before = score.analysis_annotations()

    score["keyboard"][0] = Bar([
        Note(tuple(Pitch.parse(name) for name in ("D4", "F4", "A4")))
    ])
    after = score.analysis_annotations()

    assert next(item.text for item in before if item.lane == "harmony") == (
        "Harmony: C · I"
    )
    assert next(item.text for item in after if item.lane == "harmony") == (
        "Harmony: Dm · ii"
    )


def test_analysis_options_validate_and_normalize_public_values():
    assert normalize_analysis_render_options(False) is None
    assert isinstance(
        normalize_analysis_render_options(True),
        AnalysisRenderOptions,
    )
    options = AnalysisRenderOptions(source_staves="lead")
    assert options.source_staves == ("lead",)
    assert normalize_analysis_render_options(options) is options

    with pytest.raises(TypeError, match="analysis must"):
        normalize_analysis_render_options("all")
    with pytest.raises(ValueError, match="min_confidence"):
        AnalysisRenderOptions(min_confidence=1.5)
    with pytest.raises(ValueError, match="source_staves"):
        AnalysisRenderOptions(source_staves=())


def test_unknown_source_staff_is_descriptive():
    score = Score(default_tonality=Tonality("C"))
    score["lead"] = Voice([Bar("C1")])

    with pytest.raises(KeyError, match="Unknown source staves.*missing"):
        score.analysis_annotations(
            AnalysisRenderOptions(source_staves=("missing",))
        )
