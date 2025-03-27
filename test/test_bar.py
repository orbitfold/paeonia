from paeonia import Bar, Tonality
import pytest

def test_to_lilypond():
    bar = Bar("C#4. D''8.. R2. Bb,16 <F# A# C#'>2. G, R E4.. <A C' E>1")
    assert(bar.to_lilypond() == "cis4. d''4 r2. ais'16 <fis' ais' cis''>2. g'2. r2. e'2 <a' c'' e''>1")

def test_eq():
    assert(Bar("R") == Bar("R"))

def test_retrograde():
    bar1 = Bar("Bb'2. A <A B C> C'4 R B,")
    bar2 = bar1.retrograde()
    assert(bar2 == Bar("B'2. C' <C, B A> A4 R A#"))

def test_repr():
    paeonia_notation = "C#'2. A <A B C> C'4 R B,"
    bar1 = Bar(paeonia_notation)
    assert(str(bar1) == paeonia_notation)
    assert(eval(repr(bar1)) == bar1)
    single_note = "C'1"
    bar2 = Bar(single_note)
    assert(str(bar2) == single_note)
    assert(eval(repr(bar2)) == bar2)
    
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

def test_ascending():
    bar1 = Bar("C2 E D4 G R F")
    asc = bar1.ascending()
    assert(asc == Bar("C2 D E4 F R G"))

def test_descending():
    bar1 = Bar("C2 E D4 G R F")
    desc = bar1.descending()
    assert(desc == Bar("G2 F E4 D R C"))

def test_random_order():
    bar1 = Bar("C2 E D4 G R F")
    assert(bar1.random_order() != bar1)
    assert(bar1.random_order().ascending() == Bar("C2 D E4 F R G"))

def test_map_tonality():
    bar1 = Bar("C2 Eb D4 G R F#")
    tonality = Tonality()
    bar2 = bar1.map_tonality(tonality, method="up")
    assert(bar2 == Bar("C2 E D4 G R G"))
    bar2 = bar1.map_tonality(tonality, method="down")
    assert(bar2 == Bar("C2 D D4 G R F"))
    
def test_inversion():
    bar1 = Bar("C2 Eb D4 G R F#")
    bar2 = bar1.inversion()
    assert(bar2 == Bar("C2 A, A#4 F R F#"))
    bar1 = Bar("C2 <D# G> E")
    bar2 = bar1.inversion()
    assert(bar2 == Bar("C2 <A, F> G#"))

def test_tonal_inversion():
    bar1 = Bar("C2 A, R4 B G")
    t = Tonality()
    assert(bar1.tonal_inversion(t) == Bar("C2 E R4 D F"))

@pytest.mark.skip()
def test_map_melody_to_tonality():
    bar1 = Bar("C E D# A, A# C'")
    t = Tonality()
    assert(bar1.map_melody_to_tonality(t) == Bar("C E D A, B C'"))    
    with pytest.raises(RuntimeError):
        bar2 = Bar("C <E F> D# A, A# C'")
        bar2.map_melody_to_tonality(t)

def test_tonal_transpose():
    bar1 = Bar("C D E D C")
    t = Tonality()
    assert(bar1.tonal_transpose(t, 1) == Bar("D E F E D"))
    assert(bar1.tonal_transpose(t, -3) == Bar("G, A B A G"))

def test_tonal_mode_change():
    bar1 = Bar("C D E D C")
    t = Tonality()
    assert(bar1.tonal_mode_change(t, "minor") == Bar("C D Eb D C"))
    bar2 = Bar("<C E G>")
    assert(bar2.tonal_mode_change(t, "minor") == Bar("<C D# G>"))

def test_merge_pitches():
    bar1 = Bar("C D2 R E D1 C R")
    bar2 = Bar("D F2 R G A1 R F")
    bar3 = Bar("D4 F2 G A1 F")
    result = Bar("<C D> <D F>2 R <E G> <D A>1 C F")
    assert(bar1 & bar2 == result)
    with pytest.raises(RuntimeError):
        bar1 & bar3

def test_pulse_to_durations():
    bar = Bar("C E R")
    pulses = "x.xx...x."
    new_bar_1 = bar.pulses_to_durations(pulses, legato=False)
    new_bar_2 = bar.pulses_to_durations(pulses, legato=True)
    assert(new_bar_1 == Bar("C16 R E R R R R C R"))
    assert(new_bar_2 == Bar("C8 E16 R4 C8"))
    pulses = "...x"
    new_bar_3 = bar.pulses_to_durations(pulses, legato=True)
    assert(new_bar_3 == Bar("R8. C16"))
