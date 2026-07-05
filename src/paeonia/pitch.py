from __future__ import annotations
from typing_extensions import override
from dataclasses import dataclass
import re

LETTERS = ("C", "D", "E", "F", "G", "A", "B")
NATURAL_PITCH_CLASSES = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}

_PITCH_CLASS_RE = re.compile(r"^([A-Ga-g])([#b]*)$")

@dataclass(frozen=True, slots=True)
class PitchClass:
    letter: str
    accidental: int = 0

    def __post_init__(self) -> None:
        letter = self.letter.upper()
        if letter not in NATURAL_PITCH_CLASSES:
            raise ValueError(f"Invalid pitch letter: {self.letter!r}")

    @property
    def midi_value(self) -> int:
        return (
            NATURAL_PITCH_CLASSES[self.letter]
            + self.accidental
        ) % 12

    @classmethod
    def parse(cls, value: str) -> "PitchClass":
        match = _PITCH_CLASS_RE.fullmatch(value.strip())
        if match is None:
            raise ValueError(f"Invalid pitch class: {value!r}")

        letter, symbols = match.groups()
        if "#" in symbols and "b" in symbols:
            raise ValueError("Mixed sharp and flat symbols are not allowed")

        accidental = symbols.count("#") - symbols.count("b")
        return cls(letter=letter, accidental=accidental)

    @override
    def __str__(self) -> str:
        if self.accidental > 0:
            suffix = "#" * self.accidental
        else:
            suffix = "b" * (-self.accidental)
        return self.letter + suffix

_PITCH_RE = re.compile(r"^([A-Ga-g])([#b]*)(-?\d+)$")

SHARP_SPELLINGS = (
    PitchClass("C", 0),
    PitchClass("C", 1),
    PitchClass("D", 0),
    PitchClass("D", 1),
    PitchClass("E", 0),
    PitchClass("F", 0),
    PitchClass("F", 1),
    PitchClass("G", 0),
    PitchClass("G", 1),
    PitchClass("A", 0),
    PitchClass("A", 1),
    PitchClass("B", 0),
)

FLAT_SPELLINGS = (
    PitchClass("C", 0),
    PitchClass("D", -1),
    PitchClass("D", 0),
    PitchClass("E", -1),
    PitchClass("E", 0),
    PitchClass("F", 0),
    PitchClass("G", -1),
    PitchClass("G", 0),
    PitchClass("A", -1),
    PitchClass("A", 0),
    PitchClass("B", -1),
    PitchClass("B", 0),
)

@dataclass(frozen=True, slots=True)
class Pitch:
    pitch_class: PitchClass
    octave: int

    @property
    def midi(self) -> int:
        value = 12 * (self.octave + 1) + self.pitch_class.midi_value
        if not 0 <= value <= 127:
            raise ValueError(
                f"Pitch {self} lies outside the MIDI range: {value}"
            )
        return value

    @property
    def letter(self) -> str:
        return self.pitch_class.letter

    @property
    def accidental(self) -> int:
        return self.pitch_class.accidental

    @classmethod
    def parse(cls, value: str) -> "Pitch":
        match = _PITCH_RE.fullmatch(value.strip())
        if match is None:
            raise ValueError(f"Invalid pitch: {value!r}")
        letter, accidental_text, octave_text = match.groups()
        pitch_class = PitchClass.parse(letter + accidental_text)
        return cls(pitch_class=pitch_class, octave=int(octave_text))

    @classmethod
    def from_midi(
            cls,
            midi: int,
            *,
            prefer: str = "sharps",
    ) -> "Pitch":
        if not 0 <= midi <= 127:
            raise ValueError(f"Invalid MIDI pitch: {midi}")
        if prefer not in {"sharps", "flats"}:
            raise ValueError("prefer must be 'sharps' or 'flats'")

        octave = midi // 12 - 1
        pitch_class_value = midi % 12
        spellings = (
            SHARP_SPELLINGS
            if prefer == "sharps"
            else FLAT_SPELLINGS
        )
        return cls(spellings[pitch_class_value], octave)
            
    def enharmonic_equals(self, other: "Pitch") -> bool:
        return self.midi == other.midi

    def transpose_semitones(
            self,
            semitones: int,
            *,
            prefer: str = "sharps",
    ) -> "Pitch":
        return Pitch.from_midi(self.midi + semitones, prefer=prefer)

    @override
    def __str__(self) -> str:
        return f"{self.pitch_class}{self.octave}"
