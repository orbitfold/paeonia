import json
from fractions import Fraction

import pytest

from paeonia import TriadexMuse
from paeonia.__main__ import copy_workbench
from paeonia.triadex import SOURCE_NAMES


def test_has_original_40_sources():
    assert len(SOURCE_NAMES) == 40
    assert SOURCE_NAMES[:9] == (
        "OFF",
        "ON",
        "C1/2",
        "C1",
        "C2",
        "C4",
        "C8",
        "C3",
        "C6",
    )
    assert SOURCE_NAMES[-1] == "B31"


def test_programming_manual_shift_register_example():
    muse = TriadexMuse(
        interval=("C1", "B4", "B2", "B7"),
        theme=("OFF", "B1", "B3", "B6"),
    )

    frames = [muse.step() for _ in range(10)]

    assert [frame.new_bit for frame in frames] == [1, 0, 1, 1, 0, 0, 1, 0, 0, 1]


def test_programming_manual_note_example():
    muse = TriadexMuse(
        interval=("C1", "B4", "B2", "B7"),
        theme=("OFF", "B1", "B3", "B6"),
        root=60,
    )

    pitches = [muse.step().pitch for _ in range(10)]

    # low D, low G, low D, low B, low A, low E,
    # high F, low G, high D, high E
    assert pitches == [62, 67, 62, 71, 69, 64, 77, 67, 74, 76]


def test_equal_states_are_tied_into_longer_notes():
    muse = TriadexMuse(
        interval=("OFF", "OFF", "OFF", "OFF"),
        theme=("OFF", "OFF", "OFF", "OFF"),
        root=60,
    )

    bar = muse.to_bar(beats=4, unit=Fraction(1, 4))

    assert len(bar) == 1
    assert bar[0].pitches == [60]
    assert bar[0].duration == Fraction(1, 1)


def test_lowest_state_can_be_a_rest():
    muse = TriadexMuse(
        interval=("OFF", "OFF", "OFF", "OFF"),
        theme=("OFF", "OFF", "OFF", "OFF"),
        rest=True,
    )

    bar = muse.to_bar(beats=2, unit=Fraction(1, 4))

    assert len(bar) == 1
    assert bar[0].is_rest()
    assert bar[0].duration == Fraction(1, 2)


def test_half_clock_can_change_pitch_inside_a_beat():
    muse = TriadexMuse(
        interval=("C1/2", "OFF", "OFF", "OFF"),
        theme=("OFF", "OFF", "OFF", "OFF"),
        root=60,
    )

    frames = muse.generate(beats=1, include_half_clock=True)

    assert [frame.pitch for frame in frames] == [60, 62]
    assert [frame.duration for frame in frames] == [Fraction(1, 8), Fraction(1, 8)]


def test_selector_validation():
    with pytest.raises(ValueError, match="Unknown Muse source"):
        TriadexMuse(interval=("C1", "B4", "B2", "NOPE"))


def test_workbench_can_be_copied(tmp_path):
    destination = tmp_path / "workbench.ipynb"
    result = copy_workbench(destination)

    assert result == destination.resolve()
    notebook = json.loads(destination.read_text())
    assert notebook["nbformat"] == 4
    assert any("TriadexMuse" in "".join(cell["source"]) for cell in notebook["cells"])
