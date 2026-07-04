"""Triadex Muse-inspired deterministic composition generator.

The implementation follows the original Muse's central mechanism:

* a four-bit counter supplies C1, C2, C4 and C8;
* a two-bit counter advances once every three beats and supplies C3 and C6;
* a 31-bit shift register supplies B1 through B31;
* four THEME selectors are combined with even parity (four-input XNOR) to
  produce the next B1 bit;
* four INTERVAL selectors produce a diatonic scale degree and octave.

The generator returns ordinary :class:`paeonia.Bar` objects, so generated
material can be transformed, rendered and previewed with the rest of Paeonia.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


SOURCE_NAMES: Tuple[str, ...] = (
    "OFF",
    "ON",
    "C1/2",
    "C1",
    "C2",
    "C4",
    "C8",
    "C3",
    "C6",
    *(f"B{i}" for i in range(1, 32)),
)

SOURCE_ALIASES: Dict[str, str] = {
    "C½": "C1/2",
    "C 1/2": "C1/2",
    "C0.5": "C1/2",
}

MAJOR_SCALE: Tuple[int, ...] = (0, 2, 4, 5, 7, 9, 11, 12)

# The worked example in the original programming manual.
MANUAL_EXAMPLE = {
    "interval": ("C1", "B4", "B2", "B7"),
    "theme": ("OFF", "B1", "B3", "B6"),
}

PRESETS = {
    "Manual example": MANUAL_EXAMPLE,
    "Counter melody": {
        "interval": ("C1", "C2", "C4", "C8"),
        "theme": ("OFF", "OFF", "OFF", "OFF"),
    },
    "Slow feedback": {
        "interval": ("B7", "B13", "B19", "C8"),
        "theme": ("B1", "B4", "B22", "C3"),
    },
    "Long feedback": {
        "interval": ("B2", "B11", "B23", "B31"),
        "theme": ("B1", "B3", "B28", "C6"),
    },
}


def _normalise_source(source: str) -> str:
    source = SOURCE_ALIASES.get(source.strip().upper(), source.strip().upper())
    if source not in SOURCE_NAMES:
        raise ValueError(
            f"Unknown Muse source {source!r}. Expected one of: "
            + ", ".join(SOURCE_NAMES)
        )
    return source


def _validate_selectors(name: str, selectors: Sequence[str]) -> Tuple[str, str, str, str]:
    if len(selectors) != 4:
        raise ValueError(f"{name} must contain exactly four source names")
    values = tuple(_normalise_source(source) for source in selectors)
    return values  # type: ignore[return-value]


@dataclass(frozen=True)
class MuseFrame:
    """One audible state of the Muse.

    Parameters
    ----------
    beat:
        One-based main clock count.
    half:
        Zero for the first half of the beat and one for the second half.
    new_bit:
        Bit shifted into B1 at the start of this beat.
    interval_bits:
        Current values of Interval A, B, C and D.
    pitch:
        MIDI pitch, or ``None`` for a rest.
    duration:
        Musical duration represented as a fraction of a whole note.
    """

    beat: int
    half: int
    new_bit: int
    interval_bits: Tuple[int, int, int, int]
    pitch: Optional[int]
    duration: Fraction


class TriadexMuse:
    """Generate deterministic melodies using the Triadex Muse algorithm.

    Parameters
    ----------
    interval:
        Four sources selected by Interval A, B, C and D. A, B and C form a
        three-bit scale index; D raises the result by an octave.
    theme:
        Four sources selected by Theme W, X, Y and Z. Their even parity is
        shifted into B1 on every main clock.
    root:
        MIDI pitch used for the low scale root. ``60`` is middle C.
    scale:
        Eight semitone offsets indexed by the A/B/C bits. The original Muse
        uses the major-scale mapping ``(0, 2, 4, 5, 7, 9, 11, 12)``.
    rest:
        Convert the lowest interval state ``0000`` into a rest.
    """

    def __init__(
        self,
        interval: Sequence[str] = MANUAL_EXAMPLE["interval"],
        theme: Sequence[str] = MANUAL_EXAMPLE["theme"],
        root: int = 60,
        scale: Sequence[int] = MAJOR_SCALE,
        rest: bool = False,
    ) -> None:
        self.interval = _validate_selectors("interval", interval)
        self.theme = _validate_selectors("theme", theme)

        if len(scale) != 8:
            raise ValueError("scale must contain exactly eight semitone offsets")
        if not 0 <= root <= 127:
            raise ValueError("root must be a MIDI note from 0 to 127")

        self.root = int(root)
        self.scale = tuple(int(offset) for offset in scale)
        self.rest = bool(rest)
        self.reset()

    def reset(self) -> "TriadexMuse":
        """Return all counters and shift-register cells to zero."""

        self.binary_counter = 0
        self.ternary_counter = 0
        self.ternary_phase = 0
        self.shift_register: List[int] = [0] * 31
        self.beat = 0
        return self

    def copy(self, reset: bool = False) -> "TriadexMuse":
        """Return an independent copy of this generator."""

        other = TriadexMuse(
            interval=self.interval,
            theme=self.theme,
            root=self.root,
            scale=self.scale,
            rest=self.rest,
        )
        if not reset:
            other.binary_counter = self.binary_counter
            other.ternary_counter = self.ternary_counter
            other.ternary_phase = self.ternary_phase
            other.shift_register = list(self.shift_register)
            other.beat = self.beat
        return other

    def read_source(self, source: str, half_clock: int = 0) -> int:
        """Read one of the 40 selectable binary sources."""

        source = _normalise_source(source)
        if half_clock not in (0, 1):
            raise ValueError("half_clock must be zero or one")

        if source == "OFF":
            return 0
        if source == "ON":
            return 1
        if source == "C1/2":
            return half_clock
        if source == "C1":
            return self.binary_counter & 1
        if source == "C2":
            return (self.binary_counter >> 1) & 1
        if source == "C4":
            return (self.binary_counter >> 2) & 1
        if source == "C8":
            return (self.binary_counter >> 3) & 1
        if source == "C3":
            return self.ternary_counter & 1
        if source == "C6":
            return (self.ternary_counter >> 1) & 1

        position = int(source[1:])
        return self.shift_register[position - 1]

    def _theme_bit(self) -> int:
        # The register changes on the high-to-low clock edge. At that edge the
        # C1/2 source is sampled high, immediately before it falls low.
        values = [self.read_source(source, half_clock=1) for source in self.theme]
        return int(sum(values) % 2 == 0)

    def _advance_counters(self) -> None:
        self.binary_counter = (self.binary_counter + 1) % 16
        self.ternary_phase += 1
        if self.ternary_phase == 3:
            self.ternary_phase = 0
            self.ternary_counter = (self.ternary_counter + 1) % 4

    def advance(self) -> int:
        """Advance the main clock once and return the new B1 bit."""

        new_bit = self._theme_bit()
        self.shift_register = [new_bit, *self.shift_register[:-1]]
        self._advance_counters()
        self.beat += 1
        return new_bit

    def interval_bits(self, half_clock: int = 0) -> Tuple[int, int, int, int]:
        """Read the current Interval A, B, C and D values."""

        return tuple(
            self.read_source(source, half_clock=half_clock)
            for source in self.interval
        )  # type: ignore[return-value]

    def pitch(self, half_clock: int = 0) -> Optional[int]:
        """Return the current MIDI pitch, or ``None`` for a rest."""

        a, b, c, d = self.interval_bits(half_clock=half_clock)
        scale_index = a + 2 * b + 4 * c

        if self.rest and scale_index == 0 and d == 0:
            return None

        pitch = self.root + self.scale[scale_index] + 12 * d
        if not 0 <= pitch <= 127:
            raise ValueError(
                f"Generated MIDI pitch {pitch} is outside the valid range 0..127"
            )
        return pitch

    def step(self, duration: Fraction = Fraction(1, 4)) -> MuseFrame:
        """Advance one main beat and return its first-half state.

        Use :meth:`frames` when ``C1/2`` should be audible, because it returns
        both halves of every main beat.
        """

        duration = Fraction(duration)
        new_bit = self.advance()
        bits = self.interval_bits(half_clock=0)
        return MuseFrame(
            beat=self.beat,
            half=0,
            new_bit=new_bit,
            interval_bits=bits,
            pitch=self.pitch(half_clock=0),
            duration=duration,
        )

    def frames(
        self,
        beats: int,
        unit: Fraction = Fraction(1, 4),
        include_half_clock: bool = True,
        reset: bool = True,
    ) -> Iterator[MuseFrame]:
        """Yield audible states for a number of main clock beats.

        When ``include_half_clock`` is true, each beat is emitted as two
        half-duration frames. This makes selections of ``C1/2`` audible. Equal
        consecutive frames are later joined by :meth:`to_bar` unless retrigger
        mode is requested.
        """

        if beats < 0:
            raise ValueError("beats must be non-negative")
        unit = Fraction(unit)
        if unit <= 0:
            raise ValueError("unit must be positive")
        if reset:
            self.reset()

        for _ in range(beats):
            new_bit = self.advance()
            if include_half_clock:
                frame_duration = unit / 2
                halves: Iterable[int] = (0, 1)
            else:
                frame_duration = unit
                halves = (0,)

            for half in halves:
                bits = self.interval_bits(half_clock=half)
                yield MuseFrame(
                    beat=self.beat,
                    half=half,
                    new_bit=new_bit,
                    interval_bits=bits,
                    pitch=self.pitch(half_clock=half),
                    duration=frame_duration,
                )

    def generate(
        self,
        beats: int,
        unit: Fraction = Fraction(1, 4),
        include_half_clock: bool = True,
        reset: bool = True,
    ) -> List[MuseFrame]:
        """Return generated frames as a list."""

        return list(
            self.frames(
                beats=beats,
                unit=unit,
                include_half_clock=include_half_clock,
                reset=reset,
            )
        )

    def to_bar(
        self,
        beats: int,
        unit: Fraction = Fraction(1, 4),
        include_half_clock: bool = True,
        retrigger: bool = False,
        velocity: float = 0.75,
        reset: bool = True,
    ):
        """Generate a :class:`paeonia.Bar`.

        Consecutive equal pitches are tied into one longer note by default.
        This is how rhythm emerges in the original Muse: a note remains held
        until the Interval state changes. Set ``retrigger=True`` to create one
        note per generated frame instead.
        """

        from .bar import Bar
        from .note import Note

        frames = self.frames(
            beats=beats,
            unit=unit,
            include_half_clock=include_half_clock,
            reset=reset,
        )

        notes: List[Note] = []
        for frame in frames:
            pitches = [] if frame.pitch is None else [frame.pitch]
            if (
                not retrigger
                and notes
                and notes[-1].pitches == pitches
                and notes[-1].velocity == velocity
            ):
                notes[-1].duration += frame.duration
            else:
                notes.append(
                    Note(
                        pitches=pitches,
                        duration=frame.duration,
                        velocity=velocity,
                    )
                )
        return Bar(notes=notes)

    def preview(
        self,
        beats: int = 32,
        unit: Fraction = Fraction(1, 4),
        autoplay: bool = False,
        **bar_options,
    ):
        """Generate and play a Muse phrase through Paeonia's preview system."""

        bar = self.to_bar(beats=beats, unit=unit, **bar_options)
        bar.play(autoplay=autoplay)
        return bar

    def widget(self, beats: int = 32, unit: Fraction = Fraction(1, 4)):
        """Return an interactive Jupyter control panel for this generator."""

        return muse_widget(self, beats=beats, unit=unit)


