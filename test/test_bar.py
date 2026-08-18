from copy import copy
from fractions import Fraction
from itertools import cycle

from paeonia import Bar, Note, Tonality
from paeonia.pitch import Pitch
from paeonia.tools import euclidean_rhythm, pulses_to_durations
import pytest


def semantic_events(bar):
    return [
        (
            tuple(str(pitch) for pitch in note.pitches),
            note.duration,
            note.is_rest(),
            note.is_chord,
        )
        for note in bar
    ]


def note_metadata(note):
    return (
        note.duration,
        note.velocity,
        note.tie_in,
        note.tie_out,
    )


def test_to_lilypond():
    bar = Bar("C#4. D''8.. R2. Bb,16 <F# A# C#'>2. G, R E4.. <A C' E>1")
    assert(bar.to_lilypond() == "cis'4. d'''4 r2. bes''16 <fis'' ais'' cis'''>2. g''2. r2. e''2 <a'' c''' e'''>1")

def test_eq():
    assert(Bar("R") == Bar("R"))


def test_bars_of_different_lengths_are_not_equal():
    assert Bar("C") != Bar("C C")
    assert Bar("C C") != Bar("C")


def test_bar_plus_note_preserves_left_tonality():
    tonality = Tonality("C")
    bar = Bar("C", tonality=tonality)
    note = Note.parse("E")

    combined = bar + note

    assert combined == Bar("C E", tonality=tonality)
    assert combined.tonality is tonality


def test_bar_addition_resolves_common_tonality():
    tonality = Tonality("C")
    left = Bar("C", tonality=tonality)
    right = Bar("E", tonality=tonality)

    assert (left + right) == Bar("C E", tonality=tonality)
    assert (left + Bar("E")).tonality is tonality
    assert (Bar("C") + right).tonality is tonality


def test_bar_addition_rejects_conflicting_tonalities():
    left = Bar("C", tonality=Tonality("C"))
    right = Bar("D", tonality=Tonality("D"))

    with pytest.raises(ValueError, match="conflicting tonalities"):
        _ = left + right


def test_semitone_transposition_preserves_tonality_and_note_metadata():
    tonality = Tonality("C")
    note = Note(
        pitches=(Pitch.parse("C4"),),
        duration=Fraction(3, 8),
        velocity=0.4,
        tie_in=True,
        tie_out=True,
    )
    rest = Note.rest(Fraction(1, 8)).with_velocity(0.2).with_ties(
        tie_in=True,
    )
    bar = Bar([note, rest], tonality=tonality)
    original = copy(bar)

    raised = bar + 1
    lowered = bar - 1

    assert raised.tonality is tonality
    assert lowered.tonality is tonality
    assert raised[0].midi_pitches == (61,)
    assert lowered[0].midi_pitches == (59,)
    assert raised[0].pitches[0] not in tonality
    assert raised[1].is_rest() and lowered[1].is_rest()
    assert [note_metadata(item) for item in raised] == [
        note_metadata(item) for item in bar
    ]
    assert [note_metadata(item) for item in lowered] == [
        note_metadata(item) for item in bar
    ]
    assert bar == original
    assert raised is not bar
    assert lowered is not bar


def test_multiplication_and_repeat_preserve_tonality():
    tonality = Tonality("C")
    bar = Bar("C8 R", tonality=tonality)
    expected = Bar("C8 R C R", tonality=tonality)

    assert bar * 2 == expected
    assert 2 * bar == expected
    assert bar.repeat(2) == expected
    assert (bar * 0).tonality is tonality
    assert bar.repeat(0).tonality is tonality


