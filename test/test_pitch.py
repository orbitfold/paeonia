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


@pytest.mark.parametrize("spelling", ["Eb4", "D#4", "Gbb4", "B#4", "Cb4"])
def test_octave_transposition_preserves_exact_pitch_class_spelling(spelling):
    pitch = Pitch.parse(spelling)

    raised = pitch.transpose_semitones(12)
    lowered = pitch.transpose_semitones(-12)

    assert raised.pitch_class == pitch.pitch_class
    assert lowered.pitch_class == pitch.pitch_class
    assert raised.octave == pitch.octave + 1
    assert lowered.octave == pitch.octave - 1
    assert raised.midi == pitch.midi + 12
    assert lowered.midi == pitch.midi - 12

def test_invalid_pitch_class():
    with pytest.raises(ValueError):
        _ = PitchClass.parse("H#")

def test_out_of_range_midi():
    with pytest.raises(ValueError):
        Pitch.parse("C10").midi
