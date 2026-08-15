import json

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
    assert len(notebook["cells"]) == 4
    assert "from paeonia import Bar, Note, Score, Tonality" in source
