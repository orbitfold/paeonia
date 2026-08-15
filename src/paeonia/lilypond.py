# pyright: reportImportCycles=false
"""Render Paeonia model objects as spelling-aware LilyPond notation."""

from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .bar import Bar
    from .note import Note
    from .pitch import Pitch, PitchClass
    from .score import Score
    from .tonality import Tonality, TonalityPlan
    from .voice import Voice


LILYPOND_BASE = {
    "C": "c",
    "D": "d",
    "E": "e",
    "F": "f",
    "G": "g",
    "A": "a",
    "B": "b",
}

LILYPOND_MODES = {
    "major": "major",
    "ionian": "major",
    "dorian": "dorian",
    "phrygian": "phrygian",
    "lydian": "lydian",
    "mixolydian": "mixolydian",
    "minor": "minor",
    "aeolian": "minor",
    "minor-harmonic": "minor",
    "minor-melodic": "minor",
    "locrian": "locrian",
}


def pitch_class_to_lilypond(pitch_class: PitchClass) -> str:
    """Render a spelled pitch class, including arbitrary accidentals."""
    base = LILYPOND_BASE[pitch_class.letter]
    if pitch_class.accidental > 0:
        return base + "is" * pitch_class.accidental
    if pitch_class.accidental < 0:
        return base + "es" * (-pitch_class.accidental)
    return base


def pitch_to_lilypond(pitch: Pitch) -> str:
    """Render a pitch using its spelling and explicit octave."""
    octave_delta = pitch.octave - 3
    octave_marks = (
        "'" * octave_delta
        if octave_delta >= 0
        else "," * (-octave_delta)
    )
    return pitch_class_to_lilypond(pitch.pitch_class) + octave_marks


def duration_to_lilypond(duration: Fraction) -> str:
    """Render an exact whole-note duration with at most two dots."""
    duration = Fraction(duration)
    for denominator in (1, 2, 4, 8, 16, 32, 64, 128):
        base = Fraction(1, denominator)
        for dots in range(3):
            multiplier = sum(
                (Fraction(1, 2**dot) for dot in range(dots + 1)),
                Fraction(0),
            )
            if base * multiplier == duration:
                return f"{denominator}{'.' * dots}"
    raise ValueError(f"Unsupported LilyPond duration: {duration}")


def note_to_lilypond(note: Note) -> str:
    """Render one note, chord, or rest, including an outgoing tie."""
    duration = duration_to_lilypond(note.duration)
    tie = "~" if note.tie_out else ""
    if note.is_rest():
        return f"r{duration}{tie}"
    if note.is_chord:
        pitches = " ".join(
            pitch_to_lilypond(pitch)
            for pitch in note.pitches
        )
        return f"<{pitches}>{duration}{tie}"
    return f"{pitch_to_lilypond(note.pitches[0])}{duration}{tie}"


def bar_to_lilypond(bar: Bar) -> str:
    """Render all events in a bar in order."""
    return " ".join(note_to_lilypond(note) for note in bar.notes)


def tonality_to_lilypond(tonality: Tonality) -> str:
    """Render a LilyPond key command for a supported tonality."""
    try:
        mode = LILYPOND_MODES[tonality.mode_name]
    except KeyError as exc:
        raise ValueError(
            f"Tonality mode {tonality.mode_name!r} has no LilyPond key mode"
        ) from exc
    tonic = pitch_class_to_lilypond(tonality.tonic)
    return f"\\key {tonic} \\{mode}"


def voice_to_lilypond(
        voice: Voice,
        *,
        inherited: Tonality | None = None,
        inherited_plan: TonalityPlan | None = None,
) -> str:
    """Render a voice and emit key commands only when tonality changes."""
    rendered = []
    previous = object()
    for bar_index, bar in enumerate(voice.bars):
        tonality = voice.tonality_at(
            bar_index,
            inherited=inherited,
            inherited_plan=inherited_plan,
        )
        if tonality != previous:
            if tonality is not None:
                rendered.append(tonality_to_lilypond(tonality))
            previous = tonality
        bar_text = bar_to_lilypond(bar)
        if bar_text:
            rendered.append(bar_text)
    return " ".join(rendered)


def _escape_lilypond_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def score_to_lilypond(score: Score) -> str:
    """Render aligned staves in insertion order as a LilyPond score body."""
    score.validate_alignment()
    rendered_staves = []
    for name, staff in score.staves.items():
        display_name = staff.name or name
        context = (
            "\\new Staff \\with { instrumentName = "
            f'"{_escape_lilypond_string(display_name)}"'
            " }"
        )
        voice = voice_to_lilypond(
            staff.voice,
            inherited=score.default_tonality,
            inherited_plan=score.tonality_plan,
        )
        rendered_staves.append(
            f"{context} {{ \\clef {staff.clef} "
            f"\\time {score.time_signature[0]}/{score.time_signature[1]} "
            f"\\tempo 4 = {score.tempo} {voice} \\bar \"|.\" }}"
        )
    return "\n".join(rendered_staves)
