from paeonia.parser import np
import paeonia

def test_np():
    test_input = "C#4. D''8.. R2. Bb,16 <F# A# C#'>2. G, R E4.. <A C' E>1"
    parsed_bar = np(test_input, relative=False)
    pitches = [[49], [74], None, [46], [54, 58, 61], [43], None, [52], [57, 60, 52]]
    for note, pitch_list in zip(parsed_bar.notes, pitches):
        assert(note.pitches == pitch_list)


