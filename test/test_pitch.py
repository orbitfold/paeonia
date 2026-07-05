import pytest

from paeonia.pitch import Pitch


def test_pitch_parse_natural():
    pitch = Pitch.parse("C4")

    assert pitch == Pitch("C", 0, 4)
    assert pitch.midi == 60
    assert pitch.pitch_class == 0


def test_pitch_parse_accidentals():
    assert Pitch.parse("Bb3") == Pitch("B", -1, 3)
    assert Pitch.parse("F##5") == Pitch("F", 2, 5)
    assert Pitch.parse("Gbb-1") == Pitch("G", -2, -1)


def test_pitch_parse_normalizes_case_and_whitespace():
    assert Pitch.parse(" c#4 ") == Pitch("C", 1, 4)


@pytest.mark.parametrize("value", ["H4", "C###4", "Cb#4", "C", "4C"])
def test_pitch_parse_rejects_invalid_syntax(value):
    with pytest.raises(ValueError, match="Invalid pitch"):
        Pitch.parse(value)


def test_pitch_parse_rejects_out_of_midi_range():
    with pytest.raises(ValueError, match="outside the MIDI range"):
        Pitch.parse("C-2")