def test_copy_slice_and_repeat_preserve_note_metadata_without_mutation():
    tonality = Tonality("Eb", "minor")
    chord = Note(
        pitches=(Pitch.parse("Eb4"), Pitch.parse("Gb4")),
        duration=Fraction(3, 8),
        velocity=0.35,
        tie_in=True,
    )
    rest = Note.rest(Fraction(1, 8)).with_velocity(0.2).with_ties(
        tie_out=True,
    )
    bar = Bar([chord, rest], tonality=tonality)
    original = Bar([chord, rest], tonality=tonality)

    copied = copy(bar)
    sliced = bar[1:]
    multiplied = bar * 2
    repeated = bar.repeat(2)

    assert copied == original
    assert copied is not bar
    assert copied.notes is not bar.notes
    assert sliced == Bar([rest], tonality=tonality)
    assert sliced is not bar
    expected_metadata = [
        note_metadata(chord),
        note_metadata(rest),
        note_metadata(chord),
        note_metadata(rest),
    ]
    assert multiplied.tonality is tonality
    assert repeated.tonality is tonality
    assert [note_metadata(note) for note in multiplied] == expected_metadata
    assert [note_metadata(note) for note in repeated] == expected_metadata
    assert multiplied is not bar
    assert repeated is not bar
    assert bar == original


def test_concatenation_preserves_note_metadata_without_mutation():
    tonality = Tonality("C")
    left_note = Note.parse("C8").with_velocity(0.3).with_ties(tie_in=True)
    right_note = Note.rest(Fraction(1, 8)).with_velocity(0.2).with_ties(
        tie_out=True,
    )
    left = Bar([left_note], tonality=tonality)
    right = Bar([right_note], tonality=tonality)
    original_left = copy(left)
    original_right = copy(right)

    combined = left + right

    assert combined == Bar([left_note, right_note], tonality=tonality)
    assert [note_metadata(note) for note in combined] == [
        note_metadata(left_note),
        note_metadata(right_note),
    ]
    assert combined is not left and combined is not right
    assert left == original_left
    assert right == original_right


def test_division_changes_only_durations_and_preserves_tonality():
    tonality = Tonality("C")
    note = Note(
        pitches=(Pitch.parse("C4"),),
        duration=Fraction(1, 4),
        velocity=0.4,
        tie_in=True,
        tie_out=True,
    )
    bar = Bar([note, Note.rest(Fraction(1, 8))], tonality=tonality)
    original = copy(bar)

    divided = bar / 2

    assert divided.tonality is tonality
    assert [item.duration for item in divided] == [
        Fraction(1, 8),
        Fraction(1, 16),
    ]
    assert divided[0].pitches == note.pitches
    assert divided[0].velocity == note.velocity
    assert divided[0].tie_in is True
    assert divided[0].tie_out is True
    assert divided is not bar
    assert bar == original


def test_stretch_changes_every_duration_and_preserves_bar_and_note_metadata():
    tonality = Tonality("Eb", "minor")
    chord = Note.parse("<Eb G Bb>8").with_velocity(0.4).with_ties(
        tie_in=True,
        tie_out=True,
    )
    rest = Note.rest(Fraction(1, 4)).with_velocity(0.2)
    bar = Bar([chord, rest], tonality=tonality)
    original = copy(bar)

    stretched = bar.stretch(Fraction(3, 2))

    assert [note.duration for note in stretched] == [
        Fraction(3, 16),
        Fraction(3, 8),
    ]
    assert stretched.tonality is tonality
    assert [note.pitches for note in stretched] == [
        chord.pitches,
        rest.pitches,
    ]
    assert [note.velocity for note in stretched] == [0.4, 0.2]
    assert stretched[0].tie_in is True
    assert stretched[0].tie_out is True
    assert stretched is not bar
    assert all(
        actual is not source
        for actual, source in zip(stretched, bar)
    )
    assert bar == original


def test_stretch_forwards_quantization_option_to_every_note():
    bar = Bar("C4 R")

    quantized = bar.stretch(Fraction(5, 4))
    exact = bar.stretch(Fraction(5, 4), quantize=False)

    assert [note.duration for note in quantized] == [
        Fraction(1, 4),
        Fraction(1, 4),
    ]
    assert [note.duration for note in exact] == [
        Fraction(5, 16),
        Fraction(5, 16),
    ]


def test_stretch_empty_bar_returns_new_bar_with_same_tonality():
    tonality = Tonality("C")
    bar = Bar(tonality=tonality)

    stretched = bar.stretch(2)

    assert stretched == bar
    assert stretched is not bar
    assert stretched.tonality is tonality


