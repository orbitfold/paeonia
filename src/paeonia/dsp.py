import pyaudio
import numpy as np
import time
import numba

class Line:
    def __init__(self, start, end, time):
        self.start = start
        self.end = end
        self.time = time
        self.out = None
        self.pos = start
        self.dpos = end - start
        self.block_id = 0

    @numba.njit
    def process(self, nframes, sr, block_id):
        if block_id > self.block_id:
            nsamples = int(self.time * sr)
            dpos = ((self.end - self.start) / nsamples) * nframes
            self.out = np.linspace(self.pos, self.pos + dpos, nframes)
            self.pos += dpos
            self.block_id = block_id
        return self.out

class DAC:
    phase = 0.0
    
    def __init__(self):
        pass

    def process(self, n_frames):
        pass

    @classmethod
    def callback(cls, in_data, frame_count, time_info, status):
        dphase = (frame_count / 48000.) * np.pi * 2 * 440
        data = np.sin(
            np.linspace(
                [cls.phase, cls.phase],
                [cls.phase + dphase, cls.phase + dphase], frame_count
            ),
            dtype=np.float32) * 0.1
        cls.phase += dphase
        return data, pyaudio.paContinue

if __name__ == '__main__':
    p = pyaudio.PyAudio()
    stream = p.open(
        rate=48000,
        channels=2,
        format=pyaudio.paFloat32,
        stream_callback=DAC.callback,
        output=True)
    while stream.is_active():
        time.sleep(0.1)
    stream.close()
    p.terminate()
