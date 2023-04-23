class Bar:
    def __init__(self):
        self.notes = {}
    
    def add_note(self, note, offset):
        try:
            self.notes[offset].append(note)
        except KeyError:
            self.notes[offset] = [note]
        
    def to_midi(self, channel):
        pass
