from itertools import islice
from fractions import Fraction

import pytest

from paeonia import Bar, Note, Tonality, Voice
from paeonia.tools import (
    degree_feedback,
    euclidean_rhythm,
    fill_bars,
    gate_notes,
    interval_feedback,
    note_repeat,
    pulses_to_durations,
    rule30_rhythm,
)


def test_rhythm_transformations_are_tools_not_bar_methods():
    for name in (
            "degree_feedback",
            "euclidean_rhythm",
            "interval_feedback",
            "pulses_to_durations",
            "rule30_rhythm",
    ):
        assert not hasattr(Bar, name)

    with pytest.raises(TypeError, match="bar must be a Bar"):
        pulses_to_durations(object(), "x")
    with pytest.raises(TypeError, match="bar must be a Bar"):
        euclidean_rhythm(object(), 4, 2)


def test_note_repeat_cycles_notes_and_counts_independently():
    a = Note.parse("C")
    b = Note.parse("D")
    c = Note.parse("E")

    stream = note_repeat(Bar([a, b, c]), [1, 2])

    assert list(islice(stream, 10)) == [
        a,
        b,
        b,
        c,
        a,
        a,
        b,
        c,
        c,
        a,
    ]


def test_note_repeat_is_lazy_and_preserves_original_events():
    a = Note.parse("<C E G>8").with_velocity(0.4).with_ties(tie_out=True)
    b = Note.rest().with_velocity(0.2).with_ties(tie_in=True)
    bar = Bar([a, b])

    stream = note_repeat(bar, [2, 1])
    emitted = list(islice(stream, 6))

    assert emitted == [a, a, b, a, a, b]
    assert all(
        actual is expected
        for actual, expected in zip(emitted, [a, a, b, a, a, b])
    )
    assert bar.notes == [a, b]


@pytest.mark.parametrize(
    ("bar", "repeats", "message"),
    [
        (Bar(), [1], "bar must contain"),
        (Bar("C"), [], "repeats must contain"),
        (Bar("C"), [0], "repeat counts must be positive"),
        (Bar("C"), [-1], "repeat counts must be positive"),
    ],
)
def test_note_repeat_rejects_inputs_that_cannot_produce_an_endless_stream(
        bar,
        repeats,
        message,
):
    with pytest.raises(ValueError, match=message):
        next(note_repeat(bar, repeats))


def test_note_repeat_rejects_non_integer_counts():
    with pytest.raises(TypeError, match="repeat counts must be integers"):
        next(note_repeat(Bar("C"), [1.5]))


def test_gate_notes_cycles_notes_and_switches_independently():
    a = Note.parse("C")
    b = Note.parse("D")
    c = Note.parse("E")

    stream = gate_notes(Bar([a, b, c]), [True, False])
    emitted = list(islice(stream, 7))

    assert [note.is_rest() for note in emitted] == [
        False,
        True,
        False,
        True,
        False,
        True,
        False,
    ]
    assert emitted[0] is a
    assert emitted[2] is c
    assert emitted[4] is b
    assert emitted[6] is a


def test_gate_notes_cycles_a_one_shot_pattern_iterator():
    a = Note.parse("C")
    b = Note.parse("D")
    pattern = iter((True, False))

    emitted = list(islice(gate_notes(Bar([a, b]), pattern), 6))

    assert emitted[0] is a
    assert emitted[2] is a
    assert emitted[4] is a
    assert emitted[1].is_rest()
    assert emitted[3].is_rest()
    assert emitted[5].is_rest()


def test_gate_notes_preserves_metadata_and_does_not_mutate_source():
    active = Note.parse("<C E G>8").with_velocity(0.4).with_ties(
        tie_out=True,
    )
    muted = Note.parse("D4.").with_velocity(0.2).with_ties(
        tie_in=True,
        tie_out=True,
    )
    bar = Bar([active, muted])

    emitted = list(islice(gate_notes(bar, [True, False]), 2))

    assert emitted[0] is active
    assert emitted[1].is_rest()
    assert emitted[1].duration == muted.duration
    assert emitted[1].velocity == muted.velocity
    assert not emitted[1].tie_in
    assert not emitted[1].tie_out
    assert bar.notes == [active, muted]
    assert not muted.is_rest()


