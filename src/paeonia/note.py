from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from fractions import Fraction

from .pitch import Pitch

from mido import Message, MetaMessage, MidiFile, MidiTrack
from paeonia.utils import download_sf2, message_list_to_midi_file, render_and_play_midi
import paeonia
from paeonia.parser import parse
import tempfile
import subprocess
import time
import os
import re
from string import Template
from IPython.display import display, Image
import importlib
from copy import copy
import random

_LILYPOND_LETTERS = {
    "C": "c",
    "D": "d",
    "E": "e",
    "F": "f",
    "G": "g",
    "A": "a",
    "B": "b",
}


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

    def merge_pitches(self, other: "Note") -> "Note":
        if self.duration != other.duration:
            raise ValueError("Cannot merge notes with different durations")
        return self.with_pitches(self.pitches + other.pitches)

    def sounds_like(self, other: "Note") -> bool:
        return (
            isinstance(other, Note)
            and self.midi_pitches == other.midi_pitches
            and self.duration == other.duration
        )
        
    def __lt__(self, other):
        if self.is_rest() or other.is_rest():
            return False
        for p1 in self.pitches:
            for p2 in other.pitches:
                if p1 >= p2:
                    return False
        return True

    def __gt__(self, other):
        if self.is_rest() or other.is_rest():
            return False
        for p1 in self.pitches:
            for p2 in other.pitches:
                if p1 <= p2:
                    return False
        return True

    def __mul__(self, other):
        from paeonia import Bar
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

    @staticmethod
    def _pitch_to_lilypond(pitch: Pitch) -> str:
        accidental = pitch.accidental
        if accidental > 0:
            accidental_text = "is" * accidental
        else:
            accidental_text = "es" * (-accidental)
        octave = pitch.octave - 3
        if octave > 0:
            octave_marks = "'" * octave
        else:
            octave_marks = "," * (-octave)
        return (
            _LILYPOND_LETTERS[pitch.letter]
            + accidental_text
            + octave_marks
        )

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
        duration = self._duration_to_paeonia(self.duration)
        if self.is_rest():
            return f"r{duration}"

        if self.is_chord:
            pitches = " ".join(
                self._pitch_to_lilypond(pitch) for pitch in self.pitches
            )
            return f"<{pitches}>{duration}"

        return f"{self._pitch_to_lilypond(self.pitches[0])}{duration}"

    def is_rest(self):
        """Is this note a rest.

        Returns
        -------
        bool
            True if rest, False otherwise.
        """
        return len(self.pitches) == 0

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

    def merge_pitches(self, other):
        """Merge the pitches of two notes (into a chord).

        Parameters
        ----------
        other: Note
            Another note to merge with.

        Returns
        -------
        Note
            A note with pitches merged.
        """
        new_note = copy(self)
        new_note.pitches += other.pitches
        new_note.pitches = list(sorted(new_note.pitches))
        return new_note  
      
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
