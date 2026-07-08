from copy import copy
from fractions import Fraction

import pytest

from paeonia import Note
from paeonia.pitch import Pitch


def test_integer_pitches_are_normalized_to_pitch_objects_and_preserve_midi():
    note = Note(pitches=[60, 61, 127])

    assert all(isinstance(pitch, Pitch) for pitch in note.pitches)
    assert note.midi_pitches == (60, 61, 127)


def test_pitch_spelling_survives_construction_and_copying():
    pitch = Pitch.parse("Eb4")
    note = Note(pitches=[pitch])
    copied = copy(note)

    assert str(note.pitches[0]) == "Eb4"
    assert copied.pitches == note.pitches
    assert str(copied.pitches[0]) == "Eb4"


def test_velocity_duration_ties_and_chord_pitches_survive_with_pitches():
    note = Note(
        pitches=[Pitch.parse("C4"), Pitch.parse("E4")],
        duration=Fraction(3, 8),
        velocity=0.5,
        tie_in=True,
        tie_out=True,
    )

    changed = note.with_pitches([Pitch.parse("G4"), Pitch.parse("Bb4")])

    assert changed.pitches == (Pitch.parse("G4"), Pitch.parse("Bb4"))
    assert changed.duration == Fraction(3, 8)
    assert changed.velocity == 0.5
    assert changed.tie_in is True
    assert changed.tie_out is True


def test_rest_remains_rest_through_map_pitches_and_chromatic_transposition():
    rest = Note.rest(duration=Fraction(1, 8))

    mapped = rest.map_pitches(lambda pitch: pitch.transpose_semitones(1))
    transposed = rest.transpose_semitones(7)

    assert rest.pitches == ()
    assert mapped.is_rest()
    assert transposed.is_rest()
    assert mapped == rest
    assert transposed == rest


def test_rest_remains_rest_through_tonality_mapping():
    rest = Note.rest(duration=Fraction(1, 8))

    mapped = rest.map_tonality(tonality=None)

    assert mapped.pitches == ()
    assert mapped == rest


def test_dataclass_equality_distinguishes_enharmonic_spellings_but_sounds_like_does_not():
    sharp = Note(pitches=[Pitch.parse("D#4")])
    flat = Note(pitches=[Pitch.parse("Eb4")])

    assert sharp != flat
    assert sharp.sounds_like(flat)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"duration": 0},
        {"duration": Fraction(-1, 4)},
        {"velocity": -0.01},
        {"velocity": 1.01},
    ],
)
def test_invalid_duration_and_velocity_fail_immediately(kwargs):
    with pytest.raises(ValueError):
        Note(pitches=[60], **kwargs)


def test_note_parse_rejects_notation_containing_multiple_events():
    with pytest.raises(ValueError, match="exactly one event"):
        Note.parse("C D")
