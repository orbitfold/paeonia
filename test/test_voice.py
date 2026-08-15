from fractions import Fraction
import sys
from types import ModuleType
from typing import get_type_hints

import pytest

from paeonia import Bar, Note, Tonality, Voice
from paeonia.pitch import Pitch
from paeonia.tonality import TonalityPlan


def test_init_copies_bars_and_normalizes_tonality_metadata():
    bars = [Bar("C")]
    default = Tonality("C")
    change = Tonality("G")

    voice = Voice(
        bars,
        default_tonality=default,
        tonality_plan={2: change},
        name="Soprano",
    )
    bars.append(Bar("D"))

    assert voice.bars == [Bar("C")]
    assert voice.bars is not bars
    assert voice.default_tonality is default
    assert voice.tonality_plan == TonalityPlan(((2, change),))
    assert voice.name == "Soprano"
    assert get_type_hints(Voice.__init__)["default_tonality"] == (
        Tonality | None
    )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"bars": [object()]}, "voice element"),
        ({"default_tonality": object()}, "default_tonality"),
        ({"tonality_plan": object()}, "tonality_plan"),
        ({"tonality_plan": {0: object()}}, "plan value"),
        ({"name": object()}, "name"),
    ],
)
def test_init_rejects_invalid_values(arguments, message):
    with pytest.raises(TypeError, match=message):
        Voice(**arguments)


def test_init_rejects_negative_tonality_change_indices():
    with pytest.raises(ValueError, match="non-negative"):
        Voice(tonality_plan={-1: Tonality("C")})


def test_span_and_bar_spans_return_exact_durations():
    voice = Voice([
        Bar([
            Note.rest(Fraction(1, 4)),
            Note.rest(Fraction(3, 8)),
        ]),
        Bar([Note.rest(Fraction(1, 2))]),
        Bar(),
    ])

    assert voice.bar_spans() == (
        Fraction(5, 8),
        Fraction(1, 2),
        Fraction(0),
    )
    assert all(isinstance(value, Fraction) for value in voice.bar_spans())
    assert voice.span() == Fraction(9, 8)
    assert isinstance(voice.span(), Fraction)


def test_empty_voice_has_zero_span_and_no_bar_spans():
    voice = Voice()

    assert voice.span() == Fraction(0)
    assert isinstance(voice.span(), Fraction)
    assert voice.bar_spans() == ()


def test_apply_tonality_resolves_sources_by_precedence(monkeypatch):
    default = Tonality("C")
    bar_specific = Tonality("A")
    planned = Tonality("G")
    inherited = Tonality("F")
    inherited_change = Tonality("Bb")
    target = Tonality("D")
    bars = [
        Bar("C"),
        Bar("D", tonality=bar_specific),
        Bar("E"),
        Bar("F"),
    ]
    voice = Voice(
        bars,
        default_tonality=default,
        tonality_plan={2: planned},
        name="Alto",
    )
    calls = []

    def apply(
            bar,
            target,
            source=None,
            *,
            chromatic,
            degree_policy,
    ):
        calls.append((bar, target, source, chromatic, degree_policy))
        return bar.with_tonality(target)

    monkeypatch.setattr(Bar, "apply_tonality", apply)

    result = voice.apply_tonality(
        target,
        inherited=inherited,
        inherited_plan=TonalityPlan(((1, inherited_change),)),
        chromatic="nearest",
        degree_policy="wrap",
    )

    assert [call[2] for call in calls] == [
        default,
        bar_specific,
        planned,
        planned,
    ]
    assert all(call[1] is target for call in calls)
    assert all(call[3:] == ("nearest", "wrap") for call in calls)
    assert result.default_tonality is target
    assert result.tonality_plan == TonalityPlan()
    assert result.name == "Alto"
    assert all(bar.tonality is None for bar in result.bars)
    assert voice.bars == bars
    assert voice.bars[1].tonality is bar_specific


def test_apply_tonality_uses_inherited_context_when_voice_has_none(
    monkeypatch,
):
    inherited = Tonality("F")
    inherited_change = Tonality("Bb")
    target = Tonality("D")
    voice = Voice([Bar("F"), Bar("D"), Bar("E")])
    sources = []

    def apply(
            bar,
            target,
            source=None,
            *,
            chromatic,
            degree_policy,
    ):
        sources.append(source)
        return bar.with_tonality(target)

    monkeypatch.setattr(Bar, "apply_tonality", apply)

    voice.apply_tonality(
        target,
        inherited=inherited,
        inherited_plan=TonalityPlan(((1, inherited_change),)),
    )

    assert sources == [inherited, inherited_change, inherited_change]


