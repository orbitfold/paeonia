from mido import Message, MetaMessage
from paeonia.utils import download_sf2, message_list_to_midi_file
import tempfile
import subprocess
import time
import os
import re
from string import Template
from IPython.display import display, Image
import importlib
from copy import copy

class Note:
    def __init__(self, pitches=None, duration=None, velocity=0.75):
        self.pitches = pitches
        self.duration = duration
        self.velocity = velocity

    def __copy__(self):
        if self.pitches is None:
            return Note(pitches=None, duration=self.duration)
        else:
            return Note(pitches=list(self.pitches), duration=self.duration)

    def __eq__(self, other):
        return self.pitches == other.pitches and self.duration == other.duration

    def __add__(self, other):
        if self.pitches is not None:
            new_note = copy(self)
            new_note.pitches = [pitch + other for pitch in self.pitches]
            return new_note
        else:
            return copy(self)

    def __sub__(self, other):
        if self.pitches is not None:
            new_note = copy(self)
            new_note.pitches = [pitch - other for pitch in self.pitches]
            return new_note
        else:
            return copy(self)

    def __mul__(self, other):
        new_note = copy(self)
        new_note.duration *= other
        return new_note

    def __truediv__(self, other):
        new_note = copy(self)
        new_note.duration /= other
        return new_note
        
    def to_midi(self, offset=0, tpb=480):
        """Return MIDI messages corresponding to this note.
        """
        messages = []
        for index, pitch in enumerate(self.pitches):
            messages.append(Message('note_on', note=int(pitch), velocity=int(127 * self.velocity), time=offset))
        messages.append(Message('note_off', note=int(self.pitches[0]), velocity=127, time=int(tpb * 4 * self.duration)))
        for index, pitch in enumerate(self.pitches[1:]):
            messages.append(Message('note_off', note=int(pitch), velocity=127, time=0))
        return messages

    @staticmethod
    def note_to_lilypond(pitch):
        """Convert a pitch to lilypond note name with octave identifier.

        Parameters
        ----------
        pitch: int
            MIDI pitch

        Returns
        -------
        str
            Lilypond notation note
        """
        if pitch is None:
            return "r"
        conversion = {
            0: 'c',
            1: 'cis',
            2: 'd',
            3: 'dis',
            4: 'e',
            5: 'f',
            6: 'fis',
            7: 'g',
            8: 'gis',
            9: 'a',
            10: 'ais',
            11: 'b',
        }
        name = conversion[int(pitch) % 12]
        octave = int(pitch) // 12 - 4
        if octave < 0:
            octave_identifier = "," * (-octave)
        elif octave > 0:
            octave_identifier = "'" * octave
        else:
            octave_identifier = ""
        return name + octave_identifier

    @staticmethod
    def duration_to_lilypond(duration):
        """Convert fractional duration to a lilypond duration notation.

        Parameters
        ----------
        duration: Fraction
            Duration as a fraction

        Returns
        -------
        str
            Lilypond duration
        """
        if duration.numerator == 1:
            return str(duration.denominator)
        else:
            n = duration.numerator
            d = duration.denominator
            no_dot = d // 2
            n_dots = n // 2
            return f"{no_dot}" + "." * n_dots

    def to_lilypond(self):
        """Return lilypond representation of this note.

        Returns
        -------
        str
            Lilypond representation 
        """
        if self.pitches is None:
            return "r" + Note.duration_to_lilypond(self.duration)
        elif len(self.pitches) < 2:
            return Note.note_to_lilypond(self.pitches[0]) + Note.duration_to_lilypond(self.duration)
        else:
            return "<" + " ".join([Note.note_to_lilypond(note) for note in self.pitches]) + ">" + Note.duration_to_lilypond(self.duration)

    def show(self):
        """Attempts to render a lilypond file and display it on a Jupyter notebook.
        """
        template = Template(importlib.resources.open_text('paeonia.data', 'note_template.ly').read())
        with tempfile.TemporaryDirectory() as tmpdir:
            notation = template.substitute(notation=self.to_lilypond())
            with open(os.path.join(tmpdir, 'notation.ly'), 'w') as fd:
                fd.write(notation)
            subprocess.run(['lilypond', '-dpreview', '-dresolution=300', '--loglevel=ERROR',
                            '-fpng', os.path.join(tmpdir, 'notation.ly')], cwd=tmpdir)
            display(Image(filename=os.path.join(tmpdir, 'notation.png')))
        return self


    def play(self, tpb=480):
        """Preview a note using fluidsynth.
        """
        messages = self.to_midi(tpb=tpb)
        messages.append(MetaMessage('end_of_track', time=0))
        midi_file = message_list_to_midi_file(messages, tpb)
        sf_file = download_sf2()
        subprocess.run(['fluidsynth', '-i', sf_file, midi_file],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.remove(midi_file)
        return self

