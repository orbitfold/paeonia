import os
from paeonia.dsp import Line, Table, Clock, Sampler, File

def test_sample_player(tmp_dir):
    sample = Table.from_file('test/ch.wav')
    clock = Clock(bpm=4)
    sampler = Sampler(sample)
    line = Line(0.0, 1.0, sample.length_in_seconds)
    sampler.phase = line.out
    line.trig = clock.out
    wavefile = File(os.path.join(tmp_dir, 'output.wav'))
    wavefile.in = sampler.out
    for _ in range(100):
        wavefile.process(n_frames=256, sr=48_000)
    assert(os.path.exists(os.path.join(tmp_dir, 'output.wav')))
