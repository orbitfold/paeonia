class Score:
    def __init__(self):
        self.voices = []

    def to_midi(self, path):
        for voice in self.voices:
            for bar in voice.bars:
                pass
                
    def add_voice(self, voice):
        self.voices.append(voice)
