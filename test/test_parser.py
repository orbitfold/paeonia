from fractions import Fraction

import pytest

from paeonia import Bar, Note
from paeonia.parser import parse


def pitch_spellings(notes):
    return [
        tuple(str(pitch) for pitch in note.pitches)
        for note in notes
    ]


def test_existing_example_preserves_non_relative_midi_values_and_durations():
    test_input = "C#4. D''8.. R2. Bb,16 <F# A# C#'>2. G, R E4.. <A C' E>1"
    parsed_bar = parse(test_input, relative=False)
    pitches = [[61], [86], [], [58], [66, 70, 73], [55], [], [64], [69, 72, 64]]
    for note, pitch_list in zip(parsed_bar, pitches):
        assert(note.midi_pitches == tuple(pitch_list))
    durations = [Fraction('3/8'), Fraction('1/4'), Fraction('3/4'), Fraction('1/16'),
                 Fraction('3/4'), Fraction('3/4'), Fraction('3/4'), Fraction('1/2'),
                 Fraction('1/1')]
    for note, duration in zip(parsed_bar, durations):
        assert(note.duration == duration)
    assert parsed_bar[2].pitches == ()
    assert parsed_bar[6].pitches == ()


def test_existing_example_preserves_relative_midi_values_and_durations():
    test_input = "C#4. D''8.. R2. Bb,16 <F# A# C#'>2. G, R E4.. <A C' E>1"
    durations = [Fraction('3/8'), Fraction('1/4'), Fraction('3/4'), Fraction('1/16'),
                 Fraction('3/4'), Fraction('3/4'), Fraction('3/4'), Fraction('1/2'),
                 Fraction('1/1')]
    parsed_bar = parse(test_input, relative=True)
    pitches = [[61], [86], [], [82], [78, 82, 85], [79], [], [76], [81, 84, 88]]
    for note, pitch_list in zip(parsed_bar, pitches):
        assert(note.midi_pitches == tuple(pitch_list))
    for note, duration in zip(parsed_bar, durations):
        assert(note.duration == duration)


def test_eb_and_d_sharp_remain_structurally_distinct():
    eb, d_sharp = parse("Eb D#", relative=False)

    assert eb.midi_pitches == d_sharp.midi_pitches == (63,)
    assert pitch_spellings([eb, d_sharp]) == [("Eb4",), ("D#4",)]
    assert eb.pitches != d_sharp.pitches


def test_double_sharps_and_flats_parse_correctly():
    notes = parse("F## Gbb", relative=False)

    assert [note.midi_pitches for note in notes] == [(67,), (65,)]
    assert pitch_spellings(notes) == [("F##4",), ("Gbb4",)]


def test_rests_retain_inherited_durations():
    notes = parse("C8 R R4 R", relative=False)

    assert [note.duration for note in notes] == [
        Fraction(1, 8),
        Fraction(1, 8),
        Fraction(1, 4),
        Fraction(1, 4),
    ]
    assert all(note.pitches == () for note in notes[1:])


def test_chord_pitch_spelling_survives():
    chord = parse("<Bb D# F## Gbb>", relative=False)[0]

    assert chord.midi_pitches == (70, 63, 67, 65)
    assert pitch_spellings([chord]) == [("Bb4", "D#4", "F##4", "Gbb4")]
    assert chord.is_chord


def test_relative_and_non_relative_modes_retain_current_octave_behaviour():
    notation = "C' D E, F <G A' B,>"

    non_relative = parse(notation, relative=False)
    relative = parse(notation, relative=True)

    assert [note.midi_pitches for note in non_relative] == [
        (72,),
        (62,),
        (52,),
        (65,),
        (67, 81, 59),
    ]
    assert [note.midi_pitches for note in relative] == [
        (72,),
        (74,),
        (64,),
        (65,),
        (67, 81, 71),
    ]


def test_note_parse_rejects_multiple_events_while_bar_accepts_them():
    with pytest.raises(ValueError, match="exactly one event"):
        Note.parse("C D")

    bar = Bar("C D")

    assert len(bar) == 2
    assert [note.midi_pitches for note in bar] == [(60,), (62,)]
