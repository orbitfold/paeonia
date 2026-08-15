from itertools import islice

import pytest

from paeonia import Bar, Note
from paeonia.tools import note_repeat


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
