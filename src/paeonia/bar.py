from copy import copy
from collections.abc import Callable, Iterable, Sequence
from itertools import cycle
from fractions import Fraction
import random
import warnings

from .note import Note
from .parser import parse
from .pitch import Pitch
from .tonality import ScalePosition, Tonality

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

    def note_repeat(self, times):
        """Repeat notes according to the pattern provided.

        Parameters
        ----------
        times: list
            A list with repeat values (will be cycled if it runs out).

        Returns
        -------
        Generator
            A generator of repeated notes.
        """
        times = cycle(times)
        notes = cycle(self)
        while True:
            time = next(times)
            note = next(notes)
            for _ in range(time):
                yield note

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

    def cycle(self):
        """Create a Note generator that returns the notes in this bar in a loop.

        Returns
        -------
        Generator
            Returns an infinite stream of repeating notes
        """
        return cycle(self)

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
            donors = source.cycle()
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

    def tonal_transpose(self, tonality, degrees):
        """Deprecated wrapper around :meth:`transpose_degrees`."""
        warnings.warn(
            (
                "Bar.tonal_transpose() is deprecated; "
                "use transpose_degrees() instead."
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        return self.transpose_degrees(degrees, tonality=tonality)

    def tonal_mode_change(self, tonality, mode):
        """Deprecated wrapper around :meth:`apply_tonality`."""
        warnings.warn(
            (
                "Bar.tonal_mode_change() is deprecated; "
                "use apply_tonality() instead."
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        target = Tonality(tonality.tonic, mode)
        return self.apply_tonality(target, source=tonality)

    def map_tonality(self, tonality, method="random", seed=7):
        """Deprecated wrapper around :meth:`quantize_to_tonality`."""
        warnings.warn(
            (
                "Bar.map_tonality() is deprecated; "
                "use quantize_to_tonality() instead."
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        direction = "nearest" if method == "random" else method
        return self.quantize_to_tonality(
            tonality,
            direction=direction,
            tie_break="lower",
        )

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

    def pulses_to_durations(
            self,
            pulses: str,
            legato: bool = True,
            unit: Fraction = Fraction("1/16"),
            offset: int = 0,
            emit_ties: bool = False,
    ) -> "Bar":
        """Apply an onset pattern to this bar's events.

        Each ``"x"`` starts the next event from this bar, cycling the source
        events when necessary. Each ``"."`` is either a unit rest or, in
        legato mode, a continuation of the preceding onset. Dots before the
        first onset remain rests.

        In the default legato representation, an onset and its continuation
        frames become one event whose duration is their combined length. Set
        ``emit_ties`` to represent the same sounding duration as separate
        unit-length events: sounding continuations receive internal tie flags,
        while no ties are introduced for rest spans. The source event's
        velocity, pitches, and ties at the outer boundaries are retained.

        Generated rests use :meth:`Note.rest`. Source events are transformed
        with :meth:`Note.with_pitches`, :meth:`Note.with_duration`, and, when
        needed, :meth:`Note.with_ties`; they are not reconstructed from a
        subset of their fields.

        Parameters
        ----------
        pulses : str
            Pattern whose onsets are ``"x"`` and whose rests or continuation
            frames are ``"."``.
        legato : bool, default=True
            Merge each onset with the following dot frames. When false, every
            pattern character produces one unit-length event.
        unit : Fraction, default=Fraction(1, 16)
            Duration of one pattern frame. It must be positive.
        offset : int, default=0
            Number of frames by which to rotate the pattern to the left.
        emit_ties : bool, default=False
            When both this option and ``legato`` are true, emit one sounding
            event per frame and connect those frames with ties instead of
            merging them into a single longer event. Rest spans stay merged
            and receive no generated ties. It has no effect when ``legato``
            is false.

        Returns
        -------
        Bar
            A new bar with the generated rhythm and this bar's tonality.

        Raises
        ------
        TypeError
            If ``pulses`` is not a string or ``offset`` is not an integer.
        ValueError
            If the pattern contains characters other than ``"x"`` and
            ``"."``, ``unit`` is not positive, or an onset is requested from
            an empty bar.
        """
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
            return Bar(tonality=self.tonality)
        if "x" in pulses and not self.notes:
            raise ValueError("Cannot emit pulse onsets from an empty bar")

        offset %= len(pulses)
        pulses = pulses[offset:] + pulses[:offset]
        source_notes = self.cycle()
        generated_notes = []

        def resize(source: Note, duration: Fraction) -> Note:
            # Use Note's immutable transformations so every metadata field is
            # retained. with_pitches is explicit because pulse mapping copies
            # the complete pitch spelling of the source event.
            return source.with_pitches(source.pitches).with_duration(duration)

        if not legato:
            for pulse in pulses:
                if pulse == "x":
                    generated_notes.append(resize(next(source_notes), unit))
                else:
                    generated_notes.append(Note.rest(unit))
            return Bar(generated_notes, tonality=self.tonality)

        index = 0
        while index < len(pulses):
            if pulses[index] == ".":
                end = index + 1
                while end < len(pulses) and pulses[end] == ".":
                    end += 1
                frame_count = end - index
                generated_notes.append(Note.rest(frame_count * unit))
                index = end
                continue

            source = next(source_notes)
            end = index + 1
            while end < len(pulses) and pulses[end] == ".":
                end += 1
            frame_count = end - index

            if not emit_ties or source.is_rest():
                generated_notes.append(
                    resize(source, frame_count * unit)
                )
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

        return Bar(generated_notes, tonality=self.tonality)

    def euclidean_rhythm(
            self,
            n: int,
            k: int,
            legato: bool = True,
            unit: Fraction = Fraction("1/16"),
            offset: int = 0,
            emit_ties: bool = False,
    ) -> "Bar":
        """Distribute ``k`` onsets as evenly as possible over ``n`` frames.

        Source events are selected cyclically at the generated onsets. Rhythm
        realization is delegated to :meth:`pulses_to_durations`, so merged
        legato durations, explicit tied events, metadata preservation, pattern
        rotation, and tonality behave identically in both methods.

        Parameters
        ----------
        n : int
            Positive number of frames in the generated rhythm.
        k : int
            Number of onsets. It must be between zero and ``n``, inclusive.
        legato : bool, default=True
            Merge each onset with its following continuation frames.
        unit : Fraction, default=Fraction(1, 16)
            Duration of one frame.
        offset : int, default=0
            Number of frames by which to rotate the generated pattern left.
        emit_ties : bool, default=False
            In legato mode, emit separate tied unit-length sounding events
            instead of one longer event for each onset span.

        Returns
        -------
        Bar
            A bar containing the Euclidean rhythm and this bar's tonality.

        Raises
        ------
        TypeError
            If ``n`` or ``k`` is not an integer.
        ValueError
            If ``n`` is not positive or ``k`` is outside ``0 <= k <= n``.
        """
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
            pulses = ''.join(
                "x" if left > right else "."
                for left, right in zip(remainders[:-1], remainders[1:])
            )
        return self.pulses_to_durations(
            pulses,
            legato=legato,
            unit=unit,
            offset=offset,
            emit_ties=emit_ties,
        )

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
