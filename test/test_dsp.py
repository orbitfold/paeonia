import os
import pytest
import numpy as np
from paeonia.dsp import Line

def test_line():
    line = Line(0, 1, 1)
    ref = np.linspace(0, 1, 48000)

@pytest.mark.skip
def test_sample_player(tmp_dir):
    sample = Table.from_file('test/ch.wav')
    line = Line(0.0, 1.0, sample.length_in_seconds)
    sampler = Sampler(sample)
    wavefile = File(os.path.join(tmp_dir, 'output.wav'))
    sampler.phase = line
    wavefile.in_ = sampler
    assert(os.path.exists(os.path.join(tmp_dir, 'output.wav')))
