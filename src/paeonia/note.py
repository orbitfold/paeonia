import numpy as np

class Note:
    def __init__(self):
        self.distribution = np.ones(127)
        self.normalize()
    
    def normalize(self):
        self.distribution = self.distribution / self.distribution.sum()

    def instantiate(self):
        return np.random.choice(list(range(127)), p=self.distribution)
