from fractions import Fraction
from zipfile import ZipFile

from mido import MidiFile, bpm2tempo
import pytest

from paeonia import Bar, Note, Score, Staff, Tonality, Voice
from paeonia.midi import (
    bar_to_midi_messages,
    note_to_midi_messages,
    score_to_midi,
    tonality_to_midi_key,
    voice_to_midi_messages,
)
from paeonia.pitch import Pitch
from paeonia import playback


def _absolute_messages(track, message_type):
    elapsed = 0
    result = []
    for message in track:
        elapsed += message.time
        if message.type == message_type:
            result.append((elapsed, message))
    return result


def test_note_chord_uses_offset_and_duration_only_once():
    chord = Note(
        pitches=tuple(
            Pitch.parse(value)
            for value in ("C4", "E4", "G4")
        ),
        duration=Fraction(1, 4),
        velocity=0.5,
    )

    messages = note_to_midi_messages(chord, offset=37, tpb=480)

    assert [message.type for message in messages] == [
        "note_on",
        "note_on",
        "note_on",
        "note_off",
        "note_off",
        "note_off",
    ]
    assert [message.note for message in messages] == [60, 64, 67] * 2
    assert [message.time for message in messages] == [37, 0, 0, 480, 0, 0]
    assert [message.velocity for message in messages[:3]] == [64, 64, 64]


def test_note_rest_emits_no_messages():
    assert note_to_midi_messages(
        Note.rest(Fraction(1, 2)),
        offset=123,
    ) == []


def test_bar_accumulates_leading_and_trailing_rest_offsets():
    bar = Bar([
        Note.rest(Fraction(1, 4)),
        Note.from_midi(60, duration=Fraction(1, 8)),
        Note.rest(Fraction(1, 16)),
    ])

    messages, trailing = bar_to_midi_messages(
        bar,
        offset=10,
        tpb=480,
    )

    assert [message.type for message in messages] == ["note_on", "note_off"]
    assert [message.time for message in messages] == [490, 240]
    assert trailing == 120


def test_voice_preserves_pending_offset_across_bar_boundaries():
    voice = Voice([
        Bar([Note.rest(Fraction(1, 4))]),
        Bar([Note.from_midi(60, duration=Fraction(1, 8))]),
    ])

    messages = voice_to_midi_messages(voice, tpb=480)

    assert [message.time for message in messages] == [480, 240]


def test_tied_reordered_enharmonic_chord_does_not_retrigger_across_bars():
    first = Note(
        pitches=(Pitch.parse("C#4"), Pitch.parse("E4")),
        duration=Fraction(1, 4),
        tie_out=True,
    )
    second = Note(
        pitches=(Pitch.parse("E4"), Pitch.parse("Db4")),
        duration=Fraction(1, 8),
        tie_in=True,
    )
    voice = Voice([Bar([first]), Bar([second])])

    messages = voice_to_midi_messages(voice, tpb=480)

    assert [message.type for message in messages] == [
        "note_on",
        "note_on",
        "note_off",
        "note_off",
    ]
    assert [message.note for message in messages] == [61, 64, 61, 64]
    assert [message.time for message in messages] == [0, 0, 720, 0]


@pytest.mark.parametrize(
    ("notes", "message"),
    [
        (
            [Note.from_midi(60).with_ties(tie_in=True)],
            "tie_in without",
        ),
        (
            [Note.from_midi(60).with_ties(tie_out=True)],
            "not followed",
        ),
        (
            [
                Note.from_midi(60).with_ties(tie_out=True),
                Note.from_midi(60),
            ],
            "not followed by tie_in",
        ),
        (
            [
                Note.from_midi(60).with_ties(tie_out=True),
                Note.from_midi(61).with_ties(tie_in=True),
            ],
            "incompatible pitches",
        ),
        (
            [Note.rest().with_ties(tie_out=True)],
            "Rest.*cannot participate",
        ),
    ],
)
def test_invalid_tie_structures_raise_descriptive_errors(notes, message):
    with pytest.raises(ValueError, match=message):
        bar_to_midi_messages(Bar(notes))