def test_slices_and_index_lists_preserve_tonality():
    tonality = Tonality("C")
    bar = Bar("C D E F", tonality=tonality)

    assert bar[1::2] == Bar("D F", tonality=tonality)
    assert bar[[3, 0, 3]] == Bar("F C F", tonality=tonality)


@pytest.mark.parametrize(
    "method",
    ["retrograde", "ascending", "descending", "random_order"],
)
def test_pitch_order_transforms_preserve_tonality_and_note_metadata(method):
    tonality = Tonality("C")
    notes = [
        Note(
            pitches=(Pitch.parse("G4"), Pitch.parse("C4")),
            duration=Fraction(3, 8),
            velocity=0.2,
            tie_in=True,
        ),
        Note.rest(Fraction(1, 8)).with_velocity(0.3),
        Note(
            pitches=(Pitch.parse("E4"),),
            duration=Fraction(1, 2),
            velocity=0.8,
            tie_out=True,
        ),
    ]
    bar = Bar(notes, tonality=tonality)
    original = copy(bar)

    transformed = getattr(bar, method)()

    assert transformed.tonality is tonality
    assert [len(note.pitches) for note in transformed] == [2, 0, 1]
    assert [note_metadata(note) for note in transformed] == [
        note_metadata(note) for note in bar
    ]
    assert transformed is not bar
    assert bar == original

def test_retrograde():
    bar1 = Bar("Bb'2. A <A B C> C'4 R B,")
    bar2 = bar1.retrograde()
    assert(bar2 == Bar("B'2. C' <C, B A> A4 R Bb"))

def test_repr():
    paeonia_notation = "C#'2. A <A B C> C'4 R B,"
    bar1 = Bar(paeonia_notation)
    assert semantic_events(Bar(str(bar1))) == semantic_events(bar1)
    assert(eval(repr(bar1)) == bar1)
    single_note = "C'1"
    bar2 = Bar(single_note)
    assert semantic_events(Bar(str(bar2))) == semantic_events(bar2)
    assert(eval(repr(bar2)) == bar2)


def test_paeonia_round_trip_preserves_written_pitch_spelling_and_structure():
    bar = Bar("Bb,16 <F# A# C#'>2. <Bb Db' F>4 R")
    round_tripped = Bar(str(bar))

    assert semantic_events(round_tripped) == semantic_events(bar)
    
def test_note_repeat():
    bar1 = Bar("C D E F G")
    generator = bar1.note_repeat([2, 3, 1])
    bar2 = Bar(" ".join(["R" for _ in range(16)]))
    result = bar2.take(generator, pitches=True)

    assert result == Bar("C C D D D E F F G G G C D D E E")
    assert bar2 == Bar(" ".join(["R" for _ in range(16)]))

def test_take():
    bar1 = Bar("C D E F G")
    bar2 = Bar("C2 G, F")
    pitches = bar1.take(bar2, pitches=True)
    durations = bar2.take(cycle(pitches), durations=True)

    assert str(pitches) == "C G, F C' G,"
    assert str(durations) == "C G, F"
    assert str(bar1) == "C D E F G"
    assert str(bar2) == "C2 G, F"


def test_take_combines_selected_fields_and_preserves_target_tonality():
    tonality = Tonality("C")
    target = Bar(
        [
            Note(
                pitches=(Pitch.parse("C4"),),
                duration=Fraction(1, 4),
                velocity=0.2,
                tie_in=True,
            )
        ],
        tonality=tonality,
    )
    original = copy(target)
    donor = Note(
        pitches=(Pitch.parse("G4"),),
        duration=Fraction(1, 8),
        velocity=0.9,
        tie_out=True,
    )

    result = target.take(
        [donor],
        pitches=True,
        durations=True,
        velocities=True,
    )

    assert result.tonality is tonality
    assert result[0].pitches == donor.pitches
    assert result[0].duration == donor.duration
    assert result[0].velocity == donor.velocity
    assert result[0].tie_in is True
    assert result[0].tie_out is False
    assert result is not target
    assert target == original
    assert target[0].pitches == (Pitch.parse("C4"),)


