import pyaudio
import numpy as np
import time

class Phasor:
    def __init__(self, **kwargs):
        pass

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