@pytest.mark.parametrize(
    ("bar", "pattern", "message"),
    [
        (Bar(), [True], "bar must contain"),
        (Bar("C"), [], "pattern must contain"),
    ],
)
def test_gate_notes_rejects_empty_inputs(bar, pattern, message):
    with pytest.raises(ValueError, match=message):
        next(gate_notes(bar, pattern))


def test_gate_notes_accepts_binary_integer_switches():
    a = Note.parse("C")
    b = Note.parse("D")

    emitted = list(islice(
        gate_notes(Bar([a, b]), [1, 0, 0]),
        6,
    ))

    assert emitted[0] is a
    assert emitted[3] is b
    assert [note.is_rest() for note in emitted] == [
        False,
        True,
        True,
        False,
        True,
        True,
    ]


@pytest.mark.parametrize("switch", [2, -1, 1.0, "1"])
def test_gate_notes_rejects_non_binary_switches(switch):
    with pytest.raises(TypeError, match="booleans or 0/1 integers"):
        next(gate_notes(Bar("C"), [switch]))


def test_gate_notes_can_extend_previous_note_over_muted_events():
    active = Note.parse("C8").with_velocity(0.4)
    first_muted = Note.parse("D16")
    second_muted = Note.parse("E4")
    bar = Bar([active, first_muted, second_muted])

    emitted = list(islice(
        gate_notes(
            bar,
            [True, False, False],
            extend_previous=True,
        ),
        2,
    ))

    assert all(note.pitches == active.pitches for note in emitted)
    assert all(note.duration == Fraction(7, 16) for note in emitted)
    assert all(note.velocity == active.velocity for note in emitted)
    assert bar.notes == [active, first_muted, second_muted]


def test_gate_notes_leaves_leading_muted_events_as_rests():
    leading = Note.parse("C8").with_velocity(0.2)
    active = Note.parse("D4").with_velocity(0.6)

    emitted = list(islice(
        gate_notes(
            Bar([leading, active]),
            [False, True],
            extend_previous=True,
        ),
        2,
    ))

    assert emitted[0].is_rest()
    assert emitted[0].duration == leading.duration
    assert emitted[0].velocity == leading.velocity
    assert emitted[1].pitches == active.pitches
    assert emitted[1].duration == active.duration + leading.duration


def test_gate_notes_all_false_extension_pattern_remains_productive():
    bar = Bar("C8 D16")

    emitted = list(islice(
        gate_notes(bar, [False], extend_previous=True),
        4,
    ))

    assert all(note.is_rest() for note in emitted)
    assert [note.duration for note in emitted] == [
        note.duration for note in (bar[0], bar[1], bar[0], bar[1])
    ]


def test_gate_notes_rejects_non_boolean_extension_option():
    with pytest.raises(TypeError, match="extend_previous must be a boolean"):
        next(gate_notes(
            Bar("C"),
            [True],
            extend_previous="yes",
        ))


def test_degree_feedback_applies_bounded_nonlinear_tonal_map():
    tonality = Tonality("C")
    bar = Bar("C D E", tonality=tonality)

    first = degree_feedback(bar, register_size=7)
    second = degree_feedback(first, register_size=7)

    assert first == Bar("F E B", tonality=tonality)
    assert second == Bar("E D G", tonality=tonality)
    assert bar == Bar("C D E", tonality=tonality)


def test_degree_feedback_preserves_chromatic_alterations_and_event_metadata():
    tonality = Tonality("C")
    chord = Note.parse("<C# D>8").with_velocity(0.4).with_ties(
        tie_in=True,
        tie_out=True,
    )
    rest = Note.rest(Fraction(1, 8)).with_velocity(0.2)
    note = Note.parse("E8").with_velocity(0.7)
    bar = Bar([chord, rest, note], tonality=tonality)

    result = degree_feedback(bar, register_size=7)

    assert [tuple(str(pitch) for pitch in event.pitches) for event in result] == [
        ("F#4", "E4"),
        (),
        ("B4",),
    ]
    assert [event.duration for event in result] == [
        event.duration for event in bar
    ]
    assert [event.velocity for event in result] == [0.4, 0.2, 0.7]
    assert result[0].tie_in is True
    assert result[0].tie_out is True
    assert result.tonality is tonality


