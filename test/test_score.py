from fractions import Fraction
import sys
from types import ModuleType

import pytest

from paeonia import Bar, Note, Score, Staff, Tonality, TonalityPlan, Voice
from paeonia.pitch import Pitch


def _single_pitches(voice):
    return tuple(bar[0].pitches[0] for bar in voice.bars)


def test_staff_defaults_and_validation():
    voice = Voice([Bar("C")])
    staff = Staff(voice)

    assert staff.voice is voice
    assert staff.clef == "treble"
    assert staff.name is None
    assert staff.midi_channel is None
    assert staff.midi_program is None

    with pytest.raises(ValueError, match="Invalid clef"):
        Staff(voice, clef="soprano")
    with pytest.raises(ValueError, match="channel"):
        Staff(voice, midi_channel=16)
    with pytest.raises(ValueError, match="program"):
        Staff(voice, midi_program=128)


def test_dictionary_access_and_compatibility_views_use_staves():
    score = Score()
    voice = Voice([Bar("C")])

    score["lead"] = voice

    assert score["lead"] is voice
    assert score.staves["lead"] == Staff(
        voice=voice,
        clef="treble",
        name="lead",
    )
    assert score.voices == {"lead": voice}
    assert score.clefs == {"lead": "treble"}

    score.voices.clear()
    score.clefs["lead"] = "bass"
    assert tuple(score.staves) == ("lead",)
    assert score.staves["lead"].clef == "treble"


def test_score_slice_copies_aligned_bars_and_preserves_metadata():
    c_major = Tonality("C")
    g_major = Tonality("G")
    d_major = Tonality("D")
    score = Score(
        default_tonality=c_major,
        tonality_plan={1: g_major, 3: d_major},
        tempo=84,
        time_signature=(3, 4),
        title="Excerpt",
    )
    score["lead"] = Staff(
        Voice(
            [Bar(note) for note in ("C", "D", "E", "F", "G")],
            name="Lead voice",
        ),
        clef="treble",
        name="Lead staff",
        midi_channel=2,
        midi_program=11,
    )
    score["bass"] = Staff(
        Voice(
            [Bar(note) for note in ("C,", "D,", "E,", "F,", "G,")],
            name="Bass voice",
        ),
        clef="bass",
        name="Bass staff",
        midi_channel=3,
        midi_program=42,
    )

    excerpt = score[1:4]

    assert isinstance(excerpt, Score)
    assert excerpt is not score
    assert excerpt.tempo == 84
    assert excerpt.time_signature == (3, 4)
    assert excerpt.title == "Excerpt"
    assert excerpt.default_tonality is g_major
    assert excerpt.tonality_plan == TonalityPlan(((2, d_major),))
    assert tuple(excerpt.staves) == ("lead", "bass")
    assert tuple(str(bar) for bar in excerpt["lead"].bars) == (
        "D",
        "E",
        "F",
    )
    assert tuple(str(bar) for bar in excerpt["bass"].bars) == (
        "D,",
        "E,",
        "F,",
    )
    assert (
        excerpt.staves["lead"].clef,
        excerpt.staves["lead"].name,
        excerpt.staves["lead"].midi_channel,
        excerpt.staves["lead"].midi_program,
        excerpt["lead"].name,
    ) == ("treble", "Lead staff", 2, 11, "Lead voice")
    assert excerpt.staves["lead"] is not score.staves["lead"]
    assert excerpt["lead"] is not score["lead"]
    assert excerpt["lead"].bars[0] is not score["lead"].bars[1]

    excerpt["lead"].bars[0].notes.clear()
    assert len(score["lead"].bars[1]) == 1


def test_score_slice_rebases_voice_plan_and_preserves_bar_overrides():
    c_major = Tonality("C")
    g_major = Tonality("G")
    d_major = Tonality("D")
    f_major = Tonality("F")
    a_major = Tonality("A")
    bb_major = Tonality("Bb")
    score = Score(
        default_tonality=c_major,
        tonality_plan={1: g_major, 4: f_major},
    )
    score["lead"] = Voice(
        [
            Bar("C"),
            Bar("G"),
            Bar("D"),
            Bar("Bb", tonality=bb_major),
            Bar("A"),
        ],
        tonality_plan={2: d_major, 4: a_major},
    )

    excerpt = score[1:5]

    assert excerpt.default_tonality is g_major
    assert excerpt.tonality_plan == TonalityPlan(((3, f_major),))
    assert excerpt["lead"].default_tonality is None
    assert excerpt["lead"].tonality_plan == TonalityPlan((
        (1, d_major),
        (3, a_major),
    ))
    assert tuple(
        excerpt.tonality_at("lead", index)
        for index in range(4)
    ) == (g_major, d_major, bb_major, a_major)
    assert excerpt["lead"].bars[2].tonality is bb_major


