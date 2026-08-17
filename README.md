# Paeonia

Paeonia is a Python model for computer-assisted composition. Pitches retain
their written spelling, tonal transformations work in scale-degree space, and
bars, voices, and scores carry their own tonal context. The core model does not
need LilyPond, FluidSynth, or a running notebook.

The complete generated API reference is published at
[orbitfold.github.io/paeonia](https://orbitfold.github.io/paeonia/).

Build the same documentation locally with:

```bash
python -m pip install --editable ".[docs]"
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

Install the package from the repository and import the public model directly:

```bash
pip install git+https://github.com/orbitfold/paeonia.git
```

```python
from paeonia import (
    Bar,
    Pitch,
    Score,
    Staff,
    Tonality,
    TonalityPlan,
    Voice,
)
```

## Spelled pitches

`Pitch` separates written spelling from sound. Enharmonic pitches can therefore
produce the same MIDI note without becoming the same structural value:

```python
d_sharp = Pitch.parse("D#4")
e_flat = Pitch.parse("Eb4")

assert d_sharp != e_flat
assert d_sharp.midi == e_flat.midi
assert d_sharp.enharmonic_equals(e_flat)
```

`PitchClass.parse()` accepts sharps, flats, and repeated accidentals such as
`F##` or `Ebb`. `Pitch.parse()` adds an explicit scientific-pitch octave.

## Tonal bars

A bar can carry the tonality in which its pitches should be interpreted:

```python
c_major = Tonality("C", "major")
source = Bar("C E F# G", tonality=c_major)

c_dorian = source.apply_tonality(Tonality("C", "dorian"))
d_dorian = source.apply_tonality(Tonality("D", "dorian"))
```

`apply_tonality()` analyzes each source pitch as a scale degree plus chromatic
alteration, then realizes that position in the target. In the example, `F#` is
an altered fourth degree; that alteration remains attached to the fourth degree
after either mode or tonic changes. Rests, chord boundaries, durations,
velocities, and ties are retained.

`quantize_to_tonality()` answers a different question:

```python
nearest = source.quantize_to_tonality(
    Tonality("D", "major"),
    direction="nearest",
    tie_break="lower",
)
```

It moves each sounding pitch to a nearby member of the target scale by MIDI
distance. It does not reinterpret source degrees and does not need a source
tonality. Use `apply_tonality()` for a tonal reinterpretation; use
`quantize_to_tonality()` to constrain existing sounds to a pitch collection.

## Voice and score tonal plans

A `TonalityPlan` contains persistent changes keyed by zero-based bar index. A
change remains active until a later change replaces it:

```python
g_major = Tonality("G", "major")
d_major = Tonality("D", "major")

voice = Voice(
    [Bar("C E G"), Bar("G B D"), Bar("D F# A")],
    default_tonality=c_major,
    tonality_plan=TonalityPlan.from_mapping({1: g_major, 2: d_major}),
    name="Melody",
)

assert voice.tonality_at(0) == c_major
assert voice.tonality_at(1) == g_major
assert voice.tonality_at(2) == d_major
```

`Staff` keeps a voice together with its clef and MIDI presentation metadata.
`Score` supplies inherited tonal context and a score-wide plan:

```python
score = Score(
    default_tonality=c_major,
    tonality_plan={1: g_major, 2: d_major},
    tempo=108,
    time_signature=(3, 4),
    title="Tonal plan",
)
score["melody"] = Staff(
    Voice([Bar("C E G"), Bar("G B D"), Bar("D F# A")]),
    name="Melody",
    midi_channel=0,
    midi_program=40,
)
score["bass"] = Staff(
    Voice([Bar("C, G, C"), Bar("G, D G"), Bar("D, A, D")]),
    clef="bass",
    name="Bass",
    midi_channel=1,
    midi_program=42,
)

assert score.tonality_at("bass", 1) == g_major
```

Use `score.apply_tonality(target)` to transform every staff into one target, or
`score.apply_tonality_plan({0: c_major, 2: d_major})` to transform all bars and
store synchronized target changes. Both operations return a new score.

## Workbench

Run the module to copy the bundled workbench into the current directory and
open it in JupyterLab:

```bash
python -m paeonia
```

Use `--copy-only` to create the notebook without launching Jupyter,
`--no-browser` for a headless server, and `--reset` to replace an existing local
copy with the packaged notebook.

## Triadex status

Earlier Paeonia versions included a `TriadexMuse` generator. It was intentionally
removed from the current package and is not part of the public API. The bundled
workbench calls this out instead of presenting an import that cannot run. A
future generator can return ordinary `Bar` values and participate in the tonal
workflow shown above without coupling it to the core model.

## Rendering and playback

String and MIDI conversion are handled by Paeonia itself:

```python
lilypond_source = score.to_lilypond()
score.to_midi("example.mid")
```

Displaying engraved notation with `score.show()` additionally requires the
`lilypond` executable on `PATH`. Audio preview with `score.play()` requires the
`fluidsynth` executable; the playback helper downloads its soundfont lazily on
first use. These external programs are optional and are not required for pitch,
tonality, transformation, MIDI-message, or LilyPond-string operations.
