import numpy as np

class Note:
    def __init__(self, note=None, duration=1.0):
        self.chain = []
        self.duration = duration

    @property
    def note(self):
        distribution = self.chain[0].distribution
        for rule in self.chain[1:]:
            distribution = rule.distribution * distribution
            distribution = distribution / distribution.sum()
        return np.random.choice(list(range(127)), p=distribution)

    def append(self, rule):
        self.chain.append(rule)
