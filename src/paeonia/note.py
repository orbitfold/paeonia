import numpy as np

class Note:
    def __init__(self, note=None, duration=1.0):
        if note is None:
            self.distribution = np.ones(127)
            self.normalize()
        else:
            self.note = note
        self.duration = duration
    
    def normalize(self):
        self.distribution = self.distribution / self.distribution.sum()

    @property
    def note(self):
        return np.random.choice(list(range(127)), p=self.distribution)
    
    @note.setter
    def note(self, value):
        self.distribution = np.zeros(127)
        self.distribution[value] = 1.0
