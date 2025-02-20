class Bar:
    def __init__(self, notes=[]):
        self.notes = notes

    def add_note(self, note):
        self.notes.append(note)
