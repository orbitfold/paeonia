from mido import Message, MidiFile, MidiTrack

class Score:
    def __init__(self):
        self.voices = []

    def to_midi(self, path, tpb=480):
        """Write the score to MIDI file.
    
        Parameters
        ----------
        path: str
            A filename to write to.
        """
        mid = MidiFile(ticks_per_beat=tpb)
        for voice in self.voices:
            track = MidiTrack() 
            mid.tracks.append(track)
            for bar in voice.bars:
                for note in bar.notes:
                    for pitch in note.pitches:
                        track.append(Message('note_on', note=int(pitch), velocity=int(127 * note.velocity), time=int(4 * tpb * note.duration)))
                        track.append(Message('note_off', note=int(pitch), velocity=127, time=0))
        mid.save(path)
                
    def add_voice(self, voice):
        """Add a voice to this score.

        Parameters
        ----------
        voice: Voice
            A Voice to add to the Score.
        """
        self.voices.append(voice)
