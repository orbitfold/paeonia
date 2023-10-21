import numpy as np
import deal

class Distribution:
  zero = 0.000001
  one = 0.99999

class Uniform:
  @deal.pre(lambda a, b: a < b)
  def __init__(self, a, b):
    self.a = a
    self.b = b
    
  @property
  def dist(self):
    dist = np.zeros(127)
    dist[self.a:self.b] = np.ones(self.b - self.a)
    dist = dist / dist.sum()
    return dist
