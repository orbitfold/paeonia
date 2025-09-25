from pypeg2 import optional, List, maybe_some
import pypeg2
import re
import paeonia
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

    def get_duration(self):
        d = str(self)
        idx = d.find('.')
        if idx < 0:
            return Fraction(1, int(d))
        else:
            return Fraction(1, int(d[:idx])) * (1 + Fraction(1, 2) * (len(d) - idx))        

# Define a note (combines NoteName, optional Accidental, OctaveIndicator, and Duration)
class Note(List):
    grammar = NoteName, optional(Accidental), optional(OctaveIndicator), optional(Duration)

    def get_note(self, octave=0, duration=Fraction('1/4'), relative=True):
        for c in self:
            if isinstance(c, NoteName):
                pitch = LETTER_TO_PITCH[str(c)]
            elif isinstance(c, Accidental):
                if c == '#':
                    pitch += 1
                else:
                    pitch -= 1
            elif isinstance(c, OctaveIndicator):
                for indicator in c:
                    if indicator == "'":
                        octave += 1
                    else:
                        octave -= 1
            elif isinstance(c, Duration):
                duration = c.get_duration()
        pitch = 60 + octave * 12 + pitch
        self.octave = octave
        return paeonia.Note(pitches=[pitch], duration=duration)

class Rest(List):
    grammar = "R", optional(Duration)

    def get_note(self, octave=0, duration=Fraction('1/4'), relative=True):
        self.octave = octave
        if self[0] is None:
            return paeonia.Note(pitches=[], duration=duration)
        else:
            return paeonia.Note(pitches=[], duration=self[0].get_duration())

# Define a chord (list of notes enclosed in < >, optionally followed by a duration)
class Chord(List):
    grammar = "<", maybe_some(Note), ">", optional(Duration)

    def get_note(self, octave=0, duration=Fraction('1/4'), relative=True):
        chord = []
        for note in self:
            if isinstance(note, Note):
                parsed_note = note.get_note(octave=(octave if relative else 0), duration=duration)
                octave = note.octave
                duration = parsed_note.duration
                chord.append(parsed_note.pitches[0])
            else:
                duration = note.get_duration()
        self.octave = octave
        return paeonia.Note(pitches=chord, duration=duration)

# Define a sequence of notes and chords
class Music(List):
    grammar = maybe_some([Note, Chord, Rest])

def parse(notation, relative=True):
    parsed_bar = pypeg2.parse(notation, Music)
    notes = []
    octave = 0
    duration = Fraction('1/4')
    for event in parsed_bar:
        parsed_note = event.get_note(octave=(octave if relative else 0), duration=duration, relative=relative)
        octave = event.octave
        duration = parsed_note.duration
        notes.append(parsed_note)
    return notes
