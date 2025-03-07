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

def test_to_lilypond():
    note = Note(pitches=[60, 63, 67], duration=Fraction('3/4'))
    assert(note.to_lilypond() == "<c' dis' g'>2.")

def test_add_sub():
    note = Note(pitches=[60, 68], duration=Fraction('3/4'))
    (note + 3).pitches == [63, 71]
    (note - 5).pitches == [55, 63]
    rest = Note(pitches=None, duration=Fraction('3/4'))
    assert(rest == (rest + 2))

def test_repr():
    note = Note("C''2.")
    assert(str(note) == "C''2.")
    assert(eval(repr(note)) == note)
