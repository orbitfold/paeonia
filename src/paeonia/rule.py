import numpy as np

class Scale:
  def __init__(self, root=0, mode=0, strength=1.0):
    scale = np.array([1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1])
  
  @property
  def distribution(self):
    pass

 
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
