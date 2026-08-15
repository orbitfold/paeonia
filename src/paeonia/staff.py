"""Attach notation and MIDI presentation metadata to a voice."""

from __future__ import annotations

from dataclasses import dataclass

from .voice import Voice


VALID_CLEFS = {"treble", "alto", "tenor", "bass"}


@dataclass
class Staff:
    """A voice together with its score-level presentation metadata.

    Parameters
    ----------
    voice : Voice
        Musical material carried by the staff.
    clef : str, default="treble"
        LilyPond clef name. Supported values are ``"treble"``, ``"alto"``,
        ``"tenor"``, and ``"bass"``.
    name : str | None
        Optional displayed staff name.
    midi_channel : int | None
        Optional zero-based MIDI channel in the range 0 through 15.
    midi_program : int | None
        Optional MIDI program in the range 0 through 127.

    Raises
    ------
    TypeError
        If a field has an incompatible type.
    ValueError
        If the clef, MIDI channel, or MIDI program is outside its supported
        range.
    """

    voice: Voice
    clef: str = "treble"
    name: str | None = None
    midi_channel: int | None = None
    midi_program: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.voice, Voice):
            raise TypeError("voice must be a Voice")
        if not isinstance(self.clef, str):
            raise TypeError("clef must be a string")
        if self.clef not in VALID_CLEFS:
            raise ValueError(f"Invalid clef: {self.clef}")
        if self.name is not None and not isinstance(self.name, str):
            raise TypeError("name must be a string or None")
        if self.midi_channel is not None:
            if not isinstance(self.midi_channel, int):
                raise TypeError("MIDI channel must be an integer or None")
            if not 0 <= self.midi_channel <= 15:
                raise ValueError("MIDI channel must lie between 0 and 15")
        if self.midi_program is not None:
            if not isinstance(self.midi_program, int):
                raise TypeError("MIDI program must be an integer or None")
            if not 0 <= self.midi_program <= 127:
                raise ValueError("MIDI program must lie between 0 and 127")
