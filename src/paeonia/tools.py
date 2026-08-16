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

    for note, count in zip(cycle(bar.notes), cycle(repeat_pattern)):
        for _ in range(count):
            yield note


def turn_notes_off(
        bar: Bar,
        pattern: Iterable[bool | int],
        *,
        extend_previous: bool = False,
) -> Iterator[Note]:
    """Yield an endless note stream masked by a cycling Boolean pattern.

    The notes in ``bar`` and switches in ``pattern`` advance together and
    cycle independently. A true switch yields the original event unchanged; a
    false switch normally yields an untied rest with the same duration and
    velocity. With ``extend_previous=True``, muted events following an active
    event are instead absorbed into that event's duration. Chords are treated
    as single events. Existing rests remain rests.

    Parameters
    ----------
    bar : Bar
        Non-empty bar whose events are cycled indefinitely.
    pattern : Iterable[bool | int]
        Finite, non-empty pattern containing Boolean values or the equivalent
        integers ``0`` and ``1``. The iterable is materialized once so
        generator patterns can be validated and cycled.
    extend_previous : bool, default=False
        Merge the durations of muted events into the preceding active event.
        Muted events before the first active event remain rests.

    Yields
    ------
    Note
        An active event, an extended active event, or a rest that occurs
        before any active event.

    Raises
    ------
    ValueError
        If the bar or switch pattern is empty.
    TypeError
        If a switch is not Boolean, ``0``, or ``1``, or if
        ``extend_previous`` is not Boolean.

    Notes
    -----
    Muted events have both tie flags cleared because rests cannot form valid
    ties. Active events are yielded unchanged, so callers masking tied
    material are responsible for ensuring adjacent tie chains remain valid.
    """
    if not bar:
        raise ValueError("bar must contain at least one note")
    supplied_pattern = tuple(pattern)
    if not supplied_pattern:
        raise ValueError("pattern must contain at least one switch")
    if not all(
            isinstance(switch, (bool, int))
            and switch in (0, 1)
            for switch in supplied_pattern
    ):
        raise TypeError("pattern switches must be booleans or 0/1 integers")
    if not isinstance(extend_previous, bool):
        raise TypeError("extend_previous must be a boolean")
    switch_pattern = tuple(bool(switch) for switch in supplied_pattern)

    events = zip(cycle(bar.notes), cycle(switch_pattern))
    if not extend_previous:
        for note, switch in events:
            if switch:
                yield note
            else:
                yield note.with_pitches(()).with_ties(
                    tie_in=False,
                    tie_out=False,
                )
        return

    previous = None
    for note, switch in events:
        if switch:
            if previous is not None:
                yield previous
            previous = note
        elif previous is None:
            yield note.with_pitches(()).with_ties(
                tie_in=False,
                tie_out=False,
            )
        else:
            previous = previous.with_duration(
                previous.duration + note.duration
            )
