import pytest

from paeonia.pitch import Pitch, PitchClass

def test_enharmonic_spelling_is_distinct():
    sharp = Pitch.parse("D#4")
    flat = Pitch.parse("Eb4")

    assert sharp.midi == 63
    assert flat.midi == 63
    assert sharp != flat
    assert sharp.enharmonic_equals(flat)

def test_double_accidental():
    assert Pitch.parse("F##4").midi == Pitch.parse("G4").midi

def test_midi_round_trip():
    for midi in range(128):
        assert Pitch.from_midi(midi).midi == midi

def test_invalid_pitch_class():
    with pytest.raises(ValueError):
        _ = PitchClass.parse("H#")

def test_out_of_range_midi():
    with pytest.raises(ValueError):
        Pitch.parse("C10").midi
