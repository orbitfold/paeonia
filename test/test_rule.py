from peony.rule import Scale

def test_scale():
  scale = Scale()
  assert(len(scale.distribution) == 127)
