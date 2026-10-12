"""The bundled example produces the output shown in the README."""

from pathlib import Path

import pytest

from lastgreen.cli import main

EXAMPLES = Path(__file__).parent.parent / "examples"


def test_example_diff(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["diff", str(EXAMPLES / "green.log"), str(EXAMPLES / "red.log")]) == 0
    out = capsys.readouterr().out
    assert "runner image                     ubuntu-24.04 20260928.322.1 → " in out
    assert "package pytest                   8.3.3 → 8.4.0" in out
    assert "E       fixture 'db' not found" in out


def test_missing_file_is_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["diff", "nope.log", str(EXAMPLES / "red.log")]) == 1
    assert "cannot read nope.log" in capsys.readouterr().err
