"""Time-aware vertical, harmonic, registral, and voice-leading analysis.

The functions in this module inspect model objects without modifying them.
Durations and offsets remain exact :class:`fractions.Fraction` values, and
written pitch classes are kept alongside their MIDI pitch classes so that
enharmonic spellings are never silently collapsed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from typing import Literal, Protocol

from .note import Note
from .pitch import Pitch, PitchClass
from .staff import Staff
from .tonality import ScalePosition, Tonality


class _ScoreLike(Protocol):
    """Structural score interface used to avoid a model import cycle."""

    staves: dict[str, Staff]

    def validate_alignment(self) -> None: ...

    def tonality_at(
            self,
            staff_name: str,
            bar_index: int,
    ) -> Tonality | None: ...


__all__ = [
    "BassMotion",
    "ChordCandidate",
    "DensityPoint",
    "Doubling",
    "DoublingSnapshot",
    "HarmonicChange",
    "HarmonicContext",
    "IntervalRelation",
    "IntervalSnapshot",
    "NonChordTone",
    "ParallelMotion",
    "PitchClassSet",
    "RegisterAnalysis",
    "RegisterOverlap",
    "RegisterSnapshot",
    "ScaleDegree",
    "ScaleDegreeSnapshot",
    "StaffPitches",
    "StaffRange",
    "Verticality",
    "VoiceLeadingAnalysis",
    "VoiceMotion",
    "WeightedChord",
    "interval_class_vector",
    "prime_form",
]


_DISSONANT_INTERVAL_CLASSES = frozenset({1, 2, 6})
_ROMAN_NUMERALS = ("I", "II", "III", "IV", "V", "VI", "VII")


@dataclass(frozen=True, slots=True)
class StaffPitches:
    """Pitches sounding on one staff during a vertical time frame."""

    staff: str
    pitches: tuple[Pitch, ...]


@dataclass(frozen=True, slots=True)
class PitchClassSet:
    """Both written and sounding representations of a pitch-class set."""

    written: frozenset[PitchClass]
    midi: frozenset[int]


@dataclass(frozen=True, slots=True)
class ScaleDegree:
    """A staff-owned pitch analyzed within a tonality."""

    staff: str
    pitch: Pitch
    position: ScalePosition

    @property
    def number(self) -> int:
        """Return the conventional one-based scale-degree number."""
        return self.position.degree + 1


@dataclass(frozen=True, slots=True)
class ScaleDegreeSnapshot:
    """Scale-degree analyses for one vertical time frame."""

    offset: Fraction
    duration: Fraction
    degrees: tuple[ScaleDegree, ...]


@dataclass(frozen=True, slots=True)
class IntervalRelation:
    """The sounding interval between pitches owned by two staves."""

    first_staff: str
    second_staff: str
    first_pitch: Pitch
    second_pitch: Pitch
    semitones: int
    interval_class: int
    dissonant: bool


@dataclass(frozen=True, slots=True)
class IntervalSnapshot:
    """Cross-staff intervals for one vertical time frame."""

    offset: Fraction
    duration: Fraction
    intervals: tuple[IntervalRelation, ...]


@dataclass(frozen=True, slots=True)
class Doubling:
    """A MIDI pitch class occurring more than once in a verticality."""

    midi_pitch_class: int
    count: int
    spellings: frozenset[PitchClass]
    staves: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DoublingSnapshot:
    """Pitch-class doublings for one vertical time frame."""

    offset: Fraction
    duration: Fraction
    doublings: tuple[Doubling, ...]


@dataclass(frozen=True, slots=True)
class StaffRange:
    """The lowest and highest pitches sounding on a staff."""

    staff: str
    lowest: Pitch
    highest: Pitch


@dataclass(frozen=True, slots=True)
class RegisterSnapshot:
    """Register, spacing, and voice-crossing data at one offset."""

    offset: Fraction
    duration: Fraction
    bass: Pitch | None
    soprano: Pitch | None
    ambitus: int | None
    spacing: tuple[int, ...]
    staff_ranges: tuple[StaffRange, ...]
    crossings: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class RegisterOverlap:
    """Adjacent ordered staves overlapping across two time frames."""

    offset: Fraction
    upper_staff: str
    lower_staff: str


@dataclass(frozen=True, slots=True)
class RegisterAnalysis:
    """Register snapshots and cross-frame overlaps for one bar."""

    snapshots: tuple[RegisterSnapshot, ...]
    overlaps: tuple[RegisterOverlap, ...]


@dataclass(frozen=True, slots=True)
class DensityPoint:
    """The number of sounding pitches and active staves in a time frame."""

    offset: Fraction
    duration: Fraction
    pitch_count: int
    active_staff_count: int


@dataclass(frozen=True, slots=True)
class BassMotion:
    """A change from one sounding bass pitch to the next."""

    from_offset: Fraction
    to_offset: Fraction
    from_pitch: Pitch
    to_pitch: Pitch
    semitones: int


@dataclass(frozen=True, slots=True)
class ChordCandidate:
    """A possible tertian or suspended interpretation of a sonority."""

    root: PitchClass
    quality: str
    symbol: str
    intervals: frozenset[int]
    inversion: int | None
    confidence: float
    matched_pitch_classes: frozenset[int]
    missing_pitch_classes: frozenset[int]
    extra_pitch_classes: frozenset[int]
    roman_numeral: str | None = None


@dataclass(frozen=True, slots=True)
class WeightedChord:
    """A chord candidate weighted by its duration within a bar."""

    candidate: ChordCandidate
    duration: Fraction
    coverage: Fraction


@dataclass(frozen=True, slots=True)
class HarmonicChange:
    """A contiguous span assigned the same primary chord interpretation."""

    offset: Fraction
    duration: Fraction
    candidate: ChordCandidate | None

    @property
    def roman_numeral(self) -> str | None:
        """Return this assignment's functional label, when available."""
        return (
            None
            if self.candidate is None
            else self.candidate.roman_numeral
        )

    @property
    def symbol(self) -> str | None:
        """Return this assignment's chord symbol, when available."""
        return None if self.candidate is None else self.candidate.symbol


