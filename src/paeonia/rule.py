import numpy as np

class Scale:
  def __init__(self, mode=0, strength=1.0):
    n = (5 / 12.) * (1.0 - strength)
    w = (7 / 12.) * strength
    scale = np.array([w, n, w, n, w, w, n, w, n, w, n, w])
    scale = np.roll(scale, mode)
    self.p = list(scale) * 5 + (list(scale) * 6)[:-7]
    self.p = self.p / self.p.sum()
  
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
