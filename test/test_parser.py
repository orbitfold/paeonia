from paeonia.parser import parse
import paeonia
from fractions import Fraction

def test_parse():
    test_input = "C#4. D''8.. R2. Bb,16 <F# A# C#'>2. G, R E4.. <A C' E>1"
    parsed_bar = parse(test_input, relative=False)
    pitches = [[61], [86], [], [58], [66, 70, 73], [55], [], [65], [69, 72, 64]]
    for note, pitch_list in zip(parsed_bar, pitches):
        assert(note.pitches == pitch_list)
    durations = [Fraction('3/8'), Fraction('1/4'), Fraction('3/4'), Fraction('1/16'),
                 Fraction('3/4'), Fraction('3/4'), Fraction('3/4'), Fraction('1/2'),
                 Fraction('1/1')]
    for note, duration in zip(parsed_bar, durations):
        assert(note.duration == duration)
    parsed_bar = parse(test_input, relative=True)
    pitches = [[61], [86], [], [82], [78, 82, 85], [79], [], [76], [81, 84, 88]]
    for note, pitch_list in zip(parsed_bar, pitches):
        assert(note.pitches == pitch_list)
    for note, duration in zip(parsed_bar, durations):
        assert(note.duration == duration)
        
