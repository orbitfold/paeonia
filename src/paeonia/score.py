from mido import Message, MidiFile, MidiTrack, MetaMessage
import tempfile
from paeonia.utils import download_sf2, render_and_play_midi
import os
import subprocess
import importlib
from string import Template
import tempfile
from IPython.display import display, Image

class Score:
    def __init__(self):
        self.voices = {}
        self.clefs = {}

    def __getitem__(self, idx):
        return self.voices[idx]

    def __setitem__(self, idx, voice):
        self.voices[idx] = voice
        self.clefs[idx] = "treble"

    def set_clef(self, voice, clef):
        """Set a type of clef used for a voice.

        Parameters
        ----------
        voice: str
            Voice name
        clef: str
            Clef name (treble, alto, tenor, bass)
        """
        assert(clef in ["treble", "alto", "tenor", "bass"])
        self.clefs[voice] = clef

    def to_midi(self, path, tpb=480):
        """Write the score to MIDI file.
    
        Parameters
        ----------
        path: str
            A filename to write to.
        """
        mid = MidiFile(ticks_per_beat=tpb)
        for key in self.voices:
            track = MidiTrack() 
            voice = self[key]
            track += voice.to_midi(tpb)
            track.append(MetaMessage('end_of_track', time=0))
            mid.tracks.append(track)
        mid.save(path)

    def show(self):
        """Attempts to render a lilypond file and display it on a Jupyter notebook.
        """
        template = Template(importlib.resources.open_text('paeonia.data', 'score_template.ly').read())
        with tempfile.TemporaryDirectory() as tmpdir:
            score_lilypond = []
            for voice_name in self.voices:
                score_lilypond.append("\\new Staff")
                score_lilypond.append(f"{{ \\clef {self.clefs[voice_name]} {self.voices[voice_name].to_lilypond()} \\bar \"|.\" \\break}}")
            score_notation = "\n".join(score_lilypond)
            notation = template.substitute(notation=score_notation)
            with open(os.path.join(tmpdir, 'notation.ly'), 'w') as fd:
                fd.write(notation)
            subprocess.run(['lilypond', '--loglevel=ERROR',
                            '-fpng', os.path.join(tmpdir, 'notation.ly')], cwd=tmpdir)
            display(Image(filename=os.path.join(tmpdir, 'notation.png')))
        return self

    def play(self, tpb=480, autoplay=False):
        """Preview the score using fluidsynth
        """
        midi = MidiFile(ticks_per_beat=tpb)
        for key in self.voices:
            track = MidiTrack() 
            voice = self[key]
            track += voice.to_midi(tpb)
            track.append(MetaMessage('end_of_track', time=0))
            midi.tracks.append(track)
        render_and_play_midi(midi, tpb, autoplay=autoplay)
        return self
