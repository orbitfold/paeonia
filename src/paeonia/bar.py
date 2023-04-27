import mido

# [1/4, n1, n2, [n1, n2], -1/4]

class Bar:
    def __init__(self, bar):
        self.bar = bar
        
    def to_midi(self):
        duration = 1.0
        for event in self.bar:
            pass
