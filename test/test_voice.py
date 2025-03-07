from paeonia import Bar
from paeonia import Voice

def test_to_lilypond():
    bar1 = Bar("C#4. D''8.. R2. Bb,16 <F# A# C#'>2.")
    bar2 = Bar("G, R E4.. <A C' E>1")
    assert(Voice([bar1, bar2]).to_lilypond() == " ".join([bar1.to_lilypond(), bar2.to_lilypond()]))