@dataclass(frozen=True, slots=True)
class NonChordTone:
    """A pitch outside a local chord interpretation."""

    offset: Fraction
    staff: str
    pitch: Pitch
    kind: Literal["passing", "neighbor", "unclassified"]


@dataclass(frozen=True, slots=True)
class HarmonicContext:
    """Duration-weighted harmonic interpretation of one score bar."""

    bar_index: int
    tonality: Tonality
    verticalities: tuple[Verticality, ...]
    primary: ChordCandidate | None
    primary_coverage: Fraction
    weighted_candidates: tuple[WeightedChord, ...]
    changes: tuple[HarmonicChange, ...]
    non_chord_tones: tuple[NonChordTone, ...]


@dataclass(frozen=True, slots=True)
class VoiceMotion:
    """One pitch moving between two analyzed sonorities."""

    staff: str
    from_pitch: Pitch
    to_pitch: Pitch
    semitones: int


@dataclass(frozen=True, slots=True)
class ParallelMotion:
    """Parallel perfect fifth or octave between two staff-owned motions."""

    first_staff: str
    second_staff: str
    interval_class: int


@dataclass(frozen=True, slots=True)
class VoiceLeadingAnalysis:
    """Motion from the final sonority of one bar to the first of another."""

    from_bar: int
    to_bar: int
    motions: tuple[VoiceMotion, ...]
    common_tones: tuple[int, ...]
    total_motion: int
    contrary_pairs: tuple[tuple[str, str], ...]
    parallel_perfects: tuple[ParallelMotion, ...]
    leaps: tuple[VoiceMotion, ...]


@dataclass(frozen=True, slots=True)
class Verticality:
    """All pitches sounding over one exact, half-open time interval.

    ``offset`` and ``duration`` are measured in whole-note units relative to
    the beginning of ``bar_index``. ``staff_pitches`` follows score insertion
    order and includes silent staves with an empty pitch tuple.
    """

    bar_index: int
    offset: Fraction
    duration: Fraction
    staff_pitches: tuple[StaffPitches, ...]

    @property
    def by_staff(self) -> dict[str, tuple[Pitch, ...]]:
        """Return pitches keyed by staff name in score order."""
        return {
            item.staff: item.pitches
            for item in self.staff_pitches
        }

    @property
    def pitches(self) -> tuple[Pitch, ...]:
        """Return all pitches in staff and chord order."""
        return tuple(
            pitch
            for item in self.staff_pitches
            for pitch in item.pitches
        )

    @property
    def bass(self) -> Pitch | None:
        """Return the lowest sounding pitch, or ``None`` during silence."""
        return min(self.pitches, key=lambda pitch: pitch.midi, default=None)

    @property
    def soprano(self) -> Pitch | None:
        """Return the highest sounding pitch, or ``None`` during silence."""
        return max(self.pitches, key=lambda pitch: pitch.midi, default=None)

    @property
    def pitch_classes(self) -> PitchClassSet:
        """Return written and MIDI pitch-class sets for this frame."""
        return PitchClassSet(
            written=frozenset(pitch.pitch_class for pitch in self.pitches),
            midi=frozenset(pitch.midi % 12 for pitch in self.pitches),
        )

    @property
    def interval_class_vector(self) -> tuple[int, int, int, int, int, int]:
        """Return the six-entry interval-class vector of the MIDI set."""
        return interval_class_vector(self.pitch_classes.midi)

    @property
    def prime_form(self) -> tuple[int, ...]:
        """Return a transposition/inversion-normalized pitch-class form."""
        return prime_form(self.pitch_classes.midi)

    def scale_degrees(self, tonality: Tonality) -> tuple[ScaleDegree, ...]:
        """Analyze every sounding pitch while preserving staff ownership."""
        if not isinstance(tonality, Tonality):
            raise TypeError("tonality must be a Tonality")
        return tuple(
            ScaleDegree(
                staff=item.staff,
                pitch=pitch,
                position=tonality.analyze_pitch(pitch),
            )
            for item in self.staff_pitches
            for pitch in item.pitches
        )

    def interval_matrix(
            self,
            *,
            dissonant_classes: Collection[int] = _DISSONANT_INTERVAL_CLASSES,
    ) -> tuple[IntervalRelation, ...]:
        """Return every cross-staff pitch interval in this frame."""
        classes = _normalize_interval_classes(dissonant_classes)
        relations: list[IntervalRelation] = []
        for first, second in combinations(self.staff_pitches, 2):
            for first_pitch in first.pitches:
                for second_pitch in second.pitches:
                    semitones = second_pitch.midi - first_pitch.midi
                    simple = abs(semitones) % 12
                    interval_class = min(simple, 12 - simple)
                    relations.append(IntervalRelation(
                        first_staff=first.staff,
                        second_staff=second.staff,
                        first_pitch=first_pitch,
                        second_pitch=second_pitch,
                        semitones=semitones,
                        interval_class=interval_class,
                        dissonant=(
                            simple in classes or interval_class in classes
                        ),
                    ))
        return tuple(relations)

    def dissonances(
            self,
            *,
            dissonant_classes: Collection[int] = _DISSONANT_INTERVAL_CLASSES,
    ) -> tuple[IntervalRelation, ...]:
        """Return relations classified as dissonant by MIDI interval class."""
        return tuple(
            relation
            for relation in self.interval_matrix(
                dissonant_classes=dissonant_classes,
            )
            if relation.dissonant
        )

    def doublings(self) -> tuple[Doubling, ...]:
        """Return MIDI pitch classes represented by multiple pitches."""
        occurrences: dict[int, list[tuple[str, Pitch]]] = {}
        for item in self.staff_pitches:
            for pitch in item.pitches:
                occurrences.setdefault(pitch.midi % 12, []).append(
                    (item.staff, pitch)
                )
        return tuple(
            Doubling(
                midi_pitch_class=midi_class,
                count=len(values),
                spellings=frozenset(
                    pitch.pitch_class for _, pitch in values
                ),
                staves=tuple(staff for staff, _ in values),
            )
            for midi_class, values in sorted(occurrences.items())
            if len(values) > 1
        )

    def chord_candidates(
            self,
            *,
            tonality: Tonality | None = None,
            limit: int = 5,
    ) -> tuple[ChordCandidate, ...]:
        """Rank common chord templates against the sounding MIDI set."""
        return chord_candidates(self, tonality=tonality, limit=limit)


