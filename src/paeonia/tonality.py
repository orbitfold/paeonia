from itertools import cycle

class Tonality:
    def __init__(self, root='C', mode='major'):
        intervals = [2, 2, 1, 2, 2, 2, 1]
        interval_cycle = cycle(intervals)
        self.pitches = [0]
        while True:
            new_pitch = self.pitches[-1] + next(interval_cycle)
            if new_pitch > 127:
                break
            self.pitches.append(new_pitch)

    def closest(self, pitch):
        """Find pitches in the tonality closest to the pitch given.

        Parameters
        ----------
        pitch: int
            A pitch to compare to
        """
        for d in range(12):
            closest = [x for x in self.pitches if abs(x - pitch) == d]
            if len(closest) > 0:
                return closest
