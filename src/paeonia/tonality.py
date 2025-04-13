from itertools import cycle
import paeonia
from paeonia.utils import note_name_to_pitch_class, mode_name_to_index

SCALES = {
    "chromatic": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "major": [0, 2, 4, 5, 7, 9, 11],
    "ionian": [0, 2, 4, 5, 7, 9, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "aeolian": [0, 2, 3, 5, 7, 8, 10],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "minor-harmonic": [0, 2, 3, 5, 7, 8, 11],
    "minor-melodic": [0, 2, 3, 5, 7, 9, 11],
    "locrian": [0, 1, 3, 5, 6, 8, 10]
}

class Tonality:
    def __init__(self, root='C', scale='ionian'):
        self.root = root
        self.scale_name = scale
        self.scale = SCALES[scale]
        self.pitches = []
        root = note_name_to_pitch_class(root)
        self.scale = [(x + root) % 12 for x in self.scale]
        for octave in range(11):
            for pc in self.scale:
                new_pitch = octave * 12 + pc
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
