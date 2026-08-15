"""Represent a score as an ordered mapping of named staves."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from copy import copy
from dataclasses import replace

from .staff import Staff, VALID_CLEFS
from .tonality import Tonality, TonalityPlan
from .voice import Voice


def _normalize_plan(
        plan: TonalityPlan | Mapping[int, Tonality] | None,
        *,
        label: str,
) -> TonalityPlan:
    """Normalize and validate score or transformation plan metadata."""
    if plan is None:
        normalized = TonalityPlan()
    elif isinstance(plan, TonalityPlan):
        normalized = plan
    elif isinstance(plan, Mapping):
        changes = tuple(plan.items())
        if not all(isinstance(index, int) for index, _ in changes):
            raise TypeError(f"Every {label} index must be an integer")
        normalized = TonalityPlan(changes)
    else:
        raise TypeError(f"{label} must be a TonalityPlan, mapping, or None")
    if not all(
            isinstance(index, int)
            for index, _ in normalized.changes
    ):
        raise TypeError(f"Every {label} index must be an integer")
    if not all(
            isinstance(tonality, Tonality)
            for _, tonality in normalized.changes
    ):
        raise TypeError(f"Every {label} value must be a Tonality")
    return normalized


def _copy_voice(voice: Voice) -> Voice:
    """Return a structurally independent copy of a voice."""
    return Voice(
        bars=[copy(bar) for bar in voice.bars],
        default_tonality=voice.default_tonality,
        tonality_plan=voice.tonality_plan,
        name=voice.name,
    )


def _copy_staff(staff: Staff) -> Staff:
    """Return a staff copy whose mutable voice and bars are also copied."""
    return replace(staff, voice=_copy_voice(staff.voice))


class Score:
    """An ordered collection of named staves and global musical metadata.

    ``Score`` retains dictionary-style voice access for compatibility while
    storing each voice, clef, name, and MIDI assignment together in a
    :class:`Staff`. Score-level tonality is inherited by voices that do not
    provide a more local tonal context.

    Parameters
    ----------
    default_tonality : Tonality | None
        Score-wide fallback tonality.
    tonality_plan : TonalityPlan | Mapping[int, Tonality] | None
        Score-wide tonal changes keyed by zero-based bar index.
    tempo : int, default=120
        Tempo in beats per minute.
    time_signature : tuple[int, int], default=(4, 4)
        Positive numerator and denominator.
    title : str | None
        Optional score title.
    """

    def __init__(
            self,
            *,
            default_tonality: Tonality | None = None,
            tonality_plan: (
                TonalityPlan | Mapping[int, Tonality] | None
            ) = None,
            tempo: int = 120,
            time_signature: tuple[int, int] = (4, 4),
            title: str | None = None,
    ) -> None:
        if default_tonality is not None and not isinstance(
                default_tonality,
                Tonality,
        ):
            raise TypeError("default_tonality must be a Tonality or None")
        if not isinstance(time_signature, tuple) or len(time_signature) != 2:
            raise TypeError("time_signature must be a two-item tuple")
        if not all(isinstance(value, int) for value in time_signature):
            raise TypeError("Time-signature values must be integers")
        if title is not None and not isinstance(title, str):
            raise TypeError("title must be a string or None")

        self.staves: dict[str, Staff] = {}
        self.default_tonality = default_tonality
        self.tonality_plan = _normalize_plan(
            tonality_plan,
            label="tonality_plan",
        )
        self.tempo = int(tempo)
        self.time_signature = time_signature
        self.title = title

        if self.tempo <= 0:
            raise ValueError("Tempo must be positive")
        numerator, denominator = self.time_signature
        if numerator <= 0 or denominator <= 0:
            raise ValueError("Time-signature values must be positive")

    def __setitem__(self, name: str, value: Voice | Staff) -> None:
        """Insert a voice or staff under ``name`` in score order."""
        if not isinstance(name, str):
            raise TypeError("Staff name must be a string")
        if isinstance(value, Voice):
            value = Staff(voice=value, clef="treble", name=name)
        elif isinstance(value, Staff):
            if value.name is None:
                value.name = name
        else:
            raise TypeError("Score values must be Voice or Staff instances")
        self.staves[name] = value

    def __getitem__(self, name: str) -> Voice:
        """Return the voice stored under ``name``."""
        return self.staves[name].voice

    @property
    def voices(self) -> dict[str, Voice]:
        """Return a compatibility view mapping staff names to voices."""
        return {
            name: staff.voice
            for name, staff in self.staves.items()
        }

    @property
    def clefs(self) -> dict[str, str]:
        """Return a compatibility view mapping staff names to clefs."""
        return {
            name: staff.clef
            for name, staff in self.staves.items()
        }

    def set_clef(self, voice: str, clef: str) -> None:
        """Set the clef of a named staff.

        Parameters
        ----------
        voice : str
            Name used to insert the staff into this score.
        clef : str
            One of ``"treble"``, ``"alto"``, ``"tenor"``, or ``"bass"``.
        """
        if clef not in VALID_CLEFS:
            raise ValueError(f"Invalid clef: {clef}")
        self.staves[voice].clef = clef

    def tonality_at(
            self,
            staff_name: str,
            bar_index: int,
    ) -> Tonality | None:
        """Resolve a staff's effective tonality at a bar index."""
        staff = self.staves[staff_name]
        return staff.voice.tonality_at(
            bar_index,
            inherited=self.default_tonality,
            inherited_plan=self.tonality_plan,
        )

    def copy_structure_without_staves(self) -> "Score":
        """Copy score-level metadata into a new score with no staves."""
        return Score(
            default_tonality=self.default_tonality,
            tonality_plan=self.tonality_plan,
            tempo=self.tempo,
            time_signature=self.time_signature,
            title=self.title,
        )

    def copy(self) -> "Score":
        """Return a structurally independent score copy."""
        result = self.copy_structure_without_staves()
        result.staves = {
            name: _copy_staff(staff)
            for name, staff in self.staves.items()
        }
        return result

    def _selected_staff_names(
            self,
            voices: Collection[str] | None,
    ) -> set[str]:
        if voices is None:
            selected = set(self.staves)
        elif isinstance(voices, str):
            selected = {voices}
        else:
            selected = set(voices)
        if not all(isinstance(name, str) for name in selected):
            raise TypeError("Voice names must be strings")
        unknown = selected - set(self.staves)
        if unknown:
            raise KeyError(f"Unknown voices: {sorted(unknown)}")
        return selected

    @staticmethod
    def _validate_transform_options(
            target: Tonality | None,
            source: Tonality | None,
            chromatic: str,
    ) -> None:
        if target is not None and not isinstance(target, Tonality):
            raise TypeError("target must be a Tonality")
        if source is not None and not isinstance(source, Tonality):
            raise TypeError("source must be a Tonality or None")
        if chromatic not in {
                "preserve_alteration",
                "error",
                "nearest",
        }:
            raise ValueError(f"Unknown chromatic policy: {chromatic}")

    def apply_tonality(
            self,
            target: Tonality,
            source: Tonality | None = None,
            *,
            voices: Collection[str] | None = None,
            chromatic: str = "preserve_alteration",
    ) -> "Score":
        """Reinterpret selected staves in one target tonality.

        Source tonality is resolved independently for each original bar. When
        all staves are selected, the target becomes score-level metadata. For
        a selective transformation, it becomes local metadata on each changed
        voice. Staff presentation and MIDI metadata are preserved.

        Parameters
        ----------
        target : Tonality
            Tonality in which selected pitches are realized.
        source : Tonality | None
            Optional source forced across every selected bar.
        voices : Collection[str] | None
            Staff names to transform, or ``None`` for every staff.
        chromatic : str
            Chromatic analysis policy passed to ``Bar.apply_tonality``.

        Returns
        -------
        Score
            A transformed score; the original is unchanged.
        """
        self._validate_transform_options(target, source, chromatic)
        selected = self._selected_staff_names(voices)
        self.validate_alignment()
        result = self.copy_structure_without_staves()
        transform_all = selected == set(self.staves)
        if transform_all:
            result.default_tonality = target
            result.tonality_plan = TonalityPlan()

        for name, staff in self.staves.items():
            if name not in selected:
                result.staves[name] = _copy_staff(staff)
                continue
            transformed_voice = staff.voice.apply_tonality(
                target,
                source=source,
                inherited=self.default_tonality,
                inherited_plan=self.tonality_plan,
                chromatic=chromatic,
            )
            if transform_all:
                transformed_voice.default_tonality = None
            else:
                transformed_voice.default_tonality = target
            transformed_voice.tonality_plan = TonalityPlan()
            result.staves[name] = replace(
                staff,
                voice=transformed_voice,
            )
        return result

    def apply_tonality_plan(
            self,
            target_plan: TonalityPlan | Mapping[int, Tonality],
            source: Tonality | None = None,
            *,
            voices: Collection[str] | None = None,
            chromatic: str = "preserve_alteration",
    ) -> "Score":
        """Apply a synchronized target-tonality plan to selected staves.

        The target plan must define bar zero. Each selected voice must contain
        every change index. All-staff transformations store target metadata on
        the score; selective transformations store equivalent metadata on the
        transformed voices so unselected voices retain their original score
        context.

        Parameters
        ----------
        target_plan : TonalityPlan | Mapping[int, Tonality]
            Target tonalities keyed by zero-based bar index, including zero.
        source : Tonality | None
            Optional source forced across every selected bar.
        voices : Collection[str] | None
            Staff names to transform, or ``None`` for every staff.
        chromatic : str
            Chromatic analysis policy passed to ``Bar.apply_tonality``.

        Returns
        -------
        Score
            A transformed score; the original is unchanged.
        """
        self._validate_transform_options(None, source, chromatic)
        normalized_target = _normalize_plan(
            target_plan,
            label="target_plan",
        )
        target_default = normalized_target.at(0)
        if target_default is None:
            raise ValueError("target_plan must define a tonality at bar 0")
        selected = self._selected_staff_names(voices)
        self.validate_alignment()

        for name in selected:
            bar_count = len(self.staves[name].voice)
            for bar_index, _ in normalized_target.changes:
                if bar_index >= bar_count:
                    raise ValueError(
                        f"Voice {name!r} has no bar at plan index "
                        f"{bar_index}"
                    )

        resolved_sources: dict[str, tuple[Tonality, ...]] = {}
        for name in selected:
            voice = self.staves[name].voice
            sources = []
            for bar_index in range(len(voice)):
                resolved = (
                    source
                    if source is not None
                    else self.tonality_at(name, bar_index)
                )
                if resolved is None:
                    raise ValueError(
                        "No source tonality is available for "
                        f"voice {name!r}, bar {bar_index}"
                    )
                sources.append(resolved)
            resolved_sources[name] = tuple(sources)

        later_changes = TonalityPlan(tuple(
            (index, tonality)
            for index, tonality in normalized_target.changes
            if index > 0
        ))
        result = self.copy_structure_without_staves()
        transform_all = selected == set(self.staves)
        if transform_all:
            result.default_tonality = target_default
            result.tonality_plan = later_changes

        for name, staff in self.staves.items():
            if name not in selected:
                result.staves[name] = _copy_staff(staff)
                continue
            transformed_bars = []
            for bar_index, bar in enumerate(staff.voice.bars):
                target = normalized_target.at(bar_index)
                if target is None:  # Guarded by the required change at zero.
                    raise RuntimeError("Target tonality resolution failed")
                transformed_bars.append(
                    bar.apply_tonality(
                        target,
                        source=resolved_sources[name][bar_index],
                        chromatic=chromatic,
                    ).with_tonality(None)
                )
            transformed_voice = Voice(
                bars=transformed_bars,
                default_tonality=(
                    None if transform_all else target_default
                ),
                tonality_plan=(
                    TonalityPlan() if transform_all else later_changes
                ),
                name=staff.voice.name,
            )
            result.staves[name] = replace(
                staff,
                voice=transformed_voice,
            )
        return result

    def validate_alignment(self) -> None:
        """Require all voices to have identical bar counts and spans.

        Raises
        ------
        ValueError
            If a voice has a different bar count or if corresponding bars have
            different total durations. Error messages identify the voice and,
            for duration mismatches, the bar index.
        """
        if not self.staves:
            return
        reference_name, reference_staff = next(iter(self.staves.items()))
        reference_spans = reference_staff.voice.bar_spans()
        for name, staff in self.staves.items():
            spans = staff.voice.bar_spans()
            if len(spans) != len(reference_spans):
                raise ValueError(
                    f"Voice {name!r} has {len(spans)} bars; "
                    f"{reference_name!r} has {len(reference_spans)}"
                )
            for index, (actual, expected) in enumerate(
                    zip(spans, reference_spans),
            ):
                if actual != expected:
                    raise ValueError(
                        f"Bar {index} span mismatch: {name!r}={actual}, "
                        f"{reference_name!r}={expected}"
                    )

    def to_midi(
            self,
            path,
            tpb: int = 480,
            *,
            allow_unaligned: bool = False,
    ):
        """Delegate MIDI-file export to the score renderer."""
        from .midi import score_to_midi_file

        return score_to_midi_file(
            self,
            path=path,
            tpb=tpb,
            allow_unaligned=allow_unaligned,
        )

    def to_lilypond(self) -> str:
        """Delegate aligned score notation to the LilyPond renderer."""
        from .lilypond import score_to_lilypond

        return score_to_lilypond(self)

    def show(self) -> "Score":
        """Render and display this aligned score, then return it."""
        from .playback import show_score

        show_score(self)
        return self

    def play(
            self,
            tpb: int = 480,
            autoplay: bool = False,
            *,
            allow_unaligned: bool = False,
    ) -> "Score":
        """Render and play this score, then return it."""
        from .playback import play_score

        play_score(
            self,
            tpb=tpb,
            autoplay=autoplay,
            allow_unaligned=allow_unaligned,
        )
        return self
