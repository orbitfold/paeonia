from mido import Message
from paeonia.utils import download_sf2
import fluidsynth
import time

class Note:
    def __init__(self, pitches, duration, velocity):
        self.pitches = pitches
        self.duration = duration
        self.velocity = velocity
        
    def to_midi(self, tpb=480):
        """Return MIDI messages corresponding to this node.
        """
        messages = []
        for index, pitch in enumerate(self.pitches):
            messages.append(Message('note_on', note=int(pitch), velocity=int(127 * self.velocity), time=(0 if index < len(self.pitches) - 1 else int(tpb * 4 * self.duration))))
        for index, pitch in enumerate(self.pitches):
            messages.append(Message('note_off', note=int(pitch), velocity=127, time=0))
        return messages

    def preview(self, fs=None):
        """Preview a note using fluidsynth.
        """
        if fs is None:
            fs = fluidsynth.Synth()
            fs.start()
            sfid = fs.sfload(download_sf2())
            fs.program_select(0, sfid, 0, 0)
        for index, pitch in enumerate(self.pitches):
            fs.noteon(0, pitch, self.velocity)
        time.sleep(self.duration)
        for index, pitch in enumerate(self.pitches):
            fs.noteoff(0, pitch)
