from paeonia import Note

def test_note_to_lilypond():
    note_name = Note.note_to_lilypond(60)
    assert(note_name == "c'")
    note_name = Note.note_to_lilypond(None)
    assert(note_name == "r")
    note_name = Note.note_to_lilypond(0)
    assert(note_name == "c,,,,")
    note_name = Note.note_to_lilypond(126)
    assert(note_name == "fis''''''")
