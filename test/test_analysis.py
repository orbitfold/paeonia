"""Tests for score-wide vertical and harmonic analysis."""

from fractions import Fraction

import pytest

from paeonia import Bar, Note, Pitch, PitchClass, Score, Tonality, Voice
from paeonia.analysis import interval_class_vector, prime_form


def _note(name: str, duration: Fraction = Fraction(1)) -> Note:
    return Note((Pitch.parse(name),), duration=duration)


def _one_bar_score(
        parts: dict[str, Bar],
        *,
        tonality: Tonality | None = None,
) -> Score:
    score = Score(default_tonality=tonality)
    for name, bar in parts.items():
        score[name] = Voice([bar])
    return score


def test_verticalities_follow_exact_boundaries_and_preserve_spelling():
    half = Fraction(1, 2)
    score = _one_bar_score({
        "melody": Bar([
            _note("Eb4", half),
            _note("D#4", half),
        ]),
        "harmony": Bar([
            Note((Pitch.parse("C4"), Pitch.parse("G4")), duration=1),
        ]),
        "silent": Bar([Note.rest(1)]),
    })

    frames = score.verticalities(0)

    assert tuple((frame.offset, frame.duration) for frame in frames) == (
        (Fraction(0), half),
        (half, half),
    )
    assert frames[0].by_staff == {
        "melody": (Pitch.parse("Eb4"),),
        "harmony": (Pitch.parse("C4"), Pitch.parse("G4")),
        "silent": (),
    }
    assert frames[1].by_staff["melody"] == (Pitch.parse("D#4"),)
    assert score.sonority_at(0, Fraction(3, 4)) is frames[1] or (
        score.sonority_at(0, Fraction(3, 4)) == frames[1]
    )

    pitch_classes = score.pitch_class_set(0)
    assert PitchClass.parse("Eb") in pitch_classes.written
    assert PitchClass.parse("D#") in pitch_classes.written
    assert pitch_classes.midi == frozenset({0, 3, 7})


def test_sustains_and_valid_ties_do_not_create_false_vertical_changes():
    first = _note("C4", Fraction(1, 2)).with_ties(tie_out=True)
    second = _note("C4", Fraction(1, 2)).with_ties(tie_in=True)
    score = _one_bar_score({"lead": Bar([first, second])})

    assert tuple(
        (frame.offset, frame.duration, frame.pitches)
        for frame in score.verticalities(0)
    ) == ((Fraction(0), Fraction(1), (Pitch.parse("C4"),)),)

    invalid = _one_bar_score({
        "lead": Bar([_note("C4").with_ties(tie_out=True)]),
    })
    with pytest.raises(ValueError, match="not followed by tie_in"):
        invalid.verticalities(0)


def test_rearticulated_pitch_remains_an_onset_boundary():
    score = _one_bar_score({
        "lead": Bar([
            _note("C4", Fraction(1, 2)),
            _note("C4", Fraction(1, 2)),
        ]),
    })

    assert tuple(
        (frame.offset, frame.duration)
        for frame in score.verticalities(0)
    ) == (
        (Fraction(0), Fraction(1, 2)),
        (Fraction(1, 2), Fraction(1, 2)),
    )


def test_pointwise_set_theory_uses_midi_classes():
    score = _one_bar_score({
        "chord": Bar([
            Note(tuple(Pitch.parse(name) for name in ("C4", "E4", "G4")))
        ]),
    })

    assert score.interval_class_vector(0, offset=0) == (0, 0, 1, 1, 1, 0)
    assert score.prime_form(0, offset=0) == (0, 3, 7)
    assert interval_class_vector([0, 4, 7]) == (0, 0, 1, 1, 1, 0)
    assert prime_form([0, 4, 7]) == (0, 3, 7)


def test_scale_degrees_use_effective_tonality_and_reject_conflicts():
    c_minor = Tonality("C", "minor")
    score = _one_bar_score(
        {"lead": Bar([_note("Eb4")])},
        tonality=c_minor,
    )

    degree = score.scale_degrees(0)[0].degrees[0]
    assert degree.number == 3
    assert degree.position.alteration == 0

    conflicting = Score()
    conflicting["c"] = Voice(
        [Bar([_note("C4")])],
        default_tonality=Tonality("C"),
    )
    conflicting["g"] = Voice(
        [Bar([_note("G4")])],
        default_tonality=Tonality("G"),
    )
    with pytest.raises(ValueError, match="conflicting tonalities"):
        conflicting.scale_degrees(0)

    explicit = conflicting.scale_degrees(0, tonality=Tonality("C"))
    assert len(explicit[0].degrees) == 2


def test_chord_candidates_preserve_root_spelling_and_function():
    score = _one_bar_score(
        {
            "top": Bar([_note("Bb4")]),
            "middle": Bar([_note("G4")]),
            "bass": Bar([_note("Eb3")]),
        },
        tonality=Tonality("C", "minor"),
    )

    candidate = score.chord_candidates(0)[0]

    assert candidate.root == PitchClass.parse("Eb")
    assert candidate.quality == "major"
    assert candidate.symbol == "Eb"
    assert candidate.inversion == 0
    assert candidate.confidence == 1.0
    assert candidate.roman_numeral == "III"
    assert score.roman_numerals(0)[0].roman_numeral == "III"


