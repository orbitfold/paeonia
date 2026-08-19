from copy import copy
from fractions import Fraction
from math import pi

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


def test_stretch_multiplies_duration_and_preserves_note_metadata():
    note = Note.parse("<C Eb G>8").with_velocity(0.4).with_ties(
        tie_in=True,
        tie_out=True,
    )

    stretched = note.stretch(Fraction(3, 2))

    assert stretched.duration == Fraction(3, 16)
    assert stretched.pitches == note.pitches
    assert stretched.velocity == note.velocity
    assert stretched.tie_in is True
    assert stretched.tie_out is True
    assert stretched is not note
    assert note.duration == Fraction(1, 8)


def test_stretch_accepts_integer_and_decimal_float_factors():
    note = Note.parse("C4")

    assert note.stretch(2).duration == Fraction(1, 2)
    assert note.stretch(0.1, quantize=False).duration == Fraction(1, 40)


def test_stretch_quantizes_to_nearest_notatable_duration_by_default():
    note = Note.parse("C4")

    stretched = note.stretch(pi)

    assert stretched.duration == Fraction(3, 4)
    assert stretched.to_lilypond() == "c'2."


def test_stretch_can_retain_an_exact_unsupported_duration():
    note = Note.parse("C1")

    stretched = note.stretch(pi, quantize=False)

    assert stretched.duration == Fraction("3.141592653589793")
    with pytest.raises(ValueError, match="Unsupported LilyPond duration"):
        stretched.to_lilypond()


def test_stretch_quantization_uses_long_lilypond_durations():
    stretched = Note.parse("C1").stretch(pi)

    assert stretched.duration == Fraction(3)
    assert stretched.to_lilypond() == r"c'\breve."


def test_stretch_does_not_quantize_an_exact_double_whole_downward():
    stretched = Note.parse("C4").stretch(8)

    assert stretched.duration == Fraction(2)
    assert stretched.to_lilypond() == r"c'\breve"


def test_stretch_quantization_clamps_above_largest_notatable_duration():
    stretched = Note.parse("C1").stretch(100)

    assert stretched.duration == Fraction(14)
    assert stretched.to_lilypond() == r"c'\maxima.."


def test_stretch_works_for_rests():
    rest = Note.rest(Fraction(1, 8)).with_velocity(0.2)

    stretched = rest.stretch(3)

    assert stretched.is_rest()
    assert stretched.duration == Fraction(3, 8)
    assert stretched.velocity == rest.velocity


@pytest.mark.parametrize("factor", [0, -1, Fraction(-1, 2)])
def test_stretch_rejects_non_positive_factors(factor):
    with pytest.raises(ValueError, match="factor must be positive"):
        Note.parse("C").stretch(factor)


@pytest.mark.parametrize("factor", [float("inf"), float("-inf"), float("nan")])
def test_stretch_rejects_non_finite_factors(factor):
    with pytest.raises(ValueError, match="factor must be finite"):
        Note.parse("C").stretch(factor)


@pytest.mark.parametrize("factor", [True, "2", object()])
def test_stretch_rejects_non_numeric_factors(factor):
    with pytest.raises(
            TypeError,
            match="factor must be an integer, float, or Fraction",
    ):
        Note.parse("C").stretch(factor)


def test_stretch_rejects_non_boolean_quantize_option():
    with pytest.raises(TypeError, match="quantize must be a boolean"):
        Note.parse("C").stretch(2, quantize=1)


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


def test_pitch_order_key_sorts_sounding_notes_and_places_rests_last():
    c = Note.parse("C")
    e = Note.parse("E")
    chord = Note.parse("<C E G>")
    rest = Note.rest()

    ordered = sorted([rest, e, chord, c], key=Note.pitch_order_key)

    assert ordered == [c, chord, e, rest]
    assert min([e, c], key=Note.pitch_order_key) is c


def test_pitch_order_key_sorts_chord_pitches_before_comparing_them():
    note = Note(
        pitches=[
            Pitch.parse("G4"),
            Pitch.parse("C4"),
            Pitch.parse("E4"),
        ]
    )

    assert note.pitch_order_key() == (0, (60, 64, 67))


def test_pitch_order_key_compares_enharmonic_spellings_by_sound():
    sharp = Note(pitches=[Pitch.parse("D#4")])
    flat = Note(pitches=[Pitch.parse("Eb4")])

    assert sharp.pitch_order_key() == flat.pitch_order_key()
    assert sharp != flat


def test_pitch_order_key_ignores_non_pitch_metadata():
    original = Note.parse("C4")
    changed = original.with_duration(Fraction(1, 8)).with_velocity(
        0.25
    ).with_ties(tie_in=True, tie_out=True)

    assert original.pitch_order_key() == changed.pitch_order_key()
    assert original != changed


def test_pitch_order_key_gives_all_rests_the_rest_sentinel():
    assert Note.rest().pitch_order_key() == (1, ())
    assert Note.rest(Fraction(1, 8)).pitch_order_key() == (1, ())


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