def test_apply_tonality_transforms_structure_without_mutating_source():
    source = Tonality("C", "major")
    target = Tonality("D", "minor")
    chord = Note(
        pitches=tuple(Pitch.parse(pitch) for pitch in ("C4", "E4", "G4")),
        duration=Fraction(3, 8),
        velocity=0.4,
        tie_in=True,
        tie_out=True,
    )
    rest = Note.rest(Fraction(1, 8)).with_velocity(0.2)
    bar = Bar([chord, rest])
    voice = Voice([bar], default_tonality=source, name="Tenor")

    result = voice.apply_tonality(target)

    assert result.bars[0][0].pitches == tuple(
        Pitch.parse(pitch) for pitch in ("D4", "F4", "A4")
    )
    assert result.bars[0][0].duration == chord.duration
    assert result.bars[0][0].velocity == chord.velocity
    assert result.bars[0][0].tie_in is True
    assert result.bars[0][0].tie_out is True
    assert result.bars[0][1] == rest
    assert result.bars[0].tonality is None
    assert result.default_tonality is target
    assert result.name == "Tenor"
    assert bar == Bar([chord, rest])
    assert voice.bars == [bar]


def test_apply_tonality_reports_missing_source_by_bar_index():
    with pytest.raises(ValueError, match="bar 0"):
        Voice([Bar("C")]).apply_tonality(Tonality("D"))


@pytest.mark.parametrize(
    ("arguments", "error", "message"),
    [
        ({"target": object()}, TypeError, "target"),
        (
            {"target": Tonality("D"), "source": object()},
            TypeError,
            "source",
        ),
        (
            {"target": Tonality("D"), "inherited": object()},
            TypeError,
            "inherited",
        ),
        (
            {"target": Tonality("D"), "inherited_plan": object()},
            TypeError,
            "inherited_plan",
        ),
        (
            {"target": Tonality("D"), "chromatic": "unknown"},
            ValueError,
            "chromatic",
        ),
        (
            {"target": Tonality("D"), "degree_policy": "unknown"},
            ValueError,
            "degree",
        ),
    ],
)
def test_apply_tonality_validates_arguments_for_empty_voice(
    arguments,
    error,
    message,
):
    with pytest.raises(error, match=message):
        Voice().apply_tonality(**arguments)


def test_to_midi_delegates_to_voice_renderer(monkeypatch):
    voice = Voice([Bar("C"), Bar("D")])
    expected = [object(), object()]
    calls = []
    midi = ModuleType("paeonia.midi")

    def voice_to_midi_messages(passed_voice, *, tpb):
        calls.append((passed_voice, tpb))
        return expected

    midi.voice_to_midi_messages = voice_to_midi_messages
    monkeypatch.setitem(sys.modules, "paeonia.midi", midi)

    assert voice.to_midi(tpb=960) is expected
    assert calls == [(voice, 960)]


def test_to_lilypond_delegates_with_inherited_score_context(monkeypatch):
    voice = Voice([Bar("C"), Bar("D")])
    inherited = Tonality("F")
    inherited_plan = TonalityPlan(((1, Tonality("G")),))
    calls = []
    lilypond = ModuleType("paeonia.lilypond")

    def voice_to_lilypond(
            passed_voice,
            *,
            inherited,
            inherited_plan,
    ):
        calls.append((passed_voice, inherited, inherited_plan))
        return "rendered voice"

    lilypond.voice_to_lilypond = voice_to_lilypond
    monkeypatch.setitem(sys.modules, "paeonia.lilypond", lilypond)

    assert voice.to_lilypond(
        inherited=inherited,
        inherited_plan=inherited_plan,
    ) == "rendered voice"
    assert calls == [(voice, inherited, inherited_plan)]


def test_show_and_play_delegate_and_return_voice(monkeypatch):
    voice = Voice([Bar("C")])
    calls = []
    playback = ModuleType("paeonia.playback")

    def show_voice(passed_voice):
        calls.append(("show", passed_voice))

    def play_voice(passed_voice, *, tpb, autoplay):
        calls.append(("play", passed_voice, tpb, autoplay))

    playback.show_voice = show_voice
    playback.play_voice = play_voice
    monkeypatch.setitem(sys.modules, "paeonia.playback", playback)

    assert voice.show() is voice
    assert voice.play(tpb=960, autoplay=True) is voice
    assert calls == [
        ("show", voice),
        ("play", voice, 960, True),
    ]