def test_score_emits_conductor_metadata_channels_programs_and_keys():
    score = Score(
        default_tonality=Tonality("C"),
        tempo=90,
        time_signature=(3, 4),
    )
    score["lead"] = Staff(
        Voice([Bar("C")]),
        midi_channel=4,
        midi_program=40,
    )
    score["bass"] = Staff(Voice([Bar("E")]), clef="bass")

    midi = score_to_midi(score, tpb=480)

    assert midi.type == 1
    assert midi.ticks_per_beat == 480
    assert len(midi.tracks) == 3
    conductor = midi.tracks[0]
    assert conductor[0].type == "set_tempo"
    assert conductor[0].tempo == bpm2tempo(90)
    assert conductor[1].type == "time_signature"
    assert (conductor[1].numerator, conductor[1].denominator) == (3, 4)

    lead = midi.tracks[1]
    bass = midi.tracks[2]
    program = next(message for message in lead if message.type == "program_change")
    assert (program.channel, program.program) == (4, 40)
    assert {
        message.channel
        for message in lead
        if message.type in {"note_on", "note_off"}
    } == {4}
    assert {
        message.channel
        for message in bass
        if message.type in {"note_on", "note_off"}
    } == {0}
    assert [
        message.key
        for message in lead
        if message.type == "key_signature"
    ] == ["C"]


def test_score_key_changes_are_timed_at_bar_boundaries():
    score = Score(
        default_tonality=Tonality("C"),
        tonality_plan={1: Tonality("G")},
    )
    score["lead"] = Voice([Bar("C"), Bar("G")])

    track = score_to_midi(score, tpb=480).tracks[1]
    changes = _absolute_messages(track, "key_signature")

    assert [(time, message.key) for time, message in changes] == [
        (0, "C"),
        (480, "G"),
    ]


@pytest.mark.parametrize(
    ("tonality", "expected"),
    [
        (Tonality("C", "ionian"), "C"),
        (Tonality("F#", "major"), "F#"),
        (Tonality("A", "minor"), "Am"),
        (Tonality("Eb", "minor-harmonic"), "Ebm"),
        (Tonality("D", "dorian"), None),
        (Tonality("C##", "major"), None),
    ],
)
def test_midi_key_signature_only_claims_representable_keys(
    tonality,
    expected,
):
    assert tonality_to_midi_key(tonality) == expected


def test_score_to_midi_file_round_trips(tmp_path):
    score = Score(default_tonality=Tonality("C"))
    score["lead"] = Voice([Bar("C")])
    destination = tmp_path / "score.mid"

    assert score.to_midi(destination, tpb=960) is None

    rendered = MidiFile(destination)
    assert rendered.ticks_per_beat == 960
    assert len(rendered.tracks) == 2


def test_midi_requires_power_of_two_time_signature_denominator():
    score = Score(time_signature=(4, 3))
    with pytest.raises(ValueError, match="power of two"):
        score_to_midi(score)


def test_soundfont_cache_is_created_only_when_download_is_requested(
    tmp_path,
    monkeypatch,
):
    home = tmp_path / "home"
    home.mkdir()
    calls = []
    monkeypatch.setattr(playback.Path, "home", lambda: home)

    def download(url, destination):
        calls.append(url)
        with ZipFile(destination, "w") as archive:
            archive.writestr(playback.SOUNDFONT_NAME, b"soundfont")

    monkeypatch.setattr(playback, "urlretrieve", download)
    assert not (home / ".paeonia").exists()

    path = playback.download_soundfont()

    assert path == home / ".paeonia" / playback.SOUNDFONT_NAME
    assert path.read_bytes() == b"soundfont"
    assert len(calls) == 1
    assert playback.download_soundfont() == path
    assert len(calls) == 1


def test_missing_fluidsynth_raises_before_downloading(monkeypatch):
    monkeypatch.setattr(playback.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        playback,
        "download_soundfont",
        lambda: pytest.fail("soundfont download should not start"),
    )

    with pytest.raises(FileNotFoundError, match="FluidSynth.*PATH"):
        playback.play_midi(MidiFile())
