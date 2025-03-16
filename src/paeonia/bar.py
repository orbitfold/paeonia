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
import random

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
                           len(self) if i.stop is None else (i.stop if i.stop > 0 else len(self) + i.stop),
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

    def note_repeat(self, times):
        """Repeat notes according to the pattern provided.

        Parameters
        ----------
        times: list
            A list with repeat values (will be cycled if it runs out).

        Returns
        -------
        Generator
            A generator of repeated notes.
        """
        times = cycle(times)
        notes = cycle(self)
        while True:
            time = next(times)
            note = next(notes)
            for _ in range(time):
                yield note

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

    def pitches(self):
        """Returns all pitches in this bar as a single flat list.

        Returns
        -------
        list
             A list of numbers signifying pitches.
        """
        result = []
        for note in self:
            if note.pitches is not None:
                result += note.pitches
        return result

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
        pitches = []
        for note in self:
            if note.pitches is not None:
                pitches += note.pitches
        new_pitches = fn(pitches)
        assert(len(pitches) == len(new_pitches))
        for note in self:
            if note.pitches is None:
                new_bar.add_note(copy(note))
            else:
                new_bar.add_note(Note(pitches=[new_pitches.pop(0) for _ in note.pitches], duration=note.duration))
        return new_bar

    def intervals(self):
        """Get a list of intervals for this bar.

        Returns
        -------
        list
            A list of lists of intervals.
        """
        pitches = self.pitches()
        return [b - a for a, b in zip(pitches[:-1], pitches[1:])]

    def retrograde(self):
        """Return a bar with a retrograde pitch variant.
        Durations are unaffected.

        Returns
        -------
        Bar
            A fresh new bar with pitches in reverse order
        """
        return self.pitch_variant(lambda pitch_list: list(reversed(pitch_list)))

    def inversion(self):
        """Return a bar with intervals inverted.

        Returns
        -------
        Bar
            A bar with invervals inverted
        """
        def invert(pitch_list):
            intervals = self.intervals()
            pitches = self.pitches()
            result = [pitches[0]]
            for interval in intervals:
                result.append(result[-1] - interval)
            return result
        return self.pitch_variant(invert)

    def ascending(self):
        """Return a bar with pitches in ascending order.

        Returns
        -------
        Bar
            A new bar with pitches in ascending order.
        """
        return self.pitch_variant(lambda pitch_list: list(sorted(pitch_list)))

    def descending(self):
        """Returns a bar with pitches in descending order.

        Returns
        -------
        Bar
            A new bar with pitches in descending order.
        """
        return self.pitch_variant(lambda pitch_list: list(sorted(pitch_list, key=lambda x: -x)))

    def random_order(self, seed=7):
        """Returns a bar with pitches in random order.

        Returns
        -------
        Bar
            A new bar with pitches in random order.
        """
        def shuffle(pitch_list):
            rnd = random.Random(seed)
            new_pitch_list = list(pitch_list)
            rnd.shuffle(new_pitch_list)
            return new_pitch_list
        return self.pitch_variant(shuffle)

    def cycle(self):
        """Create a Note generator that returns the notes in this bar in a loop.

        Returns
        -------
        Generator
            Returns an infinite stream of repeating notes
        """
        return cycle(self)

    def take(self, generator, pitches=False, durations=False, velocities=False):
        """Take specified note properties from a Note generator.

        Parameters
        ----------
        generator: Generator
            A Note generator
        pitches: bool
            Whether to take pitches
        durations: bool
            Whether to take durations
        velocities: bool
            Whether to take velocities
        """
        for note in self:
            next_note = next(generator)
            if pitches:
                note.pitches = list(next_note.pitches)
            if durations:
                note.duration = next_note.duration
            if velocities:
                note.velocity = next_note.velocity

    def tonal_transpose(self, tonality, degrees):
        """Transpose this bar staying in the same tonality.

        Parameters
        ----------
        tonality: Tonality
            Tonality we are working in.
        degrees: int
            How many scale degrees to shift by (up or down).

        Returns
        -------
        Bar
            A bar with notes tranposed.
        """
        return self

    def map_tonality(self, tonality, method="random", seed=7):
        """Map all notes in the bar to a tonality.

        Parameters
        ----------
        tonality: Tonality
            An instance of Tonality.

        Returns
        -------
        Bar
            A bar with notes mapped to a tonality.
        """
        new_bar = Bar()
        rnd = random.Random(seed)
        for note in self:
            new_bar += note.map_tonality(tonality, method=method, rnd=rnd)
        return new_bar

    def map_melody_to_tonality(self, tonality):
        """Attempts to map notes in the bar to a tonality while maintaining
        the shape of the melody.

        Parameters
        ----------
        tonality: Tonality
            An instance of Tonality.

        Returns
        -------
        Bar
            A bar with notes mapped to a tonality.
        """
        return copy(self)

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
            subprocess.run(['lilypond', '-dpreview', '--loglevel=ERROR',
                            '-fpng', os.path.join(tmpdir, 'notation.ly')], cwd=tmpdir)
            display(Image(filename=os.path.join(tmpdir, 'notation.preview.png')))
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
