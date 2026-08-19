from copy import copy
from collections.abc import Callable, Iterable, Sequence
from itertools import cycle, islice
from fractions import Fraction
from typing import TYPE_CHECKING
import random

from .note import Note
from .parser import parse
from .pitch import Pitch
from .tonality import ScalePosition, Tonality

if TYPE_CHECKING:
    from .voice import Voice

class Bar:
    def __init__(
            self,
            notes=None,
            tonality: Tonality | None = None,
    ):
        if notes is None:
            parsed = []
        elif isinstance(notes, str):
            parsed = parse(notes)
        else:
            parsed = list(notes)

        if not all(isinstance(note, Note) for note in parsed):
            raise TypeError("Every bar element must be a note")

        self.notes = parsed
        self.tonality = tonality

    def __copy__(self) -> "Bar":
        return Bar(
            notes=list(self.notes),
            tonality=self.tonality,
        )

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, Bar)
            and self.notes == other.notes
            and self.tonality == other.tonality
        )

    @staticmethod
    def _common_tonality(
            left: Tonality | None,
            right: Tonality | None,
    ) -> Tonality | None:
        if left is None:
            return right
        if right is None:
            return left
        if left != right:
            raise ValueError("Cannot combine bars with conflicting tonalities")
        return left

    def __add__(self, other):
        """Concatenate an event or bar, or transpose up by semitones.

        Concatenation preserves or resolves tonalities with
        :meth:`_common_tonality`. Integer semitone transposition preserves the
        bar's tonality metadata, although the resulting pitches need not be
        diatonic in that tonality.
        """
        if isinstance(other, Bar):
            tonality = self._common_tonality(
                self.tonality,
                other.tonality,
            )
            return Bar(
                notes=[*self.notes, *other.notes],
                tonality=tonality,
            )
        if isinstance(other, Note):
            return Bar(
                notes=[*self.notes, other],
                tonality=self.tonality,
            )
        if isinstance(other, int):
            return self.map_notes(
                lambda note: note.transpose_semitones(other)
            )
        return NotImplemented

    def __sub__(self, other):
        """Transpose every pitch down by a number of semitones.

        The tonality metadata is preserved, but the resulting pitches need
        not be diatonic in that tonality.
        """
        if isinstance(other, int):
            return self.map_notes(
                lambda note: note.transpose_semitones(-other)
            )
        return NotImplemented

    def __mul__(self, other):
        """Repeat the event sequence while preserving its tonality."""
        if not isinstance(other, int):
            return NotImplemented
        return Bar(
            notes=self.notes * max(0, other),
            tonality=self.tonality,
        )

    def __rmul__(self, other):
        return self * other

    def __truediv__(self, other):
        """Divide every duration while preserving all other bar data."""
        if not isinstance(other, (int, Fraction)):
            return NotImplemented
        return self.map_notes(
            lambda note: note.with_duration(note.duration / other)
        )

    def __and__(self, other):
        return self.merge_pitches(other)

    def __or__(self, other):
        return self.take(other, pitches=True)

    def __xor__(self, other):
        return self.take(other, durations=True)

    def interleave(
            self,
            other: "Bar",
            counts: Iterable[int],
    ) -> "Bar":
        """Interleave chunks from this bar and a cycling second bar.

        The first count selects consecutive events from this bar and the
        second count selects consecutive events from ``other``. Chunk pairs
        repeat until this bar is exhausted. Its final chunk may contain fewer
        events than requested; the corresponding chunk from ``other`` remains
        full. The second bar cycles from its beginning whenever it runs out.

        For example, counts ``[1, 2]`` take one event from this bar, then two
        from ``other``, and repeat that pattern. Both source bars remain
        unchanged, and emitted events retain all of their metadata. Tonality
        is inherited from the defined bar when only one has a tonality, and
        conflicting explicit tonalities are rejected.

        Parameters
        ----------
        other : Bar
            Non-empty bar whose events cycle as the second source.
        counts : Iterable[int]
            Exactly two positive integers: the chunk sizes for this bar and
            ``other``, respectively.

        Returns
        -------
        Bar
            A new bar containing the interleaved event sequence.

        Raises
        ------
        TypeError
            If ``other`` is not a bar or a count is not an integer.
        ValueError
            If there are not exactly two positive counts, the second bar is
            empty while this bar has events, or explicit tonalities conflict.
        """
        if not isinstance(other, Bar):
            raise TypeError("other must be a Bar")

        chunk_sizes = tuple(counts)
        if len(chunk_sizes) != 2:
            raise ValueError("counts must contain exactly two values")
        if any(
                isinstance(count, bool) or not isinstance(count, int)
                for count in chunk_sizes
        ):
            raise TypeError("interleave counts must be integers")
        if any(count <= 0 for count in chunk_sizes):
            raise ValueError("interleave counts must be positive")

        tonality = self._common_tonality(
            self.tonality,
            other.tonality,
        )
        if not self:
            return Bar(tonality=tonality)
        if not other:
            raise ValueError("other bar must contain at least one event")

        first_count, second_count = chunk_sizes
        other_events = cycle(other.notes)
        result = []
        for start in range(0, len(self), first_count):
            result.extend(self.notes[start:start + first_count])
            result.extend(islice(other_events, second_count))
        return Bar(result, tonality=tonality)

    def __getitem__(self, i):
        """Select events, retaining tonality for slices and index lists."""
        if isinstance(i, slice):
            return Bar(
                notes=self.notes[i],
                tonality=self.tonality,
            )
        if isinstance(i, list):
            return Bar(
                notes=[self.notes[index] for index in i],
                tonality=self.tonality,
            )
        return self.notes[i]

    def __setitem__(self, i, note):
        self.notes[i] = note

    def __len__(self):
        return len(self.notes)

    def __str__(self):
        return self.to_paeonia()

    def __repr__(self):
        return f"Bar(\"{str(self)}\")"

    def map_notes(self, function: Callable[[Note], Note]) -> "Bar":
        """Apply a function to every note in the bar.

        Parameters
        ----------
        function : Callable[[Note], Note]
            Function that maps each note to its replacement.

        Returns
        -------
        Bar
            A new bar containing the mapped notes and the same tonality.
        """
        return Bar(notes=[function(note) for note in self.notes],
                   tonality=self.tonality)

    def stretch(
            self,
            factor: (
                int
                | float
                | Fraction
                | Iterable[int | float | Fraction]
            ),
            *,
            quantize: bool = True,
    ) -> "Bar":
        """Stretch event durations and return a new bar.

        A single factor is applied to every event. When an iterable is given,
        events and factors advance together: factors cycle when shorter than
        the bar, and bar events cycle when the factor pattern is longer.
        Pairing stops after the longer input has been consumed once.

        Each result is transformed through :meth:`Note.stretch`, so rests,
        chords, pitches, velocity, and tie metadata retain their existing
        behavior. The source bar is unchanged and its tonality is preserved.

        Parameters
        ----------
        factor : int | float | Fraction | Iterable[int | float | Fraction]
            A finite, strictly positive duration multiplier, or a finite,
            non-empty pattern of such multipliers.
        quantize : bool, default=True
            Snap each result to the nearest duration directly supported by
            the LilyPond renderer. Set this to false to retain exact multiplied
            durations.

        Returns
        -------
        Bar
            A new bar containing the stretched events.

        Raises
        ------
        TypeError
            If a factor or ``quantize`` has an unsupported type.
        ValueError
            If a factor is non-finite or not strictly positive, the factor
            pattern is empty, or a non-empty pattern is applied to an empty
            bar.
        """
        if not isinstance(quantize, bool):
            raise TypeError("quantize must be a boolean")

        if isinstance(factor, (int, float, Fraction)):
            if not self:
                Note.rest().stretch(factor, quantize=quantize)
            return self.map_notes(
                lambda note: note.stretch(factor, quantize=quantize)
            )

        try:
            factors = tuple(factor)
        except TypeError as exc:
            raise TypeError(
                "factor must be an integer, float, Fraction, or iterable"
            ) from exc
        if not factors:
            raise ValueError("factor pattern must contain at least one value")
        if not self:
            raise ValueError(
                "cannot cycle events from an empty bar"
            )

        frame_count = max(len(self), len(factors))
        pairs = islice(
            zip(cycle(self.notes), cycle(factors)),
            frame_count,
        )
        return Bar(
            (
                note.stretch(amount, quantize=quantize)
                for note, amount in pairs
            ),
            tonality=self.tonality,
        )

    def rotate(self, steps: int) -> "Bar":
        """Rotate the event sequence and return a new bar.

        Positive values rotate to the right and negative values rotate to the
        left. Values larger than the number of events wrap around. Tonality
        and the original :class:`Note` objects, including all their metadata,
        are preserved; the source bar is unchanged.

        Parameters
        ----------
        steps : int
            Number of event positions to rotate. Positive values rotate right.

        Returns
        -------
        Bar
            A new bar containing the rotated event sequence.

        Raises
        ------
        TypeError
            If ``steps`` is not an integer.
        """
        if not isinstance(steps, int):
            raise TypeError("steps must be an integer")
        if not self:
            return Bar(tonality=self.tonality)

        steps %= len(self)
        if steps == 0:
            notes = list(self.notes)
        else:
            notes = self.notes[-steps:] + self.notes[:-steps]
        return Bar(notes, tonality=self.tonality)

    def gate_notes(
            self,
            pattern: Iterable[bool | int] | str,
            *,
            extend_previous: bool = False,
    ) -> "Bar":
        """Apply one gate switch to each event and return a new bar.

        This is the finite, bar-sized counterpart of
        :func:`paeonia.tools.gate_notes`. An open gate retains its event and a
        closed gate replaces it with an untied rest. String patterns use
        ``"x"`` for an open gate and ``"."`` for a closed gate. With
        ``extend_previous=True``, closed events are absorbed into the duration
        of the preceding open event; leading closed events remain rests.

        The pattern must contain exactly one switch per source event. Tonality
        and active-event metadata are preserved, and the source bar is not
        modified.

        Parameters
        ----------
        pattern : Iterable[bool | int] | str
            Gate switches matching the number of events in the bar.
        extend_previous : bool, default=False
            Extend an earlier active event across following closed events.

        Returns
        -------
        Bar
            A new bar containing one gated pass over the source events.

        Raises
        ------
        ValueError
            If the pattern length differs from the number of events or a
            string contains unsupported characters.
        TypeError
            If switches or ``extend_previous`` have unsupported types.
        """
        from .tools import gate_notes

        supplied_pattern = (
            pattern
            if isinstance(pattern, str)
            else tuple(pattern)
        )
        if len(supplied_pattern) != len(self):
            raise ValueError(
                "pattern length must match the number of events in the bar"
            )
        if not isinstance(extend_previous, bool):
            raise TypeError("extend_previous must be a boolean")
        if not self:
            return Bar(tonality=self.tonality)

        return Bar(
            gate_notes(
                self,
                supplied_pattern,
                extend_previous=extend_previous,
                frames=len(self),
            ),
            tonality=self.tonality,
        )

    def map_pitches(self, function: Callable[[Pitch], Pitch]) -> "Bar":
        """Apply a function to every pitch in the bar.

        Rests are retained unchanged.

        Parameters
        ----------
        function : Callable[[Pitch], Pitch]
            Function that maps each pitch to its replacement.

        Returns
        -------
        Bar
            A new bar containing the mapped pitches and the same tonality.
        """
        return self.map_notes(lambda note: note.map_pitches(function))

    def note_repeat(self, repeats: Iterable[int]) -> "Bar":
        """Repeat events according to a cycling count pattern.

        This is the finite counterpart of :func:`paeonia.tools.note_repeat`.
        Events and counts advance together. If the count pattern is shorter
        than the bar, the counts cycle; if it is longer, the bar's events
        cycle. Pairing stops after the longer input has been consumed once.
        The source bar is unchanged and its tonality and event metadata are
        preserved.

        Parameters
        ----------
        repeats : Iterable[int]
            Finite, non-empty sequence of positive repeat counts.

        Returns
        -------
        Bar
            A new bar containing the repeated event sequence.

        Raises
        ------
        ValueError
            If the bar or repeat pattern is empty, or a count is not positive.
        TypeError
            If a repeat count is not an integer.
        """
        from .tools import note_repeat

        repeat_pattern = tuple(repeats)
        frame_count = max(len(self), len(repeat_pattern))
        return Bar(
            note_repeat(
                self,
                repeat_pattern,
                frames=frame_count,
            ),
            tonality=self.tonality,
        )

    def repeat(self, times):
        """Repeat the bar while preserving its tonality.

        Parameters
        ----------
        times: int
            How many times to repeat the bar

        Returns
        -------
        Bar
            A new bar containing the repeated event sequence.
        """
        if not isinstance(times, int):
            raise TypeError("Repeat count must be an integer")
        return self * times

    def span(self):
        """"Return the span of the bar (sum of duration of all notes).

        Returns
        -------
        Fraction
            Sum of the durations of the notes in the bar
        """
        return sum([note.duration for note in self.notes])

    def split(
            self,
            time_signature: tuple[int, int] = (4, 4),
    ) -> "Voice":
        """Split the event sequence into measures of a given time signature.

        Sounding notes and chords that cross a measure boundary are divided
        into tied segments. Rests are split without ties, and consecutive rests
        in a resulting measure are combined. When the source does not fill its
        final measure, an untied rest pads the remaining duration. Every
        resulting bar has the source tonality, which is also installed as the
        returned voice's default tonal context. The source bar and its events
        are not modified. An empty source produces an empty voice.

        Parameters
        ----------
        time_signature : tuple[int, int], default=(4, 4)
            Positive numerator and denominator. Their ratio gives each
            measure's duration in whole-note units.

        Returns
        -------
        Voice
            A new voice containing complete, equally sized measures.

        Raises
        ------
        TypeError
            If ``time_signature`` is not a pair of integers.
        ValueError
            If either time-signature value is not positive.
        """
        from .tools import fill_bars
        from .voice import Voice

        if not isinstance(time_signature, tuple) or len(time_signature) != 2:
            raise TypeError("time_signature must be a two-item tuple")
        if any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in time_signature
        ):
            raise TypeError("time_signature values must be integers")
        numerator, denominator = time_signature
        if numerator <= 0 or denominator <= 0:
            raise ValueError("time-signature values must be positive")

        measure_span = Fraction(numerator, denominator)
        total_span = Fraction(self.span())
        full_measures, remainder = divmod(total_span, measure_span)
        measure_count = full_measures + bool(remainder)
        if measure_count == 0:
            return Voice(default_tonality=self.tonality)

        source_notes = list(self.notes)
        padding = measure_count * measure_span - total_span
        if padding:
            source_notes.append(Note.rest(padding))

        templates = [
            Bar(
                [Note.rest(measure_span)],
                tonality=self.tonality,
            )
            for _ in range(measure_count)
        ]
        filled = fill_bars(templates, source_notes)
        return Voice(
            filled.bars,
            default_tonality=self.tonality,
        )

    def add_note(self, note):
        """Append a new note to the bar.

        Parameters
        ----------
        note: Note
           A note to add
        """
        self.notes.append(note)

    def pitches(self):
        """Returns all pitches in this bar as a single flat list.

        Returns
        -------
        list
             A list of numbers signifying pitches.
        """
        result = []
        for note in self:
            result += note.pitches
        return result

    def pitch_variant(self, function: Callable[[list[Pitch]], Sequence[Pitch]]) -> "Bar":
        """Transform the bar's flattened pitch sequence.

        The transformed pitches are redistributed across the original notes
        and chords. Rests and the number of pitches in each event are
        preserved.

        Parameters
        ----------
        function : Callable[[list[Pitch]], Sequence[Pitch]]
            Function that receives all pitches as a flat list and returns a
            replacement sequence containing the same number of pitches.

        Returns
        -------
        Bar
            A new bar containing the transformed pitches and the same
            tonality.

        Raises
        ------
        ValueError
            If the transformed sequence contains a different number of
            pitches.
        """
        original = [
            pitch
            for note in self.notes
            for pitch in note.pitches
        ]
        transformed = list(function(list(original)))
        if len(transformed) != len(original):
            raise ValueError(
                "A pitch variant must preserve the number of pitches"
            )
        iterator = iter(transformed)
        new_notes = []
        for note in self.notes:
            if note.is_rest():
                new_notes.append(note)
            else:
                new_notes.append(
                    note.with_pitches(
                        next(iterator)
                        for _ in note.pitches
                    )
                )
        return Bar(new_notes, tonality=self.tonality)

    def with_tonality(self, tonality: Tonality | None) -> "Bar":
        """Return a copy of the bar with the specified tonality.

        This changes only the bar's tonal context; it does not remap the
        pitches of its notes.

        Parameters
        ----------
        tonality : Tonality | None
            Tonality to associate with the new bar, or ``None`` to remove
            the current tonal context.

        Returns
        -------
        Bar
            A new bar containing the same notes and the specified tonality.
        """
        return Bar(
            notes=list(self.notes),
            tonality=tonality,
        )

    def apply_tonality(
            self,
            target: Tonality,
            source: Tonality | None = None,
            *,
            chromatic: str = "preserve_alteration",
            degree_policy: str = "error",
    ) -> "Bar":
        """Reinterpret the bar's scale positions in another tonality.

        Each pitch is analyzed relative to the source tonality and realized
        at the same scale degree, tonal octave, and chromatic alteration in
        the target tonality. Durations, rests, chords, and other note
        properties are preserved.

        Parameters
        ----------
        target : Tonality
            Tonality in which to realize the mapped pitches.
        source : Tonality | None
            Tonality used to analyze the existing pitches. If omitted, the
            tonality assigned to the bar is used.
        chromatic : str
            Policy passed to ``Tonality.analyze_pitch`` for pitches outside
            the source tonality.
        degree_policy : str
            How to handle different source and target degree counts. Use
            ``"error"`` to reject them or ``"wrap"`` to wrap source degrees
            modulo the target's degree count.

        Returns
        -------
        Bar
            A new bar mapped to and associated with the target tonality.

        Raises
        ------
        ValueError
            If no source tonality is available, a policy is unknown, or the
            degree counts differ when ``degree_policy`` is ``"error"``.
        """
        source = self.tonality if source is None else source
        if source is None:
            raise ValueError(
                "A source tonality must be supplied or assigned to the bar"
            )
        if degree_policy not in {"error", "wrap"}:
            raise ValueError(f"Unknown degree policy: {degree_policy}")
        if chromatic not in {
                "preserve_alteration",
                "error",
                "nearest",
        }:
            raise ValueError(f"Unknown chromatic policy: {chromatic}")
        if source.degree_count != target.degree_count:
            if degree_policy == "error":
                raise ValueError(
                    "Source and target tonalities have different degree counts"
                )

        def transform(pitch: Pitch) -> Pitch:
            position = source.analyze_pitch(
                pitch,
                chromatic=chromatic,
            )
            if position.degree >= target.degree_count:
                position = ScalePosition(
                    degree=position.degree % target.degree_count,
                    tonal_octave=position.tonal_octave,
                    alteration=position.alteration,
                )
            return target.realize_pitch(position)

        return self.map_pitches(transform).with_tonality(target)

    def quantize_to_tonality(
            self,
            target: Tonality,
            *,
            direction: str = "nearest",
            tie_break: str = "lower",
    ) -> "Bar":
        """Move every pitch to a nearby pitch in a target tonality.

        Quantization is based on MIDI distance rather than scale degree.
        Rests, durations, chord structure, and other note properties are
        preserved.

        Parameters
        ----------
        target : Tonality
            Tonality whose pitches are used as quantization candidates.
        direction : str
            Direction in which to search: ``"nearest"``, ``"up"``, or
            ``"down"``.
        tie_break : str
            For equally near candidates, choose ``"lower"`` or ``"upper"``.

        Returns
        -------
        Bar
            A new quantized bar associated with the target tonality.

        Raises
        ------
        ValueError
            If a policy is unknown or no target pitch can be found in the
            requested direction.
        """
        if direction not in {"nearest", "up", "down"}:
            raise ValueError(f"Unknown quantize direction: {direction}")
        if tie_break not in {"lower", "upper"}:
            raise ValueError(f"Unknown quantize tie_break: {tie_break}")

        def transform(pitch: Pitch) -> Pitch:
            return target.quantize_pitch(
                pitch,
                direction=direction,
                tie_break=tie_break,
            )
        return self.map_pitches(transform).with_tonality(target)

    def transpose_degrees(
            self,
            degrees: int,
            tonality: Tonality | None = None,
            *,
            chromatic: str = "preserve_alteration",
    ) -> "Bar":
        """Transpose every pitch by scale degrees within a tonality.

        Positive values move pitches upward and negative values move them
        downward. Rests, durations, chord structure, and other note
        properties are preserved.

        Parameters
        ----------
        degrees : int
            Number of scale degrees by which to transpose each pitch.
        tonality : Tonality | None
            Tonality that defines the scale degrees. If omitted, the tonality
            assigned to the bar is used.
        chromatic : str
            Policy passed to ``Tonality.transpose_pitch`` for pitches outside
            the tonality: ``"preserve_alteration"``, ``"error"``, or
            ``"nearest"``.

        Returns
        -------
        Bar
            A new transposed bar associated with the tonality used.

        Raises
        ------
        ValueError
            If no tonality is available, the chromatic policy is unknown, or
            a resulting pitch falls outside the MIDI range.
        """
        tonality = self.tonality if tonality is None else tonality
        if tonality is None:
            raise ValueError("No tonality is available")
        if chromatic not in {
                "preserve_alteration",
                "error",
                "nearest",
        }:
            raise ValueError(f"Unknown chromatic policy: {chromatic}")

        return self.map_pitches(
            lambda pitch: tonality.transpose_pitch(
                pitch,
                degrees,
                chromatic=chromatic,
            )
        ).with_tonality(tonality)

    def intervals(self) -> list[int]:
        """Return successive signed MIDI-semitone intervals.

        Returns
        -------
        list[int]
            Semitone difference between each pair of flattened pitches.
        """
        pitches = self.pitches()
        return [
            following.midi - previous.midi
            for previous, following in zip(pitches[:-1], pitches[1:])
        ]

    def tonal_intervals(
            self,
            tonality: Tonality | None = None,
            *,
            chromatic: str = "preserve_alteration",
    ) -> list[int]:
        """Return signed scale-degree steps between successive pitches.

        Pitches are read as one flat sequence, so rests contribute no pitches
        and pitches within chords participate in their stored order. The
        interval values count scale-degree steps rather than semitones;
        chromatic alterations do not change a degree when they are preserved.

        Parameters
        ----------
        tonality : Tonality | None
            Tonality used to analyze the pitches. If omitted, the tonality
            assigned to the bar is used.
        chromatic : str
            Policy passed to ``Tonality.analyze_pitch`` for pitches outside
            the tonality: ``"preserve_alteration"``, ``"error"``, or
            ``"nearest"``.

        Returns
        -------
        list[int]
            Signed differences between consecutive absolute scale-degree
            positions. Bars with fewer than two pitches return an empty list.

        Raises
        ------
        ValueError
            If no tonality is available or the chromatic policy is unknown.
        """
        tonality = self.tonality if tonality is None else tonality
        if tonality is None:
            raise ValueError("No tonality is available")
        if chromatic not in {
                "preserve_alteration",
                "error",
                "nearest",
        }:
            raise ValueError(f"Unknown chromatic policy: {chromatic}")

        positions = [
            tonality.analyze_pitch(pitch, chromatic=chromatic)
            for pitch in self.pitches()
        ]
        absolute = [
            position.tonal_octave * tonality.degree_count
            + position.degree
            for position in positions
        ]
        return [b - a for a, b in zip(absolute[:-1], absolute[1:])]

    def scale_intervals(
            self,
            factor: (
                int
                | float
                | Fraction
                | Iterable[int | float | Fraction]
            ),
            *,
            operation: str = "multiply",
            chromatic: bool = False,
            tonality: Tonality | None = None,
            alteration_policy: str = "preserve_alteration",
    ) -> "Bar":
        """Contract or expand successive intervals around the first pitch.

        By default, values multiply successive signed intervals while the
        first sounding pitch remains fixed. Values between zero and one
        contract intervals, values greater than one expand them, zero
        collapses them, and negative values additionally invert their
        direction. With ``operation="add"``, values are instead added to the
        signed intervals: for example, adding one changes ``-3`` to ``-2``.

        By default, intervals are measured in scale degrees using ``tonality``
        or the bar's assigned tonality. Set ``chromatic=True`` to measure them
        in MIDI semitones instead. Tonal scaling preserves each corresponding
        source pitch's chromatic alteration according to
        ``alteration_policy``.

        A single factor applies to every interval without changing the event
        layout. For an iterable, factors and successive flattened pitches
        advance together. A short pattern cycles across the bar's intervals.
        If the pattern is longer, the source event layout cycles until every
        supplied factor has been used at least once. Chord boundaries, rests,
        durations, velocities, and ties are retained; a repeated partial cycle
        always includes complete events.

        Resulting tonal degrees and semitone intervals must remain integral.
        For example, contracting a two-degree interval by
        ``Fraction(1, 2)`` is valid, while contracting a one-degree interval
        by the same factor is not representable and raises an error.

        Parameters
        ----------
        factor : int | float | Fraction | Iterable[int | float | Fraction]
            Finite interval value or finite, non-empty value pattern.
        operation : str, default="multiply"
            Combine intervals and values with ``"multiply"`` or ``"add"``.
        chromatic : bool, default=False
            Measure intervals in semitones instead of tonal scale degrees.
        tonality : Tonality | None
            Tonality used for tonal interval analysis. Defaults to the bar's
            tonality and is ignored for chromatic scaling.
        alteration_policy : str, default="preserve_alteration"
            Tonal pitch-analysis policy: ``"preserve_alteration"``,
            ``"error"``, or ``"nearest"``.

        Returns
        -------
        Bar
            A new interval-scaled bar with preserved event metadata.

        Raises
        ------
        TypeError
            If a factor or option has an unsupported type.
        ValueError
            If a pattern is empty, no tonal context is available, a policy is
            unknown, a scaled interval is not integral, or a pitch leaves the
            MIDI range.
        """
        if operation not in {"multiply", "add"}:
            raise ValueError(f"Unknown interval operation: {operation}")
        if not isinstance(chromatic, bool):
            raise TypeError("chromatic must be a boolean")
        if alteration_policy not in {
                "preserve_alteration",
                "error",
                "nearest",
        }:
            raise ValueError(
                f"Unknown alteration policy: {alteration_policy}"
            )

        def normalize(value: int | float | Fraction) -> Fraction:
            if isinstance(value, bool) or not isinstance(
                    value,
                    (int, float, Fraction),
            ):
                raise TypeError(
                    "interval values must be integers, floats, or Fractions"
                )
            try:
                return Fraction(
                    str(value) if isinstance(value, float) else value
                )
            except (OverflowError, ValueError) as exc:
                raise ValueError("interval values must be finite") from exc

        patterned = not isinstance(factor, (int, float, Fraction))
        if patterned:
            try:
                supplied_factors = tuple(factor)
            except TypeError as exc:
                raise TypeError(
                    "factor must be a number or iterable of numbers"
                ) from exc
            if not supplied_factors:
                raise ValueError(
                    "factor pattern must contain at least one value"
                )
        else:
            supplied_factors = (factor,)
        factors = tuple(normalize(value) for value in supplied_factors)

        selected_tonality = None
        if chromatic:
            result_tonality = self.tonality
        else:
            selected_tonality = self.tonality if tonality is None else tonality
            if selected_tonality is None:
                raise ValueError("No tonality is available")
            result_tonality = selected_tonality

        if not self:
            if patterned:
                raise ValueError("cannot cycle events from an empty bar")
            return Bar(tonality=result_tonality)

        source_pitch_count = sum(len(note.pitches) for note in self.notes)
        templates = list(self.notes)
        if patterned and source_pitch_count:
            required_pitch_count = len(factors) + 1
            expanded_pitch_count = source_pitch_count
            events = cycle(self.notes)
            while expanded_pitch_count < required_pitch_count:
                note = next(events)
                templates.append(note)
                expanded_pitch_count += len(note.pitches)

        source_pitches = [
            pitch
            for note in templates
            for pitch in note.pitches
        ]
        if len(source_pitches) < 2:
            return Bar(templates, tonality=result_tonality)

        def scaled_interval(
                interval: int,
                amount: Fraction,
                index: int,
        ) -> int:
            transformed = (
                interval * amount
                if operation == "multiply"
                else interval + amount
            )
            if transformed.denominator != 1:
                unit = "semitone" if chromatic else "scale-degree"
                raise ValueError(
                    f"Transformed {unit} interval {index} is not integral: "
                    f"{interval} {operation} {amount} = {transformed}"
                )
            return transformed.numerator

        if chromatic:
            coordinates = [pitch.midi for pitch in source_pitches]
            result_coordinates = [coordinates[0]]
            for index, (previous, following, amount) in enumerate(zip(
                    coordinates,
                    coordinates[1:],
                    cycle(factors),
            )):
                interval = scaled_interval(
                    following - previous,
                    amount,
                    index,
                )
                result_coordinates.append(result_coordinates[-1] + interval)

            transformed_pitches = []
            for source, midi in zip(source_pitches, result_coordinates):
                transformed_pitches.append(
                    source if midi == source.midi else Pitch.from_midi(midi)
                )
        else:
            assert selected_tonality is not None
            positions = [
                selected_tonality.analyze_pitch(
                    pitch,
                    chromatic=alteration_policy,
                )
                for pitch in source_pitches
            ]
            coordinates = [
                position.tonal_octave * selected_tonality.degree_count
                + position.degree
                for position in positions
            ]
            result_coordinates = [coordinates[0]]
            for index, (previous, following, amount) in enumerate(zip(
                    coordinates,
                    coordinates[1:],
                    cycle(factors),
            )):
                interval = scaled_interval(
                    following - previous,
                    amount,
                    index,
                )
                result_coordinates.append(result_coordinates[-1] + interval)

            transformed_pitches = []
            for coordinate, position in zip(result_coordinates, positions):
                tonal_octave, degree = divmod(
                    coordinate,
                    selected_tonality.degree_count,
                )
                transformed_pitches.append(
                    selected_tonality.realize_pitch(ScalePosition(
                        degree=degree,
                        tonal_octave=tonal_octave,
                        alteration=position.alteration,
                    ))
                )
            result_tonality = selected_tonality

        pitch_iterator = iter(transformed_pitches)
        transformed_notes = [
            note
            if note.is_rest()
            else note.with_pitches(
                next(pitch_iterator)
                for _ in note.pitches
            )
            for note in templates
        ]
        return Bar(transformed_notes, tonality=result_tonality)

    def retrograde(self):
        """Return a bar with a retrograde pitch variant.
        Durations are unaffected.

        Returns
        -------
        Bar
            A fresh new bar with pitches in reverse order
        """
        return self.pitch_variant(lambda pitch_list: list(reversed(pitch_list)))

    def inversion(self):
        """Invert successive MIDI intervals around the first pitch.

        Returns
        -------
        Bar
            A new bar with pitch boundaries and non-pitch metadata preserved.
        """
        def invert(pitch_list):
            if not pitch_list:
                return []
            intervals = [
                following.midi - previous.midi
                for previous, following in zip(
                    pitch_list[:-1],
                    pitch_list[1:],
                )
            ]
            result = [pitch_list[0]]
            for interval in intervals:
                result.append(
                    Pitch.from_midi(result[-1].midi - interval)
                )
            return result
        return self.pitch_variant(invert)

    def tonal_inversion(
            self,
            tonality: Tonality | None = None,
            *,
            chromatic: str = "preserve_alteration",
    ) -> "Bar":
        """Invert scale-degree intervals around the first pitch.

        Inversion operates in absolute scale-degree coordinates, not MIDI
        semitones. The first analyzed scale position is retained. Every later
        degree interval has its direction negated while keeping its magnitude.

        With the default ``"preserve_alteration"`` policy, the first pitch
        keeps its alteration and every later inverted pitch receives the
        alteration of the corresponding original pitch. Alterations themselves
        are not inverted. ``"error"`` rejects chromatic pitches, while
        ``"nearest"`` analyzes them as their nearest pitches in the tonality.

        Parameters
        ----------
        tonality : Tonality | None
            Tonality that defines the scale degrees. If omitted, the tonality
            assigned to the bar is used.
        chromatic : str
            Chromatic analysis policy: ``"preserve_alteration"``, ``"error"``,
            or ``"nearest"``.

        Returns
        -------
        Bar
            A new tonally inverted bar with the original event boundaries and
            the selected tonality.

        Raises
        ------
        ValueError
            If no tonality is available, the chromatic policy is unknown, or
            an inverted pitch falls outside the MIDI range.
        """
        tonality = self.tonality if tonality is None else tonality
        if tonality is None:
            raise ValueError("No tonality is available")
        if chromatic not in {
                "preserve_alteration",
                "error",
                "nearest",
        }:
            raise ValueError(f"Unknown chromatic policy: {chromatic}")

        def invert(pitches: list[Pitch]) -> list[Pitch]:
            if not pitches:
                return []

            positions = [
                tonality.analyze_pitch(pitch, chromatic=chromatic)
                for pitch in pitches
            ]
            absolute = [
                position.tonal_octave * tonality.degree_count
                + position.degree
                for position in positions
            ]
            intervals = [
                following - previous
                for previous, following in zip(absolute[:-1], absolute[1:])
            ]

            inverted_absolute = [absolute[0]]
            for interval in intervals:
                inverted_absolute.append(inverted_absolute[-1] - interval)

            inverted: list[Pitch] = []
            for absolute_degree, original in zip(
                    inverted_absolute,
                    positions,
            ):
                tonal_octave, degree = divmod(
                    absolute_degree,
                    tonality.degree_count,
                )
                inverted.append(
                    tonality.realize_pitch(
                        ScalePosition(
                            degree=degree,
                            tonal_octave=tonal_octave,
                            alteration=original.alteration,
                        )
                    )
                )
            return inverted

        return self.pitch_variant(invert).with_tonality(tonality)

    def ascending(self):
        """Return a bar with pitches in ascending order.

        Returns
        -------
        Bar
            A new bar with pitches in ascending order.
        """
        return self.pitch_variant(
            lambda pitch_list: sorted(
                pitch_list,
                key=lambda pitch: pitch.midi,
            )
        )

    def descending(self):
        """Returns a bar with pitches in descending order.

        Returns
        -------
        Bar
            A new bar with pitches in descending order.
        """
        return self.pitch_variant(
            lambda pitch_list: sorted(
                pitch_list,
                key=lambda pitch: pitch.midi,
                reverse=True,
            )
        )

    def random_order(self, seed=7):
        """Returns a bar with pitches in random order.

        Returns
        -------
        Bar
            A new bar with pitches in random order.
        """
        def shuffle(pitch_list):
            rnd = random.Random(seed)
            new_pitch_list = list(pitch_list)
            rnd.shuffle(new_pitch_list)
            return new_pitch_list
        return self.pitch_variant(shuffle)

    def take(
            self,
            source: "Iterable[Note] | Bar",
            *,
            pitches: bool = False,
            durations: bool = False,
            velocities: bool = False,
    ) -> "Bar":
        """Copy selected note properties from a sequence of donor notes.

        This operation is immutable: neither this bar nor the donor notes are
        modified. Unselected properties, including tie metadata, remain those
        of the receiving notes, and the returned bar retains this bar's
        tonality. A source bar is cycled as needed; any other iterable must
        contain at least as many notes as this bar.

        Parameters
        ----------
        source : Iterable[Note] | Bar
            Notes from which selected properties are copied. A bar repeats
            cyclically when it is shorter than the receiving bar.
        pitches : bool
            Copy each donor's pitches when true.
        durations : bool
            Copy each donor's duration when true.
        velocities : bool
            Copy each donor's velocity when true.

        Returns
        -------
        Bar
            A new bar containing the combined note properties and this bar's
            tonality.

        Raises
        ------
        ValueError
            If a nonempty bar takes from an empty source bar or a finite source
            does not contain enough notes.
        TypeError
            If the source yields an object that is not a ``Note``.
        """
        if not any((pitches, durations, velocities)):
            return copy(self)

        if isinstance(source, Bar):
            if self.notes and not source.notes:
                raise ValueError("Cannot take notes from an empty source bar")
            donors = cycle(source.notes)
        else:
            donors = iter(source)

        result: list[Note] = []
        for note in self.notes:
            try:
                donor = next(donors)
            except StopIteration as exc:
                raise ValueError(
                    "Source does not contain enough notes"
                ) from exc
            if not isinstance(donor, Note):
                raise TypeError("Take source must yield Note objects")
            replacement = note
            if pitches:
                replacement = replacement.with_pitches(donor.pitches)
            if durations:
                replacement = replacement.with_duration(donor.duration)
            if velocities:
                replacement = replacement.with_velocity(donor.velocity)
            result.append(replacement)
        return Bar(result, tonality=self.tonality)

    def merge_pitches(self, other: "Bar") -> "Bar":
        """Merge corresponding events from rhythmically compatible bars.

        Parameters
        ----------
        other : Bar
            Bar with the same event count and corresponding durations.

        Returns
        -------
        Bar
            A new bar whose events contain the left pitches followed by the
            right pitches. Note metadata comes from the left bar, and the
            common tonality is preserved.

        Raises
        ------
        TypeError
            If ``other`` is not a bar.
        ValueError
            If the bars have different event counts, corresponding durations
            differ, or their explicit tonalities conflict.
        """
        if not isinstance(other, Bar):
            raise TypeError("Can only merge pitches with another bar")
        tonality = self._common_tonality(
            self.tonality,
            other.tonality,
        )
        if len(self) != len(other):
            raise ValueError("Bars must contain the same number of events")

        merged_notes = []
        for index, (left, right) in enumerate(zip(self, other)):
            if left.duration != right.duration:
                raise ValueError(
                    f"Bar durations differ at event {index}"
                )
            merged_notes.append(left.merge_pitches(right))
        return Bar(notes=merged_notes, tonality=tonality)

    def to_midi(self, offset=0, tpb=480):
        from .midi import bar_to_midi_messages
        return bar_to_midi_messages(self, offset=offset, tpb=tpb)

    def to_paeonia(self):
        """Return paeonia notation representation of this bar.

        Returns
        -------
        str
            Lilypond notation representing all the notes in the bar
        """
        octave = 0
        duration = Fraction("1/4")
        note_repr, octave = self[0].to_paeonia(previous_octave=octave, previous_duration=duration)
        duration = self[0].duration
        result = note_repr
        for note in self[1:]:
            note_repr, octave = note.to_paeonia(previous_octave=octave, previous_duration=duration)
            duration = note.duration
            result += " " + note_repr
        return result
            

    def to_lilypond(self):
        from .lilypond import bar_to_lilypond
        return bar_to_lilypond(self)


    def show(self):
        from .playback import show_bar
        show_bar(self)
        return self

    def play(self, tpb=480, autoplay=False):
        from .playback import play_bar
        play_bar(self, tpb=tpb, autoplay=autoplay)
        return self
