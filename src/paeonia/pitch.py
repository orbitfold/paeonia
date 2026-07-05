from dataclasses import dataclass
import re

NATURAL_PITCH_CLASSES = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}

PITCH_RE = re.compile(
    r"^\s*(?P<letter>[A-Ga-g])(?P<accidental>#{1,2}|b{1,2})?(?P<octave>-?\d+)\s*$"
)

@dataclass(frozen=True, slots=True)
class Pitch:
    letter: str
    accidental: int
    octave: int

    def __post_init__(self):
        letter = self.letter.upper()

        if letter not in NATURAL_PITCH_CLASSES:
            raise ValueError(f"Invalid pitch letter: {self.letter}")

        object.__setattr__(self, "letter", letter)

        if not -2 <= self.accidental <= 2:
            raise ValueError(
                "Only double-flat through double-sharp are supported."
            )

        if not 0 <= self.midi <= 127:
            raise ValueError(
                f"Pitch is outside the MIDI range: {self.midi}"
            )

    @property
    def midi(self) -> int:
        pitch_class = (
            NATURAL_PITCH_CLASSES[self.letter]
            + self.accidental
        ) % 12

        return 12 * (self.octave + 1) + pitch_class

    @property
    def pitch_class(self) -> int:
        return self.midi % 12

    @classmethod
    def parse(cls, value: str) -> "Pitch":
        match = PITCH_RE.match(value)
        if match is None:
            raise ValueError(f"Invalid pitch: {value!r}")

        accidental = match.group("accidental") or ""
        accidental_value = accidental.count("#") - accidental.count("b")

        return cls(
            letter=match.group("letter"),
            accidental=accidental_value,
            octave=int(match.group("octave")),
        )

    @classmethod
    def from_midi(
            cls,
            midi: int,
            *,
            prefer: str = "sharps",
    ) -> "Pitch":
        if not 0 <= midi <= 127:
            raise ValueError(f"Invalid MIDI pitch: {midi}")

        octave = midi // 12 - 1
        pitch_class = midi % 12

        sharp_spellings = (
            ("C", 0),
            ("C", 1),
            ("D", 0),
            ("D", 1),
            ("E", 0),
            ("F", 0),
            ("F", 1),
            ("G", 0),
            ("G", 1),
            ("A", 0),
            ("A", 1),
            ("B", 0),
        )

        flat_spellings = (
            ("C", 0),
            ("D", -1),
            ("D", 0),
            ("E", -1),
            ("E", 0),
            ("F", 0),
            ("G", -1),
            ("G", 0),
            ("A", -1),
            ("A", 0),
            ("B", -1),
            ("B", 0),
        )

        spellings = (
            flat_spellings
            if prefer == "flats"
            else sharp_spellings
        )

        letter, accidental = spellings[pitch_class]
        return cls(letter, accidental, octave)
