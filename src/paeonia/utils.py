_TRANSLATE_NOTE_NAME = {
    "C": 0,
    "C#": 1,
    "Cb": 11,
    "D": 2,
    "D#": 3,
    "Db": 1,
    "E": 4,
    "E#": 5,
    "Eb": 3,
    "F": 5,
    "F#": 6,
    "Fb": 4,
    "G": 7,
    "G#": 8,
    "Gb": 6,
    "A": 9,
    "A#": 10,
    "Ab": 8,
    "B": 11,
    "B#": 0,
    "Bb": 10
}

_TRANSLATE_MODE_NAME = {
    "major": 0,
    "ionian": 0,
    "dorian": 1,
    "phrygian": 2,
    "lydian": 3,
    "mixolydian": 4,
    "minor": 5,
    "aeolian": 5,
    "locrian": 6
}

def note_name_to_pitch_class(note_name):
    """Translate note name to pich class.

    Parameters
    ----------
    note_name: str
        A note name in paeonia format but without octave.

    Returns
    -------
    int
        Pitch class (0 to 11)
    """
    try:
        return _TRANSLATE_NOTE_NAME[note_name]
    except KeyError:
        raise RuntimeError(f"Note name must be in {list(_TRANSLATE_NOTE_NAME)}!")

def mode_name_to_index(mode_name):
    """Translate mode name to tranposition index.

    Parameters
    ----------
    mode_name: str
        Mode name.

    Returns
    -------
    int:
        Index
    """
    try:
        return _TRANSLATE_MODE_NAME[mode_name]
    except KeyError:
        raise RuntimeError(f"Mode name must be in {list(_TRANSLATE_MODE_NAME)}!")

def download_sf2():
    """Compatibility wrapper for :func:`playback.download_soundfont`."""
    from .playback import download_soundfont

    return str(download_soundfont())

def message_list_to_midi_file(lst, tpb):
    """Compatibility wrapper for temporary MIDI-file creation."""
    from .midi import messages_to_temporary_midi_file

    return messages_to_temporary_midi_file(lst, tpb=tpb)

def render_and_play_midi(midi_object, tpb=480, autoplay=True):
    """Compatibility wrapper for :func:`playback.play_midi`."""
    from .playback import play_midi

    return play_midi(midi_object, autoplay=autoplay)
