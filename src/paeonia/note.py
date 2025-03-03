from mido import Message, MetaMessage
from paeonia.utils import download_sf2, message_list_to_midi_file
import subprocess
import time
import os
import re

NOTE_VALUES = {
    'c': 0,
    'cs': 1,
    'cf': -1,
    'd': 2,
    'ds': 3,
    'df': 1,
    'e': 4,
    'es': 5,
    'ef': 3,
    'f': 5,
    'fs': 6,
    'ff': 4,
    'g': 7,
    'gs': 8,
    'gf': 6,
    'a': 9,
    'as': 10,
    'af': 8,
    'b': 11,
    'bs': 0,
    'bf': 10
}

class Note:
    def __init__(self, pitches=None, duration=None, velocity=0.75):
        if isinstance(pitches, str):
            p, d = self.parse_notation(pitches)
            self.pitches = [p]
            self.duration = d
        else:
            self.pitches = pitches
            self.duration = duration
            self.velocity = velocity

    def parse_notation(self, notation):
        m = re.match(r"[a-g](s|f)?", notation)
        pc = NOTE_VALUES[m.group()]
        notation = notation[len(m.group()):]
        m = re.match(r",*", notation)
        octave = 0
        if len(m.group()) > 0:
            octave = -12 * len(m.group())
        else:
            m = re.match(r"'*", notation)
            octave = 12 * len(m.group())
        pitch = 48 + octave + pc
        notation = notation[len(m.group()):]
        m = re.match(r"\d+\.?", notation)
        if m is None:
            duration = 0.25
        else:
            if m.string[-1] == '.':
                duration = (1.0 / int(m.group()[:-1])) * 1.5
            else:
                duration = 1.0 / int(m.group())
        return pitch, duration
        
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

    def preview(self, tpb=480):
        """Preview a note using fluidsynth.
        """
        messages = self.to_midi(tpb=tpb)
        messages.append(MetaMessage('end_of_track', time=0))
        midi_file = message_list_to_midi_file(messages, tpb)
        sf_file = download_sf2()
        subprocess.run(['fluidsynth', '-i', sf_file, midi_file])
        os.remove(midi_file)

