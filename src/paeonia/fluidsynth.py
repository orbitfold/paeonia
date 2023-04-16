import fluidsynth
import time

class FluidSynthProcessor:
    def __init__(self, soundfont):
        self.fs = fluidsynth.Synth(samplerate=44100.0)
        self.fs.start()
        self.sfid = self.fs.sfload(soundfont)
        self.fs.program_select(0, self.sfid, 0, 0)

    def process(self):
        self.fs.noteon(0, 60, 80)
        time.sleep(1.0)
        self.fs.noteoff(0, 60)
        time.sleep(1.0)

    def destroy(self):
        self.fs.delete()