_CHORD_TEMPLATES: tuple[tuple[str, str, frozenset[int]], ...] = (
    ("major", "", frozenset({0, 4, 7})),
    ("minor", "m", frozenset({0, 3, 7})),
    ("diminished", "dim", frozenset({0, 3, 6})),
    ("augmented", "+", frozenset({0, 4, 8})),
    ("suspended second", "sus2", frozenset({0, 2, 7})),
    ("suspended fourth", "sus4", frozenset({0, 5, 7})),
    ("dominant seventh", "7", frozenset({0, 4, 7, 10})),
    ("major seventh", "maj7", frozenset({0, 4, 7, 11})),
    ("minor seventh", "m7", frozenset({0, 3, 7, 10})),
    ("half-diminished seventh", "m7b5", frozenset({0, 3, 6, 10})),
    ("diminished seventh", "dim7", frozenset({0, 3, 6, 9})),
    ("minor-major seventh", "mMaj7", frozenset({0, 3, 7, 11})),
    ("major sixth", "6", frozenset({0, 4, 7, 9})),
    ("minor sixth", "m6", frozenset({0, 3, 7, 9})),
)


def _normalize_interval_classes(values: Collection[int]) -> frozenset[int]:
    classes = frozenset(values)
    if any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value <= 11
            for value in classes
    ):
        raise ValueError("interval classes must be integers from 0 through 11")
    return classes


def interval_class_vector(
        pitch_classes: Iterable[int],
) -> tuple[int, int, int, int, int, int]:
    """Return the standard interval-class vector for unique MIDI classes."""
    classes = sorted({int(value) % 12 for value in pitch_classes})
    counts = [0] * 6
    for first, second in combinations(classes, 2):
        distance = (second - first) % 12
        interval_class = min(distance, 12 - distance)
        if interval_class:
            counts[interval_class - 1] += 1
    return (
        counts[0],
        counts[1],
        counts[2],
        counts[3],
        counts[4],
        counts[5],
    )


def prime_form(pitch_classes: Iterable[int]) -> tuple[int, ...]:
    """Return a canonical form under transposition and inversion.

    The most compact rotation of the set and its inversion are transposed to
    zero; the more tightly left-packed of those two forms is returned.
    """
    classes = frozenset(int(value) % 12 for value in pitch_classes)
    if not classes:
        return ()
    def normal_form(values: Collection[int]) -> tuple[int, ...]:
        ordered = sorted(values)
        rotations = []
        for index in range(len(ordered)):
            rotation = (
                ordered[index:]
                + [value + 12 for value in ordered[:index]]
            )
            rotations.append(tuple(
                value - rotation[0] for value in rotation
            ))
        return min(
            rotations,
            key=lambda rotation: (rotation[-1], rotation[1:]),
        )

    original = normal_form(classes)
    inverted = normal_form({(-value) % 12 for value in classes})
    return min(original, inverted)


def _selected_staff_names(
        score: _ScoreLike,
        staves: Collection[str] | None,
) -> tuple[str, ...]:
    if staves is None:
        selected = tuple(score.staves)
    elif isinstance(staves, str):
        selected = (staves,)
    else:
        requested = set(staves)
        if not all(isinstance(name, str) for name in requested):
            raise TypeError("staff names must be strings")
        selected = tuple(name for name in score.staves if name in requested)
        unknown = requested - set(score.staves)
        if unknown:
            raise KeyError(f"Unknown staves: {sorted(unknown)}")
    if not selected:
        raise ValueError("analysis requires at least one staff")
    return selected


def _validate_bar_index(
        score: _ScoreLike,
        staff_names: Sequence[str],
        bar_index: int,
) -> None:
    if isinstance(bar_index, bool) or not isinstance(bar_index, int):
        raise TypeError("bar_index must be an integer")
    if bar_index < 0:
        raise IndexError(f"bar index out of range: {bar_index}")
    for name in staff_names:
        if bar_index >= len(score.staves[name].voice):
            raise IndexError(
                f"Staff {name!r} has no bar at index {bar_index}"
            )


def _tie_signature(note: Note) -> tuple[int, ...]:
    return tuple(sorted(pitch.midi for pitch in note.pitches))