def test_take_without_selected_fields_does_not_consume_source():
    consumed = False

    def source():
        nonlocal consumed
        consumed = True
        yield Note.parse("D")

    bar = Bar("C", tonality=Tonality("C"))
    result = bar.take(source())

    assert result == bar
    assert result is not bar
    assert consumed is False


def test_take_reports_empty_short_and_invalid_sources():
    bar = Bar("C D")

    with pytest.raises(ValueError, match="empty source bar"):
        bar.take(Bar(), pitches=True)
    with pytest.raises(ValueError, match="does not contain enough notes"):
        bar.take([Note.parse("E")], pitches=True)
    with pytest.raises(TypeError, match="must yield Note"):
        bar.take([object(), object()], pitches=True)

def test_ascending():
    bar1 = Bar("C2 E D4 G R F")
    asc = bar1.ascending()
    assert(asc == Bar("C2 D E4 F R G"))

def test_descending():
    bar1 = Bar("C2 E D4 G R F")
    desc = bar1.descending()
    assert(desc == Bar("G2 F E4 D R C"))

def test_random_order():
    bar1 = Bar("C2 E D4 G R F")
    assert(bar1.random_order() != bar1)
    assert(bar1.random_order().ascending() == Bar("C2 D E4 F R G"))

def test_deprecated_map_tonality_delegates_and_warns(monkeypatch):
    bar = Bar("C F#")
    target = Tonality("C")
    sentinel = Bar("C G", tonality=target)
    calls = []

    def quantize(self, passed_target, *, direction, tie_break="lower"):
        calls.append((self, passed_target, direction, tie_break))
        return sentinel

    monkeypatch.setattr(Bar, "quantize_to_tonality", quantize)

    with pytest.warns(DeprecationWarning, match="map_tonality"):
        result = bar.map_tonality(target, method="up")

    assert result is sentinel
    assert calls == [(bar, target, "up", "lower")]


def test_apply_tonality_preserves_structure_and_assigns_target():
    source = Tonality("C")
    target = Tonality("D")
    bar = Bar("C8 R <E G>4", tonality=source)

    mapped = bar.apply_tonality(target)

    assert mapped == Bar("D8 R <F# A>4", tonality=target)
    assert bar.tonality == source


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (Tonality("C", "minor"), "C Eb G Bb"),
        (Tonality("D", "minor"), "D F A C'"),
    ],
)
def test_apply_tonality_changes_mode_and_tonic(target, expected):
    source = Tonality("C", "major")
    bar = Bar("C E G B", tonality=source)
    original = copy(bar)

    mapped = bar.apply_tonality(target)

    assert mapped == Bar(expected, tonality=target)
    assert mapped is not bar
    assert bar == original


def test_apply_tonality_preserves_chromatic_alterations_and_spelling():
    source = Tonality("C", "major")
    target = Tonality("D", "major")
    chord = Note(
        pitches=tuple(
            Pitch.parse(spelling)
            for spelling in ("F#4", "Gb4", "B#4", "Cb4")
        )
    )
    bar = Bar([chord], tonality=source)
    original = copy(bar)

    mapped = bar.apply_tonality(target)
    source_positions = [source.analyze_pitch(pitch) for pitch in chord.pitches]
    target_positions = [
        target.analyze_pitch(pitch) for pitch in mapped[0].pitches
    ]

    assert [
        (position.degree, position.tonal_octave, position.alteration)
        for position in target_positions
    ] == [
        (position.degree, position.tonal_octave, position.alteration)
        for position in source_positions
    ]
    assert [str(pitch) for pitch in mapped[0].pitches] == [
        "G#4",
        "Ab4",
        "C##4",
        "Db5",
    ]
    assert bar == original


