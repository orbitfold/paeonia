import numpy as np

class Scale:
  def __init__(self, mode=0, strength=1.0):
    n = (5 / 12.) * (1.0 - strength)
    w = (7 / 12.) * strength
    scale = np.array([w, n, w, n, w, w, n, w, n, w, n, w])
    scale = np.roll(scale, mode)
    self.p = list(scale) * 5 + (list(scale) * 6)[:-5]
    self.p = self.p / sum(self.p)
  
  @property
  def distribution(self):
    return self.p

 
class Range:
  def __init__(self, a, b):
    assert(a < b)
    self.a = a
    self.b = b
    
  @property
  def distribution(self):
    distribution = np.zeros(127)
    distribution[self.a:self.b] = np.ones(self.b - self.a)
    distribution = distribution / distribution.sum()
    return distribution

  
class Walk:
  def __init__(self, note, weights=[1, 1, 2, 2, 3, 3, 1, 3, 3, 2, 2, 1, 1]):
    self.note = note
    self.weights = weights
    
  @property
  def distribution(self):
    distribution = np.zeros(127)
    n_weights = len(self.weights)
    n_half = math.floor(n_weights / 2.)
    last_note = self.note.history[-1]
    distribution[last_note - n_half:last_note + n_half + 1] = self.weights
    return distribution
    