def test_score_slice_rejects_unaligned_staves_and_non_unit_steps():
    unaligned = Score()
    unaligned["lead"] = Voice([Bar("C"), Bar("D")])
    unaligned["bass"] = Voice([Bar("C")])

    with pytest.raises(ValueError, match="'bass'.*1 bars"):
        _ = unaligned[0:1]

    aligned = Score()
    aligned["lead"] = Voice([Bar("C"), Bar("D")])
    with pytest.raises(ValueError, match="step of 1"):
        _ = aligned[::2]
    with pytest.raises(TypeError, match="staff names or slices"):
        _ = aligned[0]


def test_staff_insertion_and_set_clef_preserve_attached_metadata():
    score = Score()
    staff = Staff(
        Voice([Bar("C")]),
        clef="alto",
        midi_channel=3,
        midi_program=41,
    )

    score["viola"] = staff
    score.set_clef("viola", "tenor")

    assert score.staves["viola"] is staff
    assert staff.name == "viola"
    assert staff.clef == "tenor"
    assert staff.midi_channel == 3
    assert staff.midi_program == 41
    with pytest.raises(ValueError, match="Invalid clef"):
        score.set_clef("viola", "percussion")


def test_score_initializes_and_validates_global_metadata():
    default = Tonality("C")
    change = Tonality("G")
    score = Score(
        default_tonality=default,
        tonality_plan={2: change},
        tempo=96,
        time_signature=(3, 4),
        title="Trio",
    )

    assert score.default_tonality is default
    assert score.tonality_plan == TonalityPlan(((2, change),))
    assert score.tempo == 96
    assert score.time_signature == (3, 4)
    assert score.title == "Trio"

    with pytest.raises(ValueError, match="Tempo"):
        Score(tempo=0)
    with pytest.raises(ValueError, match="Time-signature"):
        Score(time_signature=(4, 0))


def test_tonality_at_resolves_global_local_and_bar_contexts():
    score_default = Tonality("C")
    score_change = Tonality("G")
    voice_change = Tonality("D")
    bar_override = Tonality("Bb")
    voice = Voice(
        [
            Bar("C"),
            Bar("G"),
            Bar("Bb", tonality=bar_override),
            Bar("D"),
        ],
        tonality_plan={2: voice_change},
    )
    score = Score(
        default_tonality=score_default,
        tonality_plan={1: score_change},
    )
    score["lead"] = voice

    assert tuple(score.tonality_at("lead", index) for index in range(4)) == (
        score_default,
        score_change,
        bar_override,
        voice_change,
    )


def test_voice_default_tonality_overrides_inherited_score_plan():
    voice_default = Tonality("A")
    voice = Voice(
        [Bar("A"), Bar("A")],
        default_tonality=voice_default,
    )
    score = Score(
        default_tonality=Tonality("C"),
        tonality_plan={1: Tonality("G")},
    )
    score["lead"] = voice

    assert score.tonality_at("lead", 0) is voice_default
    assert score.tonality_at("lead", 1) is voice_default


def test_bar_tonality_override_applies_only_to_its_bar():
    score = Score(default_tonality=Tonality("C"))
    score["lead"] = Voice([
        Bar("G", tonality=Tonality("G")),
        Bar("G"),
    ])

    result = score.apply_tonality(Tonality("D"))

    assert _single_pitches(result["lead"]) == (
        Pitch.parse("D4"),
        Pitch.parse("A4"),
    )
    assert all(bar.tonality is None for bar in result["lead"].bars)
    assert score["lead"].bars[0].tonality == Tonality("G")


