import numpy as np

class Note:
    def __init__(self, note=None):
        self.chain = []
        self._history = []
        
    @property
    def note(self):
        distribution = self.chain[0].distribution
        for rule in self.chain[1:]:
            distribution = rule.distribution * distribution
            distribution = distribution / distribution.sum()
        self._history.append(np.random.choice(list(range(127)), p=distribution))
        return self._history[-1]
        
    def append(self, rule):
        self.chain.append(rule)