def _validate_ties(
        score: _ScoreLike,
        staff_names: Sequence[str],
) -> None:
    """Validate ties because analysis treats tied segments as one sustain."""
    for staff_name in staff_names:
        events: tuple[Note, ...] = tuple(
            note
            for bar in score.staves[staff_name].voice.bars
            for note in bar.notes
        )
        for index, note in enumerate(events):
            if note.is_rest() and (note.tie_in or note.tie_out):
                raise ValueError(
                    f"Rest at event {index} in staff {staff_name!r} "
                    "cannot participate in a tie"
                )
            if note.tie_in:
                if index == 0 or not events[index - 1].tie_out:
                    raise ValueError(
                        f"Event {index} in staff {staff_name!r} has "
                        "tie_in without a preceding tie_out"
                    )
                if _tie_signature(events[index - 1]) != _tie_signature(note):
                    raise ValueError(
                        f"Tie ending at event {index} in staff "
                        f"{staff_name!r} has incompatible pitches"
                    )
            if note.tie_out:
                if index + 1 >= len(events) or not events[index + 1].tie_in:
                    raise ValueError(
                        f"tie_out at event {index} in staff "
                        f"{staff_name!r} is not followed by tie_in"
                    )
                if _tie_signature(note) != _tie_signature(events[index + 1]):
                    raise ValueError(
                        f"Tie starting at event {index} in staff "
                        f"{staff_name!r} has incompatible pitches"
                    )


def _bar_events(
        score: _ScoreLike,
        staff_name: str,
        bar_index: int,
) -> tuple[tuple[Fraction, Fraction, Note], ...]:
    result: list[tuple[Fraction, Fraction, Note]] = []
    offset = Fraction(0)
    notes = score.staves[staff_name].voice[bar_index].notes
    index = 0
    while index < len(notes):
        note = notes[index]
        end = offset + note.duration
        current = note
        while current.tie_out and index + 1 < len(notes):
            following = notes[index + 1]
            if not following.tie_in:
                break  # Descriptive validation happens before extraction.
            end += following.duration
            current = following
            index += 1
        result.append((offset, end, note))
        offset = end
        index += 1
    return tuple(result)


def verticalities(
        score: _ScoreLike,
        bar_index: int,
        *,
        staves: Collection[str] | None = None,
) -> tuple[Verticality, ...]:
    """Partition an aligned score bar into exact vertical time frames.

    Every note onset and ending contributes a boundary. Notes that began
    earlier remain present until their ending, and rests contribute time but
    no pitch. Valid tie chains are coalesced so their notation boundary is not
    mistaken for a new onset; ordinary rearticulations remain separate frames
    even when they repeat the same pitch.
    """
    staff_names = _selected_staff_names(score, staves)
    _validate_bar_index(score, staff_names, bar_index)
    score.validate_alignment()
    _validate_ties(score, staff_names)

    events_by_staff = {
        name: _bar_events(score, name, bar_index)
        for name in staff_names
    }
    boundaries = {Fraction(0)}
    for events in events_by_staff.values():
        for start, end, _ in events:
            boundaries.update((start, end))
    ordered_boundaries = sorted(boundaries)

    frames: list[Verticality] = []
    for start, end in zip(ordered_boundaries, ordered_boundaries[1:]):
        if end <= start:
            continue
        owned: list[StaffPitches] = []
        for name in staff_names:
            sounding = ()
            for event_start, event_end, note in events_by_staff[name]:
                if event_start <= start < event_end:
                    sounding = () if note.is_rest() else note.pitches
                    break
            owned.append(StaffPitches(name, sounding))
        staff_pitches = tuple(owned)
        frames.append(Verticality(
            bar_index=bar_index,
            offset=start,
            duration=end - start,
            staff_pitches=staff_pitches,
        ))
    return tuple(frames)


def sonority_at(
        score: _ScoreLike,
        bar_index: int,
        offset: int | Fraction,
        *,
        staves: Collection[str] | None = None,
) -> Verticality:
    """Return the verticality containing an exact bar-relative offset."""
    if isinstance(offset, bool) or not isinstance(offset, (int, Fraction)):
        raise TypeError("offset must be an integer or Fraction")
    normalized = Fraction(offset)
    if normalized < 0:
        raise ValueError("offset must be non-negative")
    frames = verticalities(score, bar_index, staves=staves)
    for frame in frames:
        if frame.offset <= normalized < frame.offset + frame.duration:
            return frame
    raise ValueError(
        f"offset {normalized} lies outside bar {bar_index}"
    )


def score_pitch_class_set(
        score: _ScoreLike,
        bar_index: int,
        *,
        offset: int | Fraction | None = None,
        staves: Collection[str] | None = None,
) -> PitchClassSet:
    """Return pointwise or whole-bar written and MIDI pitch-class sets."""
    frames = (
        (sonority_at(score, bar_index, offset, staves=staves),)
        if offset is not None
        else verticalities(score, bar_index, staves=staves)
    )
    pitches = tuple(pitch for frame in frames for pitch in frame.pitches)
    return PitchClassSet(
        written=frozenset(pitch.pitch_class for pitch in pitches),
        midi=frozenset(pitch.midi % 12 for pitch in pitches),
    )


def resolve_tonality(
        score: _ScoreLike,
        bar_index: int,
        *,
        tonality: Tonality | None,
        staves: Collection[str] | None,
        required: bool,
) -> Tonality | None:
    """Resolve one unambiguous analysis tonality for selected staves."""
    if tonality is not None:
        if not isinstance(tonality, Tonality):
            raise TypeError("tonality must be a Tonality or None")
        return tonality
    staff_names = _selected_staff_names(score, staves)
    _validate_bar_index(score, staff_names, bar_index)
    resolved = tuple(
        score.tonality_at(name, bar_index)
        for name in staff_names
    )
    distinct = set(resolved)
    if len(distinct) > 1:
        descriptions = ", ".join(
            f"{name}={value}"
            for name, value in zip(staff_names, resolved)
        )
        raise ValueError(
            "Selected staves have conflicting tonalities at bar "
            f"{bar_index}: {descriptions}; pass tonality explicitly"
        )
    result = resolved[0]
    if result is None and required:
        raise ValueError(
            f"No tonality is available at bar {bar_index}; "
            "pass tonality explicitly"
        )
    return result


