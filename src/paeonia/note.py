import numpy as np

class Note:
    def __init__(self, note=None, duration=1):
        if note is None:
            self.distribution = np.ones(127)
        else:
            self.distribution = np.zeros(127)
            self.distribution[note] = 1.0
        self.normalize()
    
    def normalize(self):
        self.distribution = self.distribution / self.distribution.sum()

    def instantiate(self):
        return np.random.choice(list(range(127)), p=self.distribution)