def test_apply_tonality_transforms_chords_and_retains_rests_and_metadata():
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
    bar = Bar([chord, rest], tonality=source)
    original = copy(bar)

    mapped = bar.apply_tonality(target)

    assert mapped[0].pitches == tuple(
        Pitch.parse(pitch) for pitch in ("D4", "F4", "A4")
    )
    assert mapped[1] == rest
    assert [note_metadata(note) for note in mapped] == [
        note_metadata(note) for note in bar
    ]
    assert mapped.tonality is target
    assert bar == original


def test_apply_tonality_validates_source_and_policies():
    with pytest.raises(ValueError, match="source tonality"):
        Bar("C").apply_tonality(Tonality("D"))

    bar = Bar("R", tonality=Tonality("C"))
    with pytest.raises(ValueError, match="Unknown degree policy"):
        bar.apply_tonality(Tonality("D"), degree_policy="unknown")
    with pytest.raises(ValueError, match="Unknown chromatic policy"):
        bar.apply_tonality(Tonality("D"), chromatic="unknown")


def test_apply_tonality_wraps_degrees_for_a_smaller_target_scale():
    source = Tonality("C", "chromatic")
    target = Tonality("C", intervals=(0, 2, 4, 7, 9))

    mapped = Bar("B", tonality=source).apply_tonality(
        target,
        degree_policy="wrap",
    )

    assert mapped == Bar("D", tonality=target)


def test_quantize_to_tonality_preserves_structure_and_assigns_target():
    target = Tonality("C")
    bar = Bar("F#8 R <C# D#>4")

    mapped = bar.quantize_to_tonality(target)

    assert mapped == Bar("F8 R <C D>4", tonality=target)
    assert [note.duration for note in mapped] == [
        note.duration for note in bar
    ]


def test_quantize_to_tonality_obeys_direction_and_tie_break():
    target = Tonality("C")
    bar = Bar("F#")

    assert bar.quantize_to_tonality(
        target,
        tie_break="lower",
    ) == Bar("F", tonality=target)
    assert bar.quantize_to_tonality(
        target,
        tie_break="upper",
    ) == Bar("G", tonality=target)
    assert bar.quantize_to_tonality(
        target,
        direction="down",
    ) == Bar("F", tonality=target)
    assert bar.quantize_to_tonality(
        target,
        direction="up",
    ) == Bar("G", tonality=target)


def test_quantize_to_tonality_validates_policies_for_rest_bar():
    bar = Bar("R")
    target = Tonality("C")

    with pytest.raises(ValueError, match="Unknown quantize direction"):
        bar.quantize_to_tonality(target, direction="unknown")
    with pytest.raises(ValueError, match="Unknown quantize tie_break"):
        bar.quantize_to_tonality(target, tie_break="unknown")


def test_transpose_degrees_preserves_structure_and_tonality():
    tonality = Tonality("C")
    bar = Bar("C8 R <E G>4", tonality=tonality)

    mapped = bar.transpose_degrees(1)

    assert mapped == Bar("D8 R <F A>4", tonality=tonality)
    assert bar == Bar("C8 R <E G>4", tonality=tonality)


def test_transpose_degrees_supports_negative_degrees_and_alterations():
    tonality = Tonality("C")

    assert Bar("F#", tonality=tonality).transpose_degrees(1) == Bar(
        "G#",
        tonality=tonality,
    )
    assert Bar("C", tonality=tonality).transpose_degrees(-1) == Bar(
        "B,",
        tonality=tonality,
    )


def test_transpose_degrees_assigns_explicit_tonality():
    tonality = Tonality("D")

    mapped = Bar("D").transpose_degrees(1, tonality)

    assert mapped == Bar("E", tonality=tonality)


def test_transpose_degrees_validates_context_and_rest_policy():
    with pytest.raises(ValueError, match="No tonality"):
        Bar("C").transpose_degrees(1)

    with pytest.raises(ValueError, match="Unknown chromatic policy"):
        Bar("R", tonality=Tonality("C")).transpose_degrees(
            1,
            chromatic="unknown",
        )


def test_tonal_intervals_use_assigned_tonality_and_flatten_pitches():
    tonality = Tonality("C")
    bar = Bar("C R <E G> C' B,", tonality=tonality)

    assert bar.tonal_intervals() == [2, 2, 3, -1]