def _root_spelling(
        root_midi_class: int,
        verticality: Verticality,
        tonality: Tonality | None,
) -> PitchClass:
    for pitch in verticality.pitches:
        if pitch.midi % 12 == root_midi_class:
            return pitch.pitch_class
    if tonality is not None:
        for degree, midi_class in enumerate(tonality.pitch_class):
            if midi_class == root_midi_class and tonality.degree_count == 7:
                return tonality.expected_pitch_class_for_degree(degree)
    return Pitch.from_midi(60 + root_midi_class).pitch_class


def _roman_numeral(
        root: PitchClass,
        quality: str,
        tonality: Tonality | None,
) -> str | None:
    if tonality is None or tonality.degree_count != 7:
        return None
    position = tonality.analyze_pitch(Pitch(root, 4))
    numeral = _ROMAN_NUMERALS[position.degree]
    if quality in {
            "minor",
            "minor seventh",
            "minor sixth",
            "minor-major seventh",
            "diminished",
            "diminished seventh",
            "half-diminished seventh",
    }:
        numeral = numeral.lower()
    accidental = (
        "#" * position.alteration
        if position.alteration > 0
        else "b" * (-position.alteration)
    )
    suffixes = {
        "major": "",
        "minor": "",
        "diminished": "°",
        "augmented": "+",
        "suspended second": "sus2",
        "suspended fourth": "sus4",
        "dominant seventh": "7",
        "major seventh": "maj7",
        "minor seventh": "7",
        "half-diminished seventh": "ø7",
        "diminished seventh": "°7",
        "minor-major seventh": "maj7",
        "major sixth": "6",
        "minor sixth": "6",
    }
    return accidental + numeral + suffixes[quality]


def chord_candidates(
        verticality: Verticality,
        *,
        tonality: Tonality | None = None,
        limit: int = 5,
) -> tuple[ChordCandidate, ...]:
    """Rank common chord templates against one exact verticality.

    MIDI pitch classes determine template membership, while the candidate
    root retains an observed spelling whenever the root is present. Missing
    and extra pitch classes lower confidence instead of preventing useful
    incomplete-chord and non-chord-tone interpretations.
    """
    if tonality is not None and not isinstance(tonality, Tonality):
        raise TypeError("tonality must be a Tonality or None")
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError("limit must be an integer")
    if limit < 0:
        raise ValueError("limit must be non-negative")
    observed = verticality.pitch_classes.midi
    if len(observed) < 2 or limit == 0:
        return ()
    bass_class = (
        None if verticality.bass is None else verticality.bass.midi % 12
    )
    candidates: list[ChordCandidate] = []
    for root_class in range(12):
        for quality, suffix, intervals in _CHORD_TEMPLATES:
            expected = frozenset(
                (root_class + interval) % 12
                for interval in intervals
            )
            matched = observed & expected
            if len(matched) < 2:
                continue
            missing = expected - observed
            extra = observed - expected
            coverage = len(matched) / len(expected)
            precision = len(matched) / len(observed)
            confidence = (
                0.55 * coverage
                + 0.35 * precision
                + (0.05 if root_class in observed else 0.0)
                + (0.05 if root_class == bass_class else 0.0)
            )
            confidence = max(0.0, min(1.0, confidence))
            root = _root_spelling(root_class, verticality, tonality)
            ordered_intervals = tuple(sorted(intervals))
            inversion = None
            if bass_class is not None:
                bass_interval = (bass_class - root_class) % 12
                if bass_interval in ordered_intervals:
                    inversion = ordered_intervals.index(bass_interval)
            candidates.append(ChordCandidate(
                root=root,
                quality=quality,
                symbol=f"{root}{suffix}",
                intervals=intervals,
                inversion=inversion,
                confidence=confidence,
                matched_pitch_classes=frozenset(matched),
                missing_pitch_classes=frozenset(missing),
                extra_pitch_classes=frozenset(extra),
                roman_numeral=_roman_numeral(root, quality, tonality),
            ))
    candidates.sort(key=lambda candidate: (
        -candidate.confidence,
        len(candidate.missing_pitch_classes),
        len(candidate.extra_pitch_classes),
        len(candidate.intervals),
        candidate.symbol,
    ))
    return tuple(candidates[:limit])


def score_scale_degrees(
        score: _ScoreLike,
        bar_index: int,
        *,
        tonality: Tonality | None = None,
        staves: Collection[str] | None = None,
) -> tuple[ScaleDegreeSnapshot, ...]:
    """Return time-aware scale-degree analysis for every sounding pitch."""
    resolved = resolve_tonality(
        score,
        bar_index,
        tonality=tonality,
        staves=staves,
        required=True,
    )
    assert resolved is not None
    return tuple(
        ScaleDegreeSnapshot(
            offset=frame.offset,
            duration=frame.duration,
            degrees=frame.scale_degrees(resolved),
        )
        for frame in verticalities(score, bar_index, staves=staves)
    )


def score_chord_candidates(
        score: _ScoreLike,
        bar_index: int,
        *,
        offset: int | Fraction = 0,
        tonality: Tonality | None = None,
        staves: Collection[str] | None = None,
        limit: int = 5,
) -> tuple[ChordCandidate, ...]:
    """Return ranked chord candidates at an exact score offset."""
    resolved = resolve_tonality(
        score,
        bar_index,
        tonality=tonality,
        staves=staves,
        required=False,
    )
    frame = sonority_at(score, bar_index, offset, staves=staves)
    return chord_candidates(frame, tonality=resolved, limit=limit)


