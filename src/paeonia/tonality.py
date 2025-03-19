from itertools import cycle
import paeonia
from paeonia.utils import note_name_to_pitch_class, mode_name_to_index

class Tonality:
    def __init__(self, root='C', mode='ionian'):
        self.root = root
        self.mode = mode
        intervals = [2, 2, 1, 2, 2, 2, 1]
        mode_index = mode_name_to_index(mode)
        intervals = intervals[mode_index:] + intervals[:mode_index]
        interval_cycle = cycle(intervals)
        self.pitches = [-12 + note_name_to_pitch_class(root)]
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

    def get_pitches(self, indices):
        """Get pitches corresponding to indices.

        Parameters
        ----------
        indices: list of int
            A list of integers specifying indices in the tonality.

        Returns
        -------
        list of int
            A list of pitches.
        """
        return [self.pitches[i] for i in indices]

    def get_indices(self, pitches):
        """Get indices corresponding to pitches.

        Parameters
        ----------
        pitches: list of int
            A list of pitches.

        Returns
        -------
        list of int
            A list of indices.
        """
        return [self.pitches.index(pitch) for pitch in pitches]

    def __contains__(self, other):
        """Check if an object is in this tonality.

        Parameters
        ----------
        other: Note or int
            Either a note or a pitch.

        Returns
        -------
        Bool
            True if this note or pitch is in this tonality, False otherwise.
        """
        if isinstance(other, paeonia.Note):
            return all([p in self.pitches for p in other.pitches])
        else:
            return all([p in self.pitches for p in other])
