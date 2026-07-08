from __future__ import annotations
from collections.abc import Sequence, Mapping
from dataclasses import dataclass, replace
import warnings

from itertools import cycle
import paeonia
from paeonia.utils import note_name_to_pitch_class, mode_name_to_index
from .pitch import (
    NATURAL_PITCH_CLASSES,
    Pitch,
    PitchClass,
    LETTERS,
    signed_pitch_class_difference,
)

MODES: dict[str, tuple[int, ...]] = {
    "chromatic": (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
    "major": (0, 2, 4, 5, 7, 9, 11),
    "ionian": (0, 2, 4, 5, 7, 9, 11),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "aeolian": (0, 2, 3, 5, 7, 8, 10),
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "minor-harmonic": (0, 2, 3, 5, 7, 8, 11),
    "minor-melodic": (0, 2, 3, 5, 7, 9, 11),
    "locrian": (0, 1, 3, 5, 6, 8, 10),
}


def octave_for_spelled_pitch(pitch_class: PitchClass, midi: int) -> int:
    """Return the octave that makes a spelled pitch produce the MIDI value."""
    midi = int(midi)
    if not 0 <= midi <= 127:
        raise ValueError(f"MIDI pitch is out of range: {midi}")
    if midi % 12 != pitch_class.midi_value:
        raise ValueError(
            f"Pitch class {pitch_class} cannot spell MIDI pitch {midi}"
        )
    return (midi - pitch_class.midi_value) // 12 - 1


@dataclass(frozen=True, slots=True)
class ScalePosition:
    degree: int
    tonal_octave: int
    alteration: int = 0

    def __post_init__(self) -> None:
        if self.degree < 0:
            raise ValueError("degree mus be non-negative")

@dataclass(frozen=True, slots=True)
class Tonality:
    tonic: PitchClass
    mode_name: str
    intervals: tuple[int, ...]
    
    def __init__(
            self,
            root: str | PitchClass = "C",
            scale: str = "ionian",
            *,
            intervals: Sequence[int] | None = None,
    ) -> None:
        tonic = (
            root
            if isinstance(root, PitchClass)
            else  PitchClass.parse(root)
        )
        if intervals is None:
            try:
                normalized = MODES[scale]
            except KeyError as exc:
                raise ValueError(f"Unknown mode: {scale!r}") from exc
        else:
            normalized = tuple(int(value) for value in intervals)
            scale = "custom" if scale == "ionian" else scale
        self._validate_intervals(normalized)
        object.__setattr__(self, "tonic", tonic)
        object.__setattr__(self, "mode_name", scale)
        object.__setattr__(self, "intervals", tuple(normalized))

    @staticmethod
    def _validate_intervals(intervals: Sequence[int]) -> None:
        if not intervals or intervals[0] != 0:
            raise ValueError("A scale mut begin with tonic interval 0")
        if tuple(sorted(set(intervals))) != tuple(intervals):
            raise ValueError("Scale intervals must be unique and increasing")
        if any(interval < 0 or interval > 11 for interval in intervals):
            raise ValueError("Scale intervals must lie between 0 and 11")

    @property
    def degree_count(self) -> int:
        return len(self.intervals)

    @property
    def pitch_class(self) -> tuple[int, ...]:
        return tuple(
            (self.tonic.midi_value + interval) % 12
            for interval in self.intervals
        )

    @property
    def root(self) -> str:
        return str(self.tonic)

    @property
    def scale_name(self) -> str:
        return self.mode_name

    @property
    def scale(self) -> tuple[int, ...]:
        return self.intervals

    def degree_for_letter(self, letter: str) -> int:
        if self.degree_count != 7:
            raise ValueError(
                "Letter-based deggree analysis requires a seven-note tonality"
            )
        tonic_index = LETTERS.index(self.tonic.letter)
        pitch_index = LETTERS.index(letter.upper())
        return (pitch_index - tonic_index) % 7

    def expected_pitch_class_for_degree(self, degree: int) -> PitchClass:
        if self.degree_count != 7:
            raise ValueError(
                "Theoretical spelling requires a seven-note tonality"
            )
        tonic_index = LETTERS.index(self.tonic.letter)
        letter = LETTERS[(tonic_index + degree) % 7]
        target_midi_class = (
            self.tonic.midi_value
            + self.intervals[degree]
        ) % 12
        natural = NATURAL_PITCH_CLASSES[letter]
        accidental = signed_pitch_class_difference(
            target_midi_class,
            natural,
        )
        return PitchClass(letter, accidental)

    def analyze_pitch(
            self,
            pitch: Pitch,
            *,
            chromatic: str = "preserve_alteration",
    ) -> ScalePosition:
        """Analyze a pitch as a scale position.

        ``preserve_alteration`` is fully theory-aware only for seven-degree
        tonalities, where each degree has an expected letter spelling. For
        chromatic and custom scales, analysis is pitch-class based.
        """
        if chromatic not in {
                "preserve_alteration",
                "error",
                "nearest",
        }:
            raise ValueError(f"Unknown chromatic policy: {chromatic}")
        if self.degree_count == 7:
            degree = self.degree_for_letter(pitch.letter)
            expected = self.expected_pitch_class_for_degree(degree)
            alteration = pitch.accidental - expected.accidental

            if chromatic == "error" and alteration != 0:
                raise ValueError(
                    f"Pitch {pitch} is not diatonic in {self}"
                )

            if chromatic == "nearest" and alteration != 0:
                return self.analyze_pitch(
                    self.quantize_pitch(pitch),
                    chromatic="error",
                )

            unaltered_midi = pitch.midi - alteration
            tonal_octave = (
                unaltered_midi
                - self.tonic.midi_value
                - self.intervals[degree]
            ) // 12

            return ScalePosition(
                degree=degree,
                tonal_octave=tonal_octave,
                alteration=alteration,
            )
        return self._analyze_non_heptatonic_pitch(
            pitch,
            chromatic=chromatic,
        )

    def _nearest_degree_for_pitch_class(self, pitch_class: int) -> int:
        best_degree = 0
        best_distance = 12
        for degree, scale_pitch_class in enumerate(self.pitch_class):
            distance = abs(
                signed_pitch_class_difference(
                    pitch_class,
                    scale_pitch_class,
                )
            )
            if distance < best_distance:
                best_degree = degree
                best_distance = distance
        return best_degree

    def _scale_position_for_degree(
            self,
            pitch: Pitch,
            degree: int,
    ) -> ScalePosition:
        tonal_octave = (
            pitch.midi
            - self.tonic.midi_value
            - self.intervals[degree]
        ) // 12
        return ScalePosition(
            degree=degree,
            tonal_octave=tonal_octave,
            alteration=0,
        )

    def _analyze_non_heptatonic_pitch(
            self,
            pitch: Pitch,
            *,
            chromatic: str,
    ) -> ScalePosition:
        pitch_class = pitch.midi % 12
        try:
            degree = self.pitch_class.index(pitch_class)
        except ValueError:
            if chromatic == "error":
                raise ValueError(
                    f"Pitch {pitch} is not in {self}"
                ) from None
            degree = self._nearest_degree_for_pitch_class(pitch_class)

        return self._scale_position_for_degree(pitch, degree)

    def realize_pitch(self, position: ScalePosition) -> Pitch:
        if not 0 <= position.degree < self.degree_count:
            raise ValueError(
                f"Degree {position.degree} is outside this tonality"
            )
        midi = (
            self.tonic.midi_value
            + self.intervals[position.degree]
            + 12 * position.tonal_octave
            + position.alteration
        )
        if not 0 <= midi <= 127:
            raise ValueError(f"Realized MIDI pitch is out of range: {midi}")

        if self.degree_count == 7:
            expected = self.expected_pitch_class_for_degree(position.degree)
            pitch_class = PitchClass(
                expected.letter,
                expected.accidental + position.alteration,
            )
            octave = octave_for_spelled_pitch(pitch_class, midi)
            return Pitch(pitch_class=pitch_class, octave=octave)

        return Pitch.from_midi(midi)

    def shift_position(
            self,
            position: ScalePosition,
            degrees: int,
    ) -> ScalePosition:
        absolute_degree = position.degree + degrees
        octave_delta, normalized_degree = divmod(
            absolute_degree,
            self.degree_count,
        )
        return ScalePosition(
            degree=normalized_degree,
            tonal_octave=position.tonal_octave + octave_delta,
            alteration=position.alteration,
        )

    def transpose_pitch(
            self,
            pitch: Pitch,
            degrees: int,
            *,
            chromatic: str = "preserve_alteration",
    ) -> Pitch:
        position = self.analyze_pitch(pitch, chromatic=chromatic)
        shifted = self.shift_position(position, degrees)
        return self.realize_pitch(shifted)

    def pitches_in_range(self, low: int, high: int) -> tuple[Pitch, ...]:
        low = max(0, int(low))
        high = min(127, int(high))
        if low > high:
            return ()
        pitch_classes = set(self.pitch_class)
        return tuple(
            Pitch.from_midi(midi)
            for midi in range(low, high + 1)
            if midi % 12 in pitch_classes
        )

    def quantize_pitch(
            self,
            pitch: Pitch,
            *,
            direction: str = "nearest",
            tie_break: str = "lower",
    ) -> Pitch:
        if direction not in {"nearest", "up", "down"}:
            raise ValueError(f"Unknown quantize direction: {direction}")
        if tie_break not in {"lower", "upper"}:
            raise ValueError(f"Unknown quantize tie_break: {tie_break}")

        sounding_midi = pitch.midi
        candidates = self.pitches_in_range(
            max(0, sounding_midi - 12),
            min(127, sounding_midi + 12),
        )
        if not candidates:
            raise ValueError("No quantization candidates in MIDI range")

        if direction == "up":
            upper = [
                candidate
                for candidate in candidates
                if candidate.midi >= sounding_midi
            ]
            if not upper:
                raise ValueError(f"No pitch in {self} at or above {pitch}")
            return min(upper, key=lambda candidate: candidate.midi)

        if direction == "down":
            lower = [
                candidate
                for candidate in candidates
                if candidate.midi <= sounding_midi
            ]
            if not lower:
                raise ValueError(f"No pitch in {self} at or below {pitch}")
            return max(lower, key=lambda candidate: candidate.midi)

        distance = min(
            abs(candidate.midi - sounding_midi)
            for candidate in candidates
        )
        nearest = [
            candidate
            for candidate in candidates
            if abs(candidate.midi - sounding_midi) == distance
        ]
        if tie_break == "upper":
            return max(nearest, key=lambda candidate: candidate.midi)
        return min(nearest, key=lambda candidate: candidate.midi)

    def _coerce_pitch(self, pitch: Pitch | int) -> Pitch:
        return pitch if isinstance(pitch, Pitch) else Pitch.from_midi(int(pitch))

    def _warn_legacy_pitch_api(self, name: str) -> None:
        warnings.warn(
            (
                f"Tonality.{name}() is deprecated; use analyze_pitch(), "
                "realize_pitch(), or quantize_pitch() instead."
            ),
            DeprecationWarning,
            stacklevel=3,
        )
        
    def closest(self, pitch: Pitch | int) -> list[Pitch]:
        """Deprecated wrapper around MIDI-distance quantization."""
        self._warn_legacy_pitch_api("closest")
        pitch = self._coerce_pitch(pitch)
        quantized = self.quantize_pitch(pitch)
        distance = abs(quantized.midi - pitch.midi)
        return [
            candidate
            for candidate in self.pitches_in_range(
                max(0, pitch.midi - distance),
                min(127, pitch.midi + distance),
            )
            if abs(candidate.midi - pitch.midi) == distance
        ]

    def get_pitches(self, indices: Sequence[int]) -> list[Pitch]:
        """Deprecated wrapper around realize_pitch()."""
        self._warn_legacy_pitch_api("get_pitches")
        positions = (
            ScalePosition(
                degree=degree,
                tonal_octave=tonal_octave,
            )
            for tonal_octave, degree in (
                divmod(int(index), self.degree_count)
                for index in indices
            )
        )
        return [self.realize_pitch(position) for position in positions]

    def get_indices(self, pitches: Sequence[Pitch | int]) -> list[int]:
        """Deprecated wrapper around analyze_pitch()."""
        self._warn_legacy_pitch_api("get_indices")
        indices = []
        for pitch in pitches:
            position = self.analyze_pitch(
                self._coerce_pitch(pitch),
                chromatic="error",
            )
            indices.append(
                position.tonal_octave * self.degree_count
                + position.degree
            )
        return indices

    def __contains__(self, other: object) -> bool:
        """Return whether a pitch, MIDI pitch, note, or pitch group belongs."""
        if isinstance(other, paeonia.Note):
            return all(pitch in self for pitch in other.pitches)

        if isinstance(other, Pitch):
            try:
                self.analyze_pitch(other, chromatic="error")
            except ValueError:
                return False
            return True

        if isinstance(other, int):
            return other % 12 in self.pitch_class

        try:
            return all(pitch in self for pitch in other)
        except TypeError:
            return False


@dataclass(frozen=True, slots=True)
class TonalityPlan:
    changes: tuple[tuple[int, Tonality], ...] = ()

    def __post_init__(self) -> None:
        normalized = tuple(sorted(self.changes, key=lambda item: item[0]))
        indices = [index for index, _ in normalized]
        if any(index < 0 for index in indices):
            raise ValueError("Tonality change indices must be non-negative")
        if len(indices) != len(set(indices)):
            raise ValueError("A plan may contain only one change per index")
        object.__setattr__(self, "changes", normalized)

    @classmethod
    def from_mapping(
            cls,
            mapping: Mapping[int, Tonality] | None,
    ) -> "TonalityPlan":
        if mapping is None:
            return cls()
        return cls(tuple(mapping.items()))

    def at(
            self,
            index: int,
            *,
            fallback: Tonality | None = None,
    ) -> Tonality | None:
        result = fallback
        for change_index, tonality in self.changes:
            if change_index > index:
                break
            result = tonality
        return result

    def with_change(
            self,
            index: int,
            tonality: Tonality,
    ) -> "TonalityPlan":
        mapping = dict(self.changes)
        mapping[index] = tonality
        return TonalityPlan.from_mapping(mapping)
