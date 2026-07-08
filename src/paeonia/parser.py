from pypeg2 import optional, List, maybe_some
import pypeg2
import re
from fractions import Fraction
from .pitch import PitchClass, Pitch

LETTER_TO_PITCH = {
    'C': 0,
    'D': 2,
    'E': 4,
    'F': 5,
    'G': 7,
    'A': 9,
    'B': 11,
}


def make_note(pitches=(), duration=Fraction('1/4')):
    from .note import Note as PaeoniaNote

    return PaeoniaNote(pitches=tuple(pitches), duration=duration)

# Define a note name (A-G)
class NoteName(str):
    grammar = re.compile(r"[A-G]")

# Define accidentals (# for sharp, b for flat)
class Accidental(str):
    grammar = re.compile(r"(?:##|bb|#|b)")

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
        letter = None
        accidental = 0

        for component in self:
            if isinstance(component, NoteName):
                letter = str(component)
            elif isinstance(component, Accidental):
                symbols = str(component)
                accidental = symbols.count("#") - symbols.count("b")
            elif isinstance(component, OctaveIndicator):
                for indicator in component:
                    octave += 1 if indicator == "'" else -1
            elif isinstance(component, Duration):
                duration = component.get_duration()

        if letter is None:
            raise ValueError("Parsed note has no letter")

        pitch = Pitch(
            PitchClass(letter, accidental),
            octave = 4 + octave,
        )
        self.octave = octave
        return make_note(pitches=(pitch,), duration=duration)

class Rest(List):
    grammar = "R", optional(Duration)

    def get_note(self, octave=0, duration=Fraction('1/4'), relative=True):
        self.octave = octave
        if self[0] is None:
            return make_note(duration=duration)
        else:
            return make_note(duration=self[0].get_duration())

# Define a chord (list of notes enclosed in < >, optionally followed by a duration)
class Chord(List):
    grammar = "<", maybe_some(Note), ">", optional(Duration)

    def get_note(self, octave=0, duration=Fraction('1/4'), relative=True):
        pitches = []
        chord_duration = duration

        for component in self:
            if isinstance(component, Note):
                parsed_note = component.get_note(
                    octave=(octave if relative else 0),
                    duration=chord_duration,
                    relative=relative,
                )
                octave = component.octave
                chord_duration = parsed_note.duration
                pitches += parsed_note.pitches
            elif isinstance(component, Duration):
                chord_duration = component.get_duration()

        self.octave = octave
        return make_note(pitches=pitches, duration=chord_duration)

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
