import os
import wget
import zipfile

def download_sf2():
    """Download the GM soundfont to be used with fluidsynth.
    """
    os.makedirs('~/.paeonia', exist_ok=True)
    sf2_location = '~/.paeonia/FluidR3_GM.sf2'
    zip_location = '~/.paeonia/FluidR3_GM.zip'
    sf2_link = 'https://keymusician01.s3.amazonaws.com/FluidR3_GM.zip'
    if not os.path.isfile(sf2_location):
        wget.download(sf2_link, '~/.paeonia')
        with zipfile.ZipFile(zip_location, 'r') as zip_ref:
            zip_ref.extract_all('~/.paeonia')
        return sf2_location
    else:
        return sf2_location