def score_roman_numerals(
        score: _ScoreLike,
        bar_index: int,
        *,
        tonality: Tonality | None = None,
        staves: Collection[str] | None = None,
) -> tuple[HarmonicChange, ...]:
    """Return contiguous Roman-numeral interpretations within one bar."""
    return harmonic_context(
        score,
        bar_index,
        tonality=tonality,
        staves=staves,
    ).changes


def score_interval_matrix(
        score: _ScoreLike,
        bar_index: int,
        *,
        staves: Collection[str] | None = None,
        dissonant_classes: Collection[int] = _DISSONANT_INTERVAL_CLASSES,
) -> tuple[IntervalSnapshot, ...]:
    """Return cross-staff interval matrices at every vertical change."""
    return tuple(
        IntervalSnapshot(
            offset=frame.offset,
            duration=frame.duration,
            intervals=frame.interval_matrix(
                dissonant_classes=dissonant_classes,
            ),
        )
        for frame in verticalities(score, bar_index, staves=staves)
    )


def score_dissonances(
        score: _ScoreLike,
        bar_index: int,
        *,
        staves: Collection[str] | None = None,
        dissonant_classes: Collection[int] = _DISSONANT_INTERVAL_CLASSES,
) -> tuple[IntervalSnapshot, ...]:
    """Return only dissonant cross-staff intervals at every change."""
    return tuple(
        IntervalSnapshot(
            offset=snapshot.offset,
            duration=snapshot.duration,
            intervals=tuple(
                relation
                for relation in snapshot.intervals
                if relation.dissonant
            ),
        )
        for snapshot in score_interval_matrix(
            score,
            bar_index,
            staves=staves,
            dissonant_classes=dissonant_classes,
        )
    )


def score_doublings(
        score: _ScoreLike,
        bar_index: int,
        *,
        staves: Collection[str] | None = None,
) -> tuple[DoublingSnapshot, ...]:
    """Return pitch-class doublings at every vertical change."""
    return tuple(
        DoublingSnapshot(
            offset=frame.offset,
            duration=frame.duration,
            doublings=frame.doublings(),
        )
        for frame in verticalities(score, bar_index, staves=staves)
    )


def score_density(
        score: _ScoreLike,
        bar_index: int,
        *,
        staves: Collection[str] | None = None,
) -> tuple[DensityPoint, ...]:
    """Return sounding pitch and active-staff counts over a bar."""
    return tuple(
        DensityPoint(
            offset=frame.offset,
            duration=frame.duration,
            pitch_count=len(frame.pitches),
            active_staff_count=sum(
                bool(item.pitches) for item in frame.staff_pitches
            ),
        )
        for frame in verticalities(score, bar_index, staves=staves)
    )


def _register_snapshot(frame: Verticality) -> RegisterSnapshot:
    staff_ranges = tuple(
        StaffRange(
            staff=item.staff,
            lowest=min(item.pitches, key=lambda pitch: pitch.midi),
            highest=max(item.pitches, key=lambda pitch: pitch.midi),
        )
        for item in frame.staff_pitches
        if item.pitches
    )
    by_name = {item.staff: item for item in staff_ranges}
    crossings: list[tuple[str, str]] = []
    for upper, lower in zip(frame.staff_pitches, frame.staff_pitches[1:]):
        if upper.staff not in by_name or lower.staff not in by_name:
            continue
        if by_name[lower.staff].highest.midi > by_name[upper.staff].lowest.midi:
            crossings.append((upper.staff, lower.staff))
    ordered_pitches = sorted(frame.pitches, key=lambda pitch: pitch.midi)
    spacing = tuple(
        second.midi - first.midi
        for first, second in zip(ordered_pitches, ordered_pitches[1:])
    )
    bass = frame.bass
    soprano = frame.soprano
    return RegisterSnapshot(
        offset=frame.offset,
        duration=frame.duration,
        bass=bass,
        soprano=soprano,
        ambitus=(
            None
            if bass is None or soprano is None
            else soprano.midi - bass.midi
        ),
        spacing=spacing,
        staff_ranges=staff_ranges,
        crossings=tuple(crossings),
    )


def score_register_analysis(
        score: _ScoreLike,
        bar_index: int,
        *,
        staves: Collection[str] | None = None,
) -> RegisterAnalysis:
    """Return register, spacing, crossings, and temporal voice overlaps."""
    frames = verticalities(score, bar_index, staves=staves)
    snapshots = tuple(_register_snapshot(frame) for frame in frames)
    overlaps: list[RegisterOverlap] = []
    for previous, current in zip(snapshots, snapshots[1:]):
        previous_by_name = {
            item.staff: item for item in previous.staff_ranges
        }
        current_by_name = {
            item.staff: item for item in current.staff_ranges
        }
        ordered_names = tuple(item.staff for item in frames[0].staff_pitches)
        for upper, lower in zip(ordered_names, ordered_names[1:]):
            if not {
                    upper,
                    lower,
            } <= previous_by_name.keys() or not {
                    upper,
                    lower,
            } <= current_by_name.keys():
                continue
            upper_descends_below = (
                current_by_name[upper].lowest.midi
                < previous_by_name[lower].highest.midi
            )
            lower_rises_above = (
                current_by_name[lower].highest.midi
                > previous_by_name[upper].lowest.midi
            )
            if upper_descends_below or lower_rises_above:
                overlaps.append(RegisterOverlap(
                    offset=current.offset,
                    upper_staff=upper,
                    lower_staff=lower,
                ))
    return RegisterAnalysis(
        snapshots=snapshots,
        overlaps=tuple(overlaps),
    )


