import os
import wget
import zipfile
import pathlib
import tempfile
from mido import MidiFile, MidiTrack

def download_sf2():
    """Download the GM soundfont to be used with fluidsynth.
    """
    home = pathlib.Path.home()
    os.makedirs(home / '.paeonia', exist_ok=True)
    sf2_location = home / '.paeonia' / 'FluidR3_GM.sf2'
    zip_location = home / '.paeonia' / 'FluidR3_GM.zip'
    sf2_link = 'https://keymusician01.s3.amazonaws.com/FluidR3_GM.zip'
    if not os.path.isfile(sf2_location):
        wget.download(sf2_link, str(home / '.paeonia'))
        with zipfile.ZipFile(zip_location, 'r') as zip_ref:
            zip_ref.extractall(home / '.paeonia')
        return str(sf2_location)
    else:
        return str(sf2_location)

def message_list_to_midi_file(lst, tpb):
    midi = MidiFile(ticks_per_beat=tpb)
    track = MidiTrack()
    for message in lst:
        track.append(message)
    midi.tracks.append(track)
    fd, path = tempfile.mkstemp(suffix='.mid')
    os.close(fd)
    midi.save(path)
    return path