def muse_widget(
    muse: Optional[TriadexMuse] = None,
    beats: int = 32,
    unit: Fraction = Fraction(1, 4),
):
    """Create an interactive Muse editor and preview panel for Jupyter."""

    try:
        import ipywidgets as widgets
        from IPython.display import clear_output, display
    except ImportError as exc:  # pragma: no cover - depends on notebook extras
        raise RuntimeError(
            "The Muse widget requires ipywidgets. Install Paeonia's notebook "
            "dependencies or run `pip install ipywidgets`."
        ) from exc

    muse = muse.copy(reset=True) if muse is not None else TriadexMuse()
    preset = widgets.Dropdown(
        options=list(PRESETS), value="Manual example", description="Preset"
    )
    interval_controls = [
        widgets.Dropdown(options=SOURCE_NAMES, value=value, description=label)
        for label, value in zip(("A", "B", "C", "D"), muse.interval)
    ]
    theme_controls = [
        widgets.Dropdown(options=SOURCE_NAMES, value=value, description=label)
        for label, value in zip(("W", "X", "Y", "Z"), muse.theme)
    ]
    root_control = widgets.IntSlider(
        value=muse.root, min=24, max=84, step=1, description="Root MIDI"
    )
    beats_control = widgets.IntSlider(
        value=beats, min=1, max=256, step=1, description="Beats"
    )
    unit_control = widgets.Dropdown(
        options=("1/2", "1/4", "1/8", "1/16"),
        value=str(Fraction(unit)),
        description="Beat unit",
    )
    rest_control = widgets.Checkbox(value=muse.rest, description="Lowest state rests")
    half_control = widgets.Checkbox(value=True, description="Use C1/2 half-beats")
    retrigger_control = widgets.Checkbox(value=False, description="Retrigger equal notes")
    generate_button = widgets.Button(description="Generate", button_style="primary")
    play_button = widgets.Button(description="Play")
    score_button = widgets.Button(description="Show score")
    output = widgets.Output()
    current = {"bar": None}

    def apply_preset(change=None):
        values = PRESETS[preset.value]
        for control, value in zip(interval_controls, values["interval"]):
            control.value = value
        for control, value in zip(theme_controls, values["theme"]):
            control.value = value

    def build_bar():
        generator = TriadexMuse(
            interval=tuple(control.value for control in interval_controls),
            theme=tuple(control.value for control in theme_controls),
            root=root_control.value,
            rest=rest_control.value,
        )
        return generator.to_bar(
            beats=beats_control.value,
            unit=Fraction(unit_control.value),
            include_half_clock=half_control.value,
            retrigger=retrigger_control.value,
        )

    def generate(_=None):
        bar = build_bar()
        current["bar"] = bar
        with output:
            clear_output(wait=True)
            print(bar)
            display(bar)
        return bar

    def play(_=None):
        bar = generate()
        with output:
            try:
                bar.play(autoplay=True)
            except FileNotFoundError as exc:
                print(
                    "Preview requires FluidSynth. Install it and run Play again.\n"
                    f"Original error: {exc}"
                )
            except Exception as exc:
                print(f"Could not render audio preview: {exc}")

    def show_score(_=None):
        bar = generate()
        with output:
            try:
                bar.show()
            except FileNotFoundError as exc:
                print(
                    "Score rendering requires LilyPond. Install it and run "
                    f"Show score again.\nOriginal error: {exc}"
                )
            except Exception as exc:
                print(f"Could not render score: {exc}")

    preset.observe(apply_preset, names="value")
    generate_button.on_click(generate)
    play_button.on_click(play)
    score_button.on_click(show_score)

    panel = widgets.VBox(
        [
            widgets.HTML("<h3>Triadex Muse</h3>"),
            preset,
            widgets.HTML("<b>Interval selectors</b>"),
            widgets.HBox(interval_controls),
            widgets.HTML("<b>Theme selectors</b>"),
            widgets.HBox(theme_controls),
            widgets.HBox([root_control, beats_control, unit_control]),
            widgets.HBox([rest_control, half_control, retrigger_control]),
            widgets.HBox([generate_button, play_button, score_button]),
            output,
        ]
    )

    def get_bar():
        """Return the most recently generated bar.

        Generate one using the current widget settings if necessary.
        """
        if current["bar"] is None:
            return generate()
        return current["bar"]

    panel.get_bar = get_bar
    panel.generate_bar = generate
    panel.build_bar = build_bar
    
    return panel
