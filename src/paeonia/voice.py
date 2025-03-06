from mido import MetaMessage
from paeonia.utils import download_sf2, message_list_to_midi_file
import subprocess
import os

class Voice:
    def __init__(self, bars=None):
        if bars is None:
            self.bars = []
        else:
            self.bars = bars

    def __getitem__(self, i):
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

    def play(self, tpb=480):
        """Preview a note using fluidsynth.
        """
        messages = self.to_midi(tpb=tpb)
        messages.append(MetaMessage('end_of_track', time=0))
        midi_file = message_list_to_midi_file(messages, tpb)
        sf_file = download_sf2()
        subprocess.run(['fluidsynth', '-i', sf_file, midi_file])
        os.remove(midi_file)
        return self
