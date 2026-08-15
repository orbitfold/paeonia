"""General-purpose composition iterators."""

from collections.abc import Iterable, Iterator
from itertools import cycle

from .bar import Bar
from .note import Note


def note_repeat(bar: Bar, repeats: Iterable[int]) -> Iterator[Note]:
    """Yield notes indefinitely using a cycling repeat-count pattern.

    The notes in ``bar`` and the values in ``repeats`` advance together and
    cycle independently. For example, a bar containing ``a, b, c`` and repeat
    counts ``1, 2`` produces ``a, b, b, c, a, a, b, c, c, a, ...``. Emitted
    values are the original :class:`Note` objects, so their pitches, duration,
    velocity, and tie metadata are retained.

    Parameters
    ----------
    bar : Bar
        Non-empty bar whose notes are cycled indefinitely.
    repeats : Iterable[int]
        Finite, non-empty pattern of positive repeat counts. The iterable is
        materialized once so that it can be validated and cycled.

    Yields
    ------
    Note
        Each note from ``bar``, repeated by its corresponding count.

    Raises
    ------
    ValueError
        If the bar or repeat pattern is empty, or a repeat count is not
        positive.
    TypeError
        If a repeat count is not an integer.
    """
    if not bar:
        raise ValueError("bar must contain at least one note")

    repeat_pattern = tuple(repeats)
    if not repeat_pattern:
        raise ValueError("repeats must contain at least one count")
    if not all(isinstance(count, int) for count in repeat_pattern):
        raise TypeError("repeat counts must be integers")
    if not all(count > 0 for count in repeat_pattern):
        raise ValueError("repeat counts must be positive")

    for note, count in zip(cycle(bar), cycle(repeat_pattern)):
        for _ in range(count):
            yield note
