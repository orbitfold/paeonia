from mido import Message, MetaMessage
from paeonia.utils import download_sf2, message_list_to_midi_file
from paeonia.parser import parse
from paeonia import Note
import subprocess
import os
from string import Template
import importlib
import tempfile
from IPython.display import display, Image
from copy import copy
from itertools import cycle
from fractions import Fraction

class Bar:
    def __init__(self, notes=None):
        if notes is None:
            self.notes = []
        elif isinstance(notes, str):
            self.notes = parse(notes)
        else:
            self.notes = notes

    def __copy__(self):
        new_notes = [copy(note) for note in self.notes]
        return Bar(notes=new_notes)

    def __eq__(self, other):
        return all(note1 == note2 for note1, note2 in zip(self, other))

    def __add__(self, other):
        if isinstance(other, Bar):
            self_copy = copy(self)
            for note in other.notes:
                self_copy.notes.append(copy(note))
            return self_copy
        elif isinstance(other, Note):
            self_copy = copy(self)
            self_copy.add_note(other)
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

    def __truediv__(self, other):
        new_bar = Bar()
        for note in self.notes:
            new_bar.notes.append(note / other)
        return new_bar

    def __getitem__(self, i):
        if isinstance(i, slice):
            new_bar = Bar()
            for j in range(0 if i.start is None else i.start,
                           len(self) if i.stop is None else i.stop,
                           1 if i.step is None else i.step):
                new_bar.add_note(self[j])
            return new_bar
        else:
            return self.notes[i]

    def __setitem__(self, i, note):
        self.notes[i] = note

    def __len__(self):
        return len(self.notes)

    def __str__(self):
        return self.to_paeonia()

    def __repr__(self):
        return f"Bar(\"{str(self)}\")"

    def pitch_repeat(self, times):
        """Repeat pitches in the bar specified number of times while keeping
        the same rhythm (the durations from the original bar will be cycled).
        This is a deceptively powerful method that can result in interesting
        generative melodies if the times list is chosen appropriately.

        Parameters
        ----------
        times: list
            A list with repeat values (will be cycled if it runs out)

        Returns
        -------
        Bar
            A new bar with pitches repeated
        """
        durations = cycle([note.duration for note in self.notes])
        times = cycle(times)
        pitches = [note.pitches for note in self.notes]
        new_bar = Bar()
        for pitch in pitches:
            for _ in range(next(times)):
                new_bar.add_note(Note(pitches=pitch, duration=next(durations)))
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

    def pitch_variant(self, fn):
        """General pitch variant method. Applies a given function to the pitches in bar.
        Durations and rests are unaffected.

        Parameters
        ----------
        fn: function
            Takes a list of pitches, returns a list of pitches of the same length

        Returns
        -------
        Bar
            New, processed bar
        """
        new_bar = Bar()
        pitches = [note.pitches for note in self if note.pitches is not None]
        new_pitches = fn(pitches)
        assert(len(pitches) == len(new_pitches))
        for note in self:
            if note.pitches is None:
                new_bar.add_note(copy(note))
            else:
                new_bar.add_note(Note(pitches=new_pitches.pop(0), duration=note.duration))
        return new_bar

    def retrograde(self):
        """Return a bar with a retrograde pitch variant.
        Durations are unaffected.

        Returns
        -------
        Bar
            A fresh new bar with pitches in reverse order
        """
        return self.pitch_variant(lambda pitch_list: list(reversed(pitch_list)))

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

    def to_paeonia(self):
        """Return paeonia notation representation of this bar.

        Returns
        -------
        str
            Lilypond notation representing all the notes in the bar
        """
        octave = 0
        duration = Fraction("1/4")
        note_repr, octave = self[0].to_paeonia(previous_octave=octave, previous_duration=duration)
        duration = self[0].duration
        result = note_repr
        for note in self[1:]:
            note_repr, octave = note.to_paeonia(previous_octave=octave, previous_duration=duration)
            duration = note.duration
            result += " " + note_repr
        return result
            

    def to_lilypond(self):
        """Return lilypond notation representation of this bar.

        Returns
        -------
        str
            Lilypond notation representing all the notes in the bar
        """
        return " ".join([note.to_lilypond() for note in self])

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
        return self

    def play(self, tpb=480):
        """Preview a note using fluidsynth.
        """
        messages, _ = self.to_midi(tpb=tpb)
        messages.append(MetaMessage('end_of_track', time=0))
        midi_file = message_list_to_midi_file(messages, tpb)
        sf_file = download_sf2()
        subprocess.run(['fluidsynth', '-i', sf_file, midi_file],
                       stdout=subprocess.DEVNULL)
        os.remove(midi_file)
        return self
