import os
from paeonia import Note, Bar, Voice, Score

def test_workflow():
    notes = [Note(pitch, 1, 0.75) for pitch in range(60, 69)]
    bar1 = Bar()
    bar2 = Bar()
    bar3 = Bar()
    for note in notes[0:3]:
        bar1.add_note(note)
    for note in notes[3:6]:
        bar2.add_note(note)
    for note in notes[6:9]:
        bar3.add_note(note)
    voice1 = Voice()
    voice1.add_bar(bar1)
    voice1.add_bar(bar2)
    voice2 = Voice()
    voice2.add_bar(bar3)
    score = Score()
    score.add_voice(voice1)
    score.add_voice(voice2)
    score.to_midi('test.mid')
    assert(os.path.isfile('test.mid'))
