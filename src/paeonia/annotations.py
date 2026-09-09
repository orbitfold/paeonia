# pyright: reportImportCycles=false
"""Project score analyses into renderer-independent annotations.

Analysis data is computed when notation is requested instead of being stored
on a :class:`~paeonia.score.Score`.  This prevents annotations from becoming
stale when a score window or voice is edited and keeps engraving concerns out
of :mod:`paeonia.analysis`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING

from .analysis import (
    ChordCandidate,
    EventReference,
    Verticality,
    chord_candidates,
)

if TYPE_CHECKING:
    from .score import Score
    from .tonality import Tonality


__all__ = [
    "AnalysisRenderOptions",
    "ScoreAnnotation",
    "normalize_analysis_render_options",
    "score_annotations",
]


_LANE_ORDER = {
    "harmony": 0,
    "non_chord_tone": 1,
    "voice_leading": 2,
    "register": 3,
    "dissonance": 4,
    "scale_degree": 5,
    "bass_motion": 6,
    "doubling": 7,
    "density": 8,
    "set_theory": 9,
    "interval": 10,
}


@dataclass(frozen=True, slots=True)
class AnalysisRenderOptions:
    """Choose which score analyses are included in rendered notation.

    The defaults form a readable composition-oriented preset.  They show
    harmony, non-chord tones, and exceptional voice-leading or registral
    events while leaving dense numerical diagnostics disabled.  Use
    :meth:`diagnostic` to enable every available analysis lane.

    ``source_staves`` limits the musical material used for analysis without
    limiting which staves are rendered.  This is useful, for example, when a
    pair of keyboard staves establishes harmony for a larger ensemble.
    """

    source_staves: tuple[str, ...] | None = None
    harmony: bool = True
    roman_numerals: bool = True
    non_chord_tones: bool = True
    voice_leading: bool = True
    voice_leading_summary: bool = False
    register_warnings: bool = True
    confidence: bool = False
    set_theory: bool = False
    density: bool = False
    scale_degrees: bool = False
    intervals: bool = False
    dissonances: bool = False
    doublings: bool = False
    bass_motion: bool = False
    min_confidence: float = 0.0
    leap_threshold: int = 5

    def __post_init__(self) -> None:
        if self.source_staves is not None:
            raw_staves: Iterable[str] = (
                (self.source_staves,)
                if isinstance(self.source_staves, str)
                else self.source_staves
            )
            normalized_staves = tuple(raw_staves)
            if not all(isinstance(name, str) for name in normalized_staves):
                raise TypeError("source_staves must contain only strings")
            if not normalized_staves:
                raise ValueError("source_staves must not be empty")
            object.__setattr__(self, "source_staves", normalized_staves)

        boolean_fields = (
            "harmony",
            "roman_numerals",
            "non_chord_tones",
            "voice_leading",
            "voice_leading_summary",
            "register_warnings",
            "confidence",
            "set_theory",
            "density",
            "scale_degrees",
            "intervals",
            "dissonances",
            "doublings",
            "bass_motion",
        )
        for field_name in boolean_fields:
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be a boolean")
        if isinstance(self.min_confidence, bool) or not isinstance(
                self.min_confidence,
                (int, float),
        ):
            raise TypeError("min_confidence must be a number")
        if not 0 <= self.min_confidence <= 1:
            raise ValueError("min_confidence must lie between 0 and 1")
        if isinstance(self.leap_threshold, bool) or not isinstance(
                self.leap_threshold,
                int,
        ):
            raise TypeError("leap_threshold must be an integer")
        if self.leap_threshold < 0:
            raise ValueError("leap_threshold must be non-negative")

    @classmethod
    def diagnostic(
            cls,
            *,
            source_staves: tuple[str, ...] | None = None,
    ) -> "AnalysisRenderOptions":
        """Return a preset enabling every available analysis lane."""
        return cls(
            source_staves=source_staves,
            confidence=True,
            set_theory=True,
            density=True,
            scale_degrees=True,
            intervals=True,
            dissonances=True,
            doublings=True,
            bass_motion=True,
            voice_leading_summary=True,
        )


@dataclass(frozen=True, slots=True)
class ScoreAnnotation:
    """A textual analysis label positioned in one score bar.

    Offsets and durations use Paeonia's whole-note units.  ``staff_name`` is
    ``None`` for a global label, which renderers normally place over the first
    staff.  ``source`` identifies an exact event and chord pitch when the
    underlying analysis can provide that identity.
    """

    bar_index: int
    offset: Fraction
    duration: Fraction
    lane: str
    text: str
    staff_name: str | None = None
    source: EventReference | None = None

    def __post_init__(self) -> None:
        if isinstance(self.bar_index, bool) or not isinstance(
                self.bar_index,
                int,
        ):
            raise TypeError("bar_index must be an integer")
        if self.bar_index < 0:
            raise ValueError("bar_index must be non-negative")
        offset = Fraction(self.offset)
        duration = Fraction(self.duration)
        if offset < 0:
            raise ValueError("annotation offset must be non-negative")
        if duration < 0:
            raise ValueError("annotation duration must be non-negative")
        if not isinstance(self.lane, str) or not self.lane:
            raise ValueError("annotation lane must be a non-empty string")
        if not isinstance(self.text, str) or not self.text:
            raise ValueError("annotation text must be a non-empty string")
        if self.staff_name is not None and not isinstance(
                self.staff_name,
                str,
        ):
            raise TypeError("staff_name must be a string or None")
        if self.source is not None and not isinstance(
                self.source,
                EventReference,
        ):
            raise TypeError("source must be an EventReference or None")
        object.__setattr__(self, "offset", offset)
        object.__setattr__(self, "duration", duration)


def normalize_analysis_render_options(
        analysis: bool | AnalysisRenderOptions,
) -> AnalysisRenderOptions | None:
    """Normalize a public rendering option into an options object or none."""
    if analysis is False:
        return None
    if analysis is True:
        return AnalysisRenderOptions()
    if isinstance(analysis, AnalysisRenderOptions):
        return analysis
    raise TypeError("analysis must be a boolean or AnalysisRenderOptions")


def _selected_staff_names(
        score: Score,
        requested: tuple[str, ...] | None,
) -> tuple[str, ...]:
    if requested is None:
        selected = tuple(score.staves)
    else:
        requested_set = set(requested)
        unknown = requested_set - set(score.staves)
        if unknown:
            raise KeyError(f"Unknown source staves: {sorted(unknown)}")
        selected = tuple(name for name in score.staves if name in requested_set)
    if not selected:
        raise ValueError("score analysis requires at least one staff")
    return selected


def _common_tonality(
        score: Score,
        bar_index: int,
        staff_names: tuple[str, ...],
) -> Tonality | None:
    tonalities = {
        score.tonality_at(name, bar_index)
        for name in staff_names
    }
    if len(tonalities) != 1:
        return None
    return next(iter(tonalities))


def _candidate_identity(
        candidate: ChordCandidate | None,
) -> tuple[int, str] | None:
    if candidate is None:
        return None
    return candidate.root.midi_value, candidate.quality


def _untonal_harmonic_spans(
        frames: Sequence[Verticality],
) -> tuple[tuple[Fraction, Fraction, ChordCandidate | None], ...]:
    spans: list[tuple[Fraction, Fraction, ChordCandidate | None]] = []
    for frame in frames:
        candidates = chord_candidates(frame, limit=1)
        candidate = candidates[0] if candidates else None
        if (
                spans
                and _candidate_identity(spans[-1][2])
                == _candidate_identity(candidate)
        ):
            previous_offset, previous_duration, previous_candidate = spans[-1]
            spans[-1] = (
                previous_offset,
                previous_duration + frame.duration,
                (
                    candidate
                    if candidate is not None
                    and (
                        previous_candidate is None
                        or candidate.confidence > previous_candidate.confidence
                    )
                    else previous_candidate
                ),
            )
        else:
            spans.append((frame.offset, frame.duration, candidate))
    return tuple(spans)


def _degree_label(degree: int, alteration: int) -> str:
    accidental = "#" * alteration if alteration > 0 else "b" * -alteration
    return f"{accidental}{degree + 1}"


def _append_harmonic_annotations(
        annotations: list[ScoreAnnotation],
        score: Score,
        bar_index: int,
        staff_names: tuple[str, ...],
        frames: Sequence[Verticality],
        tonality: Tonality | None,
        options: AnalysisRenderOptions,
) -> None:
    needs_context = any((
        options.harmony,
        options.roman_numerals,
        options.confidence,
        options.non_chord_tones,
    ))
    if not needs_context:
        return

    context = (
        score.harmonic_context(
            bar_index,
            tonality=tonality,
            staves=staff_names,
        )
        if tonality is not None
        else None
    )
    spans = (
        tuple(
            (change.offset, change.duration, change.candidate)
            for change in context.changes
        )
        if context is not None
        else _untonal_harmonic_spans(frames)
    )
    for offset, duration, candidate in spans:
        if candidate is None or candidate.confidence < options.min_confidence:
            continue
        parts: list[str] = []
        if options.harmony:
            parts.append(candidate.symbol)
        if options.roman_numerals and candidate.roman_numeral is not None:
            parts.append(candidate.roman_numeral)
        if options.confidence:
            parts.append(f"confidence {candidate.confidence:.0%}")
        if parts:
            annotations.append(ScoreAnnotation(
                bar_index=bar_index,
                offset=offset,
                duration=duration,
                lane="harmony",
                text="Harmony: " + " · ".join(parts),
            ))

    if context is None or not options.non_chord_tones:
        return
    durations = {frame.offset: frame.duration for frame in frames}
    seen: set[tuple[EventReference | None, Fraction, str]] = set()
    for tone in context.non_chord_tones:
        identity = (tone.source, tone.offset, tone.kind)
        if identity in seen:
            continue
        seen.add(identity)
        annotations.append(ScoreAnnotation(
            bar_index=bar_index,
            offset=tone.offset,
            duration=durations[tone.offset],
            lane="non_chord_tone",
            text=f"NCT: {tone.pitch} ({tone.kind})",
            staff_name=tone.staff,
            source=tone.source,
        ))


def _append_frame_annotations(
        annotations: list[ScoreAnnotation],
        score: Score,
        bar_index: int,
        staff_names: tuple[str, ...],
        frames: Sequence[Verticality],
        tonality: Tonality | None,
        options: AnalysisRenderOptions,
) -> None:
    if options.set_theory:
        for frame in frames:
            if not frame.pitches:
                continue
            written = ", ".join(sorted(
                str(pitch_class)
                for pitch_class in frame.pitch_classes.written
            ))
            midi = ", ".join(map(str, sorted(frame.pitch_classes.midi)))
            prime = ", ".join(map(str, frame.prime_form))
            vector = ", ".join(map(str, frame.interval_class_vector))
            annotations.append(ScoreAnnotation(
                bar_index,
                frame.offset,
                frame.duration,
                "set_theory",
                f"Set: {{{written}}} / {{{midi}}}; "
                f"PF ({prime}); ICV <{vector}>",
            ))

    if options.density:
        for point in score.density(bar_index, staves=staff_names):
            annotations.append(ScoreAnnotation(
                bar_index,
                point.offset,
                point.duration,
                "density",
                f"Density: {point.pitch_count} pitches / "
                f"{point.active_staff_count} staves",
            ))

    if options.scale_degrees and tonality is not None:
        for snapshot in score.scale_degrees(
                bar_index,
                tonality=tonality,
                staves=staff_names,
        ):
            by_staff: dict[str, list[str]] = {}
            for degree in snapshot.degrees:
                by_staff.setdefault(degree.staff, []).append(_degree_label(
                    degree.position.degree,
                    degree.position.alteration,
                ))
            for staff_name, labels in by_staff.items():
                annotations.append(ScoreAnnotation(
                    bar_index,
                    snapshot.offset,
                    snapshot.duration,
                    "scale_degree",
                    "Degrees: " + ", ".join(labels),
                    staff_name=staff_name,
                ))

    if options.intervals:
        for snapshot in score.interval_matrix(bar_index, staves=staff_names):
            if not snapshot.intervals:
                continue
            labels = "; ".join(
                f"{item.first_staff}/{item.second_staff} "
                f"{item.semitones} semitones"
                for item in snapshot.intervals
            )
            annotations.append(ScoreAnnotation(
                bar_index,
                snapshot.offset,
                snapshot.duration,
                "interval",
                f"Intervals: {labels}",
            ))

    if options.dissonances:
        for snapshot in score.dissonances(bar_index, staves=staff_names):
            for item in snapshot.intervals:
                annotations.append(ScoreAnnotation(
                    bar_index,
                    snapshot.offset,
                    snapshot.duration,
                    "dissonance",
                    f"Dissonance: {item.first_staff} {item.first_pitch} / "
                    f"{item.second_staff} {item.second_pitch} "
                    f"(ic {item.interval_class})",
                ))

    if options.doublings:
        for snapshot in score.doublings(bar_index, staves=staff_names):
            for doubling in snapshot.doublings:
                spellings = "/".join(sorted(map(str, doubling.spellings)))
                annotations.append(ScoreAnnotation(
                    bar_index,
                    snapshot.offset,
                    snapshot.duration,
                    "doubling",
                    f"Doubling: {spellings} ×{doubling.count} "
                    f"({', '.join(doubling.staves)})",
                ))

    if options.bass_motion:
        for motion in score.bass_motion(bar_index, staves=staff_names):
            annotations.append(ScoreAnnotation(
                bar_index,
                motion.to_offset,
                Fraction(0),
                "bass_motion",
                f"Bass: {motion.from_pitch}→{motion.to_pitch} "
                f"({motion.semitones:+d} semitones)",
            ))

    if options.register_warnings:
        register = score.register_analysis(bar_index, staves=staff_names)
        for snapshot in register.snapshots:
            for upper, lower in snapshot.crossings:
                annotations.append(ScoreAnnotation(
                    bar_index,
                    snapshot.offset,
                    snapshot.duration,
                    "register",
                    f"Voice crossing: {upper}/{lower}",
                    staff_name=upper,
                ))
        for overlap in register.overlaps:
            annotations.append(ScoreAnnotation(
                bar_index,
                overlap.offset,
                Fraction(0),
                "register",
                f"Voice overlap: {overlap.upper_staff}/{overlap.lower_staff}",
                staff_name=overlap.upper_staff,
            ))


def _append_voice_leading_annotations(
        annotations: list[ScoreAnnotation],
        score: Score,
        bar_index: int,
        staff_names: tuple[str, ...],
        frames: Sequence[Verticality],
        next_frames: Sequence[Verticality],
        options: AnalysisRenderOptions,
) -> None:
    if not options.voice_leading:
        return
    if not any(frame.pitches for frame in frames):
        return
    if not any(frame.pitches for frame in next_frames):
        return
    result = score.voice_leading_to(
        bar_index,
        staves=staff_names,
        leap_threshold=options.leap_threshold,
    )
    next_duration = next_frames[0].duration if next_frames else Fraction(0)
    if options.voice_leading_summary:
        annotations.append(ScoreAnnotation(
            bar_index + 1,
            Fraction(0),
            next_duration,
            "voice_leading",
            f"Voice leading: motion {result.total_motion}; "
            f"common tones {len(result.common_tones)}; "
            f"contrary pairs {len(result.contrary_pairs)}",
        ))
    for parallel in result.parallel_perfects:
        interval_name = "P8" if parallel.interval_class == 0 else "P5"
        annotations.append(ScoreAnnotation(
            bar_index + 1,
            Fraction(0),
            next_duration,
            "voice_leading",
            f"Parallel {interval_name}: {parallel.first_staff}/"
            f"{parallel.second_staff}",
        ))
    for leap in result.leaps:
        annotations.append(ScoreAnnotation(
            bar_index + 1,
            Fraction(0),
            next_duration,
            "voice_leading",
            f"Leap: {leap.from_pitch}→{leap.to_pitch} "
            f"({leap.semitones:+d} semitones)",
            staff_name=leap.staff,
        ))


def score_annotations(
        score: Score,
        options: AnalysisRenderOptions | None = None,
) -> tuple[ScoreAnnotation, ...]:
    """Compute fresh display annotations for an aligned score.

    Tonality-independent lanes remain available when selected staves do not
    share a tonal context.  In that situation chord symbols are inferred from
    pitch classes, while Roman numerals, scale degrees, and non-chord-tone
    classifications are omitted rather than assigned against an arbitrary
    key.
    """
    if options is None:
        options = AnalysisRenderOptions()
    if not isinstance(options, AnalysisRenderOptions):
        raise TypeError("options must be an AnalysisRenderOptions or None")
    score.validate_alignment()
    if not score.staves:
        return ()

    staff_names = _selected_staff_names(score, options.source_staves)
    bar_count = len(next(iter(score.staves.values())).voice)
    frames_by_bar = tuple(
        score.verticalities(index, staves=staff_names)
        for index in range(bar_count)
    )
    annotations: list[ScoreAnnotation] = []
    for bar_index, frames in enumerate(frames_by_bar):
        tonality = _common_tonality(score, bar_index, staff_names)
        _append_harmonic_annotations(
            annotations,
            score,
            bar_index,
            staff_names,
            frames,
            tonality,
            options,
        )
        _append_frame_annotations(
            annotations,
            score,
            bar_index,
            staff_names,
            frames,
            tonality,
            options,
        )
        if bar_index + 1 < bar_count:
            _append_voice_leading_annotations(
                annotations,
                score,
                bar_index,
                staff_names,
                frames,
                frames_by_bar[bar_index + 1],
                options,
            )

    return tuple(sorted(
        annotations,
        key=lambda annotation: (
            annotation.bar_index,
            annotation.offset,
            annotation.staff_name is not None,
            annotation.staff_name or "",
            _LANE_ORDER.get(annotation.lane, len(_LANE_ORDER)),
            annotation.text,
        ),
    ))
