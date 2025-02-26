from mido import Message, MetaMessage
from paeonia.utils import download_sf2, message_list_to_midi_file
import subprocess
import time
import os

class Note:
    def __init__(self, pitches, duration, velocity):
        self.pitches = pitches
        self.duration = duration
        self.velocity = velocity
        
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

