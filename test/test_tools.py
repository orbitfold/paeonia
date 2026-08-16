from itertools import islice
from fractions import Fraction

import pytest

from paeonia import Bar, Note
from paeonia.tools import note_repeat, turn_notes_off


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


def test_turn_notes_off_cycles_notes_and_switches_independently():
    a = Note.parse("C")
    b = Note.parse("D")
    c = Note.parse("E")

    stream = turn_notes_off(Bar([a, b, c]), [True, False])
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


def test_turn_notes_off_cycles_a_one_shot_pattern_iterator():
    a = Note.parse("C")
    b = Note.parse("D")
    pattern = iter((True, False))

    emitted = list(islice(turn_notes_off(Bar([a, b]), pattern), 6))

    assert emitted[0] is a
    assert emitted[2] is a
    assert emitted[4] is a
    assert emitted[1].is_rest()
    assert emitted[3].is_rest()
    assert emitted[5].is_rest()


def test_turn_notes_off_preserves_metadata_and_does_not_mutate_source():
    active = Note.parse("<C E G>8").with_velocity(0.4).with_ties(
        tie_out=True,
    )
    muted = Note.parse("D4.").with_velocity(0.2).with_ties(
        tie_in=True,
        tie_out=True,
    )
    bar = Bar([active, muted])

    emitted = list(islice(turn_notes_off(bar, [True, False]), 2))

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
def test_turn_notes_off_rejects_empty_inputs(bar, pattern, message):
    with pytest.raises(ValueError, match=message):
        next(turn_notes_off(bar, pattern))


def test_turn_notes_off_accepts_binary_integer_switches():
    a = Note.parse("C")
    b = Note.parse("D")

    emitted = list(islice(
        turn_notes_off(Bar([a, b]), [1, 0, 0]),
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
def test_turn_notes_off_rejects_non_binary_switches(switch):
    with pytest.raises(TypeError, match="booleans or 0/1 integers"):
        next(turn_notes_off(Bar("C"), [switch]))


def test_turn_notes_off_can_extend_previous_note_over_muted_events():
    active = Note.parse("C8").with_velocity(0.4)
    first_muted = Note.parse("D16")
    second_muted = Note.parse("E4")
    bar = Bar([active, first_muted, second_muted])

    emitted = list(islice(
        turn_notes_off(
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


def test_turn_notes_off_leaves_leading_muted_events_as_rests():
    leading = Note.parse("C8").with_velocity(0.2)
    active = Note.parse("D4").with_velocity(0.6)

    emitted = list(islice(
        turn_notes_off(
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


def test_turn_notes_off_all_false_extension_pattern_remains_productive():
    bar = Bar("C8 D16")

    emitted = list(islice(
        turn_notes_off(bar, [False], extend_previous=True),
        4,
    ))

    assert all(note.is_rest() for note in emitted)
    assert [note.duration for note in emitted] == [
        note.duration for note in (bar[0], bar[1], bar[0], bar[1])
    ]


def test_turn_notes_off_rejects_non_boolean_extension_option():
    with pytest.raises(TypeError, match="extend_previous must be a boolean"):
        next(turn_notes_off(
            Bar("C"),
            [True],
            extend_previous="yes",
        ))
