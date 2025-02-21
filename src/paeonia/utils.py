import os
import wget
import zipfile
import pathlib

def download_sf2():
    """Download the GM soundfont to be used with fluidsynth.
    """
    home = pathlib.Path.home()
    os.makedirs(home / '.paeonia', exist_ok=True)
    sf2_location = home / '.paeonia' / 'FluidR3_GM.sf2'
    zip_location = home / '.paeonia' / 'FluidR3_GM.zip'
    sf2_link = 'https://keymusician01.s3.amazonaws.com/FluidR3_GM.zip'
    if not os.path.isfile(sf2_location):
        wget.download(sf2_link, home / '.paeonia')
        with zipfile.ZipFile(zip_location, 'r') as zip_ref:
            zip_ref.extractall(home / '.paeonia')
        return sf2_location
    else:
        return sf2_location