def score_bass_motion(
        score: _ScoreLike,
        bar_index: int,
        *,
        staves: Collection[str] | None = None,
) -> tuple[BassMotion, ...]:
    """Return changes between successive sounding bass pitches in a bar."""
    result: list[BassMotion] = []
    previous: tuple[Fraction, Pitch] | None = None
    for frame in verticalities(score, bar_index, staves=staves):
        bass = frame.bass
        if bass is None:
            continue
        if previous is not None and bass.midi != previous[1].midi:
            result.append(BassMotion(
                from_offset=previous[0],
                to_offset=frame.offset,
                from_pitch=previous[1],
                to_pitch=bass,
                semitones=bass.midi - previous[1].midi,
            ))
        previous = (frame.offset, bass)
    return tuple(result)


def _candidate_identity(
        candidate: ChordCandidate | None,
) -> tuple[int, str] | None:
    if candidate is None:
        return None
    return candidate.root.midi_value, candidate.quality


def _frame_primary_candidates(
        frames: Sequence[Verticality],
        tonality: Tonality,
) -> tuple[ChordCandidate | None, ...]:
    return tuple(
        candidates[0] if candidates else None
        for frame in frames
        for candidates in (
            chord_candidates(frame, tonality=tonality, limit=5),
        )
    )


def _harmonic_changes(
        frames: Sequence[Verticality],
        candidates: Sequence[ChordCandidate | None],
) -> tuple[HarmonicChange, ...]:
    changes: list[HarmonicChange] = []
    for frame, candidate in zip(frames, candidates):
        if (
                changes
                and _candidate_identity(changes[-1].candidate)
                == _candidate_identity(candidate)
        ):
            previous = changes[-1]
            changes[-1] = HarmonicChange(
                offset=previous.offset,
                duration=previous.duration + frame.duration,
                candidate=(
                    candidate
                    if candidate is not None
                    and (
                        previous.candidate is None
                        or candidate.confidence
                        > previous.candidate.confidence
                    )
                    else previous.candidate
                ),
            )
        else:
            changes.append(HarmonicChange(
                offset=frame.offset,
                duration=frame.duration,
                candidate=candidate,
            ))
    return tuple(changes)


def _nearest_staff_pitch(
        frames: Sequence[Verticality],
        frame_index: int,
        staff_name: str,
        pitch: Pitch,
        direction: int,
) -> Pitch | None:
    index = frame_index + direction
    while 0 <= index < len(frames):
        pitches = frames[index].by_staff[staff_name]
        if pitches:
            return min(
                pitches,
                key=lambda candidate: abs(candidate.midi - pitch.midi),
            )
        index += direction
    return None


def _non_chord_tones(
        frames: Sequence[Verticality],
        candidates: Sequence[ChordCandidate | None],
) -> tuple[NonChordTone, ...]:
    result: list[NonChordTone] = []
    for frame_index, (frame, candidate) in enumerate(
            zip(frames, candidates),
    ):
        if candidate is None:
            continue
        for item in frame.staff_pitches:
            for pitch in item.pitches:
                if pitch.midi % 12 not in candidate.extra_pitch_classes:
                    continue
                previous = _nearest_staff_pitch(
                    frames,
                    frame_index,
                    item.staff,
                    pitch,
                    -1,
                )
                following = _nearest_staff_pitch(
                    frames,
                    frame_index,
                    item.staff,
                    pitch,
                    1,
                )
                kind: Literal["passing", "neighbor", "unclassified"]
                kind = "unclassified"
                if previous is not None and following is not None:
                    from_previous = pitch.midi - previous.midi
                    to_following = following.midi - pitch.midi
                    if (
                            previous.midi == following.midi
                            and 0 < abs(from_previous) <= 2
                    ):
                        kind = "neighbor"
                    elif (
                            from_previous * to_following > 0
                            and abs(from_previous) <= 2
                            and abs(to_following) <= 2
                    ):
                        kind = "passing"
                result.append(NonChordTone(
                    offset=frame.offset,
                    staff=item.staff,
                    pitch=pitch,
                    kind=kind,
                ))
    return tuple(result)


def harmonic_context(
        score: _ScoreLike,
        bar_index: int,
        *,
        tonality: Tonality | None = None,
        staves: Collection[str] | None = None,
) -> HarmonicContext:
    """Return a duration-weighted harmonic interpretation of one bar.

    A tonality is required for functional labels. If it is not supplied, all
    selected staves must resolve to the same effective score/voice/bar tonal
    context. Chords are ranked independently at each vertical change; their
    primary interpretations are then combined and weighted by exact duration.
    """
    resolved = resolve_tonality(
        score,
        bar_index,
        tonality=tonality,
        staves=staves,
        required=True,
    )
    assert resolved is not None
    frames = verticalities(score, bar_index, staves=staves)
    primary_by_frame = _frame_primary_candidates(frames, resolved)
    changes = _harmonic_changes(frames, primary_by_frame)

    duration_by_identity: dict[tuple[int, str], Fraction] = {}
    representative: dict[tuple[int, str], ChordCandidate] = {}
    total_duration = sum(
        (frame.duration for frame in frames),
        Fraction(0),
    )
    for frame, candidate in zip(frames, primary_by_frame):
        identity = _candidate_identity(candidate)
        if identity is None or candidate is None:
            continue
        duration_by_identity[identity] = (
            duration_by_identity.get(identity, Fraction(0))
            + frame.duration
        )
        current = representative.get(identity)
        if current is None or candidate.confidence > current.confidence:
            representative[identity] = candidate

    ordered_identities = sorted(
        duration_by_identity,
        key=lambda identity: (
            -float(duration_by_identity[identity])
            * representative[identity].confidence,
            -float(duration_by_identity[identity]),
            representative[identity].symbol,
        ),
    )
    weighted = tuple(
        WeightedChord(
            candidate=representative[identity],
            duration=duration_by_identity[identity],
            coverage=(
                Fraction(0)
                if total_duration == 0
                else duration_by_identity[identity] / total_duration
            ),
        )
        for identity in ordered_identities
    )
    primary = weighted[0].candidate if weighted else None
    primary_coverage = weighted[0].coverage if weighted else Fraction(0)
    return HarmonicContext(
        bar_index=bar_index,
        tonality=resolved,
        verticalities=frames,
        primary=primary,
        primary_coverage=primary_coverage,
        weighted_candidates=weighted,
        changes=changes,
        non_chord_tones=_non_chord_tones(frames, primary_by_frame),
    )


