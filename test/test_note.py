from paeonia import Note
from fractions import Fraction

def test_note_to_lilypond():
    note_name = Note.note_to_lilypond(60)
    assert(note_name == "c'")
    note_name = Note.note_to_lilypond(None)
    assert(note_name == "r")
    note_name = Note.note_to_lilypond(0)
    assert(note_name == "c,,,,")
    note_name = Note.note_to_lilypond(126)
    assert(note_name == "fis''''''")

def test_duration_to_lilypond():
    duration = Note.duration_to_lilypond(Fraction('1/4'))
    assert(duration == '4')
    duration = Note.duration_to_lilypond(Fraction('3/8'))
    assert(duration == '4.')
    duration = Note.duration_to_lilypond(Fraction('3/32'))
    assert(duration == '16.')
