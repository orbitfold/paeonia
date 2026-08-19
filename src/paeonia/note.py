from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from fractions import Fraction

from .pitch import Pitch

from copy import copy
import random


_NOTATABLE_BASE_DURATIONS = (
    Fraction(8),
    Fraction(4),
    Fraction(2),
    *(Fraction(1, 2**power) for power in range(8)),
)

_NOTATABLE_DURATIONS = tuple(sorted({
    base * multiplier
    for base in _NOTATABLE_BASE_DURATIONS
    for multiplier in (Fraction(1), Fraction(3, 2), Fraction(7, 4))
}))


@dataclass(frozen=True, slots=True)
class Note:
    pitches: tuple[Pitch, ...] = ()
    duration: Fraction = Fraction(1, 4)
    velocity: float = 0.75
    tie_in: bool = False
    tie_out: bool = False

    def __post_init__(self) -> None:
        normalized_pitches = tuple(
            pitch
            if isinstance(pitch, Pitch)
            else Pitch.from_midi(int(pitch))
            for pitch in self.pitches
        )
        duration = Fraction(self.duration)

        if duration <= 0:
            raise ValueError("Note duration must be positive")
        if not 0.0 <= self.velocity <= 1.0:
            raise ValueError("Velocity must be between 0 and 1")

        object.__setattr__(self, "pitches", normalized_pitches)
        object.__setattr__(self, "duration", duration)

    def is_rest(self) -> bool:
        """Return whether this event has no sounding pitches."""
        return not self.pitches

    @property
    def is_chord(self) -> bool:
        return len(self.pitches) > 1

    @property
    def midi_pitches(self) -> tuple[int, ...]:
        return tuple(pitch.midi for pitch in self.pitches)

    @classmethod
    def rest(
            cls,
            duration: Fraction = Fraction(1, 4),
    ) -> "Note":
        return cls(pitches=(), duration=duration)

    @classmethod
    def from_midi(
            cls,
            pitches: int | Iterable[int],
            duration: Fraction = Fraction(1, 4),
            velocity: float = 0.75,
    ) -> "Note":
        if isinstance(pitches, int):
            pitches=(pitches,)
        return cls(
            pitches=tuple(Pitch.from_midi(value) for value in pitches),
            duration=duration,
            velocity=velocity,
        )

    @classmethod
    def parse(cls, notation:str) -> "Note":
        from .parser import parse
        notes = parse(notation)
        if len(notes) != 1:
            raise ValueError(
                "Note.parse() requires notation containing exactly one event"
            )
        return notes[0]

    def with_pitches(self, pitches: Iterable[Pitch]) -> "Note":
        return replace(self, pitches=tuple(pitches))

    def with_duration(self, duration: Fraction) -> "Note":
        return replace(self, duration=Fraction(duration))

    def stretch(
            self,
            factor: int | float | Fraction,
            *,
            quantize: bool = True,
    ) -> "Note":
        """Return a copy whose duration is multiplied by ``factor``.

        The factor is converted to an exact :class:`fractions.Fraction` before
        multiplication. Decimal float literals therefore retain their written
        value: for example, ``0.5`` is treated as ``Fraction(1, 2)``. Pitches,
        velocity, and tie metadata are unchanged. By default, the result is
        quantized to the nearest duration that the current LilyPond renderer
        can express as one token: a power-of-two value from a maxima through
        a 128th note, with zero, one, or two dots. Equidistant values choose
        the shorter duration, and values outside the supported range clamp to
        its nearest endpoint.

        Parameters
        ----------
        factor : int | float | Fraction
            Finite, strictly positive duration multiplier.
        quantize : bool, default=True
            Snap the result to the nearest directly notatable duration. When
            false, retain the exact multiplied duration even if notation
            rendering cannot express it as one token.

        Returns
        -------
        Note
            A new note with the stretched duration.

        Raises
        ------
        TypeError
            If ``factor`` is not an integer, float, or fraction, or if
            ``quantize`` is not Boolean.
        ValueError
            If ``factor`` is non-finite or not strictly positive.
        """
        if isinstance(factor, bool) or not isinstance(
                factor,
                (int, float, Fraction),
        ):
            raise TypeError("factor must be an integer, float, or Fraction")
        if not isinstance(quantize, bool):
            raise TypeError("quantize must be a boolean")

        try:
            normalized_factor = Fraction(
                str(factor) if isinstance(factor, float) else factor
            )
        except (OverflowError, ValueError) as exc:
            raise ValueError("factor must be finite") from exc
        if normalized_factor <= 0:
            raise ValueError("factor must be positive")

        duration = self.duration * normalized_factor
        if quantize:
            duration = min(
                _NOTATABLE_DURATIONS,
                key=lambda candidate: (
                    abs(candidate - duration),
                    candidate,
                ),
            )
        return self.with_duration(duration)

    def with_velocity(self, velocity: float) -> "Note":
        return replace(self, velocity=velocity)

    def with_ties(
            self,
            *,
            tie_in: bool | None = None,
            tie_out: bool | None = None,
    ) -> "Note":
        return replace(
            self,
            tie_in=self.tie_in if tie_in is None else tie_in,
            tie_out=self.tie_out if tie_out is None else tie_out,
        )

    def map_pitches(
            self,
            function: Callable[[Pitch], Pitch],
    ) -> "Note":
        if self.is_rest():
            return self
        return self.with_pitches(function(pitch) for pitch in self.pitches)

    def transpose_semitones(
            self,
            semitones: int,
            *,
            prefer: str = "sharps",
    ) -> "Note":
        return self.map_pitches(
            lambda pitch: pitch.transpose_semitones(
                semitones,
                prefer=prefer,
            )
        )

    def sounds_like(self, other: "Note") -> bool:
        return (
            isinstance(other, Note)
            and self.midi_pitches == other.midi_pitches
            and self.duration == other.duration
        )

    def pitch_order_key(self) -> tuple[int, tuple[int, ...]]:
        """Return a pitch-based sorting key, placing rests last."""
        if self.is_rest():
            return (1, ())
        return (0, tuple(sorted(self.midi_pitches)))

    def __mul__(self, other):
        from .bar import Bar

        b = Bar()
        for _ in range(other):
            b += self
        return b

    def __and__(self, other):
        return self.merge_pitches(other)

    def __str__(self):
        note, octave = self.to_paeonia()
        return note

    def __repr__(self):
        return f"Note(\"{str(self)}\")"

    @staticmethod
    def _duration_to_paeonia(duration: Fraction) -> str:
        duration = Fraction(duration)
        for denominator in range(1, 129):
            for dots in range(3):
                candidate = Fraction(1, denominator) * (
                    1 + Fraction(1, 2) * dots
                )
                if candidate == duration:
                    return f"{denominator}{'.' * dots}"
        raise ValueError(f"Unsupported duration: {duration}")

    @staticmethod
    def _pitch_to_paeonia(pitch: Pitch, previous_octave: int) -> tuple[str, int]:
        octave = pitch.octave - 4
        octave_delta = octave - previous_octave
        if octave_delta > 0:
            octave_marks = "'" * octave_delta
        else:
            octave_marks = "," * (-octave_delta)
        return f"{pitch.pitch_class}{octave_marks}", octave

    def _duration_suffix(self, previous_duration: Fraction) -> str:
        if self.duration == previous_duration:
            return ""
        return self._duration_to_paeonia(self.duration)

    def to_paeonia(
            self,
            previous_octave: int = 0,
            previous_duration: Fraction = Fraction(1, 4),
    ) -> tuple[str, int]:
        duration = self._duration_suffix(previous_duration)
        if self.is_rest():
            return f"R{duration}", previous_octave

        if self.is_chord:
            pitch_text = []
            octave = previous_octave
            for pitch in self.pitches:
                text, octave = self._pitch_to_paeonia(pitch, octave)
                pitch_text.append(text)
            return f"<{' '.join(pitch_text)}>{duration}", octave

        text, octave = self._pitch_to_paeonia(self.pitches[0], previous_octave)
        return f"{text}{duration}", octave

    def to_lilypond(self) -> str:
        """Delegate spelling-aware notation rendering to ``lilypond.py``."""
        from .lilypond import note_to_lilypond

        return note_to_lilypond(self)

    def map_tonality(self, tonality, method="random", rnd=None):
        """Map the pitches this note consists of to a tonality.

        Parameters
        ----------
        tonality: Tonality
            Tonality to map to.
        method: str
            What method to use when there are more than one candidate.
        rnd: Random
            A random number generator.

        Returns
        -------
        Note
            A tonality mapped note.
        """
        assert(method in ["up", "down", "random"])
        if rnd is None:
            rnd = random
        if self.is_rest():
            return self
        new_note = copy(self)
        new_pitches = []
        for pitch in self.pitches:
            closest = tonality.closest(pitch)
            if len(closest) == 1:
                new_pitches.append(closest[0])
            else:
                if method == "up":
                    new_pitches.append(max(closest))
                elif method == "down":
                    new_pitches.append(min(closest))
                else:
                    new_pitches.append(rnd.choice(closest))
        new_note.pitches = new_pitches
        return new_note

    def merge_pitches(self, other: "Note") -> "Note":
        """Merge the pitches of two notes (into a chord).

        Parameters
        ----------
        other: Note
            Another note to merge with.

        Returns
        -------
        Note
            A copy carrying this note's metadata and both pitch sequences.

        Raises
        ------
        ValueError
            If the notes have different durations.
        """
        if self.duration != other.duration:
            raise ValueError("Cannot merge notes with different durations")
        return self.with_pitches(self.pitches + other.pitches)
      
    def to_midi(self, offset=0, tpb=480):
        from .midi import note_to_midi_messages
        return note_to_midi_messages(self, offset=offset, tpb=tpb)

    def show(self):
        from .playback import show_note
        show_note(self)
        return self


    def play(self, tpb=480, autoplay=False):
        from .playback import play_note
        play_note(self, tpb=tpb, autoplay=autoplay)
        return self
