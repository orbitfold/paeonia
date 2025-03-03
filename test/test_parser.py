from paeonia.parser import np
import paeonia
from fractions import Fraction

def test_np():
    test_input = "C#4. D''8.. R2. Bb,16 <F# A# C#'>2. G, R E4.. <A C' E>1"
    parsed_bar = np(test_input, relative=False)
    pitches = [[49], [74], None, [46], [54, 58, 61], [43], None, [52], [57, 60, 52]]
    for note, pitch_list in zip(parsed_bar.notes, pitches):
        assert(note.pitches == pitch_list)
    durations = [Fraction('3/8'), Fraction('1/4'), Fraction('3/4'), Fraction('1/16'),
                 Fraction('3/4'), Fraction('1/4'), Fraction('1/4'), Fraction('1/2'),
                 Fraction('1/1')]
    for note, duration in zip(parsed_bar.notes, durations):
        assert(note.duration == duration)
    parsed_bar = np(test_input, relative=True)
    pitches = [[49], [74], None, [70], [66, 70, 73], [67], None, [64], [69, 72, 76]]
    for note, pitch_list in zip(parsed_bar.notes, pitches):
        assert(note.pitches == pitch_list)
    for note, duration in zip(parsed_bar.notes, durations):
        assert(note.duration == duration)
        