def test_tonal_intervals_support_explicit_tonality_and_chromatic_policy():
    bar = Bar("C E", tonality=Tonality("C"))
    chromatic = Tonality("C", "chromatic")

    assert bar.tonal_intervals(chromatic) == [4]
    assert Bar("F# G#", tonality=Tonality("C")).tonal_intervals() == [1]
    with pytest.raises(ValueError, match="not diatonic"):
        Bar("F#", tonality=Tonality("C")).tonal_intervals(
            chromatic="error",
        )


def test_tonal_intervals_validate_context_and_rest_policy():
    with pytest.raises(ValueError, match="No tonality"):
        Bar("C").tonal_intervals()

    bar = Bar("R", tonality=Tonality("C"))
    assert bar.tonal_intervals() == []
    with pytest.raises(ValueError, match="Unknown chromatic policy"):
        bar.tonal_intervals(chromatic="unknown")


def test_inversion():
    bar1 = Bar("C2 Eb D4 G R F#")
    bar2 = bar1.inversion()
    assert(bar2 == Bar("C2 A, A#4 F R F#"))
    bar1 = Bar("C2 <D# G> E")
    bar2 = bar1.inversion()
    assert(bar2 == Bar("C2 <A, F> G#"))

def test_tonal_inversion():
    bar1 = Bar("C2 A, R4 B G")
    t = Tonality()
    assert bar1.tonal_inversion(t) == Bar(
        "C2 E R4 D F",
        tonality=t,
    )


def test_tonal_inversion_uses_degree_intervals_not_semitones():
    tonality = Tonality("C")

    inverted = Bar("C E F", tonality=tonality).tonal_inversion()

    assert inverted == Bar("C A, G", tonality=tonality)


def test_tonal_inversion_preserves_corresponding_alterations():
    tonality = Tonality("C")

    sharp = Bar("F# A#", tonality=tonality).tonal_inversion()
    flat = Bar("C Eb", tonality=tonality).tonal_inversion()

    assert sharp == Bar("F# D#", tonality=tonality)
    assert flat == Bar("C Ab,", tonality=tonality)


def test_tonal_inversion_preserves_event_boundaries_and_properties():
    tonality = Tonality("C")
    bar = Bar("<C E G>8 R4 C'2", tonality=tonality)

    inverted = bar.tonal_inversion()

    assert [len(note.pitches) for note in inverted] == [3, 0, 1]
    assert [note.duration for note in inverted] == [
        note.duration for note in bar
    ]
    assert [
        str(pitch)
        for note in inverted
        for pitch in note.pitches
    ] == ["C4", "A3", "F3", "C3"]


def test_tonal_inversion_validates_context_and_chromatic_policy():
    with pytest.raises(ValueError, match="No tonality"):
        Bar("C E").tonal_inversion()

    rest = Bar("R", tonality=Tonality("C"))
    with pytest.raises(ValueError, match="Unknown chromatic policy"):
        rest.tonal_inversion(chromatic="unknown")
    with pytest.raises(ValueError, match="not diatonic"):
        Bar("F#", tonality=Tonality("C")).tonal_inversion(
            chromatic="error",
        )


def test_tonal_inversion_nearest_policy_quantizes_anchor():
    tonality = Tonality("C")

    inverted = Bar("F#", tonality=tonality).tonal_inversion(
        chromatic="nearest",
    )

    assert inverted == Bar("F", tonality=tonality)

def test_deprecated_tonal_transpose_delegates_and_warns(monkeypatch):
    bar = Bar("C D E")
    tonality = Tonality("C")
    sentinel = Bar("D E F", tonality=tonality)
    calls = []

    def transpose(self, degrees, tonality=None, **options):
        calls.append((self, degrees, tonality, options))
        return sentinel

    monkeypatch.setattr(Bar, "transpose_degrees", transpose)

    with pytest.warns(DeprecationWarning, match="tonal_transpose"):
        result = bar.tonal_transpose(tonality, 1)

    assert result is sentinel
    assert calls == [(bar, 1, tonality, {})]


