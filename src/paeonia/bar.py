PPQN = 64

class Bar:
    def __init__(self):
        pass

    def to_midi(self, channel):
        midi = []
        for note in self:
            if note.is_rest:
                for _ in range(note.duration * 4.0 * PPQN):
                    midi.append([])
            else:
                midi.append([9 * 16 + channel, note.note, note.velocity])
                for _ in range(note.duration * 4.0 * PPQN - 1):
                    midi.append([])
                midi.append([8 * 16 + channel, note.note, note.velocity])
        return midi