def test_degree_feedback_accepts_explicit_tonality_without_attaching_it():
    tonality = Tonality("C")
    bar = Bar("C D E")

    result = degree_feedback(bar, tonality=tonality, register_size=7)

    assert result == Bar("F E B")
    assert result.tonality is None


def test_rule30_rhythm_evolves_a_cyclic_sounding_mask():
    tonality = Tonality("C")
    seed = Bar("R R C R R", tonality=tonality)

    first = rule30_rhythm(seed)
    second = rule30_rhythm(first)

    assert [not note.is_rest() for note in first] == [
        False, True, True, True, False,
    ]
    assert [not note.is_rest() for note in second] == [
        True, True, False, False, True,
    ]
    assert all(
        note.midi_pitches == (60,)
        for note in [*first, *second]
        if not note.is_rest()
    )
    assert first.tonality is tonality
    assert second.tonality is tonality
    assert seed == Bar("R R C R R", tonality=tonality)


def test_rule30_rhythm_retains_cell_metadata_and_clears_ties():
    sounding = Note.parse("<C Eb>8").with_velocity(0.4).with_ties(
        tie_in=True,
        tie_out=True,
    )
    rests = [
        Note.rest(Fraction(1, 16)).with_velocity(0.1),
        Note.rest(Fraction(1, 4)).with_velocity(0.2),
    ]
    bar = Bar([sounding, *rests])

    result = rule30_rhythm(bar)

    assert [note.duration for note in result] == [
        Fraction(1, 8), Fraction(1, 16), Fraction(1, 4),
    ]
    assert [note.velocity for note in result] == [0.4, 0.1, 0.2]
    assert all(not note.tie_in and not note.tie_out for note in result)
    assert all(
        note.pitches == sounding.pitches
        for note in result
        if not note.is_rest()
    )


def test_interval_feedback_evolves_cyclic_successive_degree_intervals():
    tonality = Tonality("C")
    bar = Bar("C D E G", tonality=tonality)

    result = interval_feedback(bar)

    assert result == Bar("C F A D'", tonality=tonality)
    assert bar == Bar("C D E G", tonality=tonality)


def test_interval_feedback_preserves_alterations_boundaries_and_metadata():
    tonality = Tonality("C")
    chord = Note.parse("<C# D>8").with_velocity(0.4).with_ties(
        tie_out=True,
    )
    rest = Note.rest(Fraction(1, 8)).with_velocity(0.2)
    tail = Note.parse("<Eb G>8").with_velocity(0.7)
    bar = Bar([chord, rest, tail], tonality=tonality)

    result = interval_feedback(bar)

    assert [tuple(str(pitch) for pitch in event.pitches) for event in result] == [
        ("C#4", "F4"),
        (),
        ("Ab4", "D5"),
    ]
    assert [event.duration for event in result] == [
        event.duration for event in bar
    ]
    assert [event.velocity for event in result] == [0.4, 0.2, 0.7]
    assert result[0].tie_out is True
    assert result.tonality is tonality


@pytest.mark.parametrize(
    ("function", "kwargs", "message"),
    [
        (degree_feedback, {}, "requires an explicit or bar tonality"),
        (interval_feedback, {}, "requires an explicit or bar tonality"),
        (degree_feedback, {"register_size": 0}, "register_size must be positive"),
        (interval_feedback, {"modulus": 1}, "modulus must be greater"),
    ],
)
def test_pitch_evolution_tools_validate_tonal_context_and_bounds(
        function,
        kwargs,
        message,
):
    with pytest.raises(ValueError, match=message):
        function(Bar("C D"), **kwargs)


@pytest.mark.parametrize(
    "function",
    [degree_feedback, interval_feedback, rule30_rhythm],
)
def test_evolution_tools_reject_non_bars(function):
    with pytest.raises(TypeError, match="bar must be a Bar"):
        function(object())


@pytest.mark.parametrize(
    "function",
    [degree_feedback, interval_feedback, rule30_rhythm],
)
def test_evolution_tools_copy_empty_bars(function):
    tonality = Tonality("C")
    bar = Bar(tonality=tonality)

    result = function(bar)

    assert result == bar
    assert result is not bar
    assert result.tonality is tonality


