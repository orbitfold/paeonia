from copy import copy
from fractions import Fraction

import pytest

from paeonia import Bar, Note, Tonality
from paeonia.transform import rotate


def test_rotate_positive_steps_moves_events_right():
    assert rotate(Bar("C D E"), 1) == Bar("E C D")


def test_rotate_negative_steps_moves_events_left():
    assert rotate(Bar("C D E"), -1) == Bar("D E C")


@pytest.mark.parametrize(
    ("steps", "expected"),
    [
        (0, "C D E"),
        (3, "C D E"),
        (4, "E C D"),
        (-4, "D E C"),
    ],
)
def test_rotate_wraps_steps(steps, expected):
    assert rotate(Bar("C D E"), steps) == Bar(expected)


def test_rotate_preserves_tonality_note_metadata_and_source():
    tonality = Tonality("Eb", "dorian")
    notes = [
        Note.parse("<C Eb>8").with_velocity(0.3).with_ties(tie_out=True),
        Note.rest(Fraction(3, 8)).with_velocity(0.2),
        Note.parse("G4").with_velocity(0.7).with_ties(tie_in=True),
    ]
    bar = Bar(notes, tonality=tonality)
    original = copy(bar)

    result = rotate(bar, 1)

    assert result.tonality is tonality
    assert result.notes == [notes[2], notes[0], notes[1]]
    assert all(
        actual is expected
        for actual, expected in zip(result.notes, [notes[2], notes[0], notes[1]])
    )
    assert result is not bar
    assert bar == original


def test_rotate_empty_bar_returns_new_empty_bar_with_tonality():
    tonality = Tonality("C")
    bar = Bar(tonality=tonality)

    result = rotate(bar, 5)

    assert result == bar
    assert result is not bar
    assert result.tonality is tonality


@pytest.mark.parametrize(
    ("bar", "steps", "message"),
    [
        (object(), 1, "bar must be a Bar"),
        (Bar("C"), 1.5, "steps must be an integer"),
    ],
)
def test_rotate_rejects_invalid_arguments(bar, steps, message):
    with pytest.raises(TypeError, match=message):
        rotate(bar, steps)