def test_deprecated_tonal_mode_change_delegates_and_warns(monkeypatch):
    bar = Bar("<C E G>")
    source = Tonality("C", "major")
    target = Tonality("C", "minor")
    sentinel = Bar("<C Eb G>", tonality=target)
    calls = []

    def apply(self, passed_target, source=None, **options):
        calls.append((self, passed_target, source, options))
        return sentinel

    monkeypatch.setattr(Bar, "apply_tonality", apply)

    with pytest.warns(DeprecationWarning, match="tonal_mode_change"):
        result = bar.tonal_mode_change(source, "minor")

    assert result is sentinel
    assert calls == [(bar, target, source, {})]

def test_merge_pitches():
    bar1 = Bar("C D2 R E D1 C R")
    bar2 = Bar("D F2 R G A1 R F")
    result = Bar("<C D> <D F>2 R <E G> <D A>1 C F")
    assert(bar1 & bar2 == result)


def test_merge_pitches_preserves_common_tonality_and_left_metadata():
    tonality = Tonality("C")
    left_note = Note(
        pitches=(Pitch.parse("C4"),),
        duration=Fraction(1, 4),
        velocity=0.25,
        tie_in=True,
        tie_out=True,
    )
    right_note = Note(
        pitches=(Pitch.parse("E4"),),
        duration=Fraction(1, 4),
        velocity=0.9,
    )

    merged = Bar([left_note], tonality=tonality).merge_pitches(
        Bar([right_note])
    )

    assert merged.tonality is tonality
    assert merged[0].pitches == (
        Pitch.parse("C4"),
        Pitch.parse("E4"),
    )
    assert note_metadata(merged[0]) == note_metadata(left_note)

    inherited = Bar([left_note]).merge_pitches(
        Bar([right_note], tonality=tonality)
    )
    assert inherited.tonality is tonality


def test_merge_pitches_requires_compatible_rhythm():
    with pytest.raises(ValueError, match="same number of events"):
        Bar("C D").merge_pitches(Bar("E"))

    with pytest.raises(ValueError, match="durations differ at event 0"):
        Bar("C4").merge_pitches(Bar("E8"))


def test_merge_pitches_rejects_conflicting_tonalities():
    left = Bar("C", tonality=Tonality("C"))
    right = Bar("E", tonality=Tonality("D"))

    with pytest.raises(ValueError, match="conflicting tonalities"):
        left.merge_pitches(right)

def test_pulse_to_durations():
    bar = Bar("C E R")
    pulses = "x.xx...x."
    new_bar_1 = pulses_to_durations(bar, pulses, legato=False)
    new_bar_2 = pulses_to_durations(bar, pulses, legato=True)
    assert(new_bar_1 == Bar("C16 R E R R R R C R"))
    assert(new_bar_2 == Bar("C8 E16 R4 C8"))
    pulses = "...x"
    new_bar_3 = pulses_to_durations(bar, pulses, legato=True)
    assert(new_bar_3 == Bar("R8. C16"))


def test_pulse_to_durations_preserves_source_metadata_and_tonality():
    tonality = Tonality("C")
    source = Note(
        pitches=(Pitch.parse("Eb4"), Pitch.parse("G4")),
        duration=Fraction(1, 2),
        velocity=0.3,
        tie_in=True,
        tie_out=True,
    )
    bar = Bar([source], tonality=tonality)
    original = copy(bar)

    result = pulses_to_durations(
        bar,
        "x..",
        unit=Fraction(1, 16),
    )

    assert result.tonality is tonality
    assert len(result) == 1
    assert result[0].pitches == source.pitches
    assert note_metadata(result[0]) == (
        Fraction(3, 16),
        source.velocity,
        source.tie_in,
        source.tie_out,
    )
    assert result is not bar
    assert bar == original