def test_fill_bars_accepts_voice_and_preserves_spans_and_tonalities():
    c_major = Tonality("C")
    g_major = Tonality("G")
    a_minor = Tonality("A", "minor")
    templates = Voice([
        Bar("R2", tonality=c_major),
        Bar("R2"),
    ], default_tonality=a_minor, tonality_plan={1: g_major}, name="melody")
    notes = [Note.parse(note) for note in ("C4", "D4", "E4", "F4")]

    result = fill_bars(templates, iter(notes))

    assert isinstance(fill_bars([], iter(())), Voice)
    assert result.bar_spans() == templates.bar_spans()
    assert result.default_tonality is a_minor
    assert result.tonality_plan is templates.tonality_plan
    assert result.name == "melody"
    assert result.bars[0].tonality is c_major
    assert result.bars[1].tonality is None
    assert result.tonality_at(0) is c_major
    assert result.tonality_at(1) is g_major
    assert result.bars[0].notes == notes[:2]
    assert result.bars[1].notes == notes[2:]
    assert result.bars[0][0] is notes[0]


def test_fill_bars_splits_chord_across_multiple_bars_with_ties():
    templates = [Bar("R4") for _ in range(3)]
    chord = Note.parse("<C E G>2.").with_velocity(0.4)

    result = fill_bars(templates, [chord])

    assert [bar.span() for bar in result] == [
        Fraction(1, 4),
        Fraction(1, 4),
        Fraction(1, 4),
    ]
    segments = [bar[0] for bar in result]
    assert all(segment.pitches == chord.pitches for segment in segments)
    assert all(segment.velocity == chord.velocity for segment in segments)
    assert [segment.duration for segment in segments] == [
        Fraction(1, 4),
        Fraction(1, 4),
        Fraction(1, 4),
    ]
    assert [
        (segment.tie_in, segment.tie_out)
        for segment in segments
    ] == [(False, True), (True, True), (True, False)]


def test_fill_bars_places_split_tail_before_next_source_note():
    templates = [Bar("R4"), Bar("R4")]
    long_note = Note.parse("C4.")
    following = Note.parse("D8")

    result = fill_bars(templates, iter((long_note, following)))

    assert result[0] == Bar([
        long_note.with_duration(Fraction(1, 4)).with_ties(tie_out=True),
    ])
    assert result[1] == Bar([
        long_note.with_duration(Fraction(1, 8)).with_ties(tie_in=True),
        following,
    ])


def test_fill_bars_splits_rests_without_ties_and_preserves_metadata():
    templates = [Bar("R4"), Bar("R4")]
    rest = Note.rest(Fraction(1, 2)).with_velocity(0.2).with_ties(
        tie_in=True,
        tie_out=True,
    )

    result = fill_bars(templates, [rest])
    segments = [bar[0] for bar in result]

    assert all(segment.is_rest() for segment in segments)
    assert all(segment.duration == Fraction(1, 4) for segment in segments)
    assert all(segment.velocity == rest.velocity for segment in segments)
    assert all(not segment.tie_in and not segment.tie_out for segment in segments)


def test_fill_bars_combines_consecutive_rests_within_each_bar():
    first = Note.rest(Fraction(1, 8)).with_velocity(0.2)
    second = Note.rest(Fraction(1, 8)).with_velocity(0.8)
    third = Note.rest(Fraction(1, 2))

    result = fill_bars([Bar("R4"), Bar("R4")], [first, second, third])

    assert len(result[0]) == 1
    assert result[0][0].is_rest()
    assert result[0][0].duration == Fraction(1, 4)
    assert result[0][0].velocity == first.velocity
    assert len(result[1]) == 1
    assert result[1][0].is_rest()
    assert result[1][0].duration == Fraction(1, 4)


def test_fill_bars_preserves_empty_templates_without_consuming_notes():
    source = iter((Note.parse("C4"),))

    result = fill_bars([Bar(), Bar("R4")], source)

    assert result[0] == Bar()
    assert result[1] == Bar("C4")


def test_fill_bars_reports_exhausted_or_invalid_sources():
    with pytest.raises(ValueError, match="ended while filling bar 1"):
        fill_bars([Bar("R4"), Bar("R4")], [Note.parse("C4")])

    with pytest.raises(TypeError, match="Generated event 0"):
        fill_bars([Bar("R4")], [object()])
    with pytest.raises(TypeError, match="Bar template 0"):
        fill_bars([object()], [Note.parse("C4")])
