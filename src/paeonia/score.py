class Score:
    def __init__(self):
        self.voices = []

    def to_midi(self, path):
        for voice in self.voices:
            for bar in voice.bars:
                pass
                
    def add_voice(self, voice):
        """Add a voice to this score.

        Parameters
        ----------
        voice: Voice
            A Voice to add to the Score.
        """
        self.voices.append(voice)