def test_pulse_to_durations_emits_explicit_tied_frames():
    tonality = Tonality("C")
    source = Note(
        pitches=(Pitch.parse("D#4"),),
        duration=Fraction(1, 4),
        velocity=0.4,
    )

    result = pulses_to_durations(
        Bar([source], tonality=tonality),
        "..x..",
        unit=Fraction(1, 16),
        emit_ties=True,
    )

    assert result.tonality is tonality
    assert len(result) == 4
    assert result[0] == Note.rest(Fraction(1, 8))
    assert all(
        note.duration == Fraction(1, 16) for note in result[1:]
    )
    assert all(note.pitches == source.pitches for note in result[1:])
    assert all(note.velocity == source.velocity for note in result[1:])
    assert [
        (note.tie_in, note.tie_out) for note in result[1:]
    ] == [(False, True), (True, True), (True, False)]


def test_pulse_to_durations_non_legato_uses_unit_events():
    source = Note.parse("F#").with_velocity(0.2).with_ties(
        tie_in=True,
        tie_out=True,
    )

    result = pulses_to_durations(
        Bar([source]),
        "x.",
        legato=False,
        unit=Fraction(1, 8),
        emit_ties=True,
    )

    assert result[0] == source.with_duration(Fraction(1, 8))
    assert result[1] == Note.rest(Fraction(1, 8))


def test_pulse_to_durations_does_not_split_source_rests_for_ties():
    source = Note.rest().with_velocity(0.2)

    result = pulses_to_durations(
        Bar([source]),
        "x..",
        unit=Fraction(1, 16),
        emit_ties=True,
    )

    assert result == Bar([source.with_duration(Fraction(3, 16))])


def test_pulse_to_durations_validates_input_and_handles_empty_pattern():
    tonality = Tonality("C")
    bar = Bar("C", tonality=tonality)

    empty = pulses_to_durations(bar, "")
    assert len(empty) == 0
    assert empty.tonality is tonality

    with pytest.raises(ValueError, match="Invalid pulse"):
        pulses_to_durations(bar, "x-o")
    with pytest.raises(ValueError, match="unit must be positive"):
        pulses_to_durations(bar, "x", unit=0)
    with pytest.raises(ValueError, match="empty bar"):
        pulses_to_durations(Bar(), "x")


def test_euclidean_rhythm():
    bar = Bar("C E D")
    er_bar = euclidean_rhythm(bar, 13, 5, offset=3)
    assert(er_bar == Bar("C8. E8 D8. C8 E8."))
    bar = Bar("C")
    er_bar = euclidean_rhythm(bar, 8, 3, offset=3)
    assert(er_bar == Bar("C8. C8 C8."))
    er_bar = euclidean_rhythm(bar, 8, 4)
    assert(er_bar == Bar("C8 C C C"))


def test_euclidean_rhythm_can_emit_tied_frames_and_preserves_tonality():
    tonality = Tonality("C")
    source = Note(
        pitches=(Pitch.parse("D#4"),),
        velocity=0.4,
    )
    bar = Bar([source], tonality=tonality)
    original = copy(bar)

    result = euclidean_rhythm(
        bar,
        8,
        4,
        emit_ties=True,
    )

    assert result.tonality is tonality
    assert len(result) == 8
    assert all(note.duration == Fraction(1, 16) for note in result)
    assert all(note.pitches == source.pitches for note in result)
    assert all(note.velocity == source.velocity for note in result)
    assert [
        (note.tie_in, note.tie_out) for note in result
    ] == [
        (False, True),
        (True, False),
        (False, True),
        (True, False),
        (False, True),
        (True, False),
        (False, True),
        (True, False),
    ]
    assert result is not bar
    assert bar == original


def test_euclidean_rhythm_validates_dimensions():
    bar = Bar("C")

    with pytest.raises(ValueError, match="n must be positive"):
        euclidean_rhythm(bar, 0, 0)
    with pytest.raises(ValueError, match="0 <= k <= n"):
        euclidean_rhythm(bar, 4, 5)
    with pytest.raises(TypeError, match="integers"):
        euclidean_rhythm(bar, 8.0, 3)


def test_euclidean_rhythm_handles_all_and_no_onsets():
    bar = Bar("C D")

    assert euclidean_rhythm(bar, 4, 4) == Bar("C16 D C D")
    assert euclidean_rhythm(bar, 4, 0) == Bar("R4")
