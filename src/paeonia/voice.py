from mido import MetaMessage, MidiFile, MidiTrack
from paeonia.utils import download_sf2, message_list_to_midi_file, render_and_play_midi
import subprocess
import os
from copy import copy
from string import Template
import importlib
import tempfile
from IPython.display import display, Image

class Voice:
    def __init__(self, bars=None):
        if bars is None:
            self.bars = []
        else:
            self.bars = bars

    def __getitem__(self, i):
        if isinstance(i, slice):
            new_voice = Voice()
            for j in range(0 if i.start is None else i.start,
                           len(self) if i.stop is None else i.stop,
                           1 if i.step is None else i.step):
                new_voice.add_bar(copy(self[j]))
            return new_voice
        else:
            return self.bars[i]

    def __setitem__(self, i, bar):
        self.bars[i] = bar

    def __len__(self):
        return len(self.bars)

    def add_bar(self, bar):
        """Add a new bar to this voice.

        Parameters
        ----------
        bar: Bar
            A Bar object
        """
        self.bars.append(bar)

    def to_midi(self, tpb=480):
        """Return MIDI messages corresponding to this voice.
        """
        message_stream = []
        offset = 0
        for bar in self.bars:
            messages, offset = bar.to_midi(offset, tpb)
            message_stream += messages
        return message_stream

    def to_lilypond(self):
        """Return lilypond notation representing this voice.

        Returns
        -------
        str
            Lilypond notation representing the voice
        """
        return " ".join([bar.to_lilypond() for bar in self])

    def show(self):
        """Attempts to render a lilypond file and display it on a Jupyter notebook.
        """
        template = Template(importlib.resources.open_text('paeonia.data', 'voice_template.ly').read())
        with tempfile.TemporaryDirectory() as tmpdir:
            notation = template.substitute(notation=self.to_lilypond())
            with open(os.path.join(tmpdir, 'notation.ly'), 'w') as fd:
                fd.write(notation)
            subprocess.run(['lilypond', '--loglevel=ERROR', '-dno-page-breaking',
                            '-fpng', os.path.join(tmpdir, 'notation.ly')], cwd=tmpdir)
            display(Image(filename=os.path.join(tmpdir, 'notation.png')))
        return self

    def play(self, tpb=480):
        """Preview a note using fluidsynth.
        """
        messages = self.to_midi(tpb=tpb)
        messages.append(MetaMessage('end_of_track', time=0))
        midi = MidiFile(ticks_per_beat=tpb)
        track = MidiTrack()
        for message in messages:
            track.append(message)
        midi.tracks.append(track)
        render_and_play_midi(midi, tpb)
        return self
