from paeonia import Bar

def test_to_lilypond():
    bar = Bar("C#4. D''8.. R2. Bb,16 <F# A# C#'>2. G, R E4.. <A C' E>1")
    assert(bar.to_lilypond() == "cis4. d''4 r2. ais'16 <fis' ais' cis''>2. g'2. r2. e'2 <a' c'' e''>1")

def test_retrograde():
    bar1 = Bar("Bb'2. A <A B C> C'4 R B,")
    bar2 = bar1.retrograde()
    pitches1 = [note.pitches for note in bar1.notes if note.pitches is not None]
    pitches2 = [note.pitches for note in bar2.notes if note.pitches is not None]
    durations1 = [note.duration for note in bar1.notes]
    durations2 = [note.duration for note in bar2.notes]
    assert(pitches1 == list(reversed(pitches2)))
    assert(durations1 == durations2)

def test_repr():
    paeonia_notation = "C#'2. A <A B C> C'4 R B,"
    bar1 = Bar(paeonia_notation)
    assert(str(bar1) == paeonia_notation)
    assert(eval(repr(bar1)) == bar1)
    
def test_note_repeat():
    bar1 = Bar("C D E F G")
    generator = bar1.note_repeat([2, 3, 1])
    bar2 = Bar(" ".join(["R" for _ in range(16)]))
    bar2.take(generator, pitches=True)
    assert(bar2 == Bar("C C D D D E F F G G G C D D E E"))

def test_take():
    bar1 = Bar("C D E F G")
    bar2 = Bar("C2 G, F")
    bar1.take(bar2.cycle(), pitches=True)
    bar2.take(bar1.cycle(), durations=True)
    assert(str(bar1) == "C G, F C' G,")
    assert(str(bar2) == "C G, F")