def score_harmonic_rhythm(
        score: _ScoreLike,
        bar_index: int,
        *,
        tonality: Tonality | None = None,
        staves: Collection[str] | None = None,
) -> tuple[HarmonicChange, ...]:
    """Return contiguous harmonic assignments and their exact durations."""
    return harmonic_context(
        score,
        bar_index,
        tonality=tonality,
        staves=staves,
    ).changes


def _match_pitches(
        source: Sequence[Pitch],
        target: Sequence[Pitch],
) -> tuple[tuple[Pitch, Pitch], ...]:
    if not source or not target:
        return ()
    if len(source) > len(target):
        return tuple(
            (first, second)
            for second, first in _match_pitches(target, source)
        )

    @lru_cache(maxsize=None)
    def solve(
            source_index: int,
            remaining_targets: tuple[int, ...],
    ) -> tuple[int, tuple[tuple[int, int], ...]]:
        if source_index == len(source):
            return 0, ()
        possibilities = []
        for target_index in remaining_targets:
            remaining = tuple(
                index
                for index in remaining_targets
                if index != target_index
            )
            later_cost, later_pairs = solve(source_index + 1, remaining)
            cost = (
                abs(target[target_index].midi - source[source_index].midi)
                + later_cost
            )
            possibilities.append((
                cost,
                ((source_index, target_index), *later_pairs),
            ))
        return min(possibilities, key=lambda possibility: possibility)

    _, indices = solve(0, tuple(range(len(target))))
    return tuple(
        (source[source_index], target[target_index])
        for source_index, target_index in indices
    )


def _edge_verticality(
        frames: Sequence[Verticality],
        *,
        first: bool,
) -> Verticality:
    iterable = frames if first else reversed(frames)
    for frame in iterable:
        if frame.pitches:
            return frame
    raise ValueError("voice-leading analysis requires a sounding sonority")


def voice_leading_to(
        score: _ScoreLike,
        from_bar: int,
        to_bar: int,
        *,
        staves: Collection[str] | None = None,
        leap_threshold: int = 5,
) -> VoiceLeadingAnalysis:
    """Analyze motion from one bar's final sonority to another's first.

    Pitches are matched independently within each staff by minimum semitone
    displacement. Chord voices can therefore yield multiple motions. A leap
    is a motion strictly larger than ``leap_threshold`` semitones. Parallel
    perfects include non-stationary similar motion that preserves a perfect
    fifth or octave between pitches on different staves.
    """
    if isinstance(leap_threshold, bool) or not isinstance(leap_threshold, int):
        raise TypeError("leap_threshold must be an integer")
    if leap_threshold < 0:
        raise ValueError("leap_threshold must be non-negative")
    staff_names = _selected_staff_names(score, staves)
    _validate_bar_index(score, staff_names, from_bar)
    _validate_bar_index(score, staff_names, to_bar)
    source = _edge_verticality(
        verticalities(score, from_bar, staves=staff_names),
        first=False,
    )
    target = _edge_verticality(
        verticalities(score, to_bar, staves=staff_names),
        first=True,
    )

    motions = tuple(
        VoiceMotion(
            staff=staff_name,
            from_pitch=first,
            to_pitch=second,
            semitones=second.midi - first.midi,
        )
        for staff_name in staff_names
        for first, second in _match_pitches(
            source.by_staff[staff_name],
            target.by_staff[staff_name],
        )
    )
    source_counter = Counter(pitch.midi for pitch in source.pitches)
    target_counter = Counter(pitch.midi for pitch in target.pitches)
    common_tones = tuple(sorted((source_counter & target_counter).elements()))

    contrary: list[tuple[str, str]] = sorted({
        (
            (first.staff, second.staff)
            if first.staff < second.staff
            else (second.staff, first.staff)
        )
        for first, second in combinations(motions, 2)
        if first.staff != second.staff
        and first.semitones * second.semitones < 0
    })
    parallels: dict[
        tuple[tuple[str, str], int],
        ParallelMotion,
    ] = {}
    for first, second in combinations(motions, 2):
        if first.staff == second.staff:
            continue
        if (
                first.semitones == 0
                or second.semitones == 0
                or first.semitones * second.semitones <= 0
        ):
            continue
        before = abs(first.from_pitch.midi - second.from_pitch.midi) % 12
        after = abs(first.to_pitch.midi - second.to_pitch.midi) % 12
        if before == after and before in {0, 7}:
            staff_pair = (
                (first.staff, second.staff)
                if first.staff < second.staff
                else (second.staff, first.staff)
            )
            parallels[(staff_pair, before)] = ParallelMotion(
                first_staff=staff_pair[0],
                second_staff=staff_pair[1],
                interval_class=before,
            )

    return VoiceLeadingAnalysis(
        from_bar=from_bar,
        to_bar=to_bar,
        motions=motions,
        common_tones=common_tones,
        total_motion=sum(abs(motion.semitones) for motion in motions),
        contrary_pairs=tuple(contrary),
        parallel_perfects=tuple(parallels.values()),
        leaps=tuple(
            motion
            for motion in motions
            if abs(motion.semitones) > leap_threshold
        ),
    )
