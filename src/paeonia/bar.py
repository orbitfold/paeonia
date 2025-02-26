from mido import Message, MetaMessage
from paeonia.utils import download_sf2, message_list_to_midi_file
import subprocess
import os

class Bar:
    def __init__(self, notes=None):
        if notes is None:
            self.notes = []
        else:
            self.notes = notes

    def add_note(self, note):
        """Append a new note to the bar.

        Parameters
        ----------
        note: Note
           A note to add
        """
        self.notes.append(note)

    def to_midi(self, tpb=480):
        """Return MIDI messages corresponding to this bar.
        """
        messages = []
        offset = 0
        for note in self.notes:
            if note.pitches is None:
                offset += int(tpb * 4 * note.duration)
            else:
                messages += note.to_midi(offset, tpb)
                offset = 0
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
