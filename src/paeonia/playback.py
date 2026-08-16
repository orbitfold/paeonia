"""External rendering, playback, downloading, and notebook display helpers."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
import re
import shutil
from string import Template
import subprocess
import tempfile
from typing import TYPE_CHECKING
from urllib.request import urlretrieve
from zipfile import ZipFile

from mido import MetaMessage, MidiFile, MidiTrack

from .lilypond import (
    bar_to_lilypond,
    note_to_lilypond,
    score_to_lilypond,
    voice_to_lilypond,
)
from .midi import (
    _voice_to_midi_messages_and_offset,
    bar_to_midi_messages,
    note_to_midi_messages,
    score_to_midi,
)
if TYPE_CHECKING:
    from .bar import Bar
    from .note import Note
    from .score import Score
    from .voice import Voice


SOUNDFONT_URL = (
    "https://keymusician01.s3.amazonaws.com/FluidR3_GM.zip"
)
SOUNDFONT_NAME = "FluidR3_GM.sf2"

_LILYPOND_PAGE_RE = re.compile(r"-page(\d+)\.png$")


def download_soundfont() -> Path:
    """Return the local GM soundfont, downloading it only when requested.

    The user cache directory ``~/.paeonia`` is created lazily by this function,
    never by importing Paeonia or constructing model objects.
    """
    cache = Path.home() / ".paeonia"
    destination = cache / SOUNDFONT_NAME
    if destination.is_file():
        return destination

    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / "FluidR3_GM.zip"
    try:
        urlretrieve(SOUNDFONT_URL, archive)
        with ZipFile(archive) as soundfonts:
            soundfonts.extractall(cache)
        if not destination.is_file():
            candidates = tuple(cache.rglob(SOUNDFONT_NAME))
            if not candidates:
                raise FileNotFoundError(
                    f"Downloaded archive did not contain {SOUNDFONT_NAME}"
                )
            candidates[0].replace(destination)
    finally:
        archive.unlink(missing_ok=True)
    return destination


def _require_executable(name: str, *, display_name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise FileNotFoundError(
            f"{display_name} executable {name!r} was not found on PATH"
        )
    return executable


def _single_track_midi(
        messages,
        *,
        trailing_offset: int,
        tpb: int,
) -> MidiFile:
    midi = MidiFile(ticks_per_beat=tpb)
    track = MidiTrack(messages)
    track.append(MetaMessage(
        "end_of_track",
        time=trailing_offset,
    ))
    midi.tracks.append(track)
    return midi


def play_midi(midi: MidiFile, *, autoplay: bool = False) -> None:
    """Render a MIDI object with FluidSynth and display the resulting audio."""
    if not isinstance(midi, MidiFile):
        raise TypeError("midi must be a MidiFile")
    fluidsynth = _require_executable(
        "fluidsynth",
        display_name="FluidSynth",
    )
    soundfont = download_soundfont()
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        midi_path = temporary / "preview.mid"
        wav_path = temporary / "preview.wav"
        midi.save(midi_path)
        subprocess.run(
            [
                fluidsynth,
                "-T",
                "wav",
                "-F",
                str(wav_path),
                "-i",
                str(soundfont),
                str(midi_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        from IPython.display import Audio, display

        display(Audio(filename=str(wav_path), autoplay=autoplay))


def play_note(
        note: Note,
        *,
        tpb: int = 480,
        autoplay: bool = False,
) -> None:
    """Render and play one note or chord."""
    messages = note_to_midi_messages(note, tpb=tpb)
    play_midi(
        _single_track_midi(messages, trailing_offset=0, tpb=tpb),
        autoplay=autoplay,
    )


def play_bar(
        bar: Bar,
        *,
        tpb: int = 480,
        autoplay: bool = False,
) -> None:
    """Render and play one bar."""
    messages, trailing = bar_to_midi_messages(bar, tpb=tpb)
    play_midi(
        _single_track_midi(
            messages,
            trailing_offset=trailing,
            tpb=tpb,
        ),
        autoplay=autoplay,
    )


def play_voice(
        voice: Voice,
        *,
        tpb: int = 480,
        autoplay: bool = False,
) -> None:
    """Render and play a voice, including ties across bar boundaries."""
    messages, trailing = _voice_to_midi_messages_and_offset(
        voice,
        tpb=tpb,
        channel=0,
    )
    play_midi(
        _single_track_midi(
            messages,
            trailing_offset=trailing,
            tpb=tpb,
        ),
        autoplay=autoplay,
    )


def play_score(
        score: Score,
        *,
        tpb: int = 480,
        autoplay: bool = False,
        allow_unaligned: bool = False,
) -> None:
    """Render and play a complete score."""
    play_midi(
        score_to_midi(
            score,
            tpb=tpb,
            allow_unaligned=allow_unaligned,
        ),
        autoplay=autoplay,
    )


def _lilypond_document(template_name: str, notation: str) -> str:
    template = Template(
        files("paeonia.data").joinpath(template_name).read_text()
    )
    return template.substitute(notation=notation)


def _lilypond_page_sort_key(path: Path) -> tuple[int, str]:
    """Sort LilyPond PNG pages numerically, including a single-page file."""
    match = _LILYPOND_PAGE_RE.search(path.name)
    page = int(match.group(1)) if match is not None else 0
    return page, path.name


def _show_lilypond(notation: str, *, template_name: str) -> None:
    """Render and display every page produced by LilyPond."""
    lilypond = _require_executable("lilypond", display_name="LilyPond")
    document = _lilypond_document(template_name, notation)
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        source = temporary / "notation.ly"
        source.write_text(document)
        subprocess.run(
            [
                lilypond,
                "--loglevel=ERROR",
                "-fpng",
                str(source),
            ],
            cwd=temporary,
            check=True,
        )
        image_paths = sorted(
            temporary.glob("notation*.png"),
            key=_lilypond_page_sort_key,
        )
        if not image_paths:
            raise FileNotFoundError(
                "LilyPond completed without producing a PNG file"
            )
        from IPython.display import Image, display

        for image_path in image_paths:
            display(Image(filename=str(image_path)))


def show_note(note: Note) -> None:
    """Render and display one note or chord with LilyPond."""
    _show_lilypond(
        note_to_lilypond(note),
        template_name="note_template.ly",
    )


def show_bar(bar: Bar) -> None:
    """Render and display one bar with LilyPond."""
    _show_lilypond(
        bar_to_lilypond(bar),
        template_name="bar_template.ly",
    )


def show_voice(voice: Voice) -> None:
    """Render and display one voice with LilyPond."""
    _show_lilypond(
        voice_to_lilypond(voice),
        template_name="voice_template.ly",
    )


def show_score(score: Score, *, bar_numbers: bool = True) -> None:
    """Render and display an aligned score, showing bar numbers by default."""
    _show_lilypond(
        score_to_lilypond(score, bar_numbers=bar_numbers),
        template_name="score_template.ly",
    )
