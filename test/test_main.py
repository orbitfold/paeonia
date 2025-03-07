import os
from paeonia import Note, Bar, Voice, Score
from paeonia.utils import download_sf2

def test_workflow():
    assert(True)

def test_download_sf2():
    file = download_sf2()
    assert(os.path.isfile(file))
