import json
import importlib

import pytest

import paeonia
from paeonia.__main__ import copy_workbench


def test_workflow():
    assert(True)


def test_workbench_can_be_copied(tmp_path):
    destination = tmp_path / "workbench.ipynb"

    result = copy_workbench(destination)
    notebook = json.loads(destination.read_text())
    source = "\n".join(
        line
        for cell in notebook["cells"]
        for line in cell["source"]
    )

    assert result == destination.resolve()
    assert notebook["nbformat"] == 4
    assert len(notebook["cells"]) >= 18
    assert "Pitch.parse" in source
    assert "apply_tonality" in source
    assert "TonalityPlan.from_mapping" in source
    assert "Staff(" in source
    assert "score.to_lilypond()" in source


def test_public_model_exports_are_complete():
    assert paeonia.__all__ == [
        "PitchClass",
        "Pitch",
        "ScalePosition",
        "Tonality",
        "TonalityPlan",
        "Note",
        "Bar",
        "Voice",
        "Staff",
        "Score",
    ]
    for name in paeonia.__all__:
        assert getattr(paeonia, name) is not None


def test_launcher_smoke_check_runs_before_copy(monkeypatch, tmp_path):
    launcher = importlib.import_module("paeonia.__main__")
    destination = tmp_path / "workbench.ipynb"

    def broken_import():
        raise ImportError("broken model import")

    monkeypatch.setattr(launcher, "_smoke_check", broken_import)

    with pytest.raises(ImportError, match="broken model import"):
        launcher.main(["--copy-only", str(destination)])

    assert not destination.exists()
