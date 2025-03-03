from pypeg2 import parse, optional, List, maybe_some
import re
from paeonia import Note as Note_
from paeonia import Bar
from fractions import Fraction

LETTER_TO_PITCH = {
    'C': 0,
    'D': 2,
    'E': 4,
    'F': 5,
    'G': 7,
    'A': 9,
    'B': 11,
}

# Define a note name (A-G)
class NoteName(str):
    grammar = re.compile(r"[A-G]")

# Define accidentals (# for sharp, b for flat)
class Accidental(str):
    grammar = re.compile(r"[#b]")

# Define octave indicators (' and ,)
class OctaveIndicator(str):
    grammar = re.compile(r"[',]*")  # Can be multiple (e.g., "C''", "D,,")

# Define a duration with at most two dots (e.g., "4.", "8..", "16").
class Duration(str):
    grammar = re.compile(r"[0-9]+\.{0,2}")  # Allows "4", "8.", or "16.."

# Define a note (combines NoteName, optional Accidental, OctaveIndicator, and Duration)
class Note(List):
    grammar = NoteName, optional(Accidental), optional(OctaveIndicator), optional(Duration)

class Rest(List):
    grammar = "R", optional(Duration)

# Define a chord (list of notes enclosed in < >, optionally followed by a duration)
class Chord(List):
    grammar = "<", maybe_some(Note), ">", optional(Duration)

# Define a sequence of notes and chords
class Music(List):
    grammar = maybe_some([Note, Chord, Rest])

def parse_duration(duration):
    d = str(duration)
    idx = d.find('.')
    if idx < 0:
        return Fraction(1, int(d))
    else:
        return Fraction(1, int(d[:idx])) * (1 + Fraction(1, 2) * (len(d) - idx))

def parse_note(event, octave=0):
    duration = Fraction(1, 4)
    pitch = None
    for c in event:
        if type(c) == NoteName:
            pitch = LETTER_TO_PITCH[str(c)]
        elif type(c) == Accidental:
            if c == '#':
                pitch += 1
            else:
                pitch -= 1
        elif type(c) == OctaveIndicator:
            for indicator in c:
                if indicator == "'":
                    octave += 1
                else:
                    octave -= 1
        elif type(c) == Duration:
            duration = parse_duration(c)
    pitch = 48 + octave * 12 + pitch
    return pitch, octave, duration

def parse_rest(event):
    if event[0] is None:
        return Fraction(1, 4)
    else:
        return parse_duration(event[0])

def np(notation, relative=True):
    parsed_bar = parse(notation, Music)
    notes = []
    octave = 0
    for event in parsed_bar:
        if type(event) == Note:
            p, o, d = parse_note(event, octave=(octave if relative else 0))
            octave = o
            notes.append(Note_(pitches=[p], duration=d))
        elif type(event) == Rest:
            d = parse_rest(event)
            notes.append(Note_(None, duration=d))
        else:
            chord = []
            for note in event:
                if type(note) == Note:
                    p, o, d = parse_note(note, octave=(octave if relative else 0))
                    octave = o
                    chord.append(p)
                else:
                    duration = parse_duration(note)
            notes.append(Note_(pitches=chord, duration=duration))
    if len(notes) == 1:
        return notes[0]
    elif len(notes) > 1:
        return Bar(notes)
