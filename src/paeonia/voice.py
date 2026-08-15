"""Represent a single musical voice as an ordered sequence of bars."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import copy
from fractions import Fraction

from .bar import Bar
from .tonality import Tonality, TonalityPlan


class Voice:
    """An ordered collection of bars forming one musical part.

    A voice owns its bar list but does not copy the individual, mutable
    :class:`Bar` objects. Its default tonality provides a fallback tonal
    context, while a :class:`TonalityPlan` can override that context at
    selected bar indices. These tonal fields are metadata; construction does
    not alter pitches or bar-level tonalities.

    Parameters
    ----------
    bars : Iterable[Bar] | None
        Initial bars. The iterable is materialized into a fresh list.
    default_tonality : Tonality | None
        Fallback tonal context for bars without a more specific assignment.
    tonality_plan : TonalityPlan | Mapping[int, Tonality] | None
        Tonality changes keyed by zero-based bar index. Mappings are converted
        to an immutable :class:`TonalityPlan`.
    name : str | None
        Optional display name for the voice.

    Raises
    ------
    TypeError
        If a bar, tonality, plan, plan value, or name has the wrong type.
    ValueError
        If the tonality plan contains an invalid bar index.
    """

    def __init__(
            self,
            bars: Iterable[Bar] | None = None,
            *,
            default_tonality: Tonality | None = None,
            tonality_plan: TonalityPlan | Mapping[int, Tonality] | None = None,
            name: str | None = None,
    ) -> None:
        self.bars = [] if bars is None else list(bars)
        if not all(isinstance(bar, Bar) for bar in self.bars):
            raise TypeError("Every voice element must be a Bar")
        if default_tonality is not None and not isinstance(
                default_tonality,
                Tonality,
        ):
            raise TypeError("default_tonality must be a Tonality or None")
        if tonality_plan is None:
            normalized_plan = TonalityPlan()
        elif isinstance(tonality_plan, TonalityPlan):
            normalized_plan = tonality_plan
        elif isinstance(tonality_plan, Mapping):
            normalized_plan = TonalityPlan.from_mapping(tonality_plan)
        else:
            raise TypeError(
                "tonality_plan must be a TonalityPlan, mapping, or None"
            )
        if not all(
                isinstance(tonality, Tonality)
                for _, tonality in normalized_plan.changes
        ):
            raise TypeError("Every tonality plan value must be a Tonality")
        if name is not None and not isinstance(name, str):
            raise TypeError("name must be a string or None")

        self.default_tonality = default_tonality
        self.tonality_plan = normalized_plan
        self.name = name

    def __getitem__(self, i):
        if isinstance(i, slice):
            new_voice = Voice()
            for j in range(0 if i.start is None else i.start,
                           len(self) if i.stop is None else i.stop,
                           1 if i.step is None else i.step):
                new_voice.add_bar(copy(self[j]))
            return new_voice
        else:
            return self.bars[i]

    def __setitem__(self, i, bar):
        self.bars[i] = bar

    def __len__(self):
        return len(self.bars)

    def apply_tonality(
            self,
            target: Tonality,
            source: Tonality | None = None,
            *,
            inherited: Tonality | None = None,
            inherited_plan: TonalityPlan | None = None,
            chromatic: str = "preserve_alteration",
            degree_policy: str = "error",
    ) -> "Voice":
        """Reinterpret every bar in a single target tonality.

        Source tonalities are resolved independently for each bar. An explicit
        ``source`` argument has highest priority, followed by the bar's own
        tonality, this voice's plan, this voice's default tonality, an inherited
        plan, and finally the inherited fallback. Plan changes persist from
        their change index onward according to :meth:`TonalityPlan.at`.

        The operation is immutable. Each transformed bar has its tonality
        cleared because the returned voice stores ``target`` as its default
        tonality. The returned voice also has an empty tonality plan and keeps
        this voice's name. Pitches, rests, chords, durations, velocity, and tie
        metadata otherwise follow :meth:`Bar.apply_tonality`.

        Parameters
        ----------
        target : Tonality
            Tonality in which every transformed pitch is realized.
        source : Tonality | None
            Optional source tonality forced across every bar. When omitted,
            the per-bar precedence chain described above is used.
        inherited : Tonality | None
            Lowest-priority tonal context inherited from a containing object.
        inherited_plan : TonalityPlan | None
            Inherited tonal changes indexed by this voice's bar positions.
        chromatic : str
            Chromatic analysis policy passed to :meth:`Bar.apply_tonality`:
            ``"preserve_alteration"``, ``"error"``, or ``"nearest"``.
        degree_policy : str
            Policy for differing source and target degree counts, passed to
            :meth:`Bar.apply_tonality`: ``"error"`` or ``"wrap"``.

        Returns
        -------
        Voice
            A new voice expressed in ``target``.

        Raises
        ------
        TypeError
            If a supplied tonal context or plan has the wrong type.
        ValueError
            If a policy is unknown, no source tonality can be resolved for a
            bar, or a bar cannot be mapped under the selected policies.
        """
        if not isinstance(target, Tonality):
            raise TypeError("target must be a Tonality")
        for label, tonality in (
                ("source", source),
                ("inherited", inherited),
        ):
            if tonality is not None and not isinstance(tonality, Tonality):
                raise TypeError(f"{label} must be a Tonality or None")
        if inherited_plan is not None and not isinstance(
                inherited_plan,
                TonalityPlan,
        ):
            raise TypeError("inherited_plan must be a TonalityPlan or None")
        if chromatic not in {
                "preserve_alteration",
                "error",
                "nearest",
        }:
            raise ValueError(f"Unknown chromatic policy: {chromatic}")
        if degree_policy not in {"error", "wrap"}:
            raise ValueError(f"Unknown degree policy: {degree_policy}")

        transformed: list[Bar] = []
        for index, bar in enumerate(self.bars):
            inherited_context = (
                inherited_plan.at(index, fallback=inherited)
                if inherited_plan is not None
                else inherited
            )
            voice_fallback = (
                self.default_tonality
                if self.default_tonality is not None
                else inherited_context
            )
            planned = self.tonality_plan.at(
                index,
                fallback=voice_fallback,
            )
            if source is not None:
                effective_source = source
            elif bar.tonality is not None:
                effective_source = bar.tonality
            else:
                effective_source = planned
            if effective_source is None:
                raise ValueError(
                    f"No source tonality is available for bar {index}"
                )
            transformed.append(
                bar.apply_tonality(
                    target=target,
                    source=effective_source,
                    chromatic=chromatic,
                    degree_policy=degree_policy,
                ).with_tonality(None)
            )
        return Voice(
            bars=transformed,
            default_tonality=target,
            tonality_plan=TonalityPlan(),
            name=self.name,
        )

    def span(self) -> Fraction:
        """Return the voice's total duration in whole-note units.

        The result is the sum of every bar's span. Rests contribute their
        durations like pitched notes, and an empty voice has a span of zero.

        Returns
        -------
        Fraction
            Exact total duration across all bars.
        """
        return sum(
            (Fraction(bar.span()) for bar in self.bars),
            Fraction(0),
        )

    def bar_spans(self) -> tuple[Fraction, ...]:
        """Return each bar's duration in voice order.

        Empty bars contribute ``Fraction(0)``. An empty voice therefore
        returns an empty tuple.

        Returns
        -------
        tuple[Fraction, ...]
            Exact duration of each bar in whole-note units.
        """
        return tuple(Fraction(bar.span()) for bar in self.bars)

    def add_bar(self, bar):
        """Add a new bar to this voice.

        Parameters
        ----------
        bar: Bar
            A Bar object
        """
        self.bars.append(bar)

    def to_midi(self, tpb: int = 480):
        """Return MIDI messages for the complete voice.

        Conversion is delegated to :func:`midi.voice_to_midi_messages`. That
        renderer is responsible for carrying the playback offset from one bar
        to the next so events remain correctly ordered across bar boundaries.

        Parameters
        ----------
        tpb : int, default=480
            MIDI ticks per beat.

        Returns
        -------
        list
            MIDI messages emitted by the voice renderer.
        """
        from .midi import voice_to_midi_messages

        return voice_to_midi_messages(self, tpb=tpb)

    def to_lilypond(
            self,
            *,
            inherited: Tonality | None = None,
            inherited_plan: TonalityPlan | None = None,
    ) -> str:
        """Return LilyPond notation for the voice in its score context.

        Rendering is delegated to :func:`lilypond.voice_to_lilypond`. The
        renderer walks bars in order, resolves the effective tonality at each
        bar using the voice and inherited score contexts, and emits a key
        signature only when that resolved tonality changes.

        Parameters
        ----------
        inherited : Tonality | None
            Default tonality inherited from the containing score.
        inherited_plan : TonalityPlan | None
            Score-level tonal changes indexed by bar position.

        Returns
        -------
        str
            LilyPond notation emitted by the voice renderer.
        """
        from .lilypond import voice_to_lilypond

        return voice_to_lilypond(
            self,
            inherited=inherited,
            inherited_plan=inherited_plan,
        )

    def show(self) -> "Voice":
        """Render and display this voice, then return it.

        Display is delegated to :func:`playback.show_voice`. Returning the
        voice supports fluent use in notebooks.

        Returns
        -------
        Voice
            This voice, unchanged.
        """
        from .playback import show_voice

        show_voice(self)
        return self

    def play(
            self,
            tpb: int = 480,
            autoplay: bool = False,
    ) -> "Voice":
        """Render and play this voice, then return it.

        Playback is delegated to :func:`playback.play_voice`.

        Parameters
        ----------
        tpb : int, default=480
            MIDI ticks per beat.
        autoplay : bool, default=False
            Whether the playback helper should start playback immediately.

        Returns
        -------
        Voice
            This voice, unchanged.
        """
        from .playback import play_voice

        play_voice(self, tpb=tpb, autoplay=autoplay)
        return self
