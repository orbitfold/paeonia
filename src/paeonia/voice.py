class Voice:
    def __init__(self):
        pass

    def to_midi(self, channel):
        return sum([bar.to_midi(channel) for bar in self], [])