def test_apply_tonality_to_whole_score_preserves_staff_metadata():
    source = Tonality("C")
    target = Tonality("D")
    score = Score(
        default_tonality=source,
        tonality_plan={1: Tonality("G")},
        tempo=88,
        time_signature=(2, 4),
        title="Duo",
    )
    score["lead"] = Staff(
        Voice([Bar("C"), Bar("G")], name="Melody"),
        clef="treble",
        name="Lead staff",
        midi_channel=2,
        midi_program=73,
    )
    score["bass"] = Staff(
        Voice([Bar("C"), Bar("G")], name="Bass line"),
        clef="bass",
        name="Bass staff",
        midi_channel=5,
        midi_program=33,
    )

    result = score.apply_tonality(target)

    assert result.default_tonality is target
    assert result.tonality_plan == TonalityPlan()
    assert result.tempo == 88
    assert result.time_signature == (2, 4)
    assert result.title == "Duo"
    assert tuple(result.staves) == ("lead", "bass")
    assert _single_pitches(result["lead"]) == (
        Pitch.parse("D4"),
        Pitch.parse("D4"),
    )
    assert _single_pitches(result["bass"]) == (
        Pitch.parse("D4"),
        Pitch.parse("D4"),
    )
    for name in result.staves:
        assert result[name].default_tonality is None
        assert result[name].tonality_plan == TonalityPlan()
        assert all(bar.tonality is None for bar in result[name].bars)
        assert result.staves[name] is not score.staves[name]
    assert (
        result.staves["lead"].clef,
        result.staves["lead"].name,
        result.staves["lead"].midi_channel,
        result.staves["lead"].midi_program,
    ) == ("treble", "Lead staff", 2, 73)
    assert score.default_tonality is source
    assert _single_pitches(score["lead"]) == (
        Pitch.parse("C4"),
        Pitch.parse("G4"),
    )


def test_selective_tonality_is_voice_local_and_copies_unselected_staff():
    source = Tonality("C")
    target = Tonality("D")
    score = Score(default_tonality=source)
    score["lead"] = Staff(
        Voice([Bar("C")]),
        midi_channel=1,
        midi_program=12,
    )
    score["bass"] = Staff(
        Voice([Bar("C")]),
        clef="bass",
        midi_channel=2,
        midi_program=34,
    )

    result = score.apply_tonality(target, voices={"lead"})

    assert result.default_tonality is source
    assert result["lead"].default_tonality is target
    assert result["bass"].default_tonality is None
    assert _single_pitches(result["lead"]) == (Pitch.parse("D4"),)
    assert _single_pitches(result["bass"]) == (Pitch.parse("C4"),)
    assert result.staves["lead"].midi_program == 12
    assert result.staves["bass"].clef == "bass"
    assert result.staves["bass"] is not score.staves["bass"]
    assert result["bass"] is not score["bass"]
    assert result["bass"].bars[0] is not score["bass"].bars[0]
    with pytest.raises(KeyError, match="Unknown voices"):
        score.apply_tonality(target, voices={"missing"})


def test_global_plan_transformation_stays_synchronized():
    source_default = Tonality("C")
    source_change = Tonality("G")
    target_default = Tonality("D")
    target_change = Tonality("F")
    score = Score(
        default_tonality=source_default,
        tonality_plan={1: source_change},
    )
    for name, channel in (("first", 1), ("second", 2)):
        score[name] = Staff(
            Voice([Bar("C"), Bar("G"), Bar("G")]),
            midi_channel=channel,
            midi_program=40 + channel,
        )

    result = score.apply_tonality_plan({
        0: target_default,
        2: target_change,
    })

    assert result.default_tonality is target_default
    assert result.tonality_plan == TonalityPlan(((2, target_change),))
    for name, channel in (("first", 1), ("second", 2)):
        assert _single_pitches(result[name]) == (
            Pitch.parse("D4"),
            Pitch.parse("D4"),
            Pitch.parse("F4"),
        )
        assert tuple(result.tonality_at(name, index) for index in range(3)) == (
            target_default,
            target_default,
            target_change,
        )
        assert result[name].default_tonality is None
        assert result[name].tonality_plan == TonalityPlan()
        assert result.staves[name].midi_channel == channel
        assert result.staves[name].midi_program == 40 + channel
    assert score.default_tonality is source_default
    assert score.tonality_plan == TonalityPlan(((1, source_change),))


