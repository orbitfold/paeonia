from fractions import Fraction

import pytest

from paeonia import Bar, Note, Score, Staff, Tonality, Voice
from paeonia import playback
from paeonia.lilypond import (
    duration_to_lilypond,
    note_to_lilypond,
    pitch_class_to_lilypond,
    pitch_to_lilypond,
    score_to_lilypond,
    tonality_to_lilypond,
    voice_to_lilypond,
)
from paeonia.pitch import Pitch, PitchClass


@pytest.mark.parametrize(
    ("spelling", "expected"),
    [
        ("Ab", "aes"),
        ("Eb", "ees"),
        ("Bb", "bes"),
        ("Cb", "ces"),
        ("B#", "bis"),
        ("C##", "cisis"),
        ("Ebb", "eeses"),
    ],
)
def test_pitch_class_spelling_survives_lilypond(spelling, expected):
    assert pitch_class_to_lilypond(PitchClass.parse(spelling)) == expected


def test_pitch_octave_comes_from_spelling_not_midi_division():
    assert pitch_to_lilypond(Pitch.parse("B#3")) == "bis"
    assert pitch_to_lilypond(Pitch.parse("C4")) == "c'"


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        (Fraction(1, 4), "4"),
        (Fraction(3, 8), "4."),
        (Fraction(7, 16), "4.."),
        (Fraction(3, 16), "8."),
        (Fraction(7, 32), "8.."),
    ],
)
def test_plain_and_dotted_durations(duration, expected):
    assert duration_to_lilypond(duration) == expected


def test_unsupported_duration_is_descriptive():
    with pytest.raises(ValueError, match="Unsupported LilyPond duration"):
        duration_to_lilypond(Fraction(1, 3))


def test_notes_rests_chords_and_ties_render():
    tied = Note(
        pitches=(Pitch.parse("Eb4"),),
        duration=Fraction(3, 8),
        tie_out=True,
    )
    chord = Note(
        pitches=(Pitch.parse("Cb4"), Pitch.parse("B#4")),
        duration=Fraction(7, 16),
        tie_out=True,
    )

    assert note_to_lilypond(tied) == "ees'4.~"
    assert note_to_lilypond(Note.rest(Fraction(1, 8))) == "r8"
    assert note_to_lilypond(chord) == "<ces' bis'>4..~"


def test_existing_bar_rendering_is_preserved():
    bar = Bar(
        "C#4. D''8.. R2. Bb,16 <F# A# C#'>2. "
        "G, R E4.. <A C' E>1"
    )

    assert bar.to_lilypond() == (
        "cis'4. d'''4 r2. bes''16 "
        "<fis'' ais'' cis'''>2. g''2. r2. e''2 "
        "<a'' c''' e'''>1"
    )


@pytest.mark.parametrize(
    ("mode", "lilypond_mode"),
    [
        ("major", "major"),
        ("ionian", "major"),
        ("dorian", "dorian"),
        ("phrygian", "phrygian"),
        ("lydian", "lydian"),
        ("mixolydian", "mixolydian"),
        ("minor", "minor"),
        ("aeolian", "minor"),
        ("locrian", "locrian"),
        ("minor-harmonic", "minor"),
        ("minor-melodic", "minor"),
    ],
)
def test_tonality_modes_map_to_lilypond(mode, lilypond_mode):
    assert tonality_to_lilypond(Tonality("Eb", mode)) == (
        f"\\key ees \\{lilypond_mode}"
    )


def test_custom_tonality_mode_is_rejected():
    tonality = Tonality("C", intervals=(0, 3, 7))
    with pytest.raises(ValueError, match="has no LilyPond key mode"):
        tonality_to_lilypond(tonality)


def test_voice_emits_key_only_when_resolved_tonality_changes():
    voice = Voice(
        [Bar("C"), Bar("G"), Bar("D")],
        default_tonality=Tonality("C"),
        tonality_plan={1: Tonality("G")},
    )

    rendered = voice_to_lilypond(voice)

    assert rendered == (
        "\\key c \\major c'4 "
        "\\key g \\major g'4 d'4"
    )
    assert rendered.count("\\key") == 2


def test_bar_override_emits_local_key_then_restores_voice_key():
    voice = Voice(
        [
            Bar("C"),
            Bar("G", tonality=Tonality("G")),
            Bar("C"),
        ],
        default_tonality=Tonality("C"),
    )

    rendered = voice_to_lilypond(voice)

    assert rendered.count("\\key c \\major") == 2
    assert rendered.count("\\key g \\major") == 1


def test_score_uses_inherited_tonality_and_staff_insertion_order():
    score = Score(
        default_tonality=Tonality("C"),
        tonality_plan={1: Tonality("G")},
        tempo=96,
        time_signature=(3, 4),
    )
    score["zeta"] = Staff(
        Voice([Bar("C"), Bar("G")]),
        clef="treble",
        name='Lead "One"',
    )
    score["alpha"] = Staff(
        Voice([Bar("E"), Bar("B")]),
        clef="bass",
        name="Bass",
    )

    rendered = score_to_lilypond(score)

    assert rendered.index('instrumentName = "Lead \\"One\\""') < (
        rendered.index('instrumentName = "Bass"')
    )
    assert "\\clef treble" in rendered
    assert "\\clef bass" in rendered
    assert rendered.count("\\time 3/4") == 2
    assert rendered.count("\\tempo 4 = 96") == 2
    assert rendered.count("\\key c \\major") == 2
    assert rendered.count("\\key g \\major") == 2


def test_score_shows_every_bar_number_by_default_and_can_opt_out():
    score = Score(time_signature=(4, 4))
    score["lead"] = Voice([Bar("C1"), Bar("D1")])

    rendered = score_to_lilypond(score)

    assert "barNumberVisibility = #all-bar-numbers-visible" in rendered
    assert (
        "\\override BarNumber.break-visibility = ##(#t #t #t)"
        in rendered
    )
    assert rendered.count("\\score {") == 1

    without_numbers = score_to_lilypond(score, bar_numbers=False)
    assert "barNumberVisibility" not in without_numbers
    assert "BarNumber.break-visibility" not in without_numbers
    assert without_numbers.startswith("\\score {")


def test_score_bar_number_option_reaches_model_and_playback(monkeypatch):
    score = Score()
    score["lead"] = Voice([Bar("C")])
    calls = []

    def show_score(passed_score, *, bar_numbers):
        calls.append((passed_score, bar_numbers))

    monkeypatch.setattr(playback, "show_score", show_score)

    assert "barNumberVisibility" in score.to_lilypond()
    assert "barNumberVisibility" not in score.to_lilypond(
        bar_numbers=False,
    )
    assert score.show() is score
    assert score.show(bar_numbers=False) is score
    assert calls == [(score, True), (score, False)]


def test_score_bar_number_option_requires_boolean():
    score = Score()

    with pytest.raises(TypeError, match="bar_numbers must be a boolean"):
        score_to_lilypond(score, bar_numbers="all")


def test_score_rendering_rejects_misalignment_before_output():
    score = Score()
    score["lead"] = Voice([Bar("C"), Bar("D")])
    score["bass"] = Voice([Bar("C")])

    with pytest.raises(ValueError, match="'bass'.*1 bars"):
        score_to_lilypond(score)


def test_missing_lilypond_has_useful_error(monkeypatch):
    monkeypatch.setattr(playback.shutil, "which", lambda name: None)
    with pytest.raises(FileNotFoundError, match="LilyPond.*PATH"):
        playback.show_note(Note.parse("C"))
