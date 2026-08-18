"""General-purpose composition tools."""

from collections.abc import Iterable, Iterator
from fractions import Fraction
from itertools import cycle

from .bar import Bar
from .note import Note
from .tonality import ScalePosition, Tonality
from .voice import Voice


def _split_note(
        note: Note,
        first_duration: Fraction,
) -> tuple[Note, Note]:
    """Split an event, adding internal ties only for sounding notes."""
    second_duration = note.duration - first_duration
    first = note.with_duration(first_duration)
    second = note.with_duration(second_duration)
    if note.is_rest():
        return (
            first.with_ties(tie_in=False, tie_out=False),
            second.with_ties(tie_in=False, tie_out=False),
        )
    return (
        first.with_ties(tie_in=note.tie_in, tie_out=True),
        second.with_ties(tie_in=True, tie_out=note.tie_out),
    )


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


def _copy_bar(bar: Bar) -> Bar:
    """Return a new bar retaining the original event objects and tonality."""
    return Bar(list(bar.notes), tonality=bar.tonality)


def _resolve_tonality(
        bar: Bar,
        supplied: Tonality | None,
        operation: str,
) -> Tonality:
    """Resolve and validate the tonality used by a pitch evolution tool."""
    if supplied is not None and not isinstance(supplied, Tonality):
        raise TypeError("tonality must be a Tonality or None")
    result = bar.tonality if supplied is None else supplied
    if result is None:
        raise ValueError(
            f"{operation} requires an explicit or bar tonality"
        )
    return result


def _absolute_degree(position: ScalePosition, degree_count: int) -> int:
    """Convert a scale position to an unbounded tonal-degree coordinate."""
    return position.tonal_octave * degree_count + position.degree


def _realize_absolute_degree(
        absolute_degree: int,
        alteration: int,
        tonality: Tonality,
):
    """Realize one absolute degree while retaining a source alteration."""
    tonal_octave, degree = divmod(absolute_degree, tonality.degree_count)
    return tonality.realize_pitch(ScalePosition(
        degree=degree,
        tonal_octave=tonal_octave,
        alteration=alteration,
    ))


