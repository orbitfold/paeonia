"""Transform musical objects without modifying their sources."""

from .bar import Bar


def rotate(bar: Bar, steps: int) -> Bar:
    """Rotate a bar's events while preserving their metadata.

    Positive values rotate to the right and negative values rotate to the
    left. Values larger than the number of events wrap around. The returned
    bar retains the source tonality and original :class:`~paeonia.note.Note`
    objects; the source bar itself is unchanged.

    Parameters
    ----------
    bar : Bar
        Bar whose events should be rotated.
    steps : int
        Number of event positions to rotate. Positive values rotate right.

    Returns
    -------
    Bar
        A new bar containing the rotated event sequence.

    Raises
    ------
    TypeError
        If ``bar`` is not a :class:`Bar` or ``steps`` is not an integer.
    """
    if not isinstance(bar, Bar):
        raise TypeError("bar must be a Bar")
    if not isinstance(steps, int):
        raise TypeError("steps must be an integer")
    if not bar:
        return Bar(tonality=bar.tonality)

    steps %= len(bar)
    if steps == 0:
        notes = list(bar.notes)
    else:
        notes = bar.notes[-steps:] + bar.notes[:-steps]
    return Bar(notes, tonality=bar.tonality)
