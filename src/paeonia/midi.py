# pyright: reportAttributeAccessIssue=false, reportMissingTypeStubs=false
"""Convert Paeonia model objects into MIDI messages and files."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from fractions import Fraction
from pathlib import Path
import tempfile
from typing import TYPE_CHECKING

from mido import (
    Message,
    MetaMessage,
    MidiFile,
    MidiTrack,
    bpm2tempo,
)

if TYPE_CHECKING:
    from .bar import Bar
    from .note import Note
    from .score import Score
    from .staff import Staff
    from .tonality import Tonality
    from .voice import Voice


_MAJOR_KEYS = {
    "C", "G", "D", "A", "E", "B", "F#", "C#",
    "F", "Bb", "Eb", "Ab", "Db", "Gb", "Cb",
}
_MINOR_KEYS = {
    "A", "E", "B", "F#", "C#", "G#", "D#", "A#",
    "D", "G", "C", "F", "Bb", "Eb", "Ab",
}
_MAJOR_MODES = {"major", "ionian"}
_MINOR_MODES = {
    "minor",
    "aeolian",
    "minor-harmonic",
    "minor-melodic",
}


def _validate_timing(*, offset: int = 0, tpb: int = 480) -> None:
    if not isinstance(offset, int):
        raise TypeError("offset must be an integer")
    if offset < 0:
        raise ValueError("offset must be non-negative")
    if not isinstance(tpb, int):
        raise TypeError("tpb must be an integer")
    if tpb <= 0:
        raise ValueError("tpb must be positive")


def _duration_ticks(duration: Fraction, tpb: int) -> int:
    return round(tpb * 4 * duration)


def note_to_midi_messages(
        note: Note,
        *,
        offset: int = 0,
        tpb: int = 480,
) -> list[Message]:
    """Convert one untied event to MIDI note messages.

    For chords, accumulated silence is attached only to the first
    ``note_on`` and sounding duration only to the first ``note_off``. This
    keeps simultaneous chord pitches simultaneous in MIDI delta time.

    Tie interpretation deliberately happens in bar or voice conversion,
    where adjacent events are available.
    """
    _validate_timing(offset=offset, tpb=tpb)
    if note.is_rest():
        return []

    velocity = round(127 * note.velocity)
    duration = _duration_ticks(note.duration, tpb)
    messages = []
    for index, pitch in enumerate(note.pitches):
        messages.append(
            Message(
                "note_on",
                note=pitch.midi,
                velocity=velocity,
                time=offset if index == 0 else 0,
            )
        )
    for index, pitch in enumerate(note.pitches):
        messages.append(
            Message(
                "note_off",
                note=pitch.midi,
                velocity=0,
                time=duration if index == 0 else 0,
            )
        )
    return messages


def _tie_signature(note: Note) -> tuple[int, ...]:
    """Return a spelling-independent, order-independent chord signature."""
    return tuple(sorted(note.midi_pitches))


def _coalesce_tied_events(events: Sequence[Note]) -> tuple[Note, ...]:
    """Validate and merge adjacent tie chains into longer sounding events."""
    result = []
    index = 0
    while index < len(events):
        note = events[index]
        if note.is_rest() and (note.tie_in or note.tie_out):
            raise ValueError(
                f"Rest at event {index} cannot participate in a tie"
            )
        if note.tie_in:
            raise ValueError(
                f"Event {index} has tie_in without a preceding tie_out"
            )
        if not note.tie_out:
            result.append(note)
            index += 1
            continue

        signature = _tie_signature(note)
        total_duration = note.duration
        current_index = index
        current = note
        while current.tie_out:
            next_index = current_index + 1
            if next_index >= len(events):
                raise ValueError(
                    f"tie_out at event {current_index} is not followed "
                    "by a tied event"
                )
            following = events[next_index]
            if not following.tie_in:
                raise ValueError(
                    f"tie_out at event {current_index} is not followed "
                    f"by tie_in at event {next_index}"
                )
            if following.is_rest() or _tie_signature(following) != signature:
                raise ValueError(
                    f"Tie between events {current_index} and {next_index} "
                    "has incompatible pitches"
                )
            total_duration += following.duration
            current = following
            current_index = next_index

        result.append(
            note.with_duration(total_duration).with_ties(
                tie_in=False,
                tie_out=False,
            )
        )
        index = current_index + 1
    return tuple(result)


def _events_to_midi_messages(
        events: Sequence[Note],
        *,
        offset: int,
        tpb: int,
        channel: int,
) -> tuple[list[Message], int]:
    _validate_timing(offset=offset, tpb=tpb)
    if not 0 <= channel <= 15:
        raise ValueError("MIDI channel must lie between 0 and 15")

    messages = []
    pending_offset = offset
    for note in _coalesce_tied_events(events):
        if note.is_rest():
            pending_offset += _duration_ticks(note.duration, tpb)
            continue
        rendered = note_to_midi_messages(
            note,
            offset=pending_offset,
            tpb=tpb,
        )
        messages.extend(
            message.copy(channel=channel)
            for message in rendered
        )
        pending_offset = 0
    return messages, pending_offset


def bar_to_midi_messages(
        bar: Bar,
        *,
        offset: int = 0,
        tpb: int = 480,
        channel: int = 0,
) -> tuple[list[Message], int]:
    """Convert a bar and return its messages plus trailing silent ticks."""
    return _events_to_midi_messages(
        tuple(bar.notes),
        offset=offset,
        tpb=tpb,
        channel=channel,
    )


def _voice_to_midi_messages_and_offset(
        voice: Voice,
        *,
        tpb: int,
        channel: int,
) -> tuple[list[Message], int]:
    events = tuple(
        note
        for bar in voice.bars
        for note in bar.notes
    )
    return _events_to_midi_messages(
        events,
        offset=0,
        tpb=tpb,
        channel=channel,
    )


def voice_to_midi_messages(
        voice: Voice,
        *,
        tpb: int = 480,
        channel: int = 0,
) -> list[Message]:
    """Convert a voice while preserving timing and ties across its bars."""
    messages, _ = _voice_to_midi_messages_and_offset(
        voice,
        tpb=tpb,
        channel=channel,
    )
    return messages


def tonality_to_midi_key(tonality: Tonality | None) -> str | None:
    """Return a standard MIDI key name when the tonality is representable."""
    if tonality is None:
        return None
    tonic = str(tonality.tonic)
    if tonality.mode_name in _MAJOR_MODES and tonic in _MAJOR_KEYS:
        return tonic
    if tonality.mode_name in _MINOR_MODES and tonic in _MINOR_KEYS:
        return f"{tonic}m"
    return None


def _staff_channels(score: Score) -> dict[str, int]:
    assigned = {
        staff.midi_channel
        for staff in score.staves.values()
        if staff.midi_channel is not None
    }
    available = iter(channel for channel in range(16) if channel not in assigned)
    channels = {}
    for name, staff in score.staves.items():
        if staff.midi_channel is not None:
            channels[name] = staff.midi_channel
            continue
        try:
            channels[name] = next(available)
        except StopIteration as exc:
            raise ValueError(
                "No MIDI channel remains for an unassigned staff"
            ) from exc
    return channels


def _bar_start_ticks(voice: Voice, tpb: int) -> tuple[int, ...]:
    starts = []
    elapsed = 0
    for bar in voice.bars:
        starts.append(elapsed)
        elapsed += sum(
            _duration_ticks(note.duration, tpb)
            for note in bar.notes
        )
    return tuple(starts)


def _staff_key_events(
        score: Score,
        staff: Staff,
        *,
        tpb: int,
) -> list[tuple[int, MetaMessage]]:
    events = []
    previous = object()
    starts = _bar_start_ticks(staff.voice, tpb)
    for bar_index, start in enumerate(starts):
        tonality = staff.voice.tonality_at(
            bar_index,
            inherited=score.default_tonality,
            inherited_plan=score.tonality_plan,
        )
        if tonality == previous:
            continue
        key = tonality_to_midi_key(tonality)
        if key is not None:
            events.append((start, MetaMessage("key_signature", key=key)))
        previous = tonality
    return events


def _absolute_messages(
        messages: Iterable[Message],
) -> tuple[list[tuple[int, Message]], int]:
    absolute = 0
    result = []
    for message in messages:
        absolute += message.time
        result.append((absolute, message))
    return result, absolute


def _staff_track(
        score: Score,
        name: str,
        staff: Staff,
        *,
        channel: int,
        tpb: int,
) -> MidiTrack:
    messages, trailing_offset = _voice_to_midi_messages_and_offset(
        staff.voice,
        tpb=tpb,
        channel=channel,
    )
    absolute_notes, note_end = _absolute_messages(messages)
    track_end = note_end + trailing_offset

    scheduled = []
    serial = 0

    def schedule(absolute: int, priority: int, message) -> None:
        nonlocal serial
        scheduled.append((absolute, priority, serial, message))
        serial += 1

    schedule(0, 1, MetaMessage("track_name", name=staff.name or name))
    if staff.midi_program is not None:
        schedule(
            0,
            2,
            Message(
                "program_change",
                program=staff.midi_program,
                channel=channel,
            ),
        )
    for absolute, key_message in _staff_key_events(
            score,
            staff,
            tpb=tpb,
    ):
        schedule(absolute, 3, key_message)
    for absolute, message in absolute_notes:
        priority = 0 if message.type == "note_off" else 4
        schedule(absolute, priority, message)

    track = MidiTrack()
    previous = 0
    for absolute, _, _, message in sorted(scheduled):
        track.append(message.copy(time=absolute - previous))
        previous = absolute
    track.append(MetaMessage(
        "end_of_track",
        time=max(0, track_end - previous),
    ))
    return track


def score_to_midi(
        score: Score,
        *,
        tpb: int = 480,
        allow_unaligned: bool = False,
) -> MidiFile:
    """Build a type-1 MIDI file for a score without touching the filesystem."""
    _validate_timing(tpb=tpb)
    if not allow_unaligned:
        score.validate_alignment()
    numerator, denominator = score.time_signature
    if denominator & (denominator - 1):
        raise ValueError(
            "MIDI time-signature denominator must be a power of two"
        )

    midi = MidiFile(type=1, ticks_per_beat=tpb)
    conductor = MidiTrack()
    conductor.append(MetaMessage(
        "set_tempo",
        tempo=bpm2tempo(score.tempo),
        time=0,
    ))
    conductor.append(MetaMessage(
        "time_signature",
        numerator=numerator,
        denominator=denominator,
        time=0,
    ))
    conductor.append(MetaMessage("end_of_track", time=0))
    midi.tracks.append(conductor)

    channels = _staff_channels(score)
    for name, staff in score.staves.items():
        midi.tracks.append(_staff_track(
            score,
            name,
            staff,
            channel=channels[name],
            tpb=tpb,
        ))
    return midi


def score_to_midi_file(
        score: Score,
        *,
        path: str | Path,
        tpb: int = 480,
        allow_unaligned: bool = False,
) -> None:
    """Render ``score`` and save it to ``path``."""
    midi = score_to_midi(
        score,
        tpb=tpb,
        allow_unaligned=allow_unaligned,
    )
    midi.save(filename=path)


def messages_to_temporary_midi_file(
        messages: Iterable[Message | MetaMessage],
        *,
        tpb: int = 480,
) -> str:
    """Write messages to a caller-owned temporary MIDI path."""
    _validate_timing(tpb=tpb)
    midi = MidiFile(ticks_per_beat=tpb)
    track = MidiTrack(messages)
    midi.tracks.append(track)
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as handle:
        path = handle.name
    midi.save(path)
    return path
