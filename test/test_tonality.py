from paeonia import Tonality

def test_tonality():
    t1 = Tonality("C#", "dorian")
    t2 = Tonality("G", "locrian")
    notes1_in = [61, 63, 64, 66, 68, 70, 71]
    notes1_out = [60, 62, 65, 67, 69]
    for note in notes1_in:
        assert(note in t1.pitches)
    for note in notes1_out:
        assert(note not in t1.pitches)
    notes2_in = [60, 61, 63, 65, 67, 68, 70]
    notes2_out = [62, 64, 66, 69, 71]
    for note in notes2_in:
        assert(note in t2.pitches)
    for note in notes2_out:
        assert(note not in t2.pitches)