def test_selective_plan_is_stored_on_selected_voice():
    source_default = Tonality("C")
    source_change = Tonality("G")
    target_default = Tonality("D")
    target_change = Tonality("F")
    score = Score(
        default_tonality=source_default,
        tonality_plan={1: source_change},
    )
    score["lead"] = Voice([Bar("C"), Bar("G"), Bar("G")])
    score["bass"] = Staff(
        Voice([Bar("C"), Bar("G"), Bar("G")]),
        clef="bass",
    )

    result = score.apply_tonality_plan(
        {0: target_default, 2: target_change},
        voices={"lead"},
    )

    assert result.default_tonality is source_default
    assert result.tonality_plan == TonalityPlan(((1, source_change),))
    assert result["lead"].default_tonality is target_default
    assert result["lead"].tonality_plan == TonalityPlan((
        (2, target_change),
    ))
    assert tuple(result.tonality_at("lead", index) for index in range(3)) == (
        target_default,
        target_default,
        target_change,
    )
    assert tuple(result.tonality_at("bass", index) for index in range(3)) == (
        source_default,
        source_change,
        source_change,
    )
    assert _single_pitches(result["bass"]) == (
        Pitch.parse("C4"),
        Pitch.parse("G4"),
        Pitch.parse("G4"),
    )


def test_plan_transformation_validates_zero_source_and_bar_indices():
    score = Score(default_tonality=Tonality("C"))
    score["lead"] = Voice([Bar("C"), Bar("D")])

    with pytest.raises(ValueError, match="bar 0"):
        score.apply_tonality_plan({1: Tonality("D")})
    with pytest.raises(ValueError, match="lead.*plan index 2"):
        score.apply_tonality_plan({0: Tonality("D"), 2: Tonality("G")})

    contextless = Score()
    contextless["lead"] = Voice([Bar("C")])
    with pytest.raises(ValueError, match="lead.*bar 0"):
        contextless.apply_tonality_plan({0: Tonality("D")})


def test_alignment_errors_identify_voice_and_bar():
    different_lengths = Score()
    different_lengths["lead"] = Voice([Bar("C"), Bar("D")])
    different_lengths["bass"] = Voice([Bar("C")])

    with pytest.raises(ValueError, match="'bass'.*1 bars.*'lead'.*2"):
        different_lengths.validate_alignment()

    different_spans = Score()
    different_spans["lead"] = Voice([
        Bar([Note.rest(Fraction(1, 4))]),
        Bar([Note.rest(Fraction(1, 4))]),
    ])
    different_spans["bass"] = Voice([
        Bar([Note.rest(Fraction(1, 4))]),
        Bar([Note.rest(Fraction(1, 2))]),
    ])

    with pytest.raises(ValueError, match="Bar 1.*'bass'.*'lead'"):
        different_spans.validate_alignment()


def test_rendering_checks_alignment_and_midi_can_opt_out(monkeypatch):
    score = Score()
    score["lead"] = Voice([Bar("C"), Bar("D")])
    score["bass"] = Voice([Bar("C")])

    with pytest.raises(ValueError, match="'bass'.*1 bars"):
        score.to_lilypond()
    with pytest.raises(ValueError, match="'bass'.*1 bars"):
        score.to_midi("score.mid")

    calls = []
    midi = ModuleType("paeonia.midi")

    def score_to_midi_file(
            passed_score,
            *,
            path,
            tpb,
            allow_unaligned,
    ):
        calls.append((passed_score, path, tpb, allow_unaligned))
        return "written"

    midi.score_to_midi_file = score_to_midi_file
    monkeypatch.setitem(sys.modules, "paeonia.midi", midi)

    assert score.to_midi(
        "score.mid",
        tpb=960,
        allow_unaligned=True,
    ) == "written"
    assert calls == [(score, "score.mid", 960, True)]


def test_staff_insertion_order_reaches_score_renderer(monkeypatch):
    score = Score()
    score["zeta"] = Voice([Bar("C")])
    score["alpha"] = Voice([Bar("D")])
    calls = []
    lilypond = ModuleType("paeonia.lilypond")

    def score_to_lilypond(passed_score):
        calls.append(tuple(passed_score.staves))
        return "rendered score"

    lilypond.score_to_lilypond = score_to_lilypond
    monkeypatch.setitem(sys.modules, "paeonia.lilypond", lilypond)

    assert score.to_lilypond() == "rendered score"
    assert calls == [("zeta", "alpha")]