def test_harmonic_context_is_duration_weighted_and_finds_passing_tone():
    quarter = Fraction(1, 4)
    score = _one_bar_score(
        {
            "soprano": Bar([
                _note("C5", quarter),
                _note("D5", quarter),
                _note("E5", Fraction(1, 2)),
            ]),
            "alto": Bar([_note("G4")]),
            "tenor": Bar([_note("E4")]),
            "bass": Bar([_note("C3")]),
        },
        tonality=Tonality("C"),
    )

    context = score.harmonic_context(0)

    assert context.primary is not None
    assert context.primary.symbol == "C"
    assert context.primary_coverage == 1
    assert context.changes[0].offset == 0
    assert context.changes[0].duration == 1
    assert context.changes[0].roman_numeral == "I"
    assert tuple(
        (tone.staff, str(tone.pitch), tone.kind)
        for tone in context.non_chord_tones
    ) == (("soprano", "D5", "passing"),)
    assert score.harmonic_rhythm(0) == context.changes


def test_harmonic_coverage_is_measured_against_the_complete_bar():
    half = Fraction(1, 2)
    score = _one_bar_score(
        {
            "top": Bar([Note.rest(half), _note("G4", half)]),
            "middle": Bar([Note.rest(half), _note("E4", half)]),
            "bass": Bar([Note.rest(half), _note("C3", half)]),
        },
        tonality=Tonality("C"),
    )

    context = score.harmonic_context(0)

    assert context.primary is not None
    assert context.primary.symbol == "C"
    assert context.primary_coverage == Fraction(1, 2)
    assert context.changes[0].candidate is None
    assert context.changes[1].roman_numeral == "I"


def test_objective_vertical_metrics_report_dissonance_doubling_and_register():
    score = _one_bar_score({
        "upper": Bar([_note("E4")]),
        "lower": Bar([_note("F4")]),
        "bass": Bar([_note("E3")]),
    })

    intervals = score.interval_matrix(0)[0].intervals
    assert len(intervals) == 3
    dissonances = score.dissonances(0)[0].intervals
    assert any(relation.interval_class == 1 for relation in dissonances)
    doubling = score.doublings(0)[0].doublings[0]
    assert doubling.midi_pitch_class == 4
    assert doubling.count == 2
    assert doubling.staves == ("upper", "bass")
    assert score.density(0)[0].pitch_count == 3
    assert score.density(0)[0].active_staff_count == 3

    register = score.register_analysis(0).snapshots[0]
    assert str(register.bass) == "E3"
    assert str(register.soprano) == "F4"
    assert register.ambitus == 13
    assert register.crossings == (("upper", "lower"),)


def test_register_overlap_and_bass_motion_follow_time():
    half = Fraction(1, 2)
    score = _one_bar_score({
        "upper": Bar([_note("C5", half), _note("E4", half)]),
        "lower": Bar([_note("G4", half), _note("A4", half)]),
        "bass": Bar([_note("C3", half), _note("D3", half)]),
    })

    register = score.register_analysis(0)
    assert register.overlaps[0].offset == half
    assert (register.overlaps[0].upper_staff,
            register.overlaps[0].lower_staff) == ("upper", "lower")
    motion = score.bass_motion(0)
    assert len(motion) == 1
    assert motion[0].semitones == 2
    assert motion[0].to_offset == half


def test_voice_leading_reports_motion_common_tones_contrary_and_parallels():
    score = Score()
    score["upper"] = Voice([
        Bar([_note("C5")]),
        Bar([_note("D5")]),
    ])
    score["lower"] = Voice([
        Bar([_note("F4")]),
        Bar([_note("G4")]),
    ])
    score["bass"] = Voice([
        Bar([_note("C3")]),
        Bar([_note("B2")]),
    ])

    result = score.voice_leading_to(0, leap_threshold=1)

    assert result.total_motion == 5
    assert result.common_tones == ()
    assert result.contrary_pairs == (
        ("bass", "lower"),
        ("bass", "upper"),
    )
    assert tuple(
        (
            parallel.first_staff,
            parallel.second_staff,
            parallel.interval_class,
        )
        for parallel in result.parallel_perfects
    ) == (("lower", "upper", 7),)
    assert {motion.staff for motion in result.leaps} == {"upper", "lower"}


def test_analysis_validates_alignment_offsets_and_staff_selection():
    score = Score()
    score["one"] = Voice([Bar([_note("C4")])])
    score["two"] = Voice([Bar([_note("E4", Fraction(1, 2))])])

    with pytest.raises(ValueError, match="span mismatch"):
        score.verticalities(0)

    aligned = _one_bar_score({"one": Bar([_note("C4")])})
    with pytest.raises(ValueError, match="outside bar"):
        aligned.sonority_at(0, 1)
    with pytest.raises(KeyError, match="Unknown staves"):
        aligned.verticalities(0, staves=["missing"])