def degree_feedback(
        bar: Bar,
        *,
        tonality: Tonality | None = None,
        multiplier: int = 1,
        neighbour_weight: int = 1,
        offset: int = 1,
        register_size: int | None = None,
) -> Bar:
    """Apply a nonlinear, neighbour-coupled map to tonal degrees.

    Pitches are flattened and analyzed as absolute degrees in ``tonality``.
    Inside a bounded register, each normalized degree ``x[i]`` becomes::

        (multiplier * x[i] ** 2
         + neighbour_weight * x[i - 1]
         + offset) % register_size

    The predecessor relationship is cyclic. By default, the register contains
    three scale octaves. Repeated application therefore produces a finite,
    deterministic trajectory that eventually cycles. Chord boundaries, rests,
    durations, velocity, ties, pitch alterations, and bar tonality are retained.

    Parameters
    ----------
    bar : Bar
        Source material. A rest-only or empty bar is copied unchanged.
    tonality : Tonality | None, default=None
        Tonal coordinate system. When omitted, use ``bar.tonality``.
    multiplier : int, default=1
        Weight of the nonlinear squared term.
    neighbour_weight : int, default=1
        Weight of the preceding pitch's degree.
    offset : int, default=1
        Constant added before modular reduction.
    register_size : int | None, default=None
        Positive number of tonal degrees in the bounded register. ``None``
        selects three times the tonality's degree count.

    Returns
    -------
    Bar
        A new bar containing the evolved pitches.

    Raises
    ------
    TypeError
        If an argument has an unsupported type.
    ValueError
        If pitched material has no effective tonality, ``register_size`` is
        not positive, or a result lies outside the MIDI range.
    """
    if not isinstance(bar, Bar):
        raise TypeError("bar must be a Bar")
    parameters = (multiplier, neighbour_weight, offset)
    if any(isinstance(value, bool) or not isinstance(value, int)
           for value in parameters):
        raise TypeError(
            "multiplier, neighbour_weight, and offset must be integers"
        )
    if register_size is not None and (
            isinstance(register_size, bool)
            or not isinstance(register_size, int)
    ):
        raise TypeError("register_size must be an integer or None")
    if register_size is not None and register_size <= 0:
        raise ValueError("register_size must be positive")

    pitches = bar.pitches()
    if not pitches:
        if tonality is not None and not isinstance(tonality, Tonality):
            raise TypeError("tonality must be a Tonality or None")
        return _copy_bar(bar)

    effective = _resolve_tonality(bar, tonality, "degree_feedback")
    if register_size is None:
        register_size = effective.degree_count * 3

    positions = [effective.analyze_pitch(pitch) for pitch in pitches]
    absolute = [
        _absolute_degree(position, effective.degree_count)
        for position in positions
    ]
    origin = (min(absolute) // register_size) * register_size
    normalized = [
        (degree - origin) % register_size
        for degree in absolute
    ]
    evolved = [
        (
            multiplier * value**2
            + neighbour_weight * normalized[index - 1]
            + offset
        ) % register_size
        for index, value in enumerate(normalized)
    ]
    realized = [
        _realize_absolute_degree(
            origin + degree,
            position.alteration,
            effective,
        )
        for degree, position in zip(evolved, positions)
    ]
    return bar.pitch_variant(lambda _: realized)


def rule30_rhythm(bar: Bar) -> Bar:
    """Evolve a bar's sounding/rest pattern by one cyclic Rule 30 step.

    Sounding events are ``1`` cells and rests are ``0`` cells. The first and
    last events are neighbors. Current sounding pitch groups are cycled across
    the active cells in the next generation; each cell retains its own
    duration and velocity. All ties are cleared because changed adjacency
    cannot safely retain the source tie structure. Pitch spelling and bar
    tonality are preserved, and the source bar is unchanged.

    Parameters
    ----------
    bar : Bar
        Source bar interpreted as a cyclic cellular-automaton row.

    Returns
    -------
    Bar
        The next Rule 30 generation.

    Raises
    ------
    TypeError
        If ``bar`` is not a :class:`Bar`.
    """
    if not isinstance(bar, Bar):
        raise TypeError("bar must be a Bar")
    if not bar:
        return _copy_bar(bar)

    cells = [not note.is_rest() for note in bar.notes]
    next_cells = [
        cells[index - 1] ^ (cells[index] or cells[(index + 1) % len(cells)])
        for index in range(len(cells))
    ]
    sounding_pitches = [
        note.pitches
        for note in bar.notes
        if not note.is_rest()
    ]
    pitch_groups = cycle(sounding_pitches) if sounding_pitches else None
    notes = []
    for source, active in zip(bar.notes, next_cells):
        pitches = next(pitch_groups) if active and pitch_groups else ()
        notes.append(source.with_pitches(pitches).with_ties(
            tie_in=False,
            tie_out=False,
        ))
    return Bar(notes, tonality=bar.tonality)


def _centered_modulo(value: int, modulus: int) -> int:
    """Wrap an integer around zero, preferring the negative midpoint."""
    midpoint = modulus // 2
    return (value + midpoint) % modulus - midpoint


def interval_feedback(
        bar: Bar,
        *,
        tonality: Tonality | None = None,
        modulus: int | None = None,
) -> Bar:
    """Evolve successive tonal intervals with a cyclic Fibonacci rule.

    After flattening the bar's pitches into absolute tonal degrees, each
    successive interval is added to its cyclic predecessor. Results are
    wrapped around zero so individual steps remain bounded. The default
    modulus permits movement by at most one scale octave in either direction.
    The first pitch remains fixed and the evolved intervals reconstruct every
    later pitch. Each pitch retains its own chromatic alteration, and
    :meth:`Bar.pitch_variant` restores the original chord and event boundaries.

    Parameters
    ----------
    bar : Bar
        Source material. Bars containing fewer than two pitches are copied.
    tonality : Tonality | None, default=None
        Tonal coordinate system. When omitted, use ``bar.tonality``.
    modulus : int | None, default=None
        Integer greater than one used to bound interval feedback. ``None``
        selects ``2 * degree_count + 1``.

    Returns
    -------
    Bar
        A new bar containing the evolved pitch intervals.

    Raises
    ------
    TypeError
        If an argument has an unsupported type.
    ValueError
        If pitched material has no effective tonality, ``modulus`` is less
        than two, or a result lies outside the MIDI range.
    """
    if not isinstance(bar, Bar):
        raise TypeError("bar must be a Bar")
    if modulus is not None and (
            isinstance(modulus, bool)
            or not isinstance(modulus, int)
    ):
        raise TypeError("modulus must be an integer or None")
    if modulus is not None and modulus < 2:
        raise ValueError("modulus must be greater than one")

    pitches = bar.pitches()
    if len(pitches) < 2:
        if tonality is not None and not isinstance(tonality, Tonality):
            raise TypeError("tonality must be a Tonality or None")
        return _copy_bar(bar)

    effective = _resolve_tonality(bar, tonality, "interval_feedback")
    if modulus is None:
        modulus = 2 * effective.degree_count + 1

    positions = [effective.analyze_pitch(pitch) for pitch in pitches]
    absolute = [
        _absolute_degree(position, effective.degree_count)
        for position in positions
    ]
    intervals = [
        right - left
        for left, right in zip(absolute, absolute[1:])
    ]
    evolved_intervals = [
        _centered_modulo(intervals[index - 1] + interval, modulus)
        for index, interval in enumerate(intervals)
    ]
    evolved = [absolute[0]]
    for interval in evolved_intervals:
        evolved.append(evolved[-1] + interval)

    realized = [
        _realize_absolute_degree(
            degree,
            position.alteration,
            effective,
        )
        for degree, position in zip(evolved, positions)
    ]
    return bar.pitch_variant(lambda _: realized)


def pulses_to_durations(
        bar: Bar,
        pulses: str,
        legato: bool = True,
        unit: Fraction = Fraction(1, 16),
        offset: int = 0,
        emit_ties: bool = False,
) -> Bar:
    """Apply an onset pattern to a bar's events.

    Each ``"x"`` starts the next source event, cycling through ``bar`` when
    necessary. Each ``"."`` is either a unit rest or, in legato mode, a
    continuation of the preceding onset. Dots before the first onset remain
    rests.

    In the default legato representation, an onset and its continuation frames
    become one longer event. With ``emit_ties=True``, sounding continuations
    are instead emitted as separate unit events joined by ties. Rest spans are
    never tied. Pitch spelling, velocity, outer tie flags, and bar tonality are
    retained, and the source bar is not modified.

    Parameters
    ----------
    bar : Bar
        Non-empty source of events when ``pulses`` contains an onset.
    pulses : str
        Pattern whose onsets are ``"x"`` and whose rests or continuations are
        ``"."``.
    legato : bool, default=True
        Merge onsets with their following dot frames. When false, every frame
        produces one unit-length event.
    unit : Fraction, default=Fraction(1, 16)
        Positive duration of one pattern frame.
    offset : int, default=0
        Number of frames by which to rotate the pattern to the left.
    emit_ties : bool, default=False
        In legato mode, emit separate tied sounding frames instead of one
        merged event. This has no effect when ``legato`` is false.

    Returns
    -------
    Bar
        A new rhythmically transformed bar with the source tonality.

    Raises
    ------
    TypeError
        If ``bar`` is not a bar, ``pulses`` is not a string, or ``offset`` is
        not an integer.
    ValueError
        If the pattern contains unsupported characters, ``unit`` is not
        positive, or an onset is requested from an empty bar.
    """
    if not isinstance(bar, Bar):
        raise TypeError("bar must be a Bar")
    if not isinstance(pulses, str):
        raise TypeError("pulses must be a string")
    if not isinstance(offset, int):
        raise TypeError("offset must be an integer")

    unit = Fraction(unit)
    if unit <= 0:
        raise ValueError("unit must be positive")

    invalid_characters = set(pulses) - {"x", "."}
    if invalid_characters:
        invalid = "".join(sorted(invalid_characters))
        raise ValueError(f"Invalid pulse character(s): {invalid!r}")
    if not pulses:
        return Bar(tonality=bar.tonality)
    if "x" in pulses and not bar:
        raise ValueError("Cannot emit pulse onsets from an empty bar")

    offset %= len(pulses)
    pulses = pulses[offset:] + pulses[:offset]
    source_notes = cycle(bar.notes)
    generated_notes: list[Note] = []

    def resize(source: Note, duration: Fraction) -> Note:
        return source.with_pitches(source.pitches).with_duration(duration)

    if not legato:
        for pulse in pulses:
            if pulse == "x":
                generated_notes.append(resize(next(source_notes), unit))
            else:
                generated_notes.append(Note.rest(unit))
        return Bar(generated_notes, tonality=bar.tonality)

    index = 0
    while index < len(pulses):
        if pulses[index] == ".":
            end = index + 1
            while end < len(pulses) and pulses[end] == ".":
                end += 1
            generated_notes.append(Note.rest((end - index) * unit))
            index = end
            continue

        source = next(source_notes)
        end = index + 1
        while end < len(pulses) and pulses[end] == ".":
            end += 1
        frame_count = end - index

        if not emit_ties or source.is_rest():
            generated_notes.append(resize(source, frame_count * unit))
        else:
            for frame in range(frame_count):
                first = frame == 0
                last = frame == frame_count - 1
                generated_notes.append(
                    resize(source, unit).with_ties(
                        tie_in=source.tie_in if first else True,
                        tie_out=source.tie_out if last else True,
                    )
                )
        index = end

    return Bar(generated_notes, tonality=bar.tonality)


def euclidean_rhythm(
        bar: Bar,
        n: int,
        k: int,
        legato: bool = True,
        unit: Fraction = Fraction(1, 16),
        offset: int = 0,
        emit_ties: bool = False,
) -> Bar:
    """Distribute ``k`` source onsets evenly over ``n`` frames.

    Source events are selected cyclically at generated onsets. Rhythm
    realization is delegated to :func:`pulses_to_durations`, so legato
    durations, explicit ties, metadata, rotation, and tonality behave
    identically in both functions.

    Parameters
    ----------
    bar : Bar
        Source events cycled at generated onsets.
    n : int
        Positive number of frames in the generated rhythm.
    k : int
        Number of onsets between zero and ``n``, inclusive.
    legato : bool, default=True
        Merge each onset with its following continuation frames.
    unit : Fraction, default=Fraction(1, 16)
        Duration of one frame.
    offset : int, default=0
        Number of frames by which to rotate the pattern to the left.
    emit_ties : bool, default=False
        In legato mode, emit tied unit events instead of merged durations.

    Returns
    -------
    Bar
        A new bar containing the generated rhythm and source tonality.

    Raises
    ------
    TypeError
        If ``bar`` is not a bar or ``n`` and ``k`` are not integers.
    ValueError
        If ``n`` is not positive or ``k`` lies outside ``0 <= k <= n``.
    """
    if not isinstance(bar, Bar):
        raise TypeError("bar must be a Bar")
    if not isinstance(n, int) or not isinstance(k, int):
        raise TypeError("n and k must be integers")
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= k <= n:
        raise ValueError("k must satisfy 0 <= k <= n")

    if k == n:
        pulses = "x" * n
    else:
        remainders = [(frame * k) % n for frame in range(-1, n)]
        pulses = "".join(
            "x" if left > right else "."
            for left, right in zip(remainders[:-1], remainders[1:])
        )
    return pulses_to_durations(
        bar,
        pulses,
        legato=legato,
        unit=unit,
        offset=offset,
        emit_ties=emit_ties,
    )


def fill_bars(
        bars: Iterable[Bar],
        notes: Iterable[Note],
) -> Voice:
    """Fill template bars with events from a note source.

    The function consumes events in order and returns one new bar for every
    template bar. Each result has exactly the template's span and tonality.
    Events that cross a bar boundary are split; sounding notes and chords are
    tied across the boundary, while rests are split without ties. Consecutive
    rests within one result bar are combined into a single rest, retaining the
    first rest's velocity. Existing tie flags are retained at the outer ends
    of a split sounding event.

    The finite bar input is consumed eagerly and the result is a concrete
    :class:`Voice`. If ``bars`` is a voice, its default tonality, tonality plan,
    and name are inherited by the result. The note source is consumed only as
    far as needed. Source events that fit without splitting are reused
    unchanged except when rest normalization requires a new event; split
    segments are created with :meth:`Note.with_duration` and
    :meth:`Note.with_ties`.

    Parameters
    ----------
    bars : Iterable[Bar]
        Finite collection of bars whose spans and tonalities define the output
        structure. A :class:`Voice` can be passed directly.
    notes : Iterable[Note]
        Finite or infinite source of notes, chords, and rests.

    Returns
    -------
    Voice
        A new voice containing the filled bars. Voice-level tonal context and
        name are inherited when the templates are supplied as a voice.

    Raises
    ------
    TypeError
        If either input produces an object of the wrong type.
    ValueError
        If the note source ends before a template bar can be filled.
    """
    def append_note(filled: list[Note], note: Note) -> None:
        if not note.is_rest():
            filled.append(note)
            return

        rest = note.with_ties(tie_in=False, tie_out=False)
        if filled and filled[-1].is_rest():
            previous = filled[-1]
            filled[-1] = previous.with_duration(
                previous.duration + rest.duration
            )
        else:
            filled.append(rest)

    note_iterator = iter(notes)
    carried: Note | None = None
    source_index = 0
    result: list[Bar] = []

    for bar_index, template in enumerate(bars):
        if not isinstance(template, Bar):
            raise TypeError(
                f"Bar template {bar_index} is not a Bar"
            )
        remaining = Fraction(template.span())
        filled: list[Note] = []

        while remaining > 0:
            if carried is None:
                try:
                    note = next(note_iterator)
                except StopIteration:
                    raise ValueError(
                        "Note source ended while filling "
                        f"bar {bar_index}"
                    ) from None
                if not isinstance(note, Note):
                    raise TypeError(
                        f"Generated event {source_index} is not a Note"
                    )
                source_index += 1
            else:
                note = carried
                carried = None

            if note.duration <= remaining:
                append_note(filled, note)
                remaining -= note.duration
                continue

            first, carried = _split_note(note, remaining)
            append_note(filled, first)
            remaining = Fraction(0)

        result.append(Bar(filled, tonality=template.tonality))

    if isinstance(bars, Voice):
        return Voice(
            result,
            default_tonality=bars.default_tonality,
            tonality_plan=bars.tonality_plan,
            name=bars.name,
        )
    return Voice(result)
