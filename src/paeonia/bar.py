class Bar:
    def __init__(self, notes=[]):
        self.notes = notes

    def add_note(self, note):
        """Append a new note to the bar.

        Parameters
        ----------
        note: Note
           A note to add
        """
        self.notes.append(note)
