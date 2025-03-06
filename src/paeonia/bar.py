from mido import Message, MetaMessage
from paeonia.utils import download_sf2, message_list_to_midi_file
from paeonia import Note
import subprocess
import os
from string import Template
import importlib
import tempfile
from IPython.display import display, Image
from copy import copy

class Bar:
    def __init__(self, notes=None):
        if notes is None:
            self.notes = []
        else:
            self.notes = notes

    def __copy__(self):
        new_notes = [copy(note) for note in self.notes]
        return Bar(notes=new_notes)

    def __add__(self, other):
        if isinstance(other, Bar):
            self_copy = copy(self)
            for note in other.notes:
                self_copy.notes.append(note)
            return self_copy
        else:
            new_bar = Bar()
            for note in self.notes:
                new_bar.notes.append(note + other)
            return new_bar

    def __sub__(self, other):
        new_bar = Bar()
        for note in self.notes:
            new_bar.notes.append(note - other)
        return new_bar

    def __mul__(self, other):
        new_bar = Bar()
        for note in self.notes:
            new_bar.notes.append(note * other)
        return new_bar

    def __div__(self, other):
        new_bar = Bar()
        for note in self.notes:
            new_bar.notes.append(note / other)
        return new_bar

    def repeat(self, times):
        """Repeat the bar multiple times and append to itself.

        Parameters
        ----------
        times: int
            How many times to repeat the bar

        Returns
        -------
        Bar
            A new bar with the contents repeatest
        """
        new_bar = Bar()
        for _ in range(times):
            new_bar = new_bar + self
        return new_bar

    def span(self):
        """"Return the span of the bar (sum of duration of all notes).

        Returns
        -------
        Fraction
            Sum of the durations of the notes in the bar
        """
        return sum([note.duration for note in self.notes])

    def add_note(self, note):
        """Append a new note to the bar.

        Parameters
        ----------
        note: Note
           A note to add
        """
        self.notes.append(note)

    def retrograde(self):
        """Return a bar with a retrograde pitch variant.
        Durations are unaffected.

        Returns
        -------
        Bar
            A fresh new bar with pitches in reverse order
        """
        new_bar = Bar()
        pitches = [note.pitches for note in self.notes if note.pitches is not None]
        reversed_pitches = list(reversed(pitches))
        for note in self.notes:
            if note.pitches is None:
                new_bar.add_note(copy(note))
            else:
                new_bar.add_note(Note(pitches=reversed_pitches.pop(0), duration=note.duration))
        return new_bar

    def to_midi(self, offset=0, tpb=480):
        """Return MIDI messages corresponding to this bar.
        """
        messages = []
        for note in self.notes:
            if note.pitches is None:
                offset += int(tpb * 4 * note.duration)
            else:
                messages += note.to_midi(offset, tpb)
                offset = 0
        return messages, offset

    def to_lilypond(self):
        """Return lilypond notation representaiton of this bar.

        Returns
        -------
        str
            Lilypond notation representing all the notes in the bar
        """
        return " ".join([note.to_lilypond() for note in self.notes])

    def show(self):
        """Attempts to render a lilypond file and display it on a Jupyter notebook.
        """
        template = Template(importlib.resources.open_text('paeonia.data', 'bar_template.ly').read())
        with tempfile.TemporaryDirectory() as tmpdir:
            notation = template.substitute(notation=self.to_lilypond())
            with open(os.path.join(tmpdir, 'notation.ly'), 'w') as fd:
                fd.write(notation)
            subprocess.run(['lilypond', '-dpreview', '-dresolution=300', '--loglevel=ERROR',
                            '-fpng', os.path.join(tmpdir, 'notation.ly')], cwd=tmpdir)
            display(Image(filename=os.path.join(tmpdir, 'notation.png')))

    def play(self, tpb=480):
        """Preview a note using fluidsynth.
        """
        messages, _ = self.to_midi(tpb=tpb)
        messages.append(MetaMessage('end_of_track', time=0))
        midi_file = message_list_to_midi_file(messages, tpb)
        sf_file = download_sf2()
        subprocess.run(['fluidsynth', '-i', sf_file, midi_file],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.remove(midi_file)
